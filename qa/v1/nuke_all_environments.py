#!/usr/bin/python
import argparse
from modules.rpcsqa_helper import *

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

# remove _default from environments
print "Removing _default environment to protect it from the destroy"
environments.names.remove('_default')
if 'cloudcafe-precise-grizzly-default' in environments.names:
    environments.names.remove('cloudcafe-precise-grizzly-default')

# destroy them all
for environment in environments.names:
    print "Cleaning up environment {0}".format(environment)
    rpcsqa.cleanup_environment(environment)
