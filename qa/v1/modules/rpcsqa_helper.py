import sys
import time
import json
from math import *
from chef import *
from chef_helper import *
from server_helper import *
from cStringIO import StringIO
from razor_api import razor_api
from subprocess import check_call, CalledProcessError


class rpcsqa_helper:

    def __init__(self, razor_ip='198.101.133.3'):
        self.razor = razor_api(razor_ip)
        self.chef = autoconfigure()
        self.chef.set_default()

    def __repr__(self):
        """ Print out current instance of razor_api"""
        outl = 'class :' + self.__class__.__name__

        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))

        return outl

    def bring_up_cluster_default_routes(self, environment, device='eth0'):
        '''
        This will bring up a clusters default routes on the given device
        '''

        # Gather all the nodes in the environment
        query = "chef_environment:{0}".format(environment)

        for node in self.node_search(query, self.chef):
            # dont need to reboot chef server
            if not node['in_use'] == 'chef-server':
                self.bring_up_dev_route(node, device)

    def bring_up_dev_route(self, node, device='eth1'):
        '''
        This will bring up a given devices route to be the default
        '''

        commands = ['ip r f exact 0/0']

        if node['platform_family'] == 'rhel':
            commands.append("/etc/sysconfig/network-scripts/ifup-routes {0}".format(device))
        else:
            raise NotImplementedError

        command = "; ".join(commands)

        run = self.run_cmd_on_node(node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, node, run['error'])


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

        # install chef client and bootstrap
        command = 'knife bootstrap {0} -x root -P {1}'.format(chef_client_node['ipaddress'],
                                                              self.razor_password(chef_client_node))

        run = self.run_cmd_on_node(chef_server_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_server_node, run['error'])

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

    def build_controller(self, controller_node, environment=None, ha_num=0, neutron=False, remote=False, chef_config_file=None):
        '''
        @summary: This will build out a controller node based on location.
        if remote, use a passed config file to build a chef_helper class and
        build with that class, otherwise build with the current chef config
        '''
        chef_node = Node(controller_node, api=self.chef)
        chef_node['in_use'] = "controller"
        if not ha_num == 0:
            print "Making {0} the ha-controller{1} node".format(controller_node, ha_num)
            if neutron:
                chef_node.run_list = ["role[ha-controller{0}]".format(ha_num), "role[single-network-node]"]
            else:
                chef_node.run_list = ["role[ha-controller{0}]".format(ha_num)]
        else:
            print "Making {0} the controller node".format(controller_node)
            if neutron:
                chef_node.run_list = ["role[single-controller]", "role[single-network-node]"]
            else:
                chef_node.run_list = ["role[single-controller]"]
        chef_node.save()

        # If remote is set, then we are building with a remote chef server
        if remote:
            remote_chef = chef_helper(chef_config_file)
            remote_chef.build_controller(controller_node,
                                         environment,
                                         'root',
                                         self.razor_password(chef_node),
                                         ha_num,
                                         neutron)
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

    def build_chef_server(self, chef_server_node):
        '''
        This will build a chef server using the rcbops script and install git
        '''

        # Load controller node
        chef_node = Node(chef_server_node, api=self.chef)
        install_script = '/var/lib/jenkins/jenkins-build/qa/v1/bash/jenkins/install-chef-server.sh'
        chef_server_ip = chef_node['ipaddress']
        chef_server_pass = self.razor_password(chef_node)

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
        commands = ['chmod u+x ~/install-chef-server.sh',
                    './install-chef-server.sh']

        command = "; ".join(commands)
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

        self.install_git(chef_server_node)

    def build_quantum_network_node(self, quantum_node, environment, remote=False, chef_config_file=None):
        """
        @summary: This method will attempt to build a quantum network node for a
        OpenStack Cluster on the given node for the given environment
        """

        chef_node = Node(quantum_node, api=self.chef)

        # IF the in_use is not set, set it
        chef_node['in_use'] = 'quantum'
        # add openrc to network_node https://github.com/rcbops/chef-cookbooks/issues/454
        chef_node.run_list = ["role[single-network-node]", "recipe[osops-utils::openrc]"]
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
                    print "Error running chef-client for controller %s" % quantum_node
                    print run2
                    sys.exit(1)
            else:
                print "Error running chef-client for controller %s" % quantum_node
                print run1
                sys.exit(1)

    def build_swift_node(self, swift_node, swift_role, environment, remote=False, chef_config_file=None):
        """
        @summary: This will build one of 3 swift nodes (keystone, proxy, storage).
        """
        # Set the node in use on Razor/Chef server
        chef_node = Node(swift_node, api=self.chef)
        chef_node['in_use'] = '{0}'.format(swift_role)
        # This can only be run on a remote chef where the cookbooks are properly set up
        #chef_node.run_list = ['role[{0}]'.format(swift_role)]
        chef_node.save()

        # If remote is set, then use the remote chef
        if remote:
            remote_chef = chef_helper(chef_config_file)
            remote_chef.build_swift(swift_node, swift_role, environment, 'root', self.razor_password(chef_node))

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
                    print "Error running chef-client for controller %s" % swift_node
                    print run2
                    sys.exit(1)
            else:
                print "Error running chef-client for controller %s" % swift_node
                print run1
                sys.exit(1)

    def build_swift_rings(self, build, management_node, proxy_nodes, storage_nodes, num_rings=3, part_power=10, replicas=3, min_part_hours=1, disk_weight=1000):

        '''
        @summary This method will build out the rings for a swift cluster
        @param build Automate the swift ring build? (only use with 1 disk per node)
        @type build Boolean
        @param management_node Swift management server node object (chef objects)
        @type management_node Object
        @param proxy_nodes Swift proxy nodes (chef objects)
        @param storage_nodes Swift storage node objects (chef objects)
        @type storage List
        @param num_rings Number of rings you want in your swift
        @type num_rings Integer
        @param part_power Power of 2 to give the partitions in the balance of the rings
        @type part_power Integer
        @param replicas Number of replicas of each object to create and store across the ring
        @type replicas Integer
        @param min_part_hours Interval if time to try to rebalance objects across the ring
        @type min_part_hours Integer
        @param disk_weight Weight to assign the disk
        @type disk_weight Integer
        '''

        #################################################################################
        ############ Run through the storage nodes and set up the disks #################
        #################################################################################

        disk = "sdb"
        disk_label = "sdb1"
        for storage_node in storage_nodes:
            commands = ["/usr/local/bin/swift-partition.sh {0}".format(disk),
                        "/usr/local/bin/swift-format.sh {0}".format(disk_label),
                        "mkdir -p /srv/node/{0}".format(disk_label),
                        "mount -t xfs -o noatime,nodiratime,logbufs=8 /dev/{0} /srv/node/{0}".format(disk_label),
                        "chown -R swift:swift /srv/node"]

            if build:
                print "#" * 60
                print "##### Configuring Disks on Storage Node @ {0}#####".format(storage_node['ip'])
                print "#" * 60
                command = "; ".join(commands)
                run = self.run_cmd_on_node(storage_node['node'], command)
                if not run['success']:
                    self.failed_ssh_command_exit(command, storage_node['node'], run['error'])
            else:
                print "##### Info to setup drives for Swift #####"
                print "##### Log into root@{0} with pass: {1} and run the following commands: #####".format(storage_node['ip'], storage_node['password'])
                for command in commands:
                    print command

        #################################################################################
        ######## Setup partitions on storage nodes, (must run as swiftops user) #########
        #################################################################################
        commands = ["su swiftops",
                    "mkdir -p ~/swift/rings",
                    "cd ~/swift/rings",
                    "git init .",
                    "echo \"backups\" > .gitignore",
                    "swift-ring-builder object.builder create {0} {1} {2}".format(part_power, replicas, min_part_hours),
                    "swift-ring-builder container.builder create {0} {1} {2}".format(part_power, replicas, min_part_hours),
                    "swift-ring-builder account.builder create {0} {1} {2}".format(part_power, replicas, min_part_hours)]

        # Determine how many storage nodes we have and add them appropriatly
        builders = [
            {
                "name": "object",
                "port": 6000
            },
            {
                "name": "container",
                "port": 6001
            },
            {
                "name": "account",
                "port": 6002
            }
        ]

        for builder in builders:
            for index, node in enumerate(storage_nodes):

                # if the current index of the node is % num_rings = 0,
                # reset num so we dont add anymore rings past num_rings
                if index % num_rings is 0:
                    num = 0

                # Add the line to command to build the object
                commands.append("swift-ring-builder {0}.builder add z{1}-{2}:{3}/{4} {5}".format(builder['name'],
                                                                                                  num + 1,
                                                                                                  node['ip'],
                                                                                                  builder['port'],
                                                                                                  disk_label,
                                                                                                  disk_weight))
                num += 1

        # Finish the command list
        cmd_list = ["swift-ring-builder object.builder rebalance",
                    "swift-ring-builder container.builder rebalance",
                    "swift-ring-builder account.builder rebalance",
                    "git remote add origin /srv/git/rings",
                    "git add .",
                    "git config user.email \"swiftops@swiftops.com\"",
                    "git config user.name \"swiftops\"",
                    "git commit -m \"initial checkin\"",
                    "git push origin master"]

        for command in cmd_list:
            commands.append(command)

        if build:
            print "#" * 60
            print "##### Setting up swift rings for cluster #####"
            print "#" * 60

            # join all the commands into a single command, seperated by ";"
            command = '; '.join(commands)

            # Run the command on the swift management node
            run = self.run_cmd_on_node(management_node['node'], command)
            if not run['success']:
                self.failed_ssh_command_exit(command, management_node['node'], run['error'])

        else:
            # loop through and print each command for the user to run
            print "#" * 60
            print "##### Info to manually set up swift rings: #####"
            print "##### Log into root@{0} with pass: {1} and run the following commands: ".format(management_node['ip'], management_node['password'])
            for command in commands:
                print command

        ######################################################################################
        ################## Time to distribute the ring to all the boxes ######################
        ######################################################################################
        command = "/usr/local/bin/pull-rings.sh"

        print "#" * 60
        print "##### PULL RING ONTO MANAGEMENT NODE #####"
        if build:
            print "##### Pulling Swift ring on Management Node #####"
            run = self.run_cmd_on_node(management_node['node'], cmd, user, password)
            if not run['success']:
                self.failed_ssh_command_exit(command, management_node['node'], run['error'])
        else:
            print "##### On node root@{0} with pass: {1} and run the following command: #####".format(management_node['ip'], management_node['password'])
            print command

        print "#" * 60
        print "##### PULL RING ONTO PROXY NODES #####"
        for proxy_node in proxy_nodes:
            if build:
                print "##### Pulling swift ring down on proxy node @ {0}: #####".format(proxy_node['ip'])
                run = self.run_cmd_on_node(proxy_node['node'], command)
                if not run['success']:
                    self.failed_ssh_command_exit(command, proxy_node['node'], run['error'])
            else:
                print "##### On node root@{0} with pass: {1} and run the following command: #####".format(proxy_node['ip'], proxy_node['password'])
                print command

        print "#" * 60
        print "##### PULL RING ONTO STORAGE NODES #####"
        for storage_node in storage_nodes:
            if build:
                print "##### Pulling swift ring down storage node: {0} #####".format(storage_node['ip'])
                run = self.run_cmd_on_node(storage_node['node'], command)
                if not run['success']:
                    self.failed_ssh_command_exit(command, storage_node['node'], run['error'])
            else:
                print "##### On node root@{0} with pass: {1} and run the following command: #####".format(storage_node['ip'], storage_node['password'])
                print command

        print "#" * 60
        print "##### Done setting up swift rings #####"

    def check_cluster_size(self, chef_nodes, size):
        if len(chef_nodes) < size:
            return False

        return True

    def cleanup_environment(self, chef_environment):
        """
        @param chef_environment
        """
        nodes = Search('node', api=self.chef).query("chef_environment:%s" % chef_environment)
        if nodes:
            for n in nodes:
                name = n['name']
                print "Node {0} belongs to chef environment {1}".format(name, chef_environment)
                node = Node(name, api=self.chef)
                if node['in_use'] != 0:
                    self.erase_node(node)
                else:
                    print "Setting node {0} to chef environment _default".format(name)
                    node.chef_environment = "_default"
                    node.save()
        else:
            print "Environment: %s has no nodes" % chef_environment

    def clone_rso_git_repo(self, server, github_user, github_pass):
        chef_node = Node(server, api=self.chef)

        # Download vm setup script on controller node.
        print "Cloning repo with setup script..."
        rcps_dir = "/opt/rpcs"
        repo = "https://%s:%s@github.com/rsoprivatecloud/scripts" % (github_user, github_pass)
        command = "mkdir -p {0}; cd {0}; git clone {1}".format(repo, rcps_dir)

        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])
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
        search = Search("node", api=chef_api).query(q)
        controller = Node(search[0]['name'], api=chef_api)

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
        commands = ['/sbin/iptables -F',
                    '/etc/init.d/iptables save',
                    '/sbin/iptables -L']
        command = "; ".join(commands)
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

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

    def erase_node(self, chef_node):
        """
        @param chef_node
        """
        print "Deleting: %s" % str(chef_node)
        am_uuid = chef_node['razor_metadata'].to_dict()['razor_active_model_uuid']
        command = 'reboot 0'
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

        #Knife node remove; knife client remove
        Client(str(chef_node)).delete()
        chef_node.delete()

        #Remove active model
        self.razor.remove_active_model(am_uuid)
        time.sleep(15)

    def failed_ssh_command_exit(self, cmd, chef_node, error_message):

        print "## Failed to run command: {0} on {1} ##".format(cmd, chef_node.name)
        print "## Exited with exception {0}".format(error_message)
        print "## EXITING ##"
        sys.exit(1)

    def gather_all_nodes(self, os):
        # Gather the nodes for the requested OS
        nodes = Search('node', api=self.chef).query("name:qa-%s-pool*" % os)
        return nodes

    def gather_size_nodes(self, os, environment, cluster_size):
        ret_nodes = []
        count = 0

        # Gather the nodes for the requested OS
        nodes = Search('node', api=self.chef).query("name:qa-%s-pool*" % os)

        # Take a node from the default environment that
        # has its network interfaces set.
        for n in nodes:
            name = n['name']
            node = Node(name, api=self.chef)
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
            # Sleep for 10 seconds, this time doesnt matter as the build isnt going to happen
            # This will give chef time to do its thing
            self.cleanup_environment(environment)
            time.sleep(10)
            Environment(environment, api=self.chef).delete()
            sys.exit(1)

        return ret_nodes

    def get_server_info(self, server):

        # Gather node info
        node = Node(server, api=self.chef)
        return {'node': node,
                'ip': node['ipaddress'],
                'password': self.razor_password(node),
                'platform': node['platform']}

    def get_node_ip(self, server):

        return self.get_server_info(server)['ip']

    def install_berkshelf(self, server):
        """
        This is needed cause berkshelf is a PITA to get up and running
        """

        # Gather node info
        server_info = self.get_server_info(server)

        # Install needed server packages for berkshelf
        packages = ['libxml2-dev', 'libxslt-dev', 'libz-dev']
        rvm_install = "curl -L https://get.rvm.io | bash -s -- stable --ruby=1.9.3 --autolibs=enable --auto-dotfiles"
        #ruby_versions = ['1.8.7', '1.9.3']
        gems = ['berkshelf', 'chef']

        # Install OS packages
        self.install_packages(server_info['node'], packages)

        # Install RVM
        run = self.run_cmd_on_node(server_info['node'], rvm_install)

        if not run['success']:
            self.failed_ssh_command_exit(rvm_install, server_info['node'], run['error'])

        # Install RVM Ruby Versions
        #self.install_rvm_versions(server_info['node'], ruby_versions)

        # Install Ruby Gems
        self.install_ruby_gems(server_info['node'], gems)

    def install_cookbooks(self, chef_server, cookbooks, local_repo='/opt/rcbops'):
        '''
        @summary: This will pull the cookbooks down for git that you pass in cookbooks
        @param chef_server: The node that the chef server is installed on
        @type chef_server: String
        @param cookbooks A List of cookbook repos in dict form {url: 'asdf', branch: 'asdf'}
        @type cookbooks dict
        @param local_repo The location to place the cookbooks i.e. '/opt/rcbops'
        @type String
        '''

        # Gather node info
        chef_server_node = Node(chef_server, api=self.chef)

        # Make directory that the cookbooks will live in
        command = 'mkdir -p {0}'.format(local_repo)
        run = self.run_cmd_on_node(chef_server_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_server_node, run['error'])

        for cookbook in cookbooks:
            self.install_cookbook(chef_server, cookbook, local_repo)

    def install_cookbook(self, chef_server, cookbook, local_repo):

        # Gather node info
        chef_server_node = Node(chef_server, api=self.chef)

        # Since we are installing from git, the urls are pretty much constant
        # Pulling the url apart to get the name of the cookbooks
        cookbook_name = cookbook['url'].split("/")[-1].split(".")[0]

        # clone to cookbook
        commands = ['cd {0}; git clone {1}'.format(local_repo, cookbook['url'])]

        # if a tag was sent in, use the tagged cookbooks
        if cookbook['tag'] is not None:
            commands.append('cd {0}/{1}; git checkout v{2}'.format(local_repo, cookbook_name, cookbook['tag']))
        else:
            commands.append('cd {0}/{1}; git checkout {2}'.format(local_repo, cookbook_name, cookbook['branch']))

        # Stupid logic to see if the repo name contains "cookbooks", if it does then
        # we need to load from cookbooks repo, not the repo itself.
        # I think this is stupid logic, there has to be a better way (jacob)
        if 'cookbooks' in cookbook_name:
             # add submodule stuff to list
            commands.append('cd {0}/{1}; '
                            'git submodule init; '
                            'git submodule sync; '
                            'git submodule update'.format(local_repo, cookbook_name))
            commands.append('knife cookbook upload --all --cookbook-path {0}/{1}/cookbooks'.format(local_repo, cookbook_name))
        else:
            commands.append('knife cookbook upload --all --cookbook-path {0}/{1}'.format(local_repo, cookbook_name))

        # Append role load to run list
        commands.append('knife role from file {0}/{1}/roles/*.rb'.format(local_repo, cookbook_name))

        command = "; ".join(commands)

        run = self.run_cmd_on_node(chef_server_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_server_node, run['error'])

    def install_git(self, chef_server):
        # This needs to be taken out and install_package used instead (jwagner)
        # Gather node info
        chef_server_node = Node(chef_server, api=self.chef)
        chef_server_platform = chef_server_node['platform']

        # Install git and clone the other cookbook
        if chef_server_platform == 'ubuntu':
            command = 'apt-get install git -y'
        elif chef_server_platform == 'centos' or chef_server_platform == 'redhat':
            command = 'yum install git -y'
        else:
            print "Platform %s not supported" % chef_server_platform
            sys.exit(1)

        run = self.run_cmd_on_node(chef_server_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_server_node, run['error'])

    def install_packages(self, chef_node, packages):

        for package in packages:
            self.install_package(chef_node, package)

    def install_package(self, chef_node, package):

        # Install package
        if chef_node['platform'] == 'ubuntu':
            command = 'apt-get install -y {0}'.format(package)
        elif chef_node['platform'] == 'centos' or chef_node['platform'] == 'redhat':
            command = 'yum install -y {0}'.format(package)
        else:
            print "Platform %s not supported" % chef_node['platform']
            sys.exit(1)

        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

        # update after install
        self.update_node(chef_node)

    def install_ruby_gems(self, chef_node, gems):

        for gem in gems:
            self.install_ruby_gem(chef_node, gem)

    def install_ruby_gem(self, chef_node, gem):

        command = 'source /usr/local/rvm/scripts/rvm; gem install --no-rdoc --no-ri {0}'.format(gem)

        run = self.run_cmd_on_node(chef_node, command)

        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['exception'])

    def install_rvm_versions(self, chef_node, versions):

        for version in versions:
            self.install_rvm_version(chef_node, version)

    def install_rvm_version(self, chef_node, version):

        command = 'source /usr/local/rvm/scripts/rvm; rvm install {0}'.format(version)

        run = self.run_cmd_on_node(chef_node, command)

        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['exception'])

    def install_server_vms(self, server, opencenter_server_ip, chef_server_ip, vm_bridge, vm_bridge_device):

        chef_node = Node(server, api=self.chef)

        # Run vm setup script on controller node
        print "Running VM setup script..."
        script = "/opt/rpcs/oc_prepare.sh"
        command = "bash %s %s %s %s %s" % (script,
                                           chef_server_ip,
                                           opencenter_server_ip,
                                           vm_bridge,
                                           vm_bridge_device)
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])
        else:
            print "VM's successfully setup on server %s..." % chef_node

    def node_search(self, query=None, api=None):
        api = api or self.chef
        search = Search("node", api=api).query(query)
        return (Node(n['name'], api=api) for n in search)

    def ping_check_cluster(self, environment):

        # Gather all the nodes in the environment
        query = "chef_environment:{0}".format(environment)

        online = False
        offline = False
        for node in self.node_search(query, self.chef):
            # Dont need to check the chef server
            if not node['in_use'] == 'chef-server':
                if self.ping_check_node(node) is False:
                    offline = True
                else:
                    online = True

        return {"online": online, "offline": offline}

    def ping_check_node(self, node):
        ip_address = node['ipaddress']
        command = "ping -c 3 %s" % ip_address
        run = run_cmd(command)
        return run['success']

    def prepare_environment(self, name, os_distro, feature_set, branch=None):
        # Gather the nodes for the requested os_distro
        nodes = Search('node', api=self.chef).query("name:qa-%s-pool*" % os_distro)

        #Make sure all network interfacing is set
        for node in nodes:
            chef_node = Node(node['name'], api=self.chef)
            self.set_network_interface(chef_node)

        # If the branch isnt set, set it to the feature (for opencenter)
        if branch is None:
            branch = feature_set

        # If the environment doesnt exist in chef, make it.
        env = "%s-%s-%s-%s" % (name, os_distro, branch, feature_set)
        chef_env = Environment(env, api=self.chef)
        if not chef_env.exists:
            print "Making environment: %s " % env
            chef_env.create(env, api=self.chef)
        return env

    def prepare_server(self, server):
        '''
        @summary: This will prepare the server (mostly used for centos and rhel)
        '''

        chef_node = Node(server, api=self.chef)
        if chef_node['platform_family'] == 'rhel':
            commands = ['rpm -Uvh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm',
                        'yum -y install openssh-clients']
        else:
            # Set command to be debian based
            commands = ["apt-get -y install openssh-clients"]

        command = "; ".join(commands)
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

        self.disable_iptables(chef_node)

    def prepare_vm_host(self, server):
        chef_node = Node(server, api=self.chef)

        if chef_node['platform_family'] == 'debian':
            commands = [("apt-get install -y curl dsh screen vim"
                         "iptables-persistent libvirt-bin python-libvirt"
                         "qemu-kvm guestfish git"),
                         "apt-get update -y",
                         "update-guestfs-appliance",
                         "ssh-keygen -f /root/.ssh/id_rsa -N \"\""]
        else:
            commands = [("yum install -y curl dsh screen vim"
                         "iptables-persistent"
                         "libvirt-bin python-libvirt qemu-kvm guestfish git"),
                         "yum update -y",
                         "update-guestfs-appliance",
                         "ssh-keygen -f /root/.ssh/id_rsa -N \"\""]

        command = "; ".join(commands)
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

    def print_computes_info(self, computes):
        for compute in computes:
            print "Compute: %s" % self.print_server_info(compute)

    def print_server_info(self, server):
        chef_node = Node(server, api=self.chef)
        return "%s - %s" % (chef_node, chef_node['ipaddress'])

    def razor_password(self, chef_node):
        node = Node(chef_node.name, api=self.chef)
        metadata = node.attributes['razor_metadata'].to_dict()
        uuid = metadata['razor_active_model_uuid']
        return self.razor.get_active_model_pass(uuid)['password']

    def remote_chef_api(self, env):
        # RSAifying key
        remote_dict = env.override_attributes['remote_chef']
        pem = StringIO(remote_dict['key'])
        remote_dict['key'] = rsa.Key(pem)
        return ChefAPI(**remote_dict)

    def remote_chef_server(self, env):
        query = "chef_environment:%s AND in_use:chef-server" % env.name
        return next(self.node_search(query=query))

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

    def run_cmd_on_node(self, node=None, cmd=None, user=None, password=None,
                        private=False):
        user = user or "root"
        password = password or self.razor_password(node)
        if private:
            iface = "eth1" if "precise" in node.name else "em2"
            print node['network']['interfaces']
            ip = str(node['network']['interfaces'][iface]['addresses'].keys()[0])
        else:
            ip = node['ipaddress']
        print "### Running: %s ###" % cmd
        print "### On: %s - %s ###" % (node.name, ip)
        return run_remote_ssh_cmd(ip, user, password, cmd)

    def run_chef_client(self, chef_node):
        """
        @param chef_node
        @param  logfile
        @return run_remote_ssh_cmd of chef-client
        """
        ip = chef_node['ipaddress']
        user_pass = self.razor_password(chef_node)
        return run_remote_ssh_cmd(ip,
                                  'root',
                                  user_pass,
                                  'chef-client')

    def reboot_cluster(self, environment):

        # Gather all the nodes in the environment
        query = "chef_environment:{0}".format(environment)

        for node in self.node_search(query, self.chef):
            # dont need to reboot chef server
            if not node['in_use'] == 'chef-server':
                if self.ping_check_node(node) is True:
                    self.reboot_node(node)

    def reboot_node(self, chef_node):
        command = 'reboot 0'
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

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

        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

    def remove_empty_environments(self):
        search = Search("environment").query("NOT name:_default")
        for e in search:
            if not Search("node").query("chef_environment:%s" % e['name']):
                print "Deleting empty environment: %s" % e['name']
                env = Environment(e['name'])
                env.delete()

    def scp_from_node(self, node=None, path=None, destination=None, user=None, password=None):
        user = user or "root"
        password = password or self.razor_password(node)
        ip = node['ipaddress']
        get_file_from_server(ip, user, password, path, destination)

    def scp_to_node(self, node=None, path=None):
        user = "root"
        password = self.razor_password(node)
        ip = node['ipaddress']
        run_remote_scp_cmd(ip, user, password, path)

    def set_environment_variables(self, environment, variable_dict, attrib_key, attributes='override'):
        '''
        Take the variable hash and place it inside the environment under the attribute tag
        @param environment The chef environment to place hash
        @type environment String
        @param variable_dict A Dict to place into the environment
        @type variable_dict Dict
        @param attrib_key The key inside the attributes to write to
        @type String
        @param attributes The attributes to place hash under (override, default, etc.)
        @type attributes String
        '''

        # Grab the environment to edit
        chef_env = Environment(environment, api=self.chef)

        # Check to see if the environment exists
        if not chef_env.exists:
            print "The chef environment you are trying to edit doesnt exist"
            sys.exit(1)

        # Load the environemnt into a dict
        env_json = chef_env.to_dict()

        # Update the appropriate attributes with the passed dict
        env_json['{0}_attributes'.format(attributes)][attrib_key].update(variable_dict)

        # Save the environment
        chef_env.save()

        # Write the environment to the file
        self.write_chef_env_to_file(environment)

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

    def set_node_in_use(self, node, role):
        # Edit the controller in our chef
        chef_node = Node(node, api=self.chef)
        chef_node['in_use'] = role
        chef_node.save()

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

    def setup_remote_chef_environment(self, environment):
        """
        @summary Duplicates the local chef environment remotely
        """
        print "Putting environment onto remote chef server"
        chef_environment = Environment(environment)
        name = chef_environment.name
        remote_api = self.remote_chef_client(chef_environment)
        env = Environment(name, api=remote_api)
        env.override_attributes = dict(chef_environment.override_attributes)
        env.save()

    def setup_neutron_network(self, environment, ha=False):
        '''
        This function will build the quantum network on the cluster with the name of the parameter
        @param environment: The clusters environment name
        @type environment: String
        '''

        controller_query = 'chef_environment:%s AND in_use:controller' % environment
        compute_query = 'chef_environment:%s AND in_use:compute' % environment

        if "precise" in environment:
            phy_dev = "eth1"
        else:
            phy_dev = "em2"

        # Setup OVS bridge on network and compute node
        print "Setting up OVS bridge and ports on Quantum / Compute Node(s)."
        commands = ['ip a f {0}'.format(phy_dev),
                    'ovs-vsctl add-port br-{0} {0}'.format(phy_dev)]
        command = "; ".join(commands)

        # Setup bridge and ports on controllers
        for controller_node in self.node_search(controller_query, self.chef):
            # Run command on controller
            controller_run = self.run_cmd_on_node(controller_node, command)
            if not controller_run['success']:
                self.failed_ssh_command_exit(command, controller_node, controller_run['error'])

        # Setup ports and bridges on computes
        for compute_node in self.node_search(compute_query, self.chef):
            # Run command on compute node
            compute_run = self.run_cmd_on_node(compute_node, command)
            if not compute_run['success']:
                self.failed_ssh_command_exit(command, compute_node, compute_run['error'])

        print "Adding Quantum Network."
        commands = ["source openrc admin",
                    "quantum net-create flattest".format(phy_dev)]

        # Need to be able to run both centos and precise tests so chop up subnet
        if phy_dev == 'eth1':
            commands.append("source openrc admin; quantum subnet-create --name testnet --no-gateway flattest 10.0.0.0/24")
        else:
            commands.append("source openrc admin; quantum subnet-create --name testnet --no-gateway flattest 10.0.0.0/24")

         # Setup bridge and ports on controllers
        command = "; ".join(commands)
        failures = 0
        for controller_node in self.node_search(controller_query, self.chef):
            # Only need to setup on controller 1 in HA
            if ha is True:
                controller_run = self.run_cmd_on_node(controller_node, command)
                if controller_run['success']:
                    print "## Network setup on controller: {0}".format(controller_node)
                    break
                else:
                    print "## Cannot setup network on controller: {0} ##".format(controller_node)
                    print "## Exited with error: {0}".format(controller_run['error'])
                    print "## Trying next controller node ##"
                    failures += 1

                if failures == 2:
                    print "## Failed to setup Neutron network on both controllers, please check ##"
                    self.failed_ssh_command_exit(command, controller_node, controller_run['error'])
            else:
                # Run command on controller
                controller_run = self.run_cmd_on_node(controller_node, command)
                if not controller_run['success']:
                    self.failed_ssh_command_exit(command, controller_node, controller_run['error'])

        print "Quantum Network setup on cluster %s." % environment

    def update_node(self, chef_node):

        if chef_node['platform_family'] == "debian":
            commands = ['apt-get update -y', 'apt-get upgrade -y']
        elif chef_node['platform_family'] == "rhel":
            commands = ['yum update -y']
        else:
            print "Platform Family %s is not supported." \
                % chef_node['platform_family']
            sys.exit(1)

        command = "; ".join(commands)
        run = self.run_cmd_on_node(chef_node, command)
        if not run['success']:
            self.failed_ssh_command_exit(command, chef_node, run['error'])

    def write_chef_env_to_file(self, environment, file_path='/var/lib/jenkins/rcbops-qa/chef-cookbooks/environments'):
        '''
        @summary writes the current chef environment to the correct file that it represents
        @param environment The chef environment to write to file (name must match file name)
        @type environment String
        @param file_path The path to the chef environments directory to write to
        @type file_path String
        '''

        # Grab the current chef environment
        chef_env = Environment(environment, api=self.chef)

        if not chef_env.exists:
            print "The chef environment that you are trying to write does not exist"
            sys.exit(1)

        # Convert the env to a json dict
        env_json = chef_env.to_dict()

        file_name = "{0}/{1}.json".format(file_path, environment)
        # Open the environment file for write
        try:
            # Open the file
            fo = open(file_name, "w")
        except IOError:
            print "Failed to open file: {0}".format(file_name)
        else:
            # Write the json string
            fo.write(json.dumps(env_json))

            #close the file
            fo.close()

            # print message for debugging
            print "{0} successfully saved".format(file_name)

    def remote_chef_client(self, env):
        # RSAifying key
        print "Create chef client for env: %s" % env.name
        env = Environment(env.name)
        remote_dict = dict(env.override_attributes['remote_chef'])
        pem = StringIO(remote_dict['key'])
        remote_dict['key'] = rsa.Key(pem)
        return ChefAPI(**remote_dict)

    def add_remote_chef_locally(self, chef_server_node, env):
        print "Adding remote chef server credentials to local chef server"
        chef_server_node = Node(chef_server_node, api=self.chef)
        cmd = "cat ~/.chef/admin.pem"
        run = self.run_cmd_on_node(node=chef_server_node, cmd=cmd)
        if not run['success']:
            self.failed_ssh_command_exit(cmd, chef_server_node, run['error'])
        admin_pem = run['return']
        remote_dict = {"client": "admin",
                       "key": admin_pem,
                       "url": "https://%s:4443" %
                       chef_server_node['ipaddress']}
        env = Environment(env)
        env.override_attributes['remote_chef'] = remote_dict
        env.save()
