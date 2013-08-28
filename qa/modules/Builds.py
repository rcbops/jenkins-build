import Roles
import Environments


class Build:
    def __init__(self, node, role):
        self.node = node
        self.role = role

    def preconfigure(self):
        raise NotImplementedError

    def apply_role(self):
        raise NotImplementedError

    def postconfigure(self):
        raise NotImplementedError


class ChefBuild(Build):
    run_list_map = []
    run_list_map[Roles.ChefServer] = qa.build_chef_server(cookbooks, env)

    def __init__(self, node, role, run_list, branch, env, chef_helper):
        super(ChefBuild, self).__init__(node, role)
        run_list = role if role else run_list_map[self.role]
        chef_helper = chef_helper

    def preconfigure(self):
        raise NotImplementedError

    def apply_role(self):
        raise NotImplementedError

    def postconfigure(self):
        raise NotImplementedError
