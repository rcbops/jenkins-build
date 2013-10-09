import argparse, json
from modules.rpcsqa_helper import rpcsqa_helper
from chef import Search, Node
import sys

# Parse arguments from the cmd line
parser = argparse.ArgumentParser()
parser.add_argument('--env', action="store", dest="environment",
                    required=False, default="autotest-precise-grizzly-openldap",
                    help="Name for the openstack chef environment")
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")

args = parser.parse_args()
rpcsqa = rpcsqa_helper(razor_ip=args.razor_ip)

rpcsqa.cleanup_environment(args.environment)
rpcsqa.delete_environment(args.environment)
