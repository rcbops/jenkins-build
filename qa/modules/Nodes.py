import types
import logging
from time import sleep
from chef import Node as CNode
from chef import Client as CClient
from inspect import getmembers, isclass
from Features import Node as node_features
from server_helper import ssh_cmd, scp_to, scp_from


class Node(object):
    """
    A individual computation entity to deploy a part OpenStack onto
    Provides server related functions
    """
    def __init__(self, ip, user, password, os, product, environment,
                 deployment):
        self.ip = ip
        self.user = user
        self.password = password
        self.os = os
        self.product = product
        self.environment = environment
        self.deployment = deployment
        self.features = []
        self._cleanups = []

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            # We want to not print the deployment because
            # it is a circular reference
            if attr != 'deployment':
                if attr == 'features':
                    features = "\tFeatures: {0}".format(
                        ", ".join(map(str, self.features)))
                elif isinstance(getattr(self, attr), types.NoneType):
                    outl += '\n\t{0} : {1}'.format(attr, 'None')
                else:
                    outl += '\n\t{0} : {1}'.format(attr, getattr(self, attr))
            outl += '\n\tIP : {1}'.format(self.ip)

        return "\n".join([outl, features])

    def run_cmd(self, remote_cmd, user=None, password=None, quiet=False):
        user = user or self.user
        password = password or self.password
        logging.info("Running: {0} on {1}".format(remote_cmd, self.name))
        return ssh_cmd(self.ip, remote_cmd=remote_cmd, user=user,
                       password=password, quiet=quiet)

    def scp_to(self, local_path, user=None, password=None, remote_path=""):
        user = user or self.user
        password = password or self.password
        return scp_to(self.ip, local_path, user=user, password=password,
                      remote_path=remote_path)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        user = user or self.user
        password = password or self.password
        return scp_from(self.ip, remote_path, user=user, password=password,
                        local_path=local_path)

    def update_environment(self):
        """Updates environment for each feature"""
        for feature in self.features:
            feature.update_environment()

    def pre_configure(self):
        """Pre configures node for each feature"""
        for feature in self.features:
            feature.pre_configure()

    def apply_feature(self):
        """Applies each feature"""
        for feature in self.features:
            feature.apply_feature()

    def post_configure(self):
        """Post configures node for each feature"""
        for feature in self.features:
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features"""
        self['in_use'] = ",".join(map(str, self.features))
        self.update_environment()
        self.pre_configure()
        self.apply_feature()
        self.pre_configure()

    def destroy(self):
        raise NotImplementedError

    @classmethod
    def test(cls):
        node = cls("192.168.0.1", "root", "secrete",
                   "precise", "compute", "precise-default",
                   None)
        features = ['nova', 'keystone', 'glance', 'cinder']
        setattr(node, 'features', features)
        print node


class ChefRazorNode(Node):
    """
    A chef entity
    Provides chef related server fuctions
    """
    def __init__(self, name, os, product, environment, deployment, provisioner,
                 branch):
        self.name = name
        self.os = os
        self.run_list = []
        self.product = product
        self.environment = environment
        self.deployment = deployment
        self.razor = provisioner
        self.branch = branch
        self.features = []
        self._cleanups = []

    def __str__(self):
        features = "{0}".format(", ".join(map(str, self.features)))
        node = ("\n\tNode: \n\t\tName: {0}\n\t\tOS: {1}\n\t\t"
                "Product: {2}\n\t\tBranch: {3}\n\t\t"
                "Features: {4}\n").format(self.name,
                                          self.os,
                                          self.product,
                                          self.branch,
                                          features)
        return node

    def apply_feature(self):
        if self.run_list:
            self.run_cmd("chef-client")
        super(ChefRazorNode, self).apply_feature()

    def _password(self):
        try:
            uuid = self['razor_metadata']['razor_active_model_uuid']
        except:
            raise Exception("Couldn't find razor_metadata/password")
        return self.razor.get_active_model_pass(uuid)['password']

    def __getattr__(self, item):
        """
        Gets ip, user, and password from chef
        """
        map = {'ip': self['ipaddress'],
               'user': self['current_user'],
               'password': self._password()}
        if item in map.keys():
            return map[item]
        else:
            return self.__dict__[item]

    def add_run_list_item(self, items):
        self.run_list.extend(items)
        CNode(self.name).run_list = self.run_list

    def __getitem__(self, item):
        """
        Node has access to chef attributes
        """
        return CNode(self.name, api=self.environment.local_api)[item]

    def __setitem__(self, item, value):
        """
        Node can set chef attributes
        """
        lnode = CNode(self.name, api=self.environment.local_api)
        lnode[item] = value
        lnode.save()
        if self.environment.remote_api:
            rnode = CNode(self.name, api=self.environment.remote_api)
            rnode[item] = value
            rnode.save()

    def destroy(self):
        cnode = CNode(self.name)
        if self['in_use'] == "provisioned":
            # Return to pool if the node is clean
            cnode.chef_environment = "_default"
            cnode.save()
        else:
            # Remove active model if the node is dirty
            active_model = cnode['razor_metadata']['razor_active_model_uuid']
            self.razor.remove_active_model(active_model)
            self.run_cmd("reboot 0")
            CClient(self.name).delete()
            cnode.delete()
            sleep(15)

    def add_features(self, features):
        classes = {k.lower(): v for (k, v) in
                   getmembers(node_features, isclass)}
        for feature in features:
            feature_class = classes[feature](self)
            self.features.append(feature_class)
