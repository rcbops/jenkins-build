"""
Private Cloud OpenStack Features
"""

from chef import ChefAPI


class Feature(object):
    """ Represents a OpenStack Feature
    """

    def __init__(self, config=None):
        self.config = config

    def __repr__(self):
        """ print current instace of class
        """
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
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
############################ Node Features ##################################
#############################################################################

class Node(Feature):
    """ Represents a feature on a node
    """

    def __init__(self, node):
        super(Node, self).__init__(node.deployment.config)
        self.node = node

    def run_chef_client(self):
        """ Runs chef-client on the given node
        """

        return self.node.run_cmd('chef-client', quiet=True)

    def set_run_list(self):
        """ Sets the nodes run list based on the Feature
        """
        run_list = self.config['rcbops'][self.node.product]\
                              [self.__name__.lower()]['run_list']
        self.node['run_list'].extend(run_list)


class Controller(Node):
    """ Represents a RPCS Controller
    """

    def __init__(self, node):
        super(Controller, self).__init__(node)

    def update_environment(self):
        pass

    def apply_feature(self):
        self.set_run_list()
        self.run_chef_client()

    def _apply_keystone(self, feature):
        pass


class Compute(Node):
    """ Represents a RPCS compute
    """

    def __init__(self, node):
        super(Compute, self).__init__(node)

    def apply_feature(self):
        self.set_run_list()
        self.run_chef_client()


class Proxy(Node):
    """ Represents a RPCS proxy node
    """

    def __init__(self, node):
        super(Proxy, self).__init__(node)

    def apply_feature(self):
        self.set_run_list()
        self.run_chef_client()


class ObjectStore(Node):
    """ Represents a RPCS object store node
    """

    def __init__(self, node):
        super(ObjectStore).__init__(node)

    def apply_feature(self):
        self.set_run_list()
        self.run_chef_client()


class ChefServer(Node):
    """ Represents a chef server
    """

    def __init__(self, node):
        super(ChefServer, self).__init__(node)
        self.iscript = self.config['chef']['server']['install_script']
        self.iscript_name = self.iscript.split('/')[-1]
        self.install_commands = ['curl {0} >> {1}'.format(self.iscript,
                                                          self.iscript_name),
                                 'chmod u+x ~/{0}'.format(self.iscript_name),
                                 './{0}'.format(self.iscript_name)]

    def pre_configure(self):
        self.remove_chef()

    def apply_feature(self):
        self._install()
        self._install_cookbooks()
        self.set_up_remote()

    def post_configure(self):
        pass

    def _install(self):
        """ Installs chef server on the given node
        """

        command = self.install_commands.join("; ")
        self.node.run_cmd(command)

    def _install_cookbooks(self):
        """ Installs cookbooks
        """

        cookbook_url = self.config['rcbops'][self.node.product]['git']['url']
        cookbook_branch = self.node.branch
        cookbook_name = cookbook_url.split("/")[-1].split(".")[0]
        install_dir = self.config['chef']['server']['install_dir']

        commands = ["mkdir -p {0}".format(install_dir),
                    "cd {0}".format(install_dir),
                    "git clone {0} --recursive".format(cookbook_url),
                    "cd {0}/cookbooks".format(cookbook_url),
                    "git checkout {0}".format(cookbook_branch)]

        if 'cookbooks' in cookbook_name:
             # add submodule stuff to list
            commands.append('cd /opt/rcbops/chef-cookbooks')
            commands.append('git submodule init')
            commands.append('git submodule sync')
            commands.append('git submodule update')
            commands.append('knife cookbook upload --all --cookbook-path'
                            '{0}/{1}/cookbooks'.format(install_dir,
                                                       cookbook_name))
        else:
            commands.append('knife cookbook upload --all'
                            ' --cookbook-path {0}/{1}'.format(install_dir,
                                                              cookbook_name))

        commands.append('knife role from file {0}/{1}/roles/*.rb'.format(
            install_dir, cookbook_name))

        command = commands.join("; ")

        return self.node.run_cmd(command)

    def _set_up_remote(self):
        """ Sets up and saves a remote api and dict to the nodes
            environment
        """

        remote_chef = {
            "client": "admin",
            "key": self._get_admin_pem(self.node),
            "url": "https://{0}:4443".format(self.node.ip)
        }

        # set the remote chef server name
        setattr(self.node.environment.chef_server_name,
                self.node.name)

        # save the remote dict
        self.node.environment.add_override_attr('remote_chef', remote_chef)

        # set the remote api
        setattr(self.node.environment.remote_api,
                self._set_remote_chef_api(remote_chef))

    def _remote_chef_api(self, chef_api_dict):
        """ Builds a remote chef API object
        """

        return ChefAPI(**chef_api_dict)

    def _get_admin_pem(self):
        """ Gets the admin pem from the chef server
        """

        command = 'cat ~/.chef/admin.pem'
        return self.node.run_cmd(command)['return']


