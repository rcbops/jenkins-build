import sys
from chef import *
from server_helper import *


class chef_helper:

    def __init__(self, chef_config=None):
        if chef_config:
            self.chef = ChefAPI.from_config_file(chef_config)
        else:
            self.chef = autoconfigure()

    def __repr__(self):
        """ Print out current instance of chef_api"""
        outl = 'class :'+self.__class__.__name__

        for attr in self.__dict__:
            outl += '\n\t'+attr+' : '+str(getattr(self, attr))

        return outl

    def build_compute(self, compute_node, environment, user, password):
        '''
        @summary: Builds a controller node
        @param controller_node: The node to build as a controller
        @type controller_node: String
        @param user: user name on controller node
        @type user: String
        @param password: password for the user
        @type password: String
        '''
        # Set node attributes
        chef_node = Node(compute_node, api=self.chef)

        chef_node['in_use'] = "compute"
        chef_node.run_list = ["role[single-compute]"]
        chef_node.save()

        # Set the environment
        self.set_node_environment(chef_node, environment)

        # Run chef client twice
        print "Running chef-client on compute node: %s, \
               this may take some time..." % compute_node
        run1 = self.run_chef_client(chef_node, user, password)
        if run1['success']:
            print "First chef-client run successful, starting second run..."
            run2 = self.run_chef_client(chef_node, user, password)
            if run2['success']:
                print "Second chef-client run successful..."
            else:
                print "Error running chef-client for compute %s" % compute_node
                print run2
                sys.exit(1)
        else:
            print "Error running chef-client for compute %s" % compute_node
            print run1
            sys.exit(1)

    def build_controller(self, controller_node, environment,
                         user, password, ha_num=0):
        '''
        @summary: Builds a controller node
        @param controller_node: The node to build as a controller
        @type controller_node: String
        @param ha_num: If not 0, enabled ha
        @type ha_num: integer
        @param user: user name on controller node
        @type user: String
        @param password: password for the user
        @type password: String
        '''

        # Gather node info
        chef_node = Node(controller_node, api=self.chef)

        if not ha_num == 0:
            print "Making %s the ha-controller%s node" % (controller_node, ha_num)
            chef_node['in_use'] = "ha-controller%s" % ha_num
            chef_node.run_list = ["role[ha-controller%s]" % ha_num]
        else:
            print "Making %s the controller node" % controller_node
            chef_node['in_use'] = "controller"
            chef_node.run_list = ["role[ha-controller1]"]

        # Save Node
        chef_node.save()

        # Set the environment
        self.set_node_environment(chef_node, environment)

        # Run chef-client twice
        print "Running chef-client for controller node, this may take some time..."
        run1 = self.run_chef_client(chef_node, user, password)
        if run1['success']:
            print "First chef-client run successful, starting second run..."
            run2 = self.run_chef_client(chef_node, user, password)
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

    def print_nodes(self):
        # prints all the nodes in the chef server
        for node in Node.list(api=self.chef):
            print node

    def print_environments(self):
        for env in Environments.list(api=self.chef):
            print env

    def set_node_environment(self, node, environment):
        print "Setting node %s chef_environment to %s" % (str(node), environment)
        node.chef_environment = environment
        node.save()

    def run_chef_client(self, node, user, password):
        '''
        @summary: Builds a controller node
        @param node: The node to run chef-client on
        @type node: String
        @param user: user name on controller node
        @type user: String
        @param password: password for the user
        @type password: String
        '''
        ip = node['ipaddress']
        return run_remote_ssh_cmd(ip, user, password, 'chef-client')
