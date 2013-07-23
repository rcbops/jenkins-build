#!/usr/bin/python
import os
import argparse
from ssh_session import ssh_session

"""
    This script connects to our blank ubuntu server and dl's and runs the set-up bash.
"""
# Gather the arguments from the command line
parser = argparse.ArgumentParser()

# Get the hostname for the alamo server
#Source File
################
parser.add_argument('--source', action="store", dest="source",
                    required=True, default="workspace/scripts/bash/build_zodiac_config.sh", help="Path to source file ")

#For the destination get....
#################################
parser.add_argument('--destination', action="store", dest="destination",
                    required=True, default="~", help="The location to get the setup file")

# Get the hostname of the host
parser.add_argument('--host_name', action="store", dest="host_name", 
                    required=True, help="Hostname/IP for the Server")

# Get the username for the host
parser.add_argument('--user_name', action="store", dest="user_name", 
                    required=True, help="Non-root user name for the host")

# Get the password for the host
parser.add_argument('--user_passwd', action="store", dest="user_passwd", 
                    required=True, help="Non-root password for the host")


# Get the password for the host
parser.add_argument('-v', action="store", dest="verbose", 
                    default=None, help="Verbose")

# Parse the parameters
results = parser.parse_args()
filename=os.path.basename(results.source)

# Download the set-up script
print " %s ==> %s:%s" % (results.source, results.host_name, results.destination)
# Connect to the host
session = ssh_session(results.user_name, results.host_name, results.user_passwd, results.verbose)
session.scp(results.source, results.destination)

print "chmod 0755 %s" % results.destination
session.ssh('chmod 0755 %s/%s' % (results.destination, filename))

# Run the script
print "Running the script: %s" % results.destination
session.sudo_ssh('sudo %s/./%s' % (results.destination, filename))

session.close()