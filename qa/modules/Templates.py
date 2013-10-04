"""
Templates for OpenStack deployments
"""

from modules.Config import Config


class Template(object):
    def __init__(self, name="default", os="precise", branch="grizzly",
                 features=[], nodes=[]):
        self.name = name
        self.os = os
        self.branch
        self.features = features
        self.nodes = nodes

    def __str__(self):
        return "{0}-{1}-{2}-{3}".format(self.name, self.os, self.branch,
                                        "-".join(self.features))

    @classmethod
    def fromfile(cls, path, name, branch):
        config = Config(path)[name]
        cls(config['name'], config['os'], config['features'])
