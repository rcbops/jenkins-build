"""
A Deployment Features
"""
import time
from modules import util
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
        self.commands

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        return outl

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__class__.__name__.lower(), self.environment)

    def post_configure(self):
        build_rings = bool(self.config['swift']['auto_build_rings'])
        self._build_rings(build_rings)

    def _build_rings(self, auto=False):
        """ This will either build the rings or 
            print how to build the rings.
        """

        # Gather all the nodes
        controller = self.deployment.search_role('controller')
        proxy_nodes = self.deployment.search_role('proxy')
        storage_nodes = self.deployment.search_role('storage')
        
        #####################################################################
        ################## Run chef on the controller node ##################
        #####################################################################

        controller.run_cmd('chef-client')

        #####################################################################
        ####### Run through the storage nodes and set up the disks ##########
        #####################################################################

        # Build Swift Rings
        disk = self.config['swift']['disk']
        label = self.config['swift']['disk_label']
        for storage_node in storage_nodes:
            commands = ["/usr/local/bin/swift-partition.sh {0}".format(disk),
                        "/usr/local/bin/swift-format.sh {0}".format(label),
                        "mkdir -p /srv/node/{0}".format(label),
                        "mount -t xfs -o noatime,nodiratime,logbufs=8 "
                        "/dev/{0} /srv/node/{0}".format(label),
                        "chown -R swift:swift /srv/node"]
            if auto:
                print "#" * 30
                print "## Configuring Disks on Storage Node @ {0} ##".format(
                    storage_node['ip'])
                print "#" * 30
                command = "; ".join(commands)
                storage_node.run_cmd(command)
            else:
                print "#" * 30
                print "##### Info to setup drives for Swift #####"
                print "#" * 30
                print "## Log into root@{0} and run the "\
                      "following commands: ##".format(storage_node.ipaddress)
                for command in commands:
                    print command
        
        ####################################################################
        ## Setup partitions on storage nodes, (must run as swiftops user) ##
        ####################################################################
        num_rings = self.config['swift']['num_rings']
        part_power = self.config['swift']['part_power']
        replicas = self.config['swift']['replicas']
        min_part_hours = self.config['swift']['min_part_hours']
        disk_weight = self.config['swift']['disk_weight']

        commands = ["su swiftops",
                    "mkdir -p ~/swift/rings",
                    "cd ~/swift/rings",
                    "git init .",
                    "echo \"backups\" > .gitignore",
                    "swift-ring-builder object.builder create "
                    "{0} {1} {2}".format(part_power,
                                         replicas,
                                         min_part_hours),
                    "swift-ring-builder container.builder create "
                    "{0} {1} {2}".format(part_power,
                                         replicas,
                                         min_part_hours),
                    "swift-ring-builder account.builder create "
                    "{0} {1} {2}".format(part_power,
                                         replicas,
                                         min_part_hours)]

        # Determine how many storage nodes wehave and add them
        builders = self.config['swift']['builders']

        for builder in builders:
            name = builder
            port = builders[builder]['port']
            for index, node in enumerate(storage_nodes):

                # if the current index of the node is % num_rings = 0,
                # reset num so we dont add anymore rings past num_rings
                if index % num_rings is 0:
                    num = 0

                # Add the line to command to build the object
                commands.append("swift-ring-builder {0}.builder add "
                                "z{1}-{2}:{3}/{4} {5}".format(name,
                                                              num + 1,
                                                              node.ipaddress,
                                                              port,
                                                              label,
                                                              disk_weight))
                num += 1

        # Finish the command list
        cmd_list = ["swift-ring-builder object.builder rebalance",
                    "swift-ring-builder container.builder rebalance",
                    "swift-ring-builder account.builder rebalance",
                    "git remote add origin /srv/git/rings",
                    "git add .",
                    "git config user.email \"swiftops@swiftops.com\"",
                    "git config user.name \"swiftops\"",
                    "git commit -m \"initial checkin\"",
                    "git push origin master"]
        commands.extend(cmd_list)

        if auto:
            print "#" * 30
            print "## Setting up swift rings for deployment ##"
            print "#" * 30

            command = "; ".join(commands)
            controller.run_cmd(command)
        else:
            print "#" * 30
            print "## Info to manually set up swift rings: ##"
            print "## Log into root@{0} "\
                  "and run the following commands: ##".format(controller.ipaddress)
            for command in commands:
                print command

        ######################################################################################
        ################## Time to distribute the ring to all the boxes ######################
        ######################################################################################
        
        command = "/usr/local/bin/pull-rings.sh"

        print "#" * 30
        print "## PULL RING ONTO MANAGEMENT NODE ##"
        if auto:
            print "## Pulling Swift ring on Management Node ##"
            controller.run_cmd(command)
        else:
            print "## On node root@{0} "\
                  "and run the following command: ##".format(
                    controller.ipaddress)
            print command

        print "#" * 30
        print "## PULL RING ONTO PROXY NODES ##"
        for proxy_node in proxy_nodes:
            if auto:
                print "## Pulling swift ring down on proxy node @ {0}: ##".format(
                    proxy_node.ipaddress)
                proxy_node.run_cmd(command)
            else:
                print "## On node root@{0} "\
                      "and run the following command: ##".format(
                        proxy_node.ipaddress)
                print command

        print "#" * 30
        print "## PULL RING ONTO STORAGE NODES ##"
        for storage_node in storage_nodes:
            if auto:
                print "## Pulling swift ring down storage node: {0} ##".format(
                    storage_node.ipaddress)
                storage_node.run_cmd(command)
            else:
                print "## On node root@{0} "\
                      "and run the following command: ##".format(
                        storage_node.ipaddress)
                print command

        print "#" * 30
        print "## Done setting up swift rings ##"


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
