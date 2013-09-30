import sys
from chef import Environment, Node

def update_openldap_environment(self, env):
        chef_env = Environment(env, api=self.chef)
        query = 'chef_environment:%s AND run_list:*qa-openldap*' % env
        ldap_name = list(self.node_search(query))
        if ldap_name:
            ldap_ip = ldap_name[0]['ipaddress']
            chef_env.override_attributes['keystone']['ldap']['url'] = "ldap://%s" % ldap_ip
            chef_env.override_attributes['keystone']['ldap']['password'] = 'ostackdemo'
            chef_env.save()
            print "Successfully updated openldap into environment!"
        else:
            raise Exception("Couldn't find ldap server: %s" % ldap_name)

def build_chef_server(self, chef_node=None, cookbooks=None, env=None):
    '''
    This will build a chef server using the rcbops script and install git
    '''
    if not chef_node:
        query = "chef_environment:%s AND in_use:chef_server" % env
        chef_node = next(self.node_search(query))
    self.remove_chef(chef_node.name)

    install_chef_script = "https://raw.github.com/rcbops/jenkins-build/master/qa/bash/jenkins/install-chef-server.sh"

    # Run the install script
    cmds = ['curl %s >> install-chef-server.sh' % install_chef_script,
            'chmod u+x ~/install-chef-server.sh',
            './install-chef-server.sh']
    for cmd in cmds:
        ssh_run = self.run_command_on_node(chef_node, cmd)
        if ssh_run['success']:
            print "command: %s ran successfully on %s" % (cmd, chef_node)

    self.install_cookbooks(chef_node, cookbooks)
    if env:
        chef_env = Environment(env)
        self.add_remote_chef_locally(chef_node, chef_env)
        self.setup_remote_chef_environment(chef_env)

def prepare_cinder(self, name, api):
    node = Node(name, api=api.api)
    cmds = ["vg=`vgdisplay 2> /dev/null | grep vg | awk '{print $3}'`",
            ("for i in `lvdisplay 2> /dev/null | grep 'LV Name' | grep lv"
             " | awk '{print $3}'`; do lvremove $i; done"),
            "vgreduce $vg --removemissing"]
    self.run_command_on_node(node, "; ".join(cmds))
    cmd = "vgdisplay 2> /dev/null | grep vg | awk '{print $3}'"
    ret = self.run_command_on_node(node, cmd)['runs'][0]
    volume_group = ret['return']
    env = Environment(node.chef_environment, api=api.api)
    env.override_attributes["cinder"]["storage"]["lvm"]["volume_group"] = volume_group

def remove_chef(self, name):
    """
    @param chef_node
    """
    chef_node = Node(name)
    print "removing chef on %s..." % chef_node
    if chef_node['platform_family'] == "debian":
        command = "apt-get remove --purge -y chef; rm -rf /etc/chef"
    elif chef_node['platform_family'] == "rhel":
        command = 'yum remove -y chef; rm -rf /etc/chef /var/chef'
    else:
        print "OS Distro not supported"
        sys.exit(1)

    run = self.run_command_on_node(chef_node, command)
    if run['success']:
        print "Removed Chef on %s" % chef_node
    else:
        print "Failed to remove chef on %s" % chef_node
        sys.exit(1)

def install_cookbooks(self, chef_node, cookbooks, local_repo='/opt/rcbops'):
    '''
    @summary: This will pull the cookbooks down for git that you pass in cookbooks
    @param chef_server: The node that the chef server is installed on
    @type chef_server: String
    @param cookbooks A List of cookbook repos in dict form {url: 'asdf', branch: 'asdf'}
    @type cookbooks dict
    @param local_repo The location to place the cookbooks i.e. '/opt/rcbops'
    @type String
    '''
    # Make directory that the cookbooks will live in
    command = 'mkdir -p {0}'.format(local_repo)
    run_cmd = self.run_command_on_node(chef_node, command)
    if not run_cmd['success']:
        print "Command: %s failed to run on %s" % (command, chef_node)
        print run_cmd
        sys.exit(1)

    for cookbook in cookbooks:
        self.install_cookbook(chef_node, cookbook, local_repo)

def install_cookbook(self, chef_node, cookbook, local_repo):
    # clone to cookbook
    cmds = ['cd {0}; git clone {1} -b {2} --recursive'.format(local_repo, cookbook['url'], cookbook['branch'])]

    cmds.append('cd /opt/rcbops/chef-cookbooks; git checkout %s' % cookbook['branch'])

    # Since we are installing from git, the urls are pretty much constant
    # Pulling the url apart to get the name of the cookbooks
    cookbook_name = cookbook['url'].split("/")[-1].split(".")[0]

    # Stupid logic to see if the repo name contains "cookbooks", if it does then
    # we need to load from cookbooks repo, not the repo itself.
    # I think this is stupid logic, there has to be a better way (jacob)
    if 'cookbooks' in cookbook_name:
         # add submodule stuff to list
        cmds.append('cd /opt/rcbops/chef-cookbooks;'
                    'git submodule init;'
                    'git submodule sync;'
                    'git submodule update')
        cmds.append('knife cookbook upload --all --cookbook-path {0}/{1}/cookbooks'.format(local_repo, cookbook_name))
    else:
        cmds = ['knife cookbook upload --all --cookbook-path {0}/{1}'.format(local_repo, cookbook_name)]

    # Append role load to run list
    cmds.append('knife role from file {0}/{1}/roles/*.rb'.format(local_repo, cookbook_name))

    for cmd in cmds:
        run_cmd = self.run_command_on_node(chef_node, cmd)
        if not run_cmd['success']:
            print "Command: %s failed to run on %s" % (cmd, chef_node)
            print run_cmd
            sys.exit(1)

def setup_remote_chef_environment(self, chef_environment):
    """
    @summary Duplicates the local chef environment remotely
    """
    print "Putting environment onto remote chef server"
    name = chef_environment.name
    remote_api = self.remote_chef_client(chef_environment)
    env = Environment(name, api=remote_api)
    env.override_attributes = dict(chef_environment.override_attributes)
    env.save()

def add_remote_chef_locally(self, chef_server_node, env):
    print "Adding remote chef server credentials to local chef server"
    chef_server_node = Node(chef_server_node.name, api=self.chef)
    cmd = "cat ~/.chef/admin.pem"
    run = self.run_command_on_node(chef_server_node, cmd)
    if not run['success']:
        print "Error acquiring pem from %s" % (chef_server_node)
        print run
        sys.exit(1)
    admin_pem = run['runs'][0]['return']
    remote_dict = {"client": "admin",
                   "key": admin_pem,
                   "url": "https://%s:4443" %
                   chef_server_node['ipaddress']}
    env.override_attributes['remote_chef'] = remote_dict
    env.save()

def bootstrap_chef(self, client_node, server_node):
    '''
    @summary: installs chef client on a node and bootstraps it to chef_server
    @param node: node to install chef client on
    @type node: String
    @param chef_server: node that is the chef server
    @type chef_server: String
    '''

    # install chef client and bootstrap
    client_node = Node(client_node.name)
    chef_client_ip = client_node['ipaddress']
    chef_client_password = self.razor_password(client_node)
    cmd = 'knife bootstrap %s -x root -P %s' % (chef_client_ip,
                                                chef_client_password)
    ssh_run = self.run_command_on_node(server_node, cmd)

    if ssh_run['success']:
        print "Successfully bootstraped chef-client on %s to chef-server on %s" % (client_node, server_node)
