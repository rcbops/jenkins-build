#!/usr/bin/python
"""
    This script connects to our blank ubuntu server and dl's and runs the set-up bash.
"""
import os
import subprocess
import argparse
from ssh_session import ssh_session

print "!!## -- Running Setup for Bare Metal -- ##!!"

# Gather the arguments from the command line
parser = argparse.ArgumentParser()

# Get the hostname for the alamo server


#For the destination get....
#################################
parser.add_argument('--ip', action="store", dest="ip",
                    required=True, default="~", help="The location to get the setup file")

# Get the username for the host
parser.add_argument('--user_name', action="store", dest="user_name", 
                    required=True, help="Non-root user name for the host")

# Get the password for the host
parser.add_argument('--user_passwd', action="store", dest="user_passwd", 
                    required=True, help="Non-root password for the host")


parser.add_argument('--zodiac_host_id', action="store", dest="zodiac_host_id", 
                    required=True, help="Host ID from the zodiac ")


# Get the password for the host
parser.add_argument('-v', action="store", dest="verbose", 
                    default=None, help="Verbose")

# Parse the parameters
results = parser.parse_args()

# Connect to the host
print "Setting up session"
session = ssh_session(results.user_name, results.ip, results.user_passwd, results.verbose)

print "Running zodiac...."
print 'bash /opt/zodiac/runZodiac.sh %s' % (results.zodiac_host_id)
session.ssh('bash /opt/zodiac/runZodiac.sh %s' % (results.zodiac_host_id))


session.close()

print "!!## -- Ending Setup for Bare Metal -- ##!!"