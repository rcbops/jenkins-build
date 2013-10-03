"""
OpenStack deployments
"""


class Deployment(object):
    """Base for OpenStack deployments"""
    def __init__(self, name, os, branch, features):
        self.name = name
        self.os = os
        self.features = features
        self.nodes = []

    def __iter__(self):
        return self.nodes

    def destroy(self):
        """ Destroys an OpenStack deployment """
        for node in self.nodes:
            node.destroy()

    def create_node(self, role):
        """ Abstract node creation method """
        raise NotImplementedError

    def provision(self):
        """Provisions nodes for each desired feature"""
        if self.features['openldap']:
            self.create_node(Roles.DirectoryServer)
        if self.features['quantum']:
            self.create_node(Roles.DirectoryServer)
        if self.features['ha']:
            self.create_node(Roles.DirectoryServer)
        for _ in xrange(config['computes']):
            self.create_node(Roles.Compute)


class ChefRazorOSDeployment(OSDeployment):
    """
    Deployment mechinisms specific to deployment using:
    Puppet's Razor as provisioner and
    Opscode's Chef as configuration management
    """
    def __init__(self, name, os, branch, features, chef, razor):
        super(ChefRazorOSDeployment, self).__init__(name, os, branch, features)
        self.chef = chef
        self.razor = razor
        self.environment = None

    def create_node(self, role):
        """Creates a node with chef cm and razor provisioner"""
        node = self.chef.free_node(self.os)
        config_manager = ChefConfigManager(node.name, self.chef,
                                           self.features)
        config_manager.set_in_use()
        am_id = node.attributes['razor_metadata']['razor_active_model_uuid']
        provisioner = RazorProvisioner(self.razor, am_id)
        password = provisioner.get_password()
        ip = node['ipaddress']
        user = "root"
        osnode = OSChefNode(ip, user, password, role, config_manager,
                            provisioner)
        osnode.add_cleanup(osnode.run_cmd("reboot 0"))
        osnode.add_cleanup(time.sleep(15))
        self.nodes.append(osnode)
        return osnode

    def search_role(self, role):
        """Returns nodes the have the desired role"""
        query = "chef_environment:%s AND in_use:%s" % (self.environment, role)
        chef_nodes = (node.name for node in self.chef.node_search(query=query))
        return (osnode for osnode in self.nodes if chef_nodes)

    def provision(self):
        """Creates remote chef node then provisions roles"""
        self.environment = self.chef.prepare_environment(self.name,
                                                         self.os,
                                                         self.os_version,
                                                         self.features)
        if self.features['remote_chef']:
            self.create_node(Roles.ChefServer)
        super(ChefRazorOSDeployment, self).provision()

    def destroy(self):
        super(ChefRazorOSDeployment, self).destroy()
        self.chef.destroy_environment(self.environment)
