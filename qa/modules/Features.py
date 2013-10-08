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


class Node(Feature):
    """ Represents a feature on a node
    """

    def __init__(self, node):
        super(Node, self).__init__(node.config)
        self.node = node

    def remove_chef(self):
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

    def run_chef_client(self):
        """ Runs chef-client on the given node
        """

        return self.node.run_cmd('chef-client', quiet=True)

    def set_run_list(self):
        """ Sets the nodes run list based on the Feature
        """
        run_list = self.config['rcbops'][self.node.product][self.__name__.lower()][
            'run_list']
        self.node['run_list'].extend(run_list)


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
        self.node.environment._add_override_attr('remote_chef', remote_chef)

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

    def pre_configure(self):
        pass

    def apply_feature(self):
        self.remove_chef()
        self._bootstrap_chef()

    def post_configure(self, deployment):
        pass

    def _bootstrap_chef(self):
        """ Bootstraps the node to a chef server
        """

        # I need the ability to get a node instance based on name
        # I think deployments need to have a list of all the nodes
        # in the deployment so i can search through them for my
        # chef server node obkect so i can use its run_cmd

        # Gather the info for the chef server
        chef_server_node = self.node.deployment.nodes['chef_server']

        command = 'knife bootstrap {0} -s root -p {1}'.format(chef_server_node.ip,
                                                              self.node.password)

        chef_server_node.run_cmd(command)


class CinderLocal(Node):
    """
    Enables cinder with local lvm backend
    """

    def __init__(self, node):
        super(CinderLocal, self).__init__(node)

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
        env._add_override_attr("cinder", cinder)


class Deployment(Feature):
    """ Represents a feature across a deployment
    """

    def __init__(self, deployment):
        super(Deployment, self).__init__(deployment.config)
        self.deployment = deployment


class HighAvailability(Deployment):
    """ Represents a highly available cluster
    """

    def __init__(self, deployment):
        super(HighAvailability, self).__init__(deployment)
        self.environment = self.config['environments']['ha'][deployment.os]

    def update_environment(self):
        self.node.environment._add_override_attr('ha', self.environment)


class Neutron(Deployment):
    """ Represents a neutron network cluster
    """

    def __init__(self, deployment):
        super(Neutron, self).__init__(deployment)
        self.environment = self.config['environments']['neutron']

    def update_environment(self):
        self.node.environment._add_override_attr('neutron', self.environment)


class Swift(Deployment):
    """ Represents a block storage cluster enabled by swift
    """

    def __init__(self, deployment):
        super(Swift, self).__init__(deployment)
        self.environment = self.config['environment']['swift']

    def update_environment(self):
        self.node.environment._add_override_attr('swift', self.environment)


class GlanceCF(Deployment):
    """ Represents a glance with cloud files backend
    """

    def __init__(self, deployment):
        super(GlanceCF, self).__init__(deployment)
        self.environment = self.config['environment']['glance']

    def update_environment(self):
        self.node.environment._add_override_attr('glance', self.environment)


class OpenLDAP(Deployment):
    """ Represents a keystone with an openldap backend
    """

    def __init__(self, deployment):
        super(OpenLDAP, self).__init__(deployment)
        self.environment = self.config['environment']['ldap']

    def update_environment(self):
        self.node.environment._add_override_attr('ldap', self.environment)
