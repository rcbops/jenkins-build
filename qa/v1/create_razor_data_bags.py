#!/usr/bin/python
import os
import json
import argparse

def create_data_bag(ip, ident=None):

	ip_array = ip.split(".")
	
	if ident is None:
		data_bag = {
			"id": temp_ident,
			"network_interfaces": {
				"debian": [
					{
						"auto": "true",
		    			"type": "static",
		    			"device": "eth0",
		    			"netmask": "255.255.255.0",
		    			"address": ip,
		    			"gateway": "%s.%s.%s.%s" % (
		    				ip_array[0], ip_array[1], ip_array[2], 1),
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
						"gateway": "%s.%s.%s.%s" % (
							ip_array[0], ip_array[1], ip_array[2], 1),
						"peerdns": "yes",
						"dns1": "8.8.8.8",
						"dns2": "8.8.4.4",
						"ipaddr": ip,
						"userctl": "no"
					}
				]
			}
		}

		try:
			# Open the file
			fo = open("%s.json" % ip, "w")
		except IOError:
			print "Failed to open file %s.json" % ip
		else:
			# Write the json string
			fo.write(json.dumps(data_bag, indent=4))

			#close the file
			fo.close()

			# print message for debugging
			print "%s.json successfully saved" % ip
	else:
		data_bag = {
			"id": ident,
			"network_interfaces": {
				"debian": [
					{
						"auto": "true",
		    			"type": "static",
		    			"device": "eth0",
		    			"netmask": "255.255.255.0",
		    			"address": ip,
		    			"gateway": "%s.%s.%s.%s" % (
		    				ip_array[0], ip_array[1], ip_array[2], 1),
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
						"gateway": "%s.%s.%s.%s" % (
							ip_array[0], ip_array[1], ip_array[2], 1),
						"peerdns": "yes",
						"dns1": "8.8.8.8",
						"dns2": "8.8.4.4",
						"ipaddr": ip,
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
	required=True, default=None, help="Path to the JSON file")

# Parse the parameters
results = parser.parse_args()

# Get the path to the JSON File
path = os.path.abspath(results.file_path)

# Open the file and write macs to ips
try:
	fo = open(path, 'r')
except IOError:
		print "Failed to open file @ %s" % path
else:
	print fo
	macs_to_ips = json.loads(fo.read())
	fo.close()

for k,v in macs_to_ips.items():
	print "key: %s, value: %s" % (k,v)
	create_data_bag(v, k)
