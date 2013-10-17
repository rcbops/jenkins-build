"""
Base Feature
"""

from modules import util


class Feature(object):
    """ Represents a OpenStack Feature
    """

    def __init__(self, config=None):
        self.config = config

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def __str__(self):
        return self.__class__.__name__

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass


def remove_chef(node):
    """ Removes chef from the given node
    """

    if node.os == "precise":
        commands = ["apt-get remove --purge -y chef",
                    "rm -rf /etc/chef"]
    if node.os in ["centos", "rhel"]:
        commands = ["yum remove -y chef",
                    "rm -rf /etc/chef /var/chef"]

    command = "; ".join(commands)

    return node.run_cmd(command, quiet=True)
