import time
from Provisioners import RazorProvisioner
from ConfigManagers import ChefConfigManager
from OSChef import OSChef
from ssh_helper import run_cmd, scp_to, scp_from


class OSNode:
    def __init__(self, ip, user, password, role,
                 config_manager=None, provisioner=None):
        self.ip = ip
        self.user = user
        self.password = password
        self.provisioner = provisioner
        self.config_manager = config_manager
        self.role = role
        self._cleanups = []

    def run_cmd(self, remote_cmd, user=None, password=None, quiet=False):
        user = user or self.user
        password = password or self.password
        run_cmd(self.ip, remote_cmd=remote_cmd, user=user, password=password,
                quiet=quiet)

    def scp_to(self, local_path, user=None, password=None, remote_path=""):
        user = user or self.user
        password = password or self.password
        scp_to(self.ip, local_path, user=user, password=password,
               remote_path=remote_path)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        user = user or self.user
        password = password or self.password
        scp_from(self.ip, remote_path, user=user, password=password,
                 local_path=local_path)

    def __str__(self):
        return "Node: %s" % self.ip

    def tear_down(self):
        self.clean_up()

    def clean_up(self):
        for cleanup in self._cleanups:
            function, args, kwargs = cleanup
            function(*args, **kwargs)

    def add_cleanup(self, function, *args, **kwargs):
        self._cleanups.append((function, args, kwargs))


class OSDeployment:
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
        self.create_node(role)


class ChefRazorOSDeployment(OSDeployment):
    def __init__(self, name, features, chef, razor, config=None):
        super(ChefRazorOSDeployment, self).__init__(name, features, config)
        self.chef = OSChef()
        self.razor = razor
        env = self.chef.prepare_environment(self.name, self.config['os'],
                                            self.config['cookbook-branch'],
                                            self.features)
        self.environment = env

    def create_node(self, role):
        node = next(self.chef)
        config_manager = ChefConfigManager(node.name, self.chef,
                                           self.environment)
        am_id = node.attributes['razor_metadata']['razor_active_model_uuid']
        provisioner = RazorProvisioner(self.razor, am_id)
        password = provisioner.get_password()
        ip = node['ipaddress']
        user = "root"
        osnode = OSNode(ip, user, password, role, config_manager, provisioner)
        osnode.add_cleanup(osnode.run_cmd("reboot 0"))
        osnode.add_cleanup(time.sleep(15))
        self.nodes.append(osnode)
        return osnode

    def searchRole(self, role):
        query = "chef_environment:%s AND in_use:%s" % (self.environment, role)
        return self.chef.node_search(query=query)
