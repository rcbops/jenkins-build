import sys
import time
import StringIO
import json
from chef import *
from server_helper import *
from razor_api import razor_api
from subprocess import check_call, CalledProcessError
import environments


class rpcsqa_helper:

    def __init__(self, razor_ip=''):
        self.razor = razor_api(razor_ip)
        self.chef = autoconfigure()
        self.chef.set_default()

    def enable_razor(self, razor_ip=''):
        if razor_ip != '':
            self.razor = razor_api(razor_ip)

    def __repr__(self):
        """ Print out current instance of razor_api"""
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
        return outl

    def prepare_environment(self, name, os_distro, branch, features):
        """ If the environment doesnt exist in chef, make it. """
        env = "%s-%s-%s-%s" % (name, os_distro, branch, "-".join(features))
        chef_env = Environment(env, api=self.chef)
        if not chef_env.exists:
            print "Making environment: %s " % env
            chef_env.create(env, api=self.chef)

        env_json = chef_env.to_dict()
        env_json['override_attributes'].update(environments.base_env['override_attributes'])
        for feature in features:
            if feature in environments.__dict__:
                env_json['override_attributes'].update(environments.__dict__[feature])
        chef_env.override_attributes.update(env_json['override_attributes'])
        chef_env.override_attributes['package_component'] = branch
        chef_env.save()
        return env

    def delete_environment(self, chef_environment):
        Environment(chef_environment, api=self.chef).delete()

    def cleanup_environment(self, chef_environment):
        """ Rekick nodes previously in use and reuse clean nodes. """
        query = "chef_environment:%s" % chef_environment
        nodes = self.node_search(query)
        for n in nodes:
            if n['in_use'] != 0:
                self.erase_node(n)
            else:
                n.chef_environment = "_default"
                n.save()

    def run_command_on_node(self, chef_node, command='', num_times=1, quiet=False):
        runs = []
        success = True
        for i in range(0, num_times):
            ip = chef_node['ipaddress']
            user_pass = self.razor_password(chef_node)
            run = run_remote_ssh_cmd(ip, 'root', user_pass, command, quiet)
            if run['success'] is False:
                success = False
            runs.append(run)
        return {'success': success, 'runs': runs}

    def run_chef_client(self, chef_node, num_times=1, log_level='error', quiet=False):
        # log level can be (debug, info, warn, error, fatal)
        return self.run_command_on_node(chef_node, 'chef-client -l %s' % log_level, num_times, quiet)

    def interface_physical_nodes(self, os):
        #Make sure all network interfacing is set
        query = "name:*%s*" % os
        for node in self.node_search(query):
            if "role[qa-base]" in node.run_list:
                node.run_list = ["recipe[network-interfaces]"]
                node['in_use'] = 0
                node.save()
                print "Running network interfaces for %s" % node
                #Run chef client thrice
                run_chef_client = self.run_chef_client(node, num_times=3, quiet=True)
                if run_chef_client['success']:
                    print "Done running chef-client"
                else:
                    for index, run in enumerate(run_chef_client['runs']):
                        print "Run %s: %s" % (index+1, run)

    def gather_razor_nodes(self, os, environment, cluster_size):
        ret_nodes = []
        count = 0
        query = "name:qa-%s-pool*" % os
        nodes = self.node_search(query)
        # Take a node from the default environment that has its network interfaces set.
        for node in nodes:
            if ((node.chef_environment == "_default" or
                 node.chef_environment == environment)
                    and "recipe[network-interfaces]" in node.run_list):
                if node.chef_environment != environment:
                    node.chef_environment = environment
                    node.save()
                ret_nodes.append(node.name)
                print "Taking node: %s" % node.name
                count += 1
                if count >= cluster_size:
                    break
        if count < cluster_size:
            raise Exception("Not enough available nodes for requested cluster size of %s, try again later..." % cluster_size)
        return ret_nodes

    def remove_broker_fail(self, policy):
        active_models = self.razor.simple_active_models(policy)
        for active in active_models:
            data = active_models[active]
            if 'broker_fail' in data['current_state']:
                print "!!## -- Removing active model  (broker_fail) -- ##!!"
                user_pass = self.razor.get_active_model_pass(
                    data['am_uuid'])['password']
                ip = data['eth1_ip']
                run = run_remote_ssh_cmd(ip, 'root', user_pass, 'reboot 0')
                if run['success']:
                    self.razor.remove_active_model(data['am_uuid'])
                    time.sleep(15)
                else:
                    print "!!## -- Trouble removing broker fail -- ##!!"
                    print run

    def erase_node(self, chef_node):
        print "Deleting: %s" % str(chef_node)
        am_uuid = chef_node['razor_metadata'].to_dict()['razor_active_model_uuid']
        run = run_remote_ssh_cmd(chef_node['ipaddress'], 'root', self.razor_password(chef_node), "reboot 0")
        if not run['success']:
            raise Exception("Error rebooting server %s@%s " % (chef_node, chef_node['ipaddress']))
        #Knife node remove; knife client remove
        Client(str(chef_node)).delete()
        chef_node.delete()
        #Remove active model
        self.razor.remove_active_model(am_uuid)
        time.sleep(15)

    def update_openldap_environment(self, env):
        chef_env = Environment(env, api=self.chef)
        query = 'chef_environment:%s AND run_list:*qa-openldap*' % env
        num_try = 0
        ldap_name = node_search(query)
        while num_try <= 10 and not ldap_name:
            num_try = num_try + 1
            print "Couldn't find openldap server....waiting 5 seconds retry (%s / 10) " % num_try
            time.sleep(5)
            ldap_name = self.node_search(query)
        if ldap_name:
            ldap_ip = ldap_name[0]['ipaddress']
            chef_env.override_attributes['keystone']['ldap']['url'] = "ldap://%s" % ldap_ip
            chef_env.override_attributes['keystone']['ldap']['password'] = 'ostackdemo'
            chef_env.save()
            print "Successfully updated openldap into environment!"
        else:
            raise Exception("Couldn't find ldap server: %s" % ldap_name)

    def get_environment_nodes(self, environment='', api=None):
        """Returns all the nodes of an environment"""
        api = api or self.chef
        query = "chef_environment:%s" % environment
        return self.node_search(query, api)
        
    def find_controller(self, environment):
        pass

    def razor_password(self, chef_node):
        chef_node = Node(chef_node.name, api=self.chef)
        metadata = chef_node.attributes['razor_metadata'].to_dict()
        uuid = metadata['razor_active_model_uuid']
        return self.razor.get_active_model_pass(uuid)['password']

    def remote_chef_client(self, env):
        # RSAifying key
        remote_dict = env.override_attributes['remote_chef']
        pem = StringIO.StringIO(remote_dict['key'])
        remote_dict['key'] = rsa.Key(pem)
        return ChefAPI(**remote_dict)

    def remove_chef(self, chef_node):
        """
        @param chef_node
        """
        print "removing chef on %s..." % chef_node
        if chef_node['platform_family'] == "debian":
            command = "apt-get remove --purge -y chef; rm -rf /etc/chef"
        elif chef_node['platform_family'] == "rhel":
            command = 'yum remove -y chef; rm -rf /etc/chef /var/chef'
        else:
            print "OS Distro not supported"
            sys.exit(1)

        run = self.run_command_on_node(self, chef_node, command)
        if run['success']:
            print "Removed Chef on %s" % server
        else:
            print "Failed to remove chef on server %s" % server
            sys.exit(1)

    def build_chef_server(self, chef_server_node=None, cookbooks=None, env=None):
        '''
        This will build a chef server using the rcbops script and install git
        '''

        if not chef_server_node:
            query = "chef_environment:{0} AND in_use:chef_server".format(env)
            chef_server_node = next(self.node_search(query))
        self.remove_chef(chef_server_node)

        install_script = '/var/lib/jenkins/jenkins-build/qa/v1/bash/jenkins/install-chef-server.sh'

        # #update node
        # self.update_node(chef_server_node)

        # SCP install script to chef_server node
        scp_run = self.scp_to_node(chef_server_node, install_script)

        if scp_run['success']:
            print "Successfully copied chef server install script to chef_server node %s" % chef_server_node
        else:
            print "Failed to copy chef server install script to chef_server node %s" % chef_server_node
            print scp_run
            sys.exit(1)

        # Run the install script
        cmds = ['chmod u+x ~/install-chef-server.sh',
                './install-chef-server.sh']
        for cmd in cmds:
            ssh_run = self.run_command_on_node(chef_server_node,
                                               command=cmd)
            if ssh_run['success']:
                print "command: %s ran successfully on %s" % (cmd, chef_server_node.name)

        self.install_git(chef_server_node)
        self.install_cookbooks(chef_server_node, cookbooks)
        if env:
            self.setup_remote_chef_environment(chef_server_node, env)

    def install_git(self, chef_server_node):
        # This needs to be taken out and install_package used instead (jwagner)
        # Gather node info
        chef_server_platform = chef_server_node['platform']

        # Install git and clone the other cookbook
        if chef_server_platform == 'ubuntu':
            to_run_list = ['apt-get install git -y']
        elif chef_server_platform == 'centos' or chef_server_platform == 'redhat':
            to_run_list = ['yum install git -y']
        else:
            print "Platform %s not supported" % chef_server_platform
            sys.exit(1)

        for cmd in to_run_list:
            run_cmd = run_command_on_node(chef_server_node, cmd)
            if not run_cmd['success']:
                print "Command: %s failed to run on %s" % (cmd, chef_server_node.name)
                print run_cmd
                sys.exit(1)

    def node_search(self, query=None, api=None):
        api = api or self.chef
        search = Search("node", api=api).query(query)
        return (Node(n['name'], api=api) for n in search)

    # Make these use run_command_on_node
    def scp_from_node(self, node=None, path=None, destination=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        return get_file_from_server(ip, user, password, path, destination)

    def scp_to_node(self, node=None, path=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        return run_remote_scp_cmd(ip, user, password, path)

    def install_cookbooks(self, chef_server_node, cookbooks, local_repo='/opt/rcbops'):
        '''
        @summary: This will pull the cookbooks down for git that you pass in cookbooks
        @param chef_server: The node that the chef server is installed on
        @type chef_server: String
        @param cookbooks A List of cookbook repos in dict form {url: 'asdf', branch: 'asdf'}
        @type cookbooks dict
        @param local_repo The location to place the cookbooks i.e. '/opt/rcbops'
        @type String
        '''

        # Make directory that the cookbooks will live in
        command = 'mkdir -p {0}'.format(local_repo)
        run_cmd = run_command_on_node(chef_server_node, command)
        if not run_cmd['success']:
            print "Command: %s failed to run on %s" % (cmd, chef_server_node.name)
            print run_cmd
            sys.exit(1)

        for cookbook in cookbooks:
            self.install_cookbook(chef_server_node, cookbook, local_repo)

    def install_cookbook(self, chef_server, cookbook, local_repo):
        # clone to cookbook
        cmds = ['cd {0}; git clone {1} -b {2} --recursive'.format(local_repo, cookbook['url'], cookbook['branch'])]

        # if a tag was sent in, use the tagged cookbooks
        if cookbook['tag'] is not None:
            cmds.append('cd /opt/rcbops/chef-cookbooks; git checkout v%s' % cookbook['tag'])
        else:
            cmds.append('cd /opt/rcbops/chef-cookbooks; git checkout %s' % cookbook['branch'])

        # Since we are installing from git, the urls are pretty much constant
        # Pulling the url apart to get the name of the cookbooks
        cookbook_name = cookbook['url'].split("/")[-1].split(".")[0]

        # Stupid logic to see if the repo name contains "cookbooks", if it does then
        # we need to load from cookbooks repo, not the repo itself.
        # I think this is stupid logic, there has to be a better way (jacob)
        if 'cookbooks' in cookbook_name:
             # add submodule stuff to list
            cmds.append('cd /opt/rcbops/chef-cookbooks;'
                        'git submodule init;'
                        'git submodule sync;'
                        'git submodule update')
            cmds.append('knife cookbook upload --all --cookbook-path {0}/{1}/cookbooks'.format(local_repo, cookbook_name))
        else:
            cmds = ['knife cookbook upload --all --cookbook-path {0}/{1}'.format(local_repo, cookbook_name)]

        # Append role load to run list
        cmds.append('knife role from file {0}/{1}/roles/*.rb'.format(local_repo, cookbook_name))

        for cmd in cmds:
            run_cmd = run_command_on_node(chef_server_node, cmd)
            if not run_cmd['success']:
                print "Command: %s failed to run on %s" % (cmd, chef_server_node.name)
                print run_cmd
                sys.exit(1)

    def setup_remote_chef_environment(self, chef_server_node, chef_environment):
        """
        @summary This will copy the environment file and set it on the remote
        chef server.
        """
        environment_file = '/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/%s.json' % chef_environment
        run_scp = self.scp_to_node(chef_server_node, environment_file)
        if not run_scp['success']:
            print "Failed to copy environment file to remote chef server"
            print run_scp
            sys.exit(1)

        cmds = ['cp ~/%s.json /opt/rcbops/chef-cookbooks/environments' % chef_environment,
                'knife environment from file /opt/rcbops/chef-cookbooks/environments/%s.json' % chef_environment]
        for cmd in cmds:
            run_cmd = self.run_command_on_node(chef_server_node, cmd)
            if not run_cmd['success']:
                print "Failed to run remote ssh command on server %s" % (chef_server_node.name)
                print run_ssh
                sys.exit(1)

        print "Successfully set up remote chef environment %s on chef server %s @ %s" % (chef_environment, 
                                                                                         chef_server_node, 
                                                                                         chef_server_node['ipaddress'])
