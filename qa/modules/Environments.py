"""
OpenStack Environments
"""

from modules import util
from chef import Environment as ChefEnvironment


class Environment(dict):

    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
        return outl


class Chef(Environment):

    def __init__(self, name, local_api, chef_server_name=None, remote_api=None,
                 description=None, default={}, override={}):
        super(Chef, self).__init__(name, description)
        self.cookbook_versions = {}
        self.json_class = "Chef::Environment"
        self.chef_type = "environment"
        self.default_attributes = default
        self.override_attributes = override
        self.local_api = local_api
        self.remote_api = remote_api
        self.chef_server_name = chef_server_name
        self.save()

    def add_override_attr(self, key, value):
        self.override_attributes[key] = value
        self.save()

    def add_default_attr(self, key, value):
        self.default_attributes[key] = value
        self.save()

    def del_override_attr(self, key, value):
        del self.override_attributes[key]
        self.save()

    def del_default_attr(self, key, value):
        del self.default_attributes[key]
        self.save()

    def save(self):
        env = ChefEnvironment(self.name, api=self.local_api)
        env.attributes = self.__dict__

        # THE ABOVE DOESN'T WORK, DOESN'T ACTUALLY SEND ATTRIBUTES
        env.override_attributes = self.override_attributes

        env.save(self.local_api)
        if self.remote_api:
            env.save(self.remote_api)

    def destroy(self):
        ChefEnvironment(self.name).delete()
