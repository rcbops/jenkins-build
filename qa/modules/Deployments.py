import os
import sys
from time import sleep
from chef import autoconfigure, Search
from Config import Config
from inspect import getmembers, isclass
from razor_api import razor_api
from Environments import Chef
from Nodes import ChefRazorNode
from Features import deployment as deployment_features

"""
OpenStack deployments
"""


class Deployment(object):
    """Base for OpenStack deployments"""
    def __init__(self, name, os_name, branch, config, features=[]):
        self.name = name
        self.os = os_name
        self.branch = branch
        self.config = config
        self.features = features
        self.nodes = []

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            if type(getattr(self, attr)) is list:
                outl += '\n\t' + attr + ' : ' + ", ".join(getattr(self, attr))
            elif type(getattr(self, attr)) is type(None):
                outl += '\n\t' + attr + ' : None'
            else:
                outl += '\n\t' + attr + ' : ' + getattr(self, attr)
        return outl

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
    def __init__(self, name, os_name, branch, config, chef, razor,
                 features=[]):
        super(ChefRazorDeployment, self).__init__(name, os_name, branch,
                                                  config, features)
        self.chef = chef
        self.razor = razor
        self.environment = None

    @classmethod
    def free_node(cls, image):
        """
        Provides a free node from
        """
        in_image_pool = "name:qa-%s-pool*" % image
        is_default_environment = "chef_environment:_default"
        is_ifaced = """run_list:recipe\[network-interfaces\]"""
        query = "%s AND %s AND %s" % (in_image_pool,
                                      is_default_environment,
                                      is_ifaced)
        nodes = cls.node_search(query)
        fails = 0
        try:
            node = next(nodes)
            node['in_use'] = "provisioned"
            node.save
            yield node
        except StopIteration:
            if fails > 10:
                print "No available chef nodes"
                sys.exit(1)
            fails += 1
            sleep(15)
            nodes = cls.node_search(query)

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
            node = cls.node_config(deployment, features, os_name, product,
                                   chef, razor, branch)
            deployment.nodes.append(node)

        return deployment

    @classmethod
    def node_config(cls, deployment, features, os_name, product, chef, razor,
                    branch):
        node = ChefRazorNode(next(cls.free_node(os_name)).name, os_name,
                             product, chef, deployment, razor, branch)
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

    @classmethod
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
        # TODO: Add destroy to a chef helper class
        self.environment.destroy()
