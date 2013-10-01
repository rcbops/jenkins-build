#!/usr/bin/python
import os
import json
import argparse


def create_data_bag(public, drac, ident=None):
    public_array = public.split(".")

    if ident is None:
        data_bag = {
            "id": "temp_ident",
            "network_interfaces": {
                "drac": drac,
                "debian": [
                    {
                        "auto": "true",
                        "type": "static",
                        "device": "eth0",
                        "netmask": "255.255.255.0",
                        "address": public,
                        "gateway": "%s.%s.%s.%s" % (public_array[0], public_array[1], public_array[2], 1),
                        "dnsnameservers": "8.8.8.8 8.8.4.4",
                        "dnssearch": "rcb.rackspace.com"
                    }
                ],
                "redhat": [
                    {
                        "device": "em1",
                        "bootproto": "none",
                        "onboot": "yes",
                        "netmask": "255.255.255.0",
                        "gateway": "%s.%s.%s.%s" % (public_array[0], public_array[1], public_array[2], 1),
                        "peerdns": "yes",
                        "dns1": "8.8.8.8",
                        "dns2": "8.8.4.4",
                        "ipaddr": public,
                        "userctl": "no"
                    }
                ]
            }
        }

        try:
            # Open the file
            fo = open("%s.json" % public, "w")
        except IOError:
            print "Failed to open file %s.json" % public
        else:
            # Write the json string
            fo.write(json.dumps(data_bag, indent=4))

            #close the file
            fo.close()

            # print message for debugging
            print "%s.json successfully saved" % public
    else:
        data_bag = {
            "id": ident,
            "network_interfaces": {
                "drac": drac,
                "debian": [
                    {
                        "auto": "true",
                        "type": "static",
                        "device": "eth0",
                        "netmask": "255.255.255.0",
                        "address": public,
                        "gateway": "%s.%s.%s.%s" % (public_array[0], public_array[1], public_array[2], 1),
                        "dnsnameservers": "8.8.8.8 8.8.4.4",
                        "dnssearch": "rcb.rackspace.com"
                    }
                ],
                "redhat": [
                    {
                        "device": "em1",
                        "bootproto": "none",
                        "onboot": "yes",
                        "netmask": "255.255.255.0",
                        "gateway": "%s.%s.%s.%s" % (public_array[0], public_array[1], public_array[2], 1),
                        "peerdns": "yes",
                        "dns1": "8.8.8.8",
                        "dns2": "8.8.4.4",
                        "ipaddr": public,
                        "userctl": "no"
                    }
                ]
            }
        }

        try:
            # Open the file
            fo = open("%s.json" % ident, "w")
        except IOError:
            print "Failed to open file %s.json" % ident
        else:
            # Write the json string
            fo.write(json.dumps(data_bag, indent=4))

            #close the file
            fo.close()

            # print message for debugging
            print "%s.json successfully saved" % ident


# MAIN PROGRAM
# Gather the arguments from the command line
parser = argparse.ArgumentParser()

# Path to JSON file of MACs
parser.add_argument('--file_path', action="store", dest="file_path",
                    required=False, default=None, help="Path to the JSON file")

# Parse the parameters
results = parser.parse_args()

# Get the path to the JSON File
path = os.path.join(os.path.dirname(__file__), 'metadata/server_management', 'mac_addresses_to_ip.json')

# Open the file and write macs to ips
try:
    fo = open(path, 'r')
except IOError:
    print "Failed to open file @ %s" % path
else:
    print fo
    macs_to_ips = json.loads(fo.read())
    fo.close()

for k, v in macs_to_ips.items():
    print "key: %s, value: %s" % (k, v)
    create_data_bag(v['public'], v['drac'], k)
