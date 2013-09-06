import time
import OS_Roles as Roles
from OSChef import OSChef
from Provisioners import RazorProvisioner
from ConfigManagers import ChefConfigManager
from OSNodes import OSChefNode


class OSDeployment(object):
    def __init__(self, name, features, config=None):
        self.name
        self.features = features
        self.config = config
        self.nodes = []

    def tear_down(self):
        for node in self.nodes:
            node.tear_down()

    def create_node(role):
        raise NotImplementedError

    def provision(self):
        """ Provisions nodes for each desired feature """
        if self.features['openldap']:
            self.create_node(Roles.DirectoryServer)
        if self.features['quantum']:
            self.create_node(Roles.DirectoryServer)
        if self.features['ha']:
            self.create_node(Roles.DirectoryServer)
        for i in xrange(self.config['computes']):
            self.create_node(Roles.Compute)


class ChefRazorOSDeployment(OSDeployment):
    def __init__(self, name, features, chef, razor, config=None):
        super(ChefRazorOSDeployment, self).__init__(name, features, config)
        self.chef = OSChef()
        self.razor = razor

    def create_node(self, role):
        """ Creates a node with chef cm and razor provisioner  """
        node = next(self.chef)
        config_manager = ChefConfigManager(node.name, self.chef,
                                           self.environment)
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

    def searchRole(self, role):
        """ Returns nodes the have the desired role """
        query = "chef_environment:%s AND in_use:%s" % (self.environment, role)
        chef_nodes = (node.name for node in self.chef.node_search(query=query))
        return (osnode for osnode in self.nodes if chef_nodes)

    def provision(self):
        """ Creates remote chef node then provisions roles """
        if self.features['remote_chef']:
            self.create_node(Roles.ChefServer)
        super(ChefRazorOSDeployment, self).provision()
