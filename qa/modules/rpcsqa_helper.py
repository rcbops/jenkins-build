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

    def run_chef_client(self, chef_node, num_times=1, quiet=False):
        return self.run_command_on_node(chef_node, 'chef-client', num_times, quiet)


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
        print ldap_query
        ldap_name = [n['name'] for n in Search('node', api=self.chef).query(ldap_query)]
        if ldap_name:
            ldap_ip = Node(ldap_name[0], api=self.chef)['ipaddress']
            chef_env.override_attributes['keystone']['ldap']['url'] = "ldap://%s" % ldap_ip
            chef_env.save()
        else:
            raise Exception("Couldn't find ldap server: %s" % ldap_name)























    def bootstrap_chef(self, client_node, server_node):
        '''
        @summary: installes chef client on a node and bootstraps it to chef_server
        @param node: node to install chef client on
        @type node: String
        @param chef_server: node that is the chef server
        @type chef_server: String
        '''

        # Gather the chef info for the nodes
        chef_server_node = Node(server_node, api=self.chef)
        chef_client_node = Node(client_node, api=self.chef)

        chef_server_ip = chef_server_node['ipaddress']
        chef_server_password = self.razor_password(chef_server_node)

        chef_client_ip = chef_client_node['ipaddress']
        chef_client_password = self.razor_password(chef_client_node)

        # install chef client and bootstrap
        cmd = 'knife bootstrap %s -x root -P %s' % (chef_client_ip,
                                                    chef_client_password)

        ssh_run = run_remote_ssh_cmd(chef_server_ip,
                                     'root',
                                     chef_server_password,
                                     cmd)

        if ssh_run['success']:
            print "Successfully bootstraped chef-client on %s to chef-server on %s" % (client_node, server_node)

    def build_dir_server(self, dir_node, dir_version, os):
        chef_node = Node(dir_node, api=self.chef)

        # We dont support 389 yet, so exit if it is not ldap
        if dir_version != 'openldap':
            print "%s as a directory service is not yet supported...exiting" \
                % dir_version
            sys.exit(1)

        # Build directory service node
        ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)
        chef_node['in_use'] = 'directory-server'
        chef_node.run_list = ["role[qa-%s-%s]" % (dir_version, os)]
        chef_node.save()

        print "Updating server...this may take some time"
        self.update_node(chef_node)

        # if redhat platform, disable iptables
        if chef_node['platform_family'] == 'rhel':
            print "Platform is RHEL family, disabling iptables"
            self.disable_iptables(chef_node)

        # Run chef-client twice
        print "Running chef-client for directory service node, \
        this may take some time..."
        run1 = self.run_chef_client(chef_node)
        if run1['success']:
            print "First chef-client run successful...starting second run..."
            run2 = self.run_chef_client(chef_node)
            if run2['success']:
                print "Second chef-client run successful..."
            else:
                print "Error running chef-client for directory node %s" \
                    % chef_node
                print run2
                sys.exit(1)
        else:
            print "Error running chef-client for directory node %s" % chef_node
            print run1
            sys.exit(1)

        #Save the ip address of the ldap server into the environment
        env = Environment(chef_node.chef_environment)
        env.override_attributes['keystone']['ldap']['url'] = "ldap://%s" % chef_node['ipaddress']
        env.save()

        #this is how you hard code :)
        with open('/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/%s.json'
                  % chef_node.chef_environment, "w") as f:
            f.write(json.dumps(env.to_dict()))

        # Directory service is set up, need to import config
        if run1['success'] and run2['success']:
            if dir_version == 'openldap':
                scp_run = run_remote_scp_cmd(ip, 'root', user_pass, '/var/lib/jenkins/source_files/ldif/*.ldif')
                if scp_run['success']:
                    ssh_run = run_remote_ssh_cmd(ip, 'root', user_pass,
                                                 "ldapadd -x -D \"cn=admin,dc=rcb,dc=me\" \
                        -f base.ldif -wostackdemo")
            elif dir_version == '389':
                # Once we support 389, code here to import needed config files
                print "389 is not yet supported..."
                sys.exit(1)
            else:
                print "%s is not supported...exiting" % dir_version
                sys.exit(1)

        if scp_run['success'] and ssh_run['success']:
            print "Directory Service: %s successfully set up..." \
                % dir_version
        else:
            print "Failed to set-up Directory Service: %s..." \
                % dir_version
            sys.exit(1)

    def build_compute(self, compute, environment, remote=False, chef_config_file=None):
        '''
        @summary: This will build out a single compute server
        '''
        compute_node = Node(compute, api=self.chef)
        compute_node['in_use'] = "compute"
        compute_node.run_list = ["role[single-compute]"]
        compute_node.save()

        if remote:
            remote_chef = chef_helper(chef_config_file)
            remote_chef.build_compute(compute,
                                      environment,
                                      'root',
                                      self.razor_password(compute_node))
        else:
            print "Updating server...this may take some time"
            self.update_node(compute_node)

            if compute_node['platform_family'] == 'rhel':
                print "Platform is RHEL family, disabling iptables"
                self.disable_iptables(compute_node)

            # Run chef client twice
            print "Running chef-client on compute node: %s, \
                   this may take some time..." % compute
            run1 = self.run_chef_client(compute_node)
            if run1['success']:
                print "First chef-client run successful, \
                       starting second run..."
                run2 = self.run_chef_client(compute_node)
                if run2['success']:
                    print "Second chef-client run successful..."
                else:
                    print "Error running chef-client for compute %s" % compute
                    print run2
                    sys.exit(1)
            else:
                print "Error running chef-client for compute %s" % compute
                print run1
                sys.exit(1)

    def build_computes(self, computes, environment, remote=False, chef_config_file=None):
        '''
        @summary: This will build out all the computes for a openstack
        environment, if remote is set it will use a remote chef server, if not
        it will use the current configured one.
        '''
        # Run computes
        print "Making the compute nodes..."
        for compute in computes:
            compute_node = Node(compute, api=self.chef)
            compute_node['in_use'] = "compute"
            compute_node.run_list = ["role[single-compute]"]
            compute_node.save()

            if remote:
                remote_chef = chef_helper(chef_config_file)
                remote_chef.build_compute(compute,
                                          environment,
                                          'root',
                                          self.razor_password(compute_node))
            else:
                print "Updating server...this may take some time"
                self.update_node(compute_node)

                if compute_node['platform_family'] == 'rhel':
                    print "Platform is RHEL family, disabling iptables"
                    self.disable_iptables(compute_node)

                # Run chef client twice
                print "Running chef-client on compute node: %s, \
                       this may take some time..." % compute
                run1 = self.run_chef_client(compute_node)
                if run1['success']:
                    print "First chef-client run successful, \
                           starting second run..."
                    run2 = self.run_chef_client(compute_node)
                    if run2['success']:
                        print "Second chef-client run successful..."
                    else:
                        print "Error running chef-client for compute %s" % compute
                        print run2
                        sys.exit(1)
                else:
                    print "Error running chef-client for compute %s" % compute
                    print run1
                    sys.exit(1)

    def build_controller(self, controller_node, environment=None, ha_num=0, remote=False, chef_config_file=None):
        '''
        @summary: This will build out a controller node based on location.
        if remote, use a passed config file to build a chef_helper class and
        build with that class, otherwise build with the current chef config
        '''
        chef_node = Node(controller_node, api=self.chef)
        if not ha_num == 0:
            print "Making %s the ha-controller%s node" % (controller_node,
                                                          ha_num)
            chef_node['in_use'] = "ha-controller%s" % ha_num
            chef_node.run_list = ["role[ha-controller%s]" % ha_num]
        else:
            print "Making %s the controller node" % controller_node
            chef_node['in_use'] = "controller"
            chef_node.run_list = ["role[single-controller]"]
        chef_node.save()

        # If remote is set, then we are building with a remote chef server
        if remote:
            remote_chef = chef_helper(chef_config_file)
            remote_chef.build_controller(controller_node,
                                         environment,
                                         'root',
                                         self.razor_password(chef_node),
                                         ha_num)
        else:
            print "Updating server...this may take some time"
            self.update_node(chef_node)

            if chef_node['platform_family'] == 'rhel':
                print "Platform is RHEL family, disabling iptables"
                self.disable_iptables(chef_node)

            # Run chef-client twice
            print "Running chef-client for controller node, this may take some time..."
            run1 = self.run_chef_client(chef_node)
            if run1['success']:
                print "First chef-client run successful, starting second run..."
                run2 = self.run_chef_client(chef_node)
                if run2['success']:
                    print "Second chef-client run successful..."
                else:
                    print "Error running chef-client for controller %s" % controller_node
                    print run2
                    sys.exit(1)
            else:
                print "Error running chef-client for controller %s" % controller_node
                print run1
                sys.exit(1)

    def build_chef_server(self, controller_node):
        '''
        @summary: This method will build a chef server VM on the controller_node with IP chef_server_ip.
        @param controller_node: Chef node name that will be the controller_node
        @type controller_node: String
        '''

        # Load controller node
        chef_node = Node(controller_node, api=self.chef)
        install_script = '/var/lib/jenkins/jenkins-build/qa/scripts/bash/jenkins/install-chef-server.sh'
        controller_ip = chef_node['ipaddress']
        controller_pass = self.razor_password(chef_node)

        #update node
        self.update_node(chef_node)

        # SCP install script to controller node
        scp_run = run_remote_scp_cmd(controller_ip,
                                     'root',
                                     controller_pass,
                                     install_script)
        if scp_run['success']:
            print "Successfully copied chef server install script to controller node %s" % controller_node
        else:
            print "Failed to copy chef server install script to controller node %s" % controller_node
            print scp_run
            sys.exit(1)

        # Run the install script
        to_run_list = ['chmod u+x ~/install-chef-server.sh',
                       './install-chef-server.sh']
        for cmd in to_run_list:
            ssh_run = run_remote_ssh_cmd(controller_ip,
                                         'root',
                                         controller_pass,
                                         cmd)
            if ssh_run['success']:
                print "command: %s ran successfully on %s" % (cmd,
                                                              controller_node)

    def build_quantum_network_node(self, quantum_node, environment=None, remote=False, chef_config_file=None):
        """
        @summary: This method will attempt to build a quantum network node for a
        OpenStack Cluster on the given node for the given environment
        """

        chef_node = Node(quantum_node, api=self.chef)

        # IF the in_use is not set, set it
        chef_node['in_use'] = 'quantum'
        chef_node.run_list = ["role[single-network-node]"]
        chef_node.save()

        # If remote is set, then we are building with a remote chef server
        if remote:
            remote_chef = chef_helper(chef_config_file)
            remote_chef.build_quantum(quantum_node,
                                      environment,
                                      'root',
                                      self.razor_password(chef_node))
        else:
            print "Updating server...this may take some time"
            self.update_node(chef_node)

            if chef_node['platform_family'] == 'rhel':
                print "Platform is RHEL family, disabling iptables"
                self.disable_iptables(chef_node)

            # Run chef-client twice
            print "Running chef-client for controller node, this may take some time..."
            run1 = self.run_chef_client(chef_node)
            if run1['success']:
                print "First chef-client run successful, starting second run..."
                run2 = self.run_chef_client(chef_node)
                if run2['success']:
                    print "Second chef-client run successful..."
                else:
                    print "Error running chef-client for controller %s" % controller_node
                    print run2
                    sys.exit(1)
            else:
                print "Error running chef-client for controller %s" % controller_node
                print run1
                sys.exit(1)

    def check_cluster_size(self, chef_nodes, size):
        if len(chef_nodes) < size:
            print "*****************************************************"
            print "Not enough nodes for the cluster_size given: %s " \
                % size
            print "*****************************************************"
            sys.exit(1)


    def clone_git_repo(self, server, github_user, github_pass):
        chef_node = Node(server, api=self.chef)
        node_ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)

        # Download vm setup script on controller node.
        print "Cloning repo with setup script..."
        rcps_dir = "/opt/rpcs"
        repo = "https://%s:%s@github.com/rsoprivatecloud/scripts" \
               % (github_user, github_pass)
        command = "mkdir -p /opt/rpcs; git clone %s %s" % (repo, rcps_dir)
        download_run = run_remote_ssh_cmd(node_ip,
                                          'root',
                                          user_pass,
                                          command)
        if not download_run['success']:
            print "Failed to clone script repo on server %s@%s" \
                % (chef_node, node_ip)
            print "Return Code: %s" % download_run['exception'].returncode
            print "Exception: %s" % download_run['exception']
            sys.exit(1)
        else:
            print "Successfully cloned repo with setup script..."

    def cluster_controller(self, environment, chef_api):
        chef_api = chef_api or self.chef
        ks_ip = None
        # Have to check for HA, if HA return the VIP for keystone
        ks_ip = None
        if 'vips' in environment.override_attributes:
            ks_ip = environment.override_attributes['vips']['keystone-service-api']
            controller_name = "ha-controller1"
        else:
            controller_name = "single-controller"

        # Queue the chef environment and get the controller node
        q = "chef_environment:%s AND run_list:*%s*" % (environment.name,
                                                       controller_name)
        search = Search("node", api=self.chef).query(q)
        controller = Node(search[0]['name'], api=self.chef)

        ks_ip = ks_ip or controller['ipaddress']

        return controller, ks_ip

    def cluster_environment(self, name=None, os_distro=None, feature_set=None, branch=None, chef_api=None):
        chef_api = chef_api or self.chef
        name = "%s-%s-%s-%s" % (name, os_distro, branch, feature_set)
        env = Environment(name, api=self.chef)
        return env

    def cluster_nodes(self, environment=None, api=None):
        """Returns all the nodes of an environment"""
        query = "chef_environment:%s" % environment
        self.node_search(query=query, api=api)

    def disable_iptables(self, chef_node, logfile="STDOUT"):
        ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)
        commands = '/etc/init.d/iptables save; \
                    /etc/init.d/iptables stop; \
                    /etc/init.d/iptables save'
        return run_remote_ssh_cmd(ip, 'root', user_pass, commands)

    def environment_exists(self, env):
        if not Search("environment", api=self.chef).query("name:%s" % env):
            return False
        return True

    def environment_has_controller(self, environment):
        # Load Environment
        nodes = Search('node', api=self.chef).query("chef_environment:%s" % environment)
        roles = ['role[qa-single-controller]',
                 'role[qa-ha-controller1]',
                 'role[qa-ha-controller2]']
        for node in nodes:
            chef_node = Node(node['name'], api=self.chef)
            if any(x in chef_node.run_list for x in roles):
                return True
            else:
                return False

    def gather_all_nodes(self, os):
        # Gather the nodes for the requested OS
        nodes = Search('node', api=self.chef).query("name:qa-%s-pool*" % os)
        return nodes

 

    def install_cookbooks(self, chef_server, openstack_release):
        '''
        @summary: This will install git and then pull the proper
        cookbooks into chef.
        @param chef_server: The node that the chef server is installed on
        @type chef_server: String
        @param openstack_release: grizzly, folsom, diablo
        @type oepnstack_release: String
        '''

        # Gather node info
        chef_server_node = Node(chef_server, api=self.chef)
        chef_server_ip = chef_server_node['ipaddress']
        chef_server_password = self.razor_password(chef_server_node)
        chef_server_platform = chef_server_node['platform']

        # Install git and clone rcbops repo
        rcbops_git = 'https://github.com/rcbops/chef-cookbooks.git'
        if chef_server_platform == 'ubuntu':
            to_run_list = ['apt-get install git -y',
                           'mkdir -p /opt/rcbops',
                           'cd /opt/rcbops; git clone %s -b %s --recursive' % (rcbops_git, openstack_release)]
        elif chef_server_platform == 'centos' or chef_server_platform == 'redhat':
            to_run_list = ['yum install git -y',
                           'mkdir -p /opt/rcbops',
                           'cd /opt/rcbops; git clone %s -b %s --recursive' % (rcbops_git, openstack_release)]
        else:
            print "Platform %s not supported" % chef_server_platform
            sys.exit(1)

        for cmd in to_run_list:
            run_cmd = run_remote_ssh_cmd(chef_server_ip,
                                         'root',
                                         chef_server_password,
                                         cmd)
            if not run_cmd['success']:
                print "Command: %s failed to run on %s" % (cmd, chef_server)
                print run_cmd
                sys.exit(1)

        # Install the cookbooks on the chef server
        to_run_list = ['knife cookbook upload --all --cookbook-path /opt/rcbops/chef-cookbooks/cookbooks',
                       'knife role from file /opt/rcbops/chef-cookbooks/roles/*.rb']

        for cmd in to_run_list:
            run_cmd = run_remote_ssh_cmd(chef_server_ip,
                                         'root',
                                         chef_server_password,
                                         cmd)
            if not run_cmd['success']:
                print "Command: %s failed to run on %s" % (cmd, chef_server)
                print run_cmd
                sys.exit(1)

    def install_cookbook(self, chef_server, giturl, branch):
        # Gather node info
        chef_server_node = Node(chef_server, api=self.chef)
        chef_server_ip = chef_server_node['ipaddress']
        chef_server_password = self.razor_password(chef_server_node)
        chef_server_platform = chef_server_node['platform']

        # Install git and clone the other cookbook
        if chef_server_platform == 'ubuntu':
            to_run_list = ['apt-get install git -y',
                           'mkdir -p /opt/test_cookbooks',
                           'cd /opt/test_cookbooks; git clone %s -b %s --recursive' % (giturl, branch)]
        elif chef_server_platform == 'centos' or chef_server_platform == 'redhat':
            to_run_list = ['yum install git -y',
                           'mkdir -p /opt/test_cookbooks',
                           'cd /opt/test_cookbooks; git clone %s -b %s --recursive' % (giturl, branch)]
        else:
            print "Platform %s not supported" % chef_server_platform
            sys.exit(1)

        for cmd in to_run_list:
            run_cmd = run_remote_ssh_cmd(chef_server_ip,
                                         'root',
                                         chef_server_password,
                                         cmd)
            if not run_cmd['success']:
                print "Command: %s failed to run on %s" % (cmd, chef_server)
                print run_cmd
                sys.exit(1)

        # Install the cookbooks on the chef server
        to_run_list = ['knife cookbook upload --all --cookbook-path /opt/test_cookbooks']
        for cmd in to_run_list:
            run_cmd = run_remote_ssh_cmd(chef_server_ip,
                                         'root',
                                         chef_server_password,
                                         cmd)
            if not run_cmd['success']:
                print "Command: %s failed to run on %s" % (cmd, chef_server)
                print run_cmd
                sys.exit(1)

    def install_opencenter(self, server, install_script,
                           role, oc_server_ip='0.0.0.0'):
        chef_node = Node(server, api=self.chef)
        user_pass = self.razor_password(chef_node)
        print ""
        print ""
        print "*****************************************************"
        print "*****************************************************"
        print "Installing %s..." % role
        print "*****************************************************"
        print "*****************************************************"
        print ""
        print ""
        if chef_node['platform_family'] == "debian":
            run_remote_ssh_cmd(chef_node['ipaddress'], 'root',
                               user_pass, 'apt-get update -y -qq')
        elif chef_node['platform_family'] == "rhel":
            run_remote_ssh_cmd(chef_node['ipaddress'], 'root', user_pass,
                               ('yum update -y -q;'
                                '/etc/init.d/iptables save;'
                                '/etc/init.d/iptables stop'))
        command = "bash <(curl %s) --role=%s --ip=%s" % (
            install_script, role, oc_server_ip)
        print command
        ret = run_remote_ssh_cmd(chef_node['ipaddress'],
                                 'root',
                                 user_pass,
                                 command)
        if not ret['success']:
            print "Failed to install opencenter %s" % type

    def install_opencenter_vm(self, vm_ip, oc_server_ip,
                              install_script, role, user, passwd):
        command = "bash <(curl %s) --role=%s --ip=%s" % (
            install_script, role, oc_server_ip)
        install_run = run_remote_ssh_cmd(vm_ip, user, passwd, command)
        if not install_run['success']:
            print "Failed to install OpenCenter %s on VM..." % role
            print "Return Code: %s" % install_run['exception'].returncode
            print "Exception: %s" % install_run['exception']
            sys.exit(1)
        else:
            print "OpenCenter %s successfully installed on vm with ip %s" \
                % (role, vm_ip)

    def install_server_vms(self, server, opencenter_server_ip,
                           chef_server_ip, vm_bridge, vm_bridge_device):
        chef_node = Node(server, api=self.chef)
        node_ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)

        # Run vm setup script on controller node
        print "Running VM setup script..."
        script = "/opt/rpcs/oc_prepare.sh"
        command = "bash %s %s %s %s %s" % (script,
                                           chef_server_ip,
                                           opencenter_server_ip,
                                           vm_bridge,
                                           vm_bridge_device)
        print "Prepare command to run: %s" % command
        install_run = run_remote_ssh_cmd(node_ip, 'root', user_pass, command)
        if not install_run['success']:
            print "Failed VM setup script on server %s@%s" % (
                chef_node, node_ip)
            print "Command ran: %s" % install_run['command']
            print "Return Code: %s" % install_run['exception'].returncode
            print "Exception: %s" % install_run['exception']
            sys.exit(1)
        else:
            print "VM's successfully setup on server %s..." % chef_node

    def node_search(self, query=None, api=None):
        api = api or self.chef
        search = Search("node", api=api).query(query)
        return (Node(n['name'], api=api) for n in search)

    def ping_check_vm(self, ip_address):
        command = "ping -c 5 %s" % ip_address
        try:
            ret = check_call(command, shell=True)
            return {'success': True,
                    'return': ret,
                    'exception': None}
        except CalledProcessError, cpe:
            return {'success': False,
                    'return': None,
                    'exception': cpe,
                    'command': command}


    def prepare_server(self, server):
        '''
        @sumary: This will prepare the server. If anything else needs to be
        installed, add it to prep_list
        '''

        chef_node = Node(server, api=self.chef)
        node_ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)

        prep_list = ['openssh-clients']

        if chef_node['platform_family'] == 'rhel':
            # Add EPEL to the repo list
            run_cmd = run_remote_ssh_cmd(node_ip,
                                         'root',
                                         user_pass,
                                         'rpm -Uvh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm')
            if not run_cmd['success']:
                print "Failed to add EPEL repo."
                print "Failed with return code {0}".format(
                    run_cmd['exception'].returncode)

            # Set command to be RHEL based
            command = "yum -y install"
        else:
            # Set command to be debian based
            command = "apt-get -y install"

        for item in prep_list:
            install_run = run_remote_ssh_cmd(node_ip,
                                             'root',
                                             user_pass,
                                             '%s %s' % (command, item))

            if not install_run['success']:
                print "Failed to install package %s on %s, check logs" % (
                    item, server)
                print install_run
                sys.exit(1)

        self.disable_iptables(chef_node)

    def prepare_vm_host(self, server):
        chef_node = Node(server, api=self.chef)
        controller_ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)

        if chef_node['platform_family'] == 'debian':
            commands = [("aptitude install -y curl dsh screen vim"
                         "iptables-persistent libvirt-bin python-libvirt"
                         "qemu-kvm guestfish git"),
                        "aptitude update -y",
                        "update-guestfs-appliance",
                        "ssh-keygen -f /root/.ssh/id_rsa -N \"\""]
        else:
            commands = [("yum install -y curl dsh screen vim"
                         "iptables-persistent"
                         "libvirt-bin python-libvirt qemu-kvm guestfish git"),
                        "yum update -y",
                        "update-guestfs-appliance",
                        "ssh-keygen -f /root/.ssh/id_rsa -N \"\""]

        for command in commands:
            print "************************************"
            print "Prepare command to run: %s" % command
            print "************************************"
            prepare_run = run_remote_ssh_cmd(controller_ip,
                                             'root',
                                             user_pass,
                                             command)

            if not prepare_run['success']:
                print "Failed to run command %s" % command
                print "check the server %s @ ip: %s" % (chef_node,
                                                        controller_ip)
                print "Return Code: %s" % prepare_run['exception'].returncode
                print "Exception: %s" % prepare_run['exception']
                sys.exit(1)

    def print_computes_info(self, computes):
        for compute in computes:
            print "Compute: %s" % self.print_server_info(compute)

    def print_server_info(self, server):
        chef_node = Node(server, api=self.chef)
        return "%s - %s" % (chef_node, chef_node['ipaddress'])

    def razor_password(self, chef_node):
        chef_node = Node(chef_node.name, api=self.chef)
        metadata = chef_node.attributes['razor_metadata'].to_dict()
        uuid = metadata['razor_active_model_uuid']
        return self.razor.get_active_model_pass(uuid)['password']

    def remote_chef_api(self, env):
        # RSAifying key
        remote_dict = env.override_attributes['remote_chef']
        pem = StringIO.StringIO(remote_dict['key'])
        remote_dict['key'] = rsa.Key(pem)
        return ChefAPI(**remote_dict)

    def remote_chef_server(self, env):
        query = "chef_environment:%s AND in_use:chef-server" % env.name
        return next(self.node_search(query=query))

    
    def run_cmd_on_node(self, node=None, cmd=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        run_remote_ssh_cmd(ip, user, password, cmd)


    def remove_chef(self, server):
        """
        @param chef_node
        """
        chef_node = Node(server, api=self.chef)
        user_pass = self.razor_password(chef_node)

        print "removing chef on %s..." % chef_node
        if chef_node['platform_family'] == "debian":
            command = "apt-get remove --purge -y chef; rm -rf /etc/chef"
        elif chef_node['platform_family'] == "rhel":
            command = 'yum remove -y chef; rm -rf /etc/chef /var/chef'
        else:
            print "OS Distro not supported"
            sys.exit(1)
        run = run_remote_ssh_cmd(chef_node['ipaddress'],
                                 'root',
                                 user_pass,
                                 command)
        if run['success']:
            print "Removed Chef on %s" % server
        else:
            print "Failed to remove chef on server %s" % server
            sys.exit(1)

    def remove_empty_environments(self):
        search = Search("environment").query("NOT name:_default")
        for e in search:
            if not Search("node").query("chef_environment:%s" % e['name']):
                print "Deleting empty environment: %s" % e['name']
                env = Environment(e['name'])
                env.delete()

    def scp_from_node(self, node=None, path=None, destination=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        get_file_from_server(ip, user, password, path, destination)

    def scp_to_node(self, node=None, path=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        run_remote_scp_cmd(ip, user, password, path)


    def set_node_in_use(self, node, role):
        # Edit the controller in our chef
        chef_node = Node(node, api=self.chef)
        chef_node['in_use'] = '%s' % role
        node_ip = chef_node['ipaddress']
        chef_node.save()

        return node_ip

    def set_nodes_environment(self, chef_node, environment):
        print "Nodes environment is %s, trying to set to %s" % (
            chef_node.chef_environment, environment)
        if chef_node.chef_environment != environment:
            print "Environment mismatch, setting environment"
            chef_node.chef_environment = environment
            chef_node.save()

    def setup_remote_chef_client_folder(self, chef_environment_name):
        '''
        This will set up a directory for each chef environment locally
        so that we can have local clients for all of the environments
        chef servers.
        '''
        chef_file_path = "/var/lib/jenkins/rcbops-qa/remote-chef-clients/%s/.chef" % chef_environment_name
        command = "mkdir -p %s" % chef_file_path
        try:
            check_call(command, shell=True)
            return chef_file_path
        except CalledProcessError, cpe:
            print "Failed to setup directory for %s" % chef_environment_name
            print "Exception: %s" % cpe
            sys.exit(1)

    def setup_remote_chef_client(self, chef_server, chef_environment):

        # Gather chef server info
        chef_server_node = Node(chef_server, api=self.chef)
        chef_server_ip = chef_server_node['ipaddress']
        chef_server_password = self.razor_password(chef_server_node)

        # Set up file for storing chef validation info locally
        print "Setting up client directory on localhost"
        chef_file_path = self.setup_remote_chef_client_folder(chef_environment)

        # Log onto server and copy chef-validator.pem and chef-webui.pem
        print "Copying new chef server validation files"
        to_run_list = ['admin.pem', 'chef-validator.pem']

        for item in to_run_list:
            get_file_ret = get_file_from_server(chef_server_ip,
                                                'root',
                                                chef_server_password,
                                                '~/.chef/%s' % item,
                                                chef_file_path)
            if not get_file_ret['success']:
                print "Failed to copy %s from server @ %s, check stuff" % (item, chef_server_ip)
                print get_file_ret
                sys.exit(1)

        # build knife.rb
        knife_dict = {"log_level": ":info",
                      "log_location": "STDOUT",
                      "node_name": "'admin'",
                      "client_key": "'%s/admin.pem'" % chef_file_path,
                      "validation_client_name": "'chef-validator'",
                      "validation_key": "'%s/chef-validator.pem'" % chef_file_path,
                      "chef_server_url": "'https://%s:4443'" % chef_server_ip}

        try:
            # Open the file
            fo = open("%s/knife.rb" % chef_file_path, "w")
        except IOError:
            print "Failed to open file %s/knife.rb" % chef_file_path
        else:
            # Write the json string
            for key, value in knife_dict.iteritems():
                fo.write("%s\t%s\n" % (key, value))

            #close the file
            fo.close()

            # print message for debugging
            print "%s/knife.rb successfully saved" % chef_file_path

        env = Environment(chef_environment)
        pem_file_name = "%s/admin.pem" % chef_file_path
        try:
            pem_file = open(pem_file_name)
            admin_pem = pem_file.read()
        except IOError:
            print "Error: can\'t find file or read data"
        else:
            print "Wrote pem file successfully"
            pem_file.close()
        remote_dict = {"client": "admin", "key": admin_pem, "url": "https://%s:4443" % chef_server_ip}
        env.override_attributes['remote_chef'] = remote_dict
        env.save()

        remote_config_file = '%s/knife.rb' % chef_file_path
        return remote_config_file

    def setup_remote_chef_environment(self, chef_server, chef_environment):
        """
        @summary This will copy the environment file and set it on the remote
        chef server.
        """

        # Gather chef server info
        chef_server_node = Node(chef_server, api=self.chef)
        chef_server_ip = chef_server_node['ipaddress']
        chef_server_password = self.razor_password(chef_server_node)

        environment_file = '/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments/%s.json' % chef_environment

        run_scp = run_remote_scp_cmd(chef_server_ip,
                                     'root',
                                     chef_server_password,
                                     environment_file)

        if not run_scp['success']:
            print "Failed to copy environment file to remote chef server"
            print run_scp
            sys.exit(1)

        to_run_list = ['cp ~/%s.json /opt/rcbops/chef-cookbooks/environments' % chef_environment,
                       'knife environment from file /opt/rcbops/chef-cookbooks/environments/%s.json' % chef_environment]

        for cmd in to_run_list:
            run_ssh = run_remote_ssh_cmd(chef_server_ip,
                                         'root',
                                         chef_server_password,
                                         cmd)

            if not run_ssh['success']:
                print "Failed to run remote ssh command on server %s @ %s" % (chef_server, chef_server_ip)
                print run_ssh
                sys.exit(1)

        print "Successfully set up remote chef environment %s on chef server %s @ %s" % (chef_environment, chef_server, chef_server_ip)

    def setup_quantum_network(self, environment):
        '''
        This function will build the quantum network on the cluseter
        with the name of the parameter
        @param environment: The clusters environment name
        @type environment: String
        '''

        # Find the Controller node info
        controller_query = 'chef_environment:%s AND in_use:controller' % environment
        controller_node = next(self.node_search(controller_query, self.chef))
        controller_node_ip = controller_node['ipaddress']
        controller_node_password = self.razor_password(controller_node)

        # Find the Quantum node info
        quantum_query = 'chef_environment:%s AND in_use:quantum' % environment
        quantum_node = next(self.node_search(quantum_query, self.chef))
        quantum_node_ip = quantum_node['ipaddress']
        quantum_node_password = self.razor_password(quantum_node)

        # Find the Compute node info
        compute_query = 'chef_environment:%s AND in_use:compute' % environment
        compute_node = next(self.node_search(compute_query, self.chef))
        compute_node_ip = compute_node['ipaddress']
        compute_node_password = self.razor_password(compute_node)

        # Setup OVS bridge on network and compute node
        print "Setting up OVS bridge and ports on Quantum / Compute Node(s)."
        to_run_list = ['ip a f eth1',
                       'ovs-vsctl add-br br-eth1',
                       'ovs-vsctl add-port br-eth1 eth1']

        for command in to_run_list:
            # Run command on quantum node
            quantum_ssh_run = run_remote_ssh_cmd(quantum_node_ip,
                                                 'root',
                                                 quantum_node_password,
                                                 command)

            if not quantum_ssh_run['success']:
                print "Failed to run command %s on server @ %s." % (
                    command, quantum_node_ip)
                print quantum_ssh_run
                sys.exit(1)

            # Run command on compute node
            compute_ssh_run = run_remote_ssh_cmd(compute_node_ip,
                                                 'root',
                                                 compute_node_password,
                                                 command)

            if not compute_ssh_run['success']:
                print "Failed to run command %s on server @ %s." % (
                    command, compute_node_ip)
                print compute_ssh_run
                sys.exit(1)

        print "Adding Quantum Network to Quantum Server."
        to_run_list = ["source openrc admin; quantum net-create --provider:physical_network=ph-eth1 --provider:network_type=flat flattest",
                       "source openrc admin; quantum subnet-create --name testnet --no-gateway --host-route destination=0.0.0.0/0,nexthop=10.0.0.1 --allocation-pool start=10.0.0.129,end=10.0.0.254 flattest 10.0.0.128/25"]

        for command in to_run_list:
            ssh_run = run_remote_ssh_cmd(controller_node_ip,
                                         'root',
                                         controller_node_password,
                                         command)

            if not ssh_run['success']:
                print "Failed to run command %s on server @ %s." % (
                    command, controller_node_ip)
                print ssh_run
                sys.exit(1)

        print "Quantum Network setup on cluster %s." % environment

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
