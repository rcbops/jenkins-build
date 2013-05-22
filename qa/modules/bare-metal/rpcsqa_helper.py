import os
import sys
import time
from chef import *
from chef_helper import *
from server_helper import *
from razor_api import razor_api
from subprocess import check_call, CalledProcessError

class rpcsqa_helper:

    def __init__(self, razor_ip='198.101.133.3'):
        self.razor = razor_api(razor_ip)
        self.chef = autoconfigure()
        self.chef.set_default()

    def __repr__(self):
        """ Print out current instance of razor_api"""
        outl = 'class :'+self.__class__.__name__

        for attr in self.__dict__:
            outl += '\n\t'+attr+' : '+str(getattr(self, attr))

        return outl

    def bootstrap_chef(self, client_node, server_node):
        '''
        @summary: installes chef client on a node and bootstraps it to chef_server
        @param node: node to install chef client on
        @type node: String
        @param chef_server: node that is the chef server
        @type chef_server: String
        '''

        # Gather the chef info for the nodes
        chef_server_node = Node(server_node)
        chef_client_node = Node(client_node)

        chef_server_ip = chef_server_node['ipaddress']
        chef_server_password = self.razor_password(server_node)

        chef_client_ip = chef_client_node['ipaddress']
        chef_client_password = self.razor_password(client_node)

        # install chef client and bootstrap
        cmd = 'knife bootstrap %s -x root -P %s' % (chef_client_ip,
                                                    chef_client_password)

        ssh_run = run_remote_ssh_cmd(chef_server_ip,
                                     'root',
                                     chef_server_password,
                                     cmd)

        if ssh_run['success']:
            print "Successfully bootstraped chef-client on %s \
            to chef-server on %s" % (client_node, server_node)

    def build_dir_server(self, dir_node, dir_version, os):
        chef_node = Node(dir_node)

        # We dont support 389 yet, so exit if it is not ldap
        if dir_version != 'openldap':
            print "%s as a directory service is not yet supported...exiting" \
                % dir_version
            sys.exit(1)

        # Build directory service node
        ip = chef_node['ipaddress']
        root_pass = self.razor_password(chef_node)
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

        # Directory service is set up, need to import config
        if run1['success'] and run2['success']:
            if dir_version == 'openldap':
                scp_run = run_remote_scp_cmd(ip, 'root', root_pass,
                    '/var/lib/jenkins/source_files/ldif/*.ldif')
                if scp_run['success']:
                    ssh_run = run_remote_ssh_cmd(ip, 'root', root_pass,
                        "ldapadd -x -D \"cn=admin,dc=dev,dc=rcbops,dc=me\" \
                        -f base.ldif -w@privatecloud")
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

    def build_computes(self, computes, remote=False, chef_config_file=None):
        '''
        @summary: This will build out all the computes for a openstack
        environment, if remote is set it will use a remote chef server, if not
        it will use the current configured one.
        '''
        # Run computes
        print "Making the compute nodes..."
        for compute in computes:
            compute_node = Node(compute)
            compute_node['in_use'] = "compute"
            compute_node.run_list = ["role[single-compute]"]
            compute_node.save()

            if remote:
                remote_chef = chef_helper(chef_config_file)
                remote_chef.build_compute(compute,
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

    def build_controller(self, controller_node, ha_num=0,
                         remote=False, chef_config_file=None):
        '''
        @summary: This will build out a controller node based on location.
        if remote, use a passed config file to build a chef_helper class and
        build with that class, otherwise build with the current chef config
        '''
        chef_node = Node(controller_node)
        if not ha_num == 0:
            print "Making %s the ha-controller%s node" % (controller_node,
                                                          ha_num)
            chef_node['in_use'] = "ha-controller%s" % ha_num
            chef_node.run_list = ["role[ha-controller%s]" % ha_num]
        else:
            print "Making %s the controller node" % controller_node
            chef_node['in_use'] = "controller"
            chef_node.run_list = ["role[ha-controller1]"]
        chef_node.save()

        # If remote is set, then we are building with a remote chef server
        if remote:
            remote_chef = chef_helper(chef_config_file)
            remote_chef.build_controller(controller_node,
                                         ha_num,
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

    def build_chef_server(self, controller_node):
        '''
        @summary: This method will build a chef server VM on the controller_node with IP chef_server_ip.
        @param controller_node: Chef node name that will be the controller_node
        @type controller_node: String
        '''

        # Load controller node
        chef_node = Node(controller_node)
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

    def check_cluster_size(self, chef_nodes, size):
        if len(chef_nodes) < size:
            print "*****************************************************"
            print "Not enough nodes for the cluster_size given: %s " \
                % size
            print "*****************************************************"
            sys.exit(1)

    def cleanup_environment(self, chef_environment):
        """
        @param chef_environment
        """
        nodes = Search('node').query("chef_environment:%s" % chef_environment)
        for n in nodes:
            name = n['name']
            node = Node(name)
            if node['in_use'] != 0:
                self.erase_node(node)
            else:
                node.chef_environment = "_default"
                node.save()

    def clear_pool(self, chef_nodes, environment):
        for n in chef_nodes:
            name = n['name']
            node = Node(name)
            if node.chef_environment == environment:
                if node['in_use'] != 0:
                    self.erase_node(node)
                else:
                    node.chef_environment = "_default"
                    node.save()

    def clone_git_repo(self, server, github_user, github_pass):
        chef_node = Node(server)
        node_ip = chef_node['ipaddress']
        root_pass = self.razor_password(chef_node)

        # Download vm setup script on controller node.
        print "Cloning repo with setup script..."
        rcps_dir = "/opt/rpcs"
        repo = "https://%s:%s@github.com/rsoprivatecloud/scripts" \
               % (github_user, github_pass)
        command = "mkdir -p /opt/rpcs; git clone %s %s" % (repo, rcps_dir)
        download_run = run_remote_ssh_cmd(node_ip,
                                          'root',
                                          root_pass,
                                          command)
        if not download_run['success']:
            print "Failed to clone script repo on server %s@%s" \
                % (chef_node, node_ip)
            print "Return Code: %s" % download_run['exception'].returncode
            print "Exception: %s" % download_run['exception']
            sys.exit(1)
        else:
            print "Successfully cloned repo with setup script..."

    def cluster_controller(self, environment):
        controller_name = "ha-controller1"
        q = "chef_environment:%s AND run_list:*%s*" % (environment.name,
                                                       controller_name)
        search = Search("node").query(q)
        if not search:
            return None
        return Node(search[0]['name'])

    def cluster_environment(self, name, os, feature_set):
        name = "%s-%s-%s" % (name, os, feature_set)
        env = Environment(name)
        return env

    def disable_iptables(self, chef_node, logfile="STDOUT"):
        ip = chef_node['ipaddress']
        root_pass = self.razor_password(chef_node)
        commands = '/etc/init.d/iptables save; \
                    /etc/init.d/iptables stop; \
                    /etc/init.d/iptables save'
        return run_remote_ssh_cmd(ip, 'root', root_pass, commands)

    def environment_has_controller(self, environment):
        # Load Environment
        nodes = Search('node').query("chef_environment:%s" % environment)
        roles = ['role[qa-single-controller]',
                 'role[qa-ha-controller1]',
                 'role[qa-ha-controller2]']
        for node in nodes:
            chef_node = Node(node['name'])
            if any(x in chef_node.run_list for x in roles):
                return True
            else:
                return False

    def erase_node(self, chef_node):
        """
        @param chef_node
        """
        print "Deleting: %s" % str(chef_node)
        am_uuid = \
            chef_node['razor_metadata'].to_dict()['razor_active_model_uuid']
        run = run_remote_ssh_cmd(chef_node['ipaddress'],
                                 'root',
                                 self.razor_password(chef_node),
                                 "reboot 0")
        if not run['success']:
            print "Error rebooting server %s@%s " % (
                chef_node, chef_node['ipaddress'])
            # TODO: return failure
            sys.exit(1)

        #Knife node remove; knife client remove
        Client(str(chef_node)).delete()
        chef_node.delete()

        #Remove active model
        self.razor.remove_active_model(am_uuid)
        time.sleep(15)

    def gather_all_nodes(self, os):
        # Gather the nodes for the requested OS
        nodes = Search('node').query("name:qa-%s-pool*" % os)
        return nodes

    def gather_size_nodes(self, os, environment, cluster_size):
        ret_nodes = []
        count = 0

        # Gather the nodes for the requested OS
        nodes = Search('node').query("name:qa-%s-pool*" % os)

        # Take a node from the default environment that
        # has its network interfaces set.
        for n in nodes:
            name = n['name']
            node = Node(name)
            if ((node.chef_environment == "_default" or
                node.chef_environment == environment) and
                    "recipe[network-interfaces]" in node.run_list):
                self.set_nodes_environment(node, environment)
                ret_nodes.append(name)
                print "Taking node: %s" % name
                count += 1

                if count >= cluster_size:
                    break

        if count < cluster_size:
            print "Not enough available nodes for requested cluster size of %s, try again later..." % cluster_size
            sys.exit(1)

        return ret_nodes

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
        chef_server_node = Node(chef_server)
        chef_server_ip = chef_server_node['ipaddress']
        chef_server_password = self.razor_password(chef_server_node)
        chef_server_platform = chef_server_node['platform']

        # Install git and clone rcbops repo
        rcbops_git = 'https://github.com/rcbops/chef-cookbooks.git'
        if chef_server_platform == 'ubuntu':
            to_run_list = ['apt-get install git -y',
                           'mkdir -p /opt/rcbops',
                           'cd /opt/rcbops; git clone --recursive %s' % rcbops_git,
                           'cd /opt/rcbops/chef-cookbooks; git branch -t %s remotes/origin/%s' % (openstack_release, openstack_release),
                           'cd /opt/rcbops/chef-cookbooks; git checkout %s' % openstack_release,
                           'cd /opt/rcbops/chef-cookbooks; git submodule init; git submodule update']
        elif chef_server_platform == 'centos' or chef_server_platform == 'redhat':
            to_run_list = ['yum install git -y',
                           'mkdir -p /opt/rcbops',
                           'cd /opt/rcbops; git clone --recursive %s' % rcbops_git,
                           'cd /opt/rcbops/chef-cookbooks; git branch -t %s remotes/origin/%s' % (openstack_release, openstack_release),
                           'cd /opt/rcbops/chef-cookbooks; git checkout %s' % openstack_release,
                           'cd /opt/rcbops/chef-cookbooks; git submodule init; git submodule update']
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

    def install_opencenter(self, server, install_script,
                           role, oc_server_ip='0.0.0.0'):
        chef_node = Node(server)
        root_pass = self.razor_password(chef_node)
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
                               root_pass, 'apt-get update -y -qq')
        elif chef_node['platform_family'] == "rhel":
            run_remote_ssh_cmd(chef_node['ipaddress'], 'root', root_pass,
                               ('yum update -y -q;'
                                '/etc/init.d/iptables save;'
                                '/etc/init.d/iptables stop'))
        command = "bash <(curl %s) --role=%s --ip=%s" % (
            install_script, role, oc_server_ip)
        print command
        ret = run_remote_ssh_cmd(chef_node['ipaddress'],
                                 'root',
                                 root_pass,
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
        chef_node = Node(server)
        node_ip = chef_node['ipaddress']
        root_pass = self.razor_password(chef_node)

        # Run vm setup script on controller node
        print "Running VM setup script..."
        script = "/opt/rpcs/oc_prepare.sh"
        command = "bash %s %s %s %s %s" % (script,
                                           chef_server_ip,
                                           opencenter_server_ip,
                                           vm_bridge,
                                           vm_bridge_device)
        print "Prepare command to run: %s" % command
        install_run = run_remote_ssh_cmd(node_ip, 'root', root_pass, command)
        if not install_run['success']:
            print "Failed VM setup script on server %s@%s" % (
                chef_node, node_ip)
            print "Command ran: %s" % install_run['command']
            print "Return Code: %s" % install_run['exception'].returncode
            print "Exception: %s" % install_run['exception']
            sys.exit(1)
        else:
            print "VM's successfully setup on server %s..." % chef_node

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

    def prepare_environment(self, name, os_distro, feature_set):
        # Gather the nodes for the requested os_distro
        nodes = Search('node').query("name:qa-%s-pool*" % os_distro)

        #Make sure all networking interfacing is set
        for node in nodes:
            chef_node = Node(node['name'])
            self.set_network_interface(chef_node)

        # If the environment doesnt exist in chef, make it.
        env = "%s-%s-%s" % (name, os_distro, feature_set)
        if not Search("environment").query("name:%s" % env):
            print "Making environment: %s " % env
            Environment.create(env)

        return env

    def prepare_vm_host(self, server):
        chef_node = Node(server)
        controller_ip = chef_node['ipaddress']
        root_pass = self.razor_password(chef_node)

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
                                             root_pass,
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
        chef_node = Node(server)
        return "%s - %s" % (chef_node, chef_node['ipaddress'])

    def razor_password(self, chef_node):
        metadata = chef_node.attributes['razor_metadata'].to_dict()
        uuid = metadata['razor_active_model_uuid']
        return self.razor.get_active_model_pass(uuid)['password']

    def remove_broker_fail(self, policy):
        active_models = self.razor.simple_active_models(policy)
        for active in active_models:
            data = active_models[active]
            if 'broker_fail' in data['current_state']:
                print "!!## -- Removing active model  (broker_fail) -- ##!!"
                root_pass = self.razor.get_active_model_pass(
                    data['am_uuid'])['password']
                ip = data['eth1_ip']
                run = run_remote_ssh_cmd(ip, 'root', root_pass, 'reboot 0')
                if run['success']:
                    self.razor.remove_active_model(data['am_uuid'])
                    time.sleep(15)
                else:
                    print "!!## -- Trouble removing broker fail -- ##!!"
                    print run

    def run_chef_client(self, chef_node):
        """
        @param chef_node
        @param  logfile
        @return run_remote_ssh_cmd of chef-client
        """
        ip = chef_node['ipaddress']
        root_pass = self.razor_password(chef_node)
        return run_remote_ssh_cmd(ip,
                                  'root',
                                  root_pass,
                                  'chef-client')

    def remove_chef(self, server):
        """
        @param chef_node
        """
        chef_node = Node(server)
        try:
            root_pass = self.razor_password(chef_node)
            print "removing chef on %s..." % chef_node
            command = ""
            if chef_node['platform_family'] == "debian":
                command = "apt-get remove --purge -y chef; rm -rf /etc/chef"
            elif chef_node['platform_family'] == "rhel":
                command = 'yum remove -y chef; rm -rf /etc/chef /var/chef'
            run = run_remote_ssh_cmd(chef_node['ipaddress'],
                                     'root',
                                     root_pass,
                                     command)
        except:
            raise Exception("Error removing chef")

    def set_network_interface(self, chef_node):
        if "role[qa-base]" in chef_node.run_list:
            chef_node.run_list = ["recipe[network-interfaces]"]
            chef_node['in_use'] = 0
            chef_node.save()
            print "Running network interfaces for %s" % chef_node

            #Run chef client thrice
            run1 = self.run_chef_client(chef_node)
            run2 = self.run_chef_client(chef_node)
            run3 = self.run_chef_client(chef_node)

            if run1['success'] and run2['success'] and run3['success']:
                print "Done running chef-client"
            else:
                print "Error running chef client to set network interfaces"
                print "First run: %s" % run1
                print "Second run: %s" % run2
                print "Final run: %s" % run3
                raise Exception("Failed to set network interface for %s"
                                % chef_node)

    def set_node_in_use(self, node, role):
        # Edit the controller in our chef
        chef_node = Node(node)
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
            ret = check_call(command, shell=True)
            return chef_file_path
        except CalledProcessError, cpe:
            print "Failed to setup directory for %s" % chef_environment_name
            print "Exception: %s" % cpe
            sys.exit(1)

    def setup_remote_chef_client(self, controller, chef_environment):

        # Gather chef server info
        chef_server = Node(controller)
        chef_server_ip = chef_server['ipaddress']
        chef_server_password = self.razor_password(chef_server)

        # Set up file for storing chef validation info locally
        print "Setting up client directory on localhost"
        chef_file_path = self.setup_remote_chef_client_folder(chef_environment)

        # Log onto server and copy chef-validator.pem and chef-webui.pem
        print "Copying new chef server validation files"
        to_run_list = ['chef-validator.pem']

        for item in to_run_list:
            get_file_ret = get_file_from_server(chef_server_ip, 
                                                'root', 
                                                chef_server_password, 
                                                '/etc/chef-server/%s' % item, chef_file_path)
            if not get_file_ret['success']:
                print "Failed to copy %s from server @ %s, check stuff" % (item, chef_server_ip)
                print get_file_ret
                sys.exit(1)

        # setup remote chef client using files
        command = "knife configure --user %s --server-url %s --validation-client-name %s --validation-key %s/%s" % ('remote-jenkins', 'https://%s:4443' % chef_server_ip, 'chef-validator', chef_file_path, 'chef-validator.pem')

        try:
            check_call(command, shell=True)
        except CalledProcessError, cpe:
            print "Failed to setup knife client for remote chef server %s" % chef_server_ip
            print cpe
            sys.exit(1)

    def update_node(self, chef_node):
        ip = chef_node['ipaddress']
        root_pass = self.razor_password(chef_node)
        if chef_node['platform_family'] == "debian":
            run_remote_ssh_cmd(ip, 'root', root_pass,
                               'apt-get update -y; apt-get upgrade -y')
        elif chef_node['platform_family'] == "rhel":
            run_remote_ssh_cmd(ip, 'root', root_pass, 'yum update -y')
        else:
            print "Platform Family %s is not supported." \
                % chef_node['platform_family']
            sys.exit(1)

    def node_search(self, query=None):
        search = Search("node").query(query)
        return (Node(n['name']) for n in search)

    def run_cmd_on_node(self, node=None, cmd=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        run_remote_ssh_cmd(ip, user, password, cmd)

    def environment_exists(self, env):
        if not Search("environment").query("name:%s" % env):
            return False
        return True
