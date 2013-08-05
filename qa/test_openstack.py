import argparse, json
from modules.rpcsqa_helper import rpcsqa_helper
from chef import Search, Node
import sys

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--environment', action="store", dest="environment",
                    required=False, default="autotest-precise-grizzly-openldap",
                    help="Name for the openstack chef environment")
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")

args = parser.parse_args()

qa = rpcsqa_helper(razor_ip=args.razor_ip)

search = Search("node", api=qa.chef).query("chef_environment:%s AND (roles:single-controller OR roles:ha-controller1)" % args.environment)

if len(search) < 1: print "Could not find controller"
elif len(search) > 1: print "Found too many controllers (what?!) "
else:        
    controller = Node(search[0]['name'],api=qa.chef)

    print "Adding tempest to controller run_list"
    if 'recipe[tempest]' not in controller.run_list:
        controller.run_list.append('recipe[tempest]')
    print controller.run_list
    controller.save()

    print "Running chef-client"
    chef_client = qa.run_chef_client(controller, num_times=1, log_level='info')
