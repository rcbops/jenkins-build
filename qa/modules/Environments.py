"""
OpenStack Environments
"""


class Environment(dict):

    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __repr__(self):
        """ print current instace of class
        """
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))


class Chef(Environment):

    def __init__(self, name, description, default={}, override={}):
        super(Chef, self).__init__(name, description)
        self.cookbook_versions = {}
        self.json_class = "Chef::Environment"
        self.chef_type = "environment"
        self.default_attributes = default
        self.override_attributes = override
