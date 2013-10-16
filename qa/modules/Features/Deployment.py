"""
A Deployment Features
"""
import time
import logging
from Feature import Feature


class Deployment(Feature):
    """ Represents a feature across a deployment
    """

    def __init__(self, deployment):
        super(Deployment, self).__init__(deployment.config)
        self.deployment = deployment

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass


#############################################################################
############################ OpenStack Features #############################
#############################################################################

class OpenStack(Deployment):
    """ Represents a Rackspace Private Cloud Software Feature
    """

    def __init__(self, deployment):
        super(OpenStack, self).__init__(deployment)

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl


class Neutron(Deployment):
    """ Represents a neutron network cluster
    """

    def __init__(self, deployment, rpcs_feature):
        super(Neutron, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__class__.__name__.lower()][
                rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)

    def post_configure(self):
        """ Runs cluster post configure commands
        """
        if self.deployment.os in ['centos', 'rhel']:
            self._reboot_cluster()

    def _reboot_cluster(self):
        
        # reboot the deployment
        self.deployment.reboot_deployment()

        # Sleep for 20 seconds to let the deployment reboot
        time.sleep(20)

        # Keep sleeping till the deployment comes back
        # Max at 8 minutes
        sleep_in_minutes = 5
        total_sleep_time = 0
        while not self.deployment.is_online():
            print "## Current Deployment is Offline ##"
            print "## Sleeping for {0} minutes ##".format(
                str(sleep_in_minutes))
            time.sleep(sleep_in_minutes * 60)
            total_sleep_time += sleep_in_minutes
            sleep_in_minutes -= 1

            # if we run out of time to wait, exit
            if sleep_in_minutes == 0:
                error = ("## -- Failed to reboot deployment"
                         "after {0} minutes -- ##".format(total_sleep_time))
                raise Exception(error)


class Swift(Deployment):
    """ Represents a block storage cluster enabled by swift
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Swift, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__class__.__name__.lower()][
                rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)

    def post_configure(self):

        # Run chef on the controller node
        controller = self.deployment.search_role('controller')
        controller.run_cmd('chef-client')

        # Build Swift Rings
        disk = self.config['disks']['disk']
        disk_label = self.config['disks']['disk_label']


class Glance(Deployment):
    """ Represents a glance with cloud files backend
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Glance, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__class__.__name__.lower()][
                rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)


class Keystone(Deployment):
    """ Represents the keystone feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Keystone, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__class__.__name__.lower()][
                rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)


class Nova(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Nova, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__class__.__name__.lower()][
                rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)


class Horizon(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Horizon, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__class__.__name__.lower()][
                rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)


class Cinder(Deployment):
    """ Represents the Cinder feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Cinder, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__class__.__name__.lower()][
                rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)


#############################################################################
############### Rackspace Private Cloud Software Features ###################
#############################################################################

class RPCS(Deployment):
    """ Represents a Rackspace Private Cloud Software Feature
    """

    def __init__(self, deployment, name):
        super(RPCS, self).__init__(deployment)
        self.name = name

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        pass


class Monitoring(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment,
                                         self.__class__.__name__.lower())
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)


class MySql(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment,
                                         self.__class__.__name__.lower())
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class OsOps(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(OsOps, self).__init__(deployment,
                                    self.__class__.__name__.lower())
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class DeveloperMode(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(DeveloperMode, self).__init__(deployment, 'developer_mode')
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class OsOpsNetworks(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(OsOpsNetworks, self).__init__(deployment, 'osops_networks')
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class HighAvailability(RPCS):
    """ Represents a highly available cluster
    """

    def __init__(self, deployment):
        super(HighAvailability, self).__init__(deployment, 'ha')
        self.environment = \
            self.config['environments'][self.name][deployment.os]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(self.name,
                                                      self.environment)


class LDAP(RPCS):
    """ Represents a keystone with an openldap backend
    """

    def __init__(self, deployment):
        super(LDAP, self).__init__(deployment,
                                   self.__class__.__name__.lower())
        self.environment = \
            self.config['environments'][self.name]

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)
