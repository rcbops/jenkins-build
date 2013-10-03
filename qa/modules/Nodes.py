from server_helper import ssh_cmd, scp_to, scp_from


class Node(object):
    """
    A individual computation entity to deploy a part OpenStack onto
    Provides server related functions
    """
    def __init__(self, ip, user, password, os, features=[]):
        self.ip = ip
        self.user = user
        self.password = password
        self.os = os
        self.features = features
        self._cleanups = []

    def run_cmd(self, remote_cmd, user=None, password=None, quiet=False):
        user = user or self.user
        password = password or self.password
        ssh_cmd(self.ip, remote_cmd=remote_cmd, user=user, password=password,
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

    def update_environment(self):
        """Updates environment for each feature"""
        (feature.update_environment() for feature in self.features)

    def pre_configure(self):
        """Pre configures node for each feature"""
        (feature.pre_configure() for feature in self.features)

    def apply_feature(self):
        """Applies each feature"""
        (feature.apply_feature() for feature in self.features)

    def post_configure(self):
        """Post configures node for each feature"""
        (feature.post_configure() for feature in self.features)

    def build(self):
        """Runs build steps for node's features"""
        self.update_environment()
        self.pre_configure()
        self.apply_feature()
        self.pre_configure()

    def __str__(self):
        return "Node: %s" % self.ip

    def destroy(self):
        raise NotImplementedError

    def clean_up(self):
        for cleanup in self._cleanups:
            function, args, kwargs = cleanup
            function(*args, **kwargs)

    def add_cleanup(self, function, *args, **kwargs):
        self._cleanups.append((function, args, kwargs))


class ChefNode(Node):
    """
    A chef entity
    Provides chef related server fuctions
    """
    def __init__(self, name, os, api, qa, branch, features=[]):
        self.name = name
        self.os = os
        self.api = api
        self.qa = qa
        self.branch = branch
        self.features = features
        self._cleanups = []

    def __getattr__(self, item):
        """
        Gets ip, user, and password from provisioners
        """
        map = {'ip': Node(self.name)['ipaddress'],
               'user': Node(self.name)['current_user'],
               'password': self.qa.razor_password(self.name)}
        if item in map.keys():
            return map[item]
        else:
            return self.__dict__[item]

    def install_chef_server(self):
        """
        Installs a chef server onto node
        """
        cmd = 'curl {0} | bash'.format(self.qa.config['chef']['server_script'])
        ssh_run = self.run_cmd(cmd)
        if ssh_run['success']:
            print "Installed Chef Server on %s" % self
        self.install_cookbooks(self.qa.config['rcbops']['git']['url'],
                               self.branch)

    def install_cookbooks(self, url, branch, local_repo='/opt/rcbops'):
        '''
        Install cookbooks onto chef server
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
        upload = ('knife cookbook upload --all '
                  '--cookbook-path {0}'.format(cookbook_path))
        commands.append(upload)

        # Append role load to run list
        role_path = '{0}/{1}/roles/*.rb'.format(local_repo, cookbook_name)
        commands.append('knife role from file {0}'.format(role_path))
        command = "; ".join(commands)

        self.run_cmd(command)
