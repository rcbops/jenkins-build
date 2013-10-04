import sys
from time import sleep
from modules.Environments import Chef
from modules.Nodes import ChefRazorNode

"""
OpenStack deployments
"""


class Deployment(object):
    """Base for OpenStack deployments"""
    def __init__(self, name, os, branch, features=[]):
        self.name = name
        self.os = os
        self.features = features
        self.nodes = []

    def destroy(self):
        """ Destroys an OpenStack deployment """
        for node in self.nodes:
            node.destroy()

    def create_node(self, role):
        """ Abstract node creation method """
        raise NotImplementedError

    def provision(self):
        """Provisions nodes for each desired feature"""

    def pre_configure(self):
        """Pre configures node for each feature"""
        for feature in self.features:
            feature.pre_configure(self)

    def build_nodes(self):
        """Builds each node"""
        for node in self.nodes:
            node.build()

    def post_configure(self):
        """Post configures node for each feature"""
        for feature in self.features:
            feature.post_configure(self)

    def build(self):
        """Runs build steps for node's features"""
        self.update_environment()
        self.pre_configure()
        self.build_nodes()
        self.pre_configure()


class ChefRazorDeployment(Deployment):
    """
    Deployment mechinisms specific to deployment using:
    Puppet's Razor as provisioner and
    Opscode's Chef as configuration management
    """
    def __init__(self, name, os, branch, features, chef, razor):
        super(ChefRazorDeployment, self).__init__(name, os, branch, features)
        self.chef = chef
        self.razor = razor
        self.environment = None

    def free_node(self, image):
        """
        Provides a free node from
        """
        in_image_pool = "name:qa-%s-pool*" % image
        is_default_environment = "chef_environment:_default"
        is_ifaced = """run_list:recipe\[network-interfaces\]"""
        query = "%s AND %s AND %s" % (in_image_pool,
                                      is_default_environment,
                                      is_ifaced)
        nodes = self.node_search(query)
        fails = 0
        try:
            node = next(nodes)
            node['in_use'] = "provisioned"
            nodes.save
            yield node
        except StopIteration:
            if fails > 10:
                print "No available chef nodes"
                sys.exit(1)
            fails += 1
            sleep(15)
            nodes = self.node_search(query)

    def create_node(self, os):
        """Creates a node with chef cm and razor provisioner"""
        chef_node = self.free_node(self.os)
        osnode = ChefRazorNode(name, os, product, envrionment, provisioner,
                               branch, features)

        self.nodes.append(osnode)
        return osnode

    def search_role(self, role):
        """Returns nodes the have the desired role"""
        query = "chef_environment:%s AND in_use:%s" % (self.environment, role)
        chef_nodes = (node.name for node in self.chef.node_search(query=query))
        return (osnode for osnode in self.nodes if chef_nodes)

    def provision(self):
        """Creates remote chef node then provisions roles"""
        self.environment = self.chef.prepare_environment(self.name,
                                                         self.os,
                                                         self.os_version,
                                                         self.features)
        if self.features['remote_chef']:
            self.create_node(Roles.ChefServer)
        super(ChefRazorOSDeployment, self).provision()

    def destroy(self):
        super(ChefRazorOSDeployment, self).destroy()
        self.chef.destroy_environment(self.environment)
