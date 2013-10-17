from chef import *
from modules.server_helper import ssh_cmd
from modules import razor

api = autoconfigure()
env = "precise-default"
nodes = [Node(node['name'], api=api) for node in Search("node", api=api).query("in_use:provisioned")]
for node in nodes:
    print "fixing in_use:" + node.name
    node.attributes['in_use'] = 0
    node.save()

nodes = [Node(node['name'], api=api) for node in Search("node", api=api).query("chef_environment:{0}".format(env))]
for node in nodes:
    if node['in_use'] == "provisioned":
        print "fixing env:" + node.name
        node.chef_environment = "_default"
        node.save()
    else:
        ip = node['ipaddress']
        print "rebooting:" + node.name
        cmd = "reboot 0"
        ssh_cmd(ip, cmd, password="ostackdemo")
        name = node.name
        active_model = cnode['razor_metadata']['razor_active_model_uuid']
        razor.remove_active_model(active_model)
        node.delete()
        Client(name, api=api).delete()

cenv = Environment(env, api=api)
if cenv.exists:
    print "deleting env:" + cenv.name
    cenv.delete()
