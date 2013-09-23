"""
OpenStack Build objects
"""
import sys
import Environments
import traceback

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
        super(ChefBuild, self).__init__()

    def apply_role():
