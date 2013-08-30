import OS_Roles


class ConfigManager():
    def tear_down(self):
        raise NotImplementedError


class ChefConfigManager(ConfigManager):
    run_lists = []
    run_lists[OS_Roles.ChefServer] = ''
    run_lists[OS_Roles.SingleController] = ['role[ha-controller1]']
    run_lists[OS_Roles.DirectoryServer] = ['role[qa-openldap-%s]']
    run_lists[OS_Roles.HAController1] = ['role[ha-controller1]']
    run_lists[OS_Roles.HAController2] = ['role[ha-controller2]']

    def __init__(self, name, chef, environment):
        self.name = name
        self.chef = chef
        self.environment = environment

    def __str__(self):
        return "Chef Node: %s - %s" % (self.name, self.ip)

    def tear_down(self):
        self.chef.delete_client_node(self.name)

    def apply_role(self, name, role):
        self.chef.set_run_list(self.run_lists[role])
