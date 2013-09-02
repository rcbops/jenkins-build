import sys
import time
import OS_Roles as Roles
from OSChef import OSChef
from Provisioners import RazorProvisioner
from ConfigManagers import ChefConfigManager
from ssh_helper import run_cmd, scp_to, scp_from


class OSNode(object):
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


class OSChefNode(OSNode):
    def __init__(self, ip, user, password, role,
                 config_manager=None, provisioner=None):
        super(OSChefNode, self).__init__(ip, user, password, role,
                                         config_manager=None, provisioner=None)

    def install_chef_server(self):
        install_script = '/var/lib/jenkins/jenkins-build/qa/v1/bash/jenkins/install-chef-server.sh'

        # SCP install script to chef_server node
        scp_run = self.scp_to(install_script)

        if scp_run['success']:
            print "Sent chef server install to %s" % self
        else:
            print "Failed send chef server install to %s" % self
            sys.exit(1)

        # Run the install script
        cmds = ['chmod u+x ~/install-chef-server.sh',
                './install-chef-server.sh']
        for cmd in cmds:
            ssh_run = self.run_cmd(cmd)
            if ssh_run['success']:
                print "Installed Chef Server on %s" % self
        self.install_cookbook(url, branch)

    def install_cookbook(self, url, branch, local_repo='/opt/rcbops'):
        '''
        @summary: Install cookbooks
        @param url git url of cookbook
        @type url String
        @param branch git branch of cookbook
        @type branch String
        @param local_repo Location to place cookbooks
        @type String
        '''
        # Make directory that the cookbooks will live in
        command = 'mkdir -p {0}'.format(local_repo)
        self.run_cmd(command)

        # Pulling the url apart to get the name of the cookbooks
        cookbook_name = url.split("/")[-1].split(".")[0]

        # clone to cookbook
        commands = ['cd {0}; git clone {1}'.format(local_repo, url)]
        commands.append('cd {0}/{1}; git checkout {2}'.format(local_repo,
                                                              cookbook_name,
                                                              branch))

        commands.append('cd {0}/{1}; '
                        'git submodule init; '
                        'git submodule sync; '
                        'git submodule update'.format(local_repo,
                                                      cookbook_name))
        cookbook_path = '{0}/{1}/cookbooks'.format(local_repo, cookbook_name)
        upload = 'knife cookbook upload --all --cookbook-path {0}'.format(cookbook_path)
        commands.append(upload)

        # Append role load to run list
        role_path = '{0}/{1}/roles/*.rb'.format(local_repo, cookbook_name)
        commands.append('knife role from file {0}'.format(role_path))
        command = "; ".join(commands)

        self.run_cmd(command)


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
        query = "chef_environment:%s AND in_use:%s" % (self.environment, role)
        return self.chef.node_search(query=query)

    def provision(self):
        if self.features['remote_chef']:
            self.create_node(Roles.ChefServer)
        super(ChefRazorOSDeployment, self).provision()
