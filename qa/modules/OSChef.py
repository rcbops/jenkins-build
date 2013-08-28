import sys
from time import sleep
from chef import autoconfigure, Search


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
        env_json['override_attributes'].update(environments.base_env['override_attributes'])
        for feature in features:
            if feature in environments.__dict__:
                env_json['override_attributes'].update(environments.__dict__[feature])
        chef_env.override_attributes.update(env_json['override_attributes'])
        chef_env.override_attributes['package_component'] = branch
        if os_distro == "centos":
            chef_env.override_attributes['nova']['networks']['public']['bridge_dev'] = "em1"
        chef_env.save()
        return env
