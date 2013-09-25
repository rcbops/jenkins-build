"""
OpenStack Build objects
"""
import sys
import traceback
from chef import Node
from modules.chef_api import chef_api

class Build(object):
    """
    Base openstack Build object
    """
    def __init__(self, name, role, qa, pre_commands=[], post_commands=[]):
	self.name = name
	self.role = role
	self.qa = qa
	self.pre_commands = pre_commands
	self.post_commands = post_commands

    def build(self):
	self.preconfigure()
	self.apply_role()
	self.postconfigure()

    def preconfigure(self):
	self._run_commands(self.pre_commands)

    def apply_role(self):
	raise NotImplementedError

    def postconfigure(self):
	self._run_commands(self.post_commands)

    def _run_commands(qa, node, commands):
	print "#" * 70
	print "Running {0} chef-client commands....".format(node)
	for command in commands:
	    print "Running:  %s" % command
	    #If its a string run on remote server
	    if isinstance(command, str):
		qa.run_command_on_node(node, command)
	    if isinstance(command, dict):
		try:
		    func = command['function']
		    func(**command['kwargs'])
		except:
		    print traceback.print_exc()
		    sys.exit(1)
	    #elif function run the function
	    elif hasattr(command, '__call__'):
		command()
	print "#" * 70


class ChefBuild(Build):

    def __init__(self, name, role, qa, env):
	super(ChefBuild, self).__init__(name, role, qa)
	self.environment = env
	self.run_list = self.run_list_map(role)
	self.chef = chef

    def _run_list_map(role):
	return {
	    "chef-server": [],
	    "single-controller": ['role[ha-controller1]'],
	    "directory-server": ['role[qa-openldap-%s]'],
	    "ha-controller1": ['role[ha-controller1]'],
	    "ha-controller2": ['role[ha-controller2]']
	}[role]

    def preconfigure(self):
	node = Node(self.name)
	node['in_use'] = self.role
	node.chef_environment = self.environment
	node.save()
	if args.remote_chef and not b['in_use'] in ["chef_server","openldap"]:
	    qa.remove_chef(node)
	    query = "chef_environment:%s AND in_use:chef_server" % env
	    chef_server = next(qa.node_search(query))
	    qa.bootstrap_chef(node, chef_server)
	    api = qa.remote_chef_client(environment)
	super(ChefBuild, self).__init__()

    def apply_role():
	node = Node(self.name, api=api)
	node.run_list = b['run_list']
	node.chef_environment = env
	node.save()
	print "Running chef client for %s" % node
	print node.run_list
	chef_client = qa.run_chef_client(node,
					 num_times=2,
					 log_level=args.log_level)
	if not chef_client['success']:
	    print "chef-client run failed"
	    success = False
	    break


class DeploymentBuild(Build):
    """
    Base build for entire deployment
    """

    def __init__(self, name, builds=[], pre_commands=[], post_commands=[]):
	self.name = name
	self.builds = builds
	self.pre_commands = pre_commands
	self.post_commands = post_commands

    def __iter__(self):
	return self.builds

    def build(self):
	self.preconfigure()
	for build in self:
	    build.build()
	self.postconfigure()

class ChefDeploymentBuild(DeploymentBuild):
    """
    Base build for entire chef deployment
    """
    def __init__(self, name, is_remote=True, builds=[], pre_commands=[], post_commands=[]):
	super(ChefDeploymentBuild, self).__init__(name, builds=[], pre_commands=[], post_commands=[])
	self.is_remote = is_remote
	self.api = chef_api()


    def