class Remote(Node):
    """ Represents the deployment having a remote chef server
    """

    def __init__(self, node):
        super(Remote, self).__init__(node)

    def apply_feature(self):
        self._remove_chef()
        self._bootstrap_chef()

    def _remove_chef(self):
        """ Removes chef from the given node
        """

        if self.node.os == "precise":
            commands = ["apt-get remove --purge -y chef",
                        "rm -rf /etc/chef"]
        if self.node.os in ["centos", "rhel"]:
            commands = ["yum remove -y chef",
                        "rm -rf /etc/chef /var/chef"]

        command = commands.join("; ")

        return self.node.run_cmd(command, quiet=True)

    def _bootstrap_chef(self):
        """ Bootstraps the node to a chef server
        """

        # I need the ability to get a node instance based on name
        # I think deployments need to have a list of all the nodes
        # in the deployment so i can search through them for my
        # chef server node obkect so i can use its run_cmd

        # Gather the info for the chef server
        chef_server_node = self.node.deployment.nodes['chef_server']

        command = 'knife bootstrap {0} -s root -p {1}'.format(
            chef_server_node.ip, self.node.password)

        chef_server_node.run_cmd(command)


class Cinder(Node):
    """
    Enables cinder with local lvm backend
    """

    def __init__(self, node, location):
        super(Cinder, self).__init__(node)
        self.location = location
        self.name = 'cinder-{0}'.format(location)

    def pre_configure(self):
        self.prepare_cinder()
        self.set_run_list()

    def prepare_cinder(self):
        """ Prepares the node for use with cinder
        """

        # Clean up any VG errors
        commands = ["vg=`pvdisplay | grep unknown -A 1 | grep VG | "
                    "awk '{print $3}'`",
                    "for i in `lvdisplay | grep 'LV Name' | grep $vg "
                    "| awk '{print $3}'`; do lvremove $i; done",
                    "vgreduce $vg --removemissing"]
        command = commands.join("; ")
        self.node.run_cmd(command)

        # Gather the created volume group for cinder
        command = "vgdisplay 2> /dev/null | grep pool | awk '{print $3}'"
        ret = self.node.run_cmd(command)
        volume_group = ret['return'].replace("\n", "").replace("\r", "")

        # Update our environment
        env = self.node.environment
        cinder = {
            "storage": {
                "lvm": {
                    "volume_group": volume_group
                }
            }
        }
        env.add_override_attr("cinder", cinder)


#############################################################################
######################### Deployment Features ###############################
#############################################################################


class Deployment(Feature):
    """ Represents a feature across a deployment
    """

    def __init__(self, deployment):
        super(Deployment, self).__init__(deployment.config)
        self.deployment = deployment

    def update_environment(self):
        pass


#############################################################################
############################ OpenStack Features #############################
#############################################################################

class OpenStack(Deployment):
    """ Represents a Rackspace Private Cloud Software Feature
    """

    def __init__(self, deployment):
        super(OpenStack, self).__init__(deployment)

    def update_environment(self):
        pass

class Neutron(Deployment):
    """ Represents a neutron network cluster
    """

    def __init__(self, deployment, rpcs_feature):
        super(Neutron, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__name__.lower()][rpcs_feature]

    def update_environment(self):
        self.node.environment.add_override_attr('neutron', self.environment)


class Swift(Deployment):
    """ Represents a block storage cluster enabled by swift
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Swift, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__name__.lower()][rpcs_feature]

    def update_environment(self):
        self.node.environment.add_override_attr(
            self.__name__.lower(), self.environment)


class Glance(Deployment):
    """ Represents a glance with cloud files backend
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Glance, self).__init__(deployment)
        self.environment = \
            self.config['environment'][self.__name__.lower()][rpcs_feature]

    def update_environment(self):
        self.node.environment.add_override_attr(
            self.__name__.lower(), self.environment)


class Keystone(Deployment):
    """ Represents the keystone feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Keystone, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__name__.lower()][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__name__.lower(), self.environment)


class Nova(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__name__.lower()][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__name__.lower(), self.environment)


class Horizon(Deployment):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment)
        self.environment = \
            self.config['environments'][self.__name__.lower()][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__name__.lower(), self.environment)


#############################################################################
############### Rackspace Private Cloud Software Features ###################
#############################################################################

class RPCS(Deployment):
    """ Represents a Rackspace Private Cloud Software Feature
    """

    def __init__(self, deployment, name):
        super(RPCS, self).__init__(deployment)
        self.name = name

    def update_environment(self):
        pass

class Monitoring(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment,
                                         self.__name__.lower())
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.__name__.lower(), self.environment)

class MySql(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment,
                                         self.__name__.lower())
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class OsOps(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment,
                                         self.__name__.lower())
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class DeveloperMode(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment, 'developer_mode')
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)


class OsOpsNetworks(RPCS):
    """ Represents the monitoring feature
    """

    def __init__(self, deployment, rpcs_feature='default'):
        super(Monitoring, self).__init__(deployment, 'osops_networks')
        self.environment = \
            self.config['environments'][self.name][rpcs_feature]

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

    def update_environment(self):
        self.node.environment.add_override_attr(self.name, self.environment)


class LDAP(RPCS):
    """ Represents a keystone with an openldap backend
    """

    def __init__(self, deployment):
        super(LDAP, self).__init__(deployment,
                                   self.__name__.lower())
        self.environment = \
            self.config['environments'][self.name]

    def update_environment(self):
        self.deployment.environment.add_override_attr(
            self.name, self.environment)