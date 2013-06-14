#!/usr/bin/python
from rpcsqa_helper import *

parser = argparse.ArgumentParser()

#Defaulted arguments
parser.add_argument('--razor_ip', action="store", dest="razor_ip",
                    default="198.101.133.3",
                    help="IP for the Razor server")

# Save the parsed arguments
results = parser.parse_args()

# create helper class for our chef server
rpcsqa = rpcsqa_helper(results.razor_ip)

# gather all current environments
environments = Environment.list(api=rpcsqa.chef)

# destroy them all
for environment in environments.names:
    if not '_default' in environment:
        print "Cleaning up environment {0}".format(environment)
        rpcsqa.cleanup_environment(environment)
