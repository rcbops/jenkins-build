"""
openstack Build objects
"""
import sys
import commands as _commands
import traceback
from chef import Node
from chef_api import chef_api


class Builds():
    chef_server = "chef_server"
    compute = "compute"
    directory_server = "directory_server"
    controller1 = "controller1"
    controller2 = "controller2"


class Build(object):
    """
    Base openstack Build object
    """

    def __init__(self, name, role, qa, branch, pre_commands=None,
                 post_commands=None):
        self.name = name
        self.role = role
        self.qa = qa
        self.branch = branch
        self.pre_commands = pre_commands
        self.post_commands = post_commands
        self.status = "Prebuild"

    def build(self):
        self.status = "Building"
        self.preconfigure()
        self.status = "Building"
        self.apply_role()
        self.postconfigure()

    def preconfigure(self):
        self.status = "Preconfigure"
        self._run_commands(self.pre_commands)

    def apply_role(self):
        self.status = "Preconfigure"
        raise NotImplementedError

    def postconfigure(self):
        self.status = "Postconfigure"
        self._run_commands(self.post_commands)

    def _run_commands(self, commands):
        raise NotImplementedError

    def _map_kwargs(self, kwargs):
        for key in kwargs.keys():
            kwargs[key] = getattr(self, kwargs[key])
        return kwargs

    def __str__(self):
        return ("Build: {0} - Role: {1} - "
                "pre: {2} - post {3}").format(self.name, self.role,
                                              self.pre_commands,
                                              self.post_commands)


class ChefBuild(Build):
    """
    Base openstack Build object using chef
    """

    def __init__(self, name, role, qa, branch, env, api=None,
                 pre_commands=None, post_commands=None):
        super(ChefBuild, self).__init__(name, role, qa, branch,
                                        pre_commands=pre_commands,
                                        post_commands=post_commands)
        self.environment = env
        self.run_list = self._run_list_map(role)
        self.api = api or chef_api()
        self.cookbooks = self.cookbook_branch(self.role)

    def _run_list_map(self, role):
        return {
            "chef_server": [],
            "compute": ['role[single-compute]', 'role[cinder_all]'],
            "directory_server": ['role[qa_openldap]'],
            "controller1": ['role[ha_controller1]', 'role[cinder_all]'],
            "controller2": ['role[ha_controller2]']
        }[role]

    def bootstrap(self):
        self.qa.remove_chef(self.name)
        self.qa.bootstrap_chef(self.name, self.api.server)

    def _run_commands(self, commands):
        for command in commands:
            #If its a string run on remote server
            if isinstance(command, str):
                self.qa.run_command_on_node(Node(self.name), command)
            if isinstance(command, dict):
                try:
                    func = getattr(_commands, command['function'])
                    kwargs = self._map_kwargs(command['kwargs'])
                    func(**kwargs)
                except:
                    print traceback.print_exc()
                    sys.exit(1)
            #elif function run the function
            elif hasattr(command, '__call__'):
                command()

    def preconfigure(self):
        self.status = "Preconfigure"
        node = Node(self.name)
        node['in_use'] = self.role
        node.chef_environment = self.environment
        node.save()
        if self.api.remote and not self.role in ["chef_server", "openldap"]:
            self.bootstrap()
        super(ChefBuild, self).preconfigure()
        if self.role is "chef_server":
            # This should be done in the chef_server build
            self.api.remote = self\
                    .qa.remote_chef_client(self.environment)

    def apply_role(self):
        node = Node(self.name, api=self.api.api)
        node.run_list = self._run_list_map(self.role)
        node.chef_environment = self.environment
        node.save()

        if node.run_list:
            print "Running chef client for %s" % node
            print node.run_list
            chef_client = self.qa.run_chef_client(node, num_times=2)
            if not chef_client['success']:
                print "chef_client run failed"
                self.status = "Failure"
                raise Exception

    def cookbook_branch(self, branch):
        return [
            {
                "url": "https://github.com/rcbops/chef-cookbooks.git",
                "branch": branch
            }
        ]


class DeploymentBuild(Build):
    """
    Base build for entire deployment
    """

    def __init__(self, name, builds=[], pre_commands=[], post_commands=[]):
        self.name = name
        self.builds = builds
        self.pre_commands = pre_commands
        self.post_commands = post_commands

    def build(self):
        self.preconfigure()
        for build in self.builds:
            build.build()
        self.postconfigure()

    def append(self, item):
        self.builds.append(item)

    def __str__(self):
        deployment = "Deployment: {0}\n".format(self.name)
        return deployment + "\n".join(str(build) for build in self.builds)


class ChefDeploymentBuild(DeploymentBuild):
    """
    Base build for entire chef deployment
    """

    def __init__(self, name, is_remote=True, builds=[], pre_commands=[],
                 post_commands=[]):
        super(ChefDeploymentBuild, self).__init__(name, builds=[],
                                                  pre_commands=[],
                                                  post_commands=[])
        self.is_remote = is_remote
        self.api = chef_api()

    def _run_commands(self, commands):
        for command in commands:
            #If its a string run on remote server
            if isinstance(command, (str, str)):
                node, command = command
                self.qa.run_command_on_node(Node(node), command)
            if isinstance(command, dict):
                try:
                    func = getattr(_commands, command['function'])
                    kwargs = self._map_kwargs(command['kwargs'])
                    func(**kwargs)
                except:
                    print traceback.print_exc()
                    sys.exit(1)
            #elif function run the function
            elif hasattr(command, '__call__'):
                command()

    def preconfigure(self):
        if self.is_remote:
            chef_server = next(b.name for b in self.builds
                               if b.role == "chef_server")
            self.api.server = chef_server
            super(ChefDeploymentBuild, self).preconfigure()
