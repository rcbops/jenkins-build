import os
import types
import logging
from time import sleep
from Config import Config
from razor_api import razor_api
from Environments import Chef
from Nodes import ChefRazorNode
from chef import autoconfigure, Search
from inspect import getmembers, isclass
import Features.Deployment as deployment_features

"""
OpenStack deployments
"""


class Deployment(object):
    """Base for OpenStack deployments"""
    def __init__(self, name, os_name, branch, config):
        self.name = name
        self.os = os_name
        self.branch = branch
        self.config = config
        self.features = []
        self.nodes = []

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            if attr == 'features':
                features = "\tFeatures: {0}".format(
                    ", ".join(map(str, self.features)))
            elif attr == 'nodes':
                nodes = "\tNodes: {0}".format(
                    "".join(map(str, self.nodes)))
            elif isinstance(getattr(self, attr), types.NoneType):
                outl += '\n\t{0} : {1}'.format(attr, 'None')
            else:
                outl += '\n\t{0} : {1}'.format(attr, getattr(self, attr))

        return "\n".join([outl, features, nodes])

    def destroy(self):
        """ Destroys an OpenStack deployment """
        for node in self.nodes:
            node.destroy()

    def create_node(self, role):
        """ Abstract node creation method """
        raise NotImplementedError

    def provision(self):
        """Provisions nodes for each desired feature"""

    def update_environment(self):
        """Pre configures node for each feature"""
        for feature in self.features:
            feature.update_environment()

    def pre_configure(self):
        """Pre configures node for each feature"""
        for feature in self.features:
            feature.pre_configure()

    def build_nodes(self):
        """Builds each node"""
        for node in self.nodes:
            node.build()

    def post_configure(self):
        """Post configures node for each feature"""
        for feature in self.features:
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features"""
        self.update_environment()
        self.pre_configure()
        self.build_nodes()
        self.post_configure()

    @classmethod
    def test(cls):
        deployment = cls("Test Deployment",
                         "precuse",
                         "grizzly",
                         "config.yaml")
        features = ['ha', 'ldap']
        setattr(deployment, 'features', features)

        print deployment


class ChefRazorDeployment(Deployment):
    """
    Deployment mechinisms specific to deployment using:
    Puppet's Razor as provisioner and
    Opscode's Chef as configuration management
    """
    def __init__(self, name, os_name, branch, config, environment, razor):
        super(ChefRazorDeployment, self).__init__(name, os_name, branch,
                                                  config)
        self.environment = environment
        self.razor = razor
        self.set_network_interfaces(os_name)
        self.has_controller = False

    def set_network_interfaces(self, os):
        #Make sure all network interfacing is set
        query = "name:*%s*" % os
        for node in self.node_search(query):
            if "role[qa-base]" in node.run_list:
                crnode = ChefRazorNode.from_chef_node(node, os, None,
                                                      self.environment, None,
                                                      self.razor, None)
                crnode.add_run_list_item("recipe[network-interfaces]")
                crnode['in_use'] = 0
                logging.info("Running network interfaces for %s" % node)
                for i in xrange(3):
                    crnode.run_cmd('chef-client')

    def free_node(self, image, environment):
        """
        Provides a free node from
        """
        nodes = self.node_search("name:qa-%s-pool*" % image)
        for node in nodes:
            is_default = node.chef_environment == "_default"
            iface_in_run_list = "recipe[network-interfaces]" in node.run_list
            if (is_default and iface_in_run_list):
                node.chef_environment = environment.name
                node['in_use'] = "provisioned"
                node.save()
                return node
        raise Exception("No more nodes!!")
        self.destroy()

    @classmethod
    def fromfile(cls, name, branch, config, path=None):
        if not path:
            path = os.path.join(os.path.dirname(__file__),
                                os.pardir,
                                'deployment_templates/default.yaml')
        template = Config(path)[name]
        local_api = autoconfigure()
        chef = Chef(name, local_api, description=name)
        razor = razor_api(config['razor']['ip'])
        os_name = template['os']
        product = template['product']
        name = template['name']

        deployment = cls.deployment_config(template['os-features'],
                                           template['rpcs-features'], name,
                                           os_name, branch, config, chef,
                                           razor)
        for features in template['nodes']:
            node = deployment.node_config(features, os_name, product, chef,
                                          razor, branch)
            deployment.nodes.append(node)

        return deployment

    def node_config(self, features, os_name, product, chef, razor,
                    branch):
        cnode = self.free_node(os_name, chef)
        node = ChefRazorNode.from_chef_node(cnode, os_name, product, chef,
                                            self, razor, branch)
        node.add_features(features)
        return node

    @classmethod
    def deployment_config(cls, os_features, rpcs_features, name, os_name,
                          branch, config, chef, razor):
        deployment = cls(name, os_name, branch, config, chef,
                         razor)
        deployment.add_features(os_features)
        try:
            deployment.add_features(rpcs_features)
        except AttributeError:
            pass
        return deployment

    def add_features(self, features):
        classes = {k.lower(): v for (k, v) in
                   getmembers(deployment_features, isclass)}
        for feature, rpcs_feature in features.items():
            self.features.append(classes[feature](self, rpcs_feature[0]))

    def node_search(cls, query, environment=None, tries=10):
        api = autoconfigure()
        if environment:
            api = environment.local_api
        search = None
        while not search and tries > 0:
            search = Search("node", api=api).query(query)
            sleep(10)
            tries = tries - 1
        return (n.object for n in search)

    def search_role(self, feature):
        """Returns nodes the have the desired role"""
        return (node for node in self.nodes if feature in node.features)

    def destroy(self):
        super(ChefRazorDeployment, self).destroy()
        self.environment.destroy()
