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
        # If the environment doesnt exist in chef, make it.
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
        nodes = Search('node', api=self.chef).query("chef_environment:%s" % chef_environment)
        if nodes:
            for n in nodes:
                name = n['name']
                node = Node(name, api=self.chef)
                if node['in_use'] != 0:
                    self.erase_node(node)
                else:
                    node.chef_environment = "_default"
                    node.save()
            #Environment(chef_environment).delete()

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
        for node in Search('node', api=self.chef).query("name:*%s*" % os):
            chef_node = Node(node['name'], api=self.chef)
            if "role[qa-base]" in chef_node.run_list:
                chef_node.run_list = ["recipe[network-interfaces]"]
                chef_node['in_use'] = 0
                chef_node.save()
                print "Running network interfaces for %s" % chef_node
                #Run chef client thrice
                run_chef_client = self.run_chef_client(chef_node, num_times=3, quiet=True)
                if run_chef_client['success']:
                    print "Done running chef-client"
                else:
                    for index, run in enumerate(run_chef_client['runs']):
                        print "Run %s: %s" % (index+1, run)

    def gather_razor_nodes(self, os, environment, cluster_size):
        ret_nodes = []
        count = 0
        nodes = Search('node', api=self.chef).query("name:qa-%s-pool*" % os)
        # Take a node from the default environment that has its network interfaces set.
        for n in nodes:
            name = n['name']
            node = Node(name, api=self.chef)
            if ((node.chef_environment == "_default" or node.chef_environment == environment)
                    and "recipe[network-interfaces]" in node.run_list):
                if node.chef_environment != environment:
                    node.chef_environment = environment
                    node.save()
                ret_nodes.append(name)
                print "Taking node: %s" % name
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
        ldap_query = 'chef_environment:%s AND run_list:*qa-openldap*' % env
        num_try = 0
        ldap_name = [n['name'] for n in Search('node', api=self.chef).query(ldap_query)]
        while num_try <= 10 and not ldap_name:
            num_try = num_try + 1
            print "Couldn't find openldap server....waiting 5 seconds retry (%s / 10) " % num_try
            time.sleep(5)
            ldap_name = [n['name'] for n in Search('node', api=self.chef).query(ldap_query)]
        if ldap_name:
            ldap_ip = Node(ldap_name[0], api=self.chef)['ipaddress']
            chef_env.override_attributes['keystone']['ldap']['url'] = "ldap://%s" % ldap_ip
            chef_env.override_attributes['keystone']['ldap']['password'] = 'ostackdemo'
            chef_env.save()
            print "Successfully updated openldap into environment!"
        else:
            raise Exception("Couldn't find ldap server: %s" % ldap_name)


    def get_environment_nodes(self, environment='', api=None):
        """Returns all the nodes of an environment"""
        api = api or self.chef
        search = Search("node", api=api).query("chef_environment:%s" % environment)
        return (Node(n['name'], api=api) for n in search)
        
    def find_controller(self, environment):
        pass


    def razor_password(self, chef_node):
        chef_node = Node(chef_node.name, api=self.chef)
        metadata = chef_node.attributes['razor_metadata'].to_dict()
        uuid = metadata['razor_active_model_uuid']
        return self.razor.get_active_model_pass(uuid)['password']

    def set_remote_chef_client(self, env):
        # RSAifying key
        remote_dict = env.override_attributes['remote_chef']
        pem = StringIO.StringIO(remote_dict['key'])
        remote_dict['key'] = rsa.Key(pem)
        self.chef = ChefAPI(**remote_dict)

    def remove_chef(self, server):
        """
        @param chef_node
        """
        chef_node = Node(server, api=self.chef)

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

    def build_chef_server(self, chef_server_node):
        '''
        This will build a chef server using the rcbops script and install git
        '''

        # Load controller node
        chef_node = Node(chef_server_node, api=self.chef)
        install_script = '/var/lib/jenkins/jenkins-build/qa/v1/bash/jenkins/install-chef-server.sh'


        ##TODO: CAMERON

        #update node
        self.update_node(chef_node)

        # SCP install script to chef_server node
        scp_run = run_remote_scp_cmd(chef_server_ip,
                                     'root',
                                     chef_server_pass,
                                     install_script)
        if scp_run['success']:
            print "Successfully copied chef server install script to chef_server node %s" % chef_server_node
        else:
            print "Failed to copy chef server install script to chef_server node %s" % chef_server_node
            print scp_run
            sys.exit(1)

        # Run the install script
        to_run_list = ['chmod u+x ~/install-chef-server.sh',
                       './install-chef-server.sh']
        for cmd in to_run_list:
            ssh_run = run_remote_ssh_cmd(chef_server_ip,
                                         'root',
                                         chef_server_pass,
                                         cmd)
            if ssh_run['success']:
                print "command: %s ran successfully on %s" % (cmd,
                                                              chef_server_node)

        self.install_git(chef_server_node)

    def update_node(self, chef_node):
        ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)
        if chef_node['platform_family'] == "debian":
            run_remote_ssh_cmd(ip, 'root', user_pass,
                               'apt-get update -y; apt-get upgrade -y')
        elif chef_node['platform_family'] == "rhel":
            run_remote_ssh_cmd(ip, 'root', user_pass, 'yum update -y')
        else:
            print "Platform Family %s is not supported." \
                % chef_node['platform_family']
            sys.exit(1)
