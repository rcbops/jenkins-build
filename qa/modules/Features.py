"""
OpenStack Features
"""

from Config import Config

class Feature(object):
    """ Represents a OpenStack Feature
    """

    def __init__(self):
        self.config = Config()
    
    def __repr__(self):
        """ print current instace of class
        """
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
        return outl

    def update_environment(self):
        raise NotImplementedError

    def pre_configure(self):
        raise NotImplementedError

    def apply_feature(self):
        raise NotImplementedError

    def post_configure(self):
        raise NotImplementedError

    def _remove_chef(self):
        raise NotImplementedError

class ChefServer(Feature):
    """ Represents a chef server
    """

    def __init__(self):
        super(ChefServer, self).__init__()
        self.iscript = self.config['chef']['server']['install_script']
        self.iscript_name = self.iscript.split('/')[-1]
        self.install_commands = ['curl {0} >> {1}'.format(
                                    self.iscript,
                                    self.iscript_name),
                                 'chmod u+x ~/{0}'.format(self.iscript_name),
                                 './{0}'.format(self.iscript_name)
                                ]

    def pre_configure(self):
        self._remove_chef()

    def apply_feature(self):
        self._install()
    
    def post_configure(self):
        self._install_cookbooks()

    def _install(self):
        raise NotImplementedError

    def _install_cookbooks(self):
        raise NotImplementedError

class HighAvailability(Feature):
    """ Represents a highly available cluster
    """

    def __init__(self, number):
        super(HighAvailability, self).__init__()
        self.number = number
        self.environment = self.config['environments']['ha']

    def update_environment(self):
        raise NotImplementedError

    def pre_configure(self):
        raise NotImplementedError

    def apply_feature(self):
        raise NotImplementedError
    
    def post_configure(self):
        raise NotImplementedError


class Neutron(Feature):
    """ Represents a neutron network cluster
    """

    def __init__(self):
        super(Neutron, self).__init__()
        self.environment = self.config['environments']['neutron']

    def update_environment(self):
        raise NotImplementedError

    def pre_configure(self):
        raise NotImplementedError

    def apply_feature(self):
        raise NotImplementedError
    
    def post_configure(self):
        raise NotImplementedError


class OpenLDAP(Feature):
    """ Represents a keystone with an openldap backend
    """

    def __init__(self):
        super(OpenLDAP, self).__init__()
        self.environment = self.config['environment']['ldap']
        self.ldapadd_cmd = 'ldapadd -x -D "cn=admin,dc=rcb,dc=me -wostackdemo -f /root/base.ldif'

    def update_environment(self):
        raise NotImplementedError

    def pre_configure(self):
        raise NotImplementedError

    def apply_feature(self):
        raise NotImplementedError
    
    def post_configure(self):
        self._ldap_add()

    def _ldap_add(self):
        raise NotImplementedError


class GlanceCF(Feature):
    """ Represents a glance with cloud files backend
    """

    def __init__(self):
        super(GlanceCF, self).__init__()
        self.environment = self.config['environment']['glance']

    def update_environment(self):
        raise NotImplementedError

    def pre_configure(self):
        raise NotImplementedError

    def apply_feature(self):
        raise NotImplementedError
    
    def post_configure(self):
        raise NotImplementedError


class Swift(Feature):
    """ Represents a block storage cluster enabled by swift
    """

    def __init__(self):
        super(Swift, self).__init__()
        self.environment = self.config['environment']['swift']

    def update_environment(self):
        raise NotImplementedError

    def pre_configure(self):
        raise NotImplementedError

    def apply_feature(self):
        raise NotImplementedError
    
    def post_configure(self):
        raise NotImplementedError
