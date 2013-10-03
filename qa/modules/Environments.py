"""
OpenStack Environments
"""

class Environment(dict):

    def __init__(self, name, description):
        self.name = name
        self.description = description

class Chef(Environment):

    def __init__(self, name, description, default={}, override={}):
        super(Chef, self).__init__(name, description)
        self.cookbook_versions = {}
        self.json_class = "Chef::Environment"
        self.chef_type = "environment"
        self.default_attributes = default
        self.override_attributes = override

    def _add_override_attr(self, key, value):
        self.override_attributes[key] = value

    def _add_default_attr(self, key, value):
        self.default_attributes[key] = value

    def _del_override_attr(self, key, value):
        del self.override_attributes[key]

    def _del_default_attr(self, key, value):
        del self.default_attributes[key]