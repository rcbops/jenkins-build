import sys
from time import sleep
from chef import autoconfigure, Search, Environment, Node, Client
import environments


class OSChef:
    def __init__(self, api=None, remote_api=None):
        self.api = api or autoconfigure()
        self.remote_api = remote_api

    def node_search(self, query=None, api=None, tries=10):
        api = api or self.chef
        search = None
        while not search and tries > 0:
            search = Search("node", api=api).query(query)
            sleep(10)
            tries = tries - 1
        return (n.object for n in search)

    # Python 3 compatibility
    def __next__(self):
        return self.next()

    def next(self):
        in_image_pool = "name:qa-%s-pool*" % self.image
        is_default_environment = "chef_environment:_default"
        is_ifaced = """run_list:recipe\[network-interfaces\]"""
        query = "%s AND %s AND %s" % (in_image_pool,
                                      is_default_environment,
                                      is_ifaced)
        nodes = self.node_search(query)
        fails = 0
        try:
            node = next(nodes)
            node['in_use'] = "provisioned"
            yield node
        except StopIteration:
            if fails > 10:
                print "No available chef nodes"
                sys.exit(1)
            fails += 1
            sleep(15)
            nodes = self.node_search(query)

    def prepare_environment(self, name, os_distro, branch, features):
        """ If the environment doesnt exist in chef, make it. """
        env = "%s-%s-%s-%s" % (name, os_distro, branch, "-".join(features))
        chef_env = Environment(env, api=self.chef)
        if not chef_env.exists:
            print "Making environment: %s " % env
            chef_env.create(env, api=self.chef)

        env_json = chef_env.to_dict()
        override_attributes = environments.base_env['override_attributes']
        env_json['override_attributes'].update(override_attributes)
        for feature in features:
            if feature in environments.__dict__:
                feature_attribs = environments.__dict__[feature]
                env_json['override_attributes'].update(feature_attribs)
        chef_env.override_attributes.update(env_json['override_attributes'])
        chef_env.override_attributes['package_component'] = branch
        if os_distro == "centos":
            chef_env.override_attributes['nova']['networks']['public']['bridge_dev'] = "em1"
        chef_env.save()
        return env

    def set_in_use(self, name, use):
        node = Node(name, api=self.api)
        node['in_use'] = use
        node.save()

    def set_run_list(self, name, run_list):
        api = self.remote_api or self.api
        node = Node(name, api=api)
        node['run_list'] = run_list
        node.save()

    def build_chef_server(self, chef_node=None, cookbooks=None, env=None):
        '''
        This will build a chef server using the rcbops script and install git
        '''

        if not chef_node:
            query = "chef_environment:%s AND in_use:chef_server" % env
            chef_node = next(self.node_search(query))
        self.remove_chef(chef_node)

        install_script = '/var/lib/jenkins/jenkins-build/qa/v1/bash/jenkins/install-chef-server.sh'

        # SCP install script to chef_server node
        scp_run = self.scp_to_node(chef_node, install_script)

        if scp_run['success']:
            print "Successfully copied chef server install script to chef_server node %s" % chef_node
        else:
            print "Failed to copy chef server install script to chef_server node %s" % chef_node
            print scp_run
            sys.exit(1)

        # Run the install script
        cmds = ['chmod u+x ~/install-chef-server.sh',
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

    def delte_client_node(self, name):
        node = Node(self.name, self.api)
        node.delete()
        Client(self.name).delete()
