"""
	This class is designed to consume the razor API to manage nodes

	Pre-Requisites : 
		- requests : A Python library for simple http requests
		- json : A Python libray to consume json

	Author: Solomon J Wagner
"""

import json
import requests
import os, sys

class razor_api:
	
	def __init__(self, rzrip, rzrport='8026'):
		""" Initilizer for razor_api class"""
		self.ip = rzrip
		self.port = rzrport
		self.url = 'http://' + rzrip + ':' + rzrport + '/razor/api'

	def __repr__(self):
		""" Print out current instnace of razor_api"""
		outl = 'class :'+self.__class__.__name__
		
		for attr in self.__dict__:
			outl += '\n\t'+attr+' : '+str(getattr(self, attr))
		
		return outl

	def images(self):

		# Call the Razor RESTful API to get a list of models
		headers = {'content-type': 'application/json'}
		r = requests.get(self.url + '/model', headers=headers)

		# Check the status code and return appropriately
		if r.status_code == 200:
			return json.loads(r.content)
		else:
			return 'Error in request, exited with status code:' \
				+ str(r.status_code)

	def nodes(self):
		# Call the Razor RESTful API to get a list of models
		headers = {'content-type': 'application/json'}
		r = requests.get(self.url + '/node', headers=headers)

		# Check the status code and return appropriately
		if r.status_code == 200:
			return json.loads(r.content)
		else:
			return 'Error in request, exited with status code:' \
				+ str(r.status_code)

	def model_templates(self):

		# Call the Razor RESTful API to get a list of models
		headers = {'content-type': 'application/json'}
		r = requests.get(self.url + '/model/templates', headers=headers)

		# Check the status code and return appropriately
		if r.status_code == 200:
			return json.loads(r.content)
		else:
			return 'Error in request, exited with status code:' \
				+ str(r.status_code)

	def models(self):
		""" This function returns the whole model json returned by Razor."""
		
		# Call the Razor RESTful API to get a list of models
		headers = {'content-type': 'application/json'}
		r = requests.get(self.url + '/model', headers=headers)

		# Check the status code and return appropriately
		if r.status_code == 200:
			return json.loads(r.content)
		else:
			return 'Error in request, exited with status code:' \
				+ str(r.status_code)

	def simple_models(self, uuid=None):
		""" 
		This returns a smaller, simpler set of information 
		about the models returned by Razor.
		"""
		
		# Call the Razor RESTful API to get a list of models
		headers = {'content-type': 'application/json'}

		if uuid is None:
			r = requests.get(self.url + '/model', headers=headers)
			if r.status_code == 200:
				return json.loads(r.content)
			else:
				return 'Error in request, exited with status code:' \
					+ str(r.status_code)
		else:
			r = requests.get(self.url + '/model/' + uuid, headers=headers)
			if r.status_code == 200:
				return self.build_simple_model(json.loads(r.content))
			else:
				return 'Error in request, exited with status code:' \
					+ str(r.status_code)

	def build_simple_model(self, razor_json):
		""" 
		This will return the current available 
		model in a simple minimal info json
		"""
		
		# loop through all the nodes that were returned and take the simple info from them
		for response in razor_json['response']:
			model = {'name': response['@name'],
					 'root_password': response['@root_password'],
					 'current_state': response['@current_state'],
					 'uuid': response['@uuid'],
					 'label': response['@label']
					 }

		return model

	def active_models(self, filter=None):
		"""
		 This return the whole json returned 
		by the Razor API for a single active model.
		"""
		
		if filter is None:
			url = self.url + '/active_model'
		else:
			url = self.url + '/active_model?label=%s' % filter
			
		# make the request to get active models from Razor
		headers = {'content-type': 'application/json'}
		r = requests.get(url, headers=headers)

		# Check the status code and return appropriately
		if r.status_code == 200:
			return json.loads(r.content)
		else:
			return 'Error in request, exited with status code: ' \
				+ str(r.status_code)

	def simple_active_models(self, filter=None):
		""" 
		This will return all the active 
		models with an easy to consume JSON
		"""
		# make the request to get active models from Razor
		
		am_content = self.active_models(filter)

		#print json.dumps(am_content, indent=4)
		
		# Check the status code and return appropriately
		if 'response' in am_content.keys():
			active_models = {}
			for response in am_content['response']:

				# get info from razor about the active model
				headers = {'content-type': 'application/json'}
				r = requests.get(self.url + '/active_model/' 
					+ response['@uuid'], headers=headers)
				single_am_content = json.loads(r.content)
				#print json.dumps(single_am_content, indent=2)
				active_models[response['@uuid']] = \
					self.build_simple_active_model(single_am_content)

			return active_models
		else:
			return 'Error in request, exited with status code: ' \
				+ str(r.status_code)

	def build_simple_active_model(self, razor_json):
		"""
		This will return an active model JSON 
		that is simplified from the Razor API json
		"""

		# step through the json and gather simplified information
		for item in razor_json['response']:

			if item['@broker'] is not None:
				broker = item['@broker']['@name']
			else:
				broker = None

			active_model = {'node_uuid': item['@node_uuid'],
							'am_uuid': item['@uuid'],
							'description': item['@model']['@description'],
							'root_password': item['@model']['@root_password'],
							'current_state': item['@model']['@current_state'],
							'final_state': item['@model']['@final_state'],
							'broker': broker,
							'bind_number': item['@model']['@counter'],
							'hostname_prefix': \
								item['@model']['@hostname_prefix'],
							'domain': item['@model']['@domainname']
							}
			try:
				hdwnic_count = int(item['@model']['@node']\
					['@attributes_hash']['mk_hw_nic_count'])
				active_model['nic_count'] = hdwnic_count
				# Get the active network interface ips
				for i in range(0, hdwnic_count):
					try:
						me = item['@model']['@node']\
						['@attributes_hash']['macaddress_eth%d' % i]
						active_model['eth%d_mac' % i] = item['@model']['@node']['@attributes_hash']['macaddress_eth%d' % i]
					except KeyError:
						pass
	
					try:
						active_model['eth%d_ip' % i] = item['@model']['@node']['@attributes_hash']['ipaddress_eth%d' % i]
					except KeyError:
						pass
			except:
				print "Error getting nic count"
				print "Model: %s " %  item['@model']
		return active_model

	def active_ready(self, razor_json):
		"""
		This method will return all the online complete servers
		"""

		servers = []

		# step through the json and gather simplified information
		for item in razor_json:
			if 'complete' in razor_json[item]['current_state']:
				ready_server = {'description': razor_json[item]['description'],
								'node_uuid': razor_json[item]['node_uuid'],
								'am_uuid': razor_json[item]['am_uuid'],
								'root_passwd': razor_json[item]['root_password'],
								'broker': razor_json[item]['broker'],
								'bind_number': item['@model']['@counter'],
								'hostname_prefix': item['@model']['@hostname_prefix'],
								'domain': item['@model']['@domainname']
								}
				for x in range(0, razor_json[item]['nic_count']):
					try:
						ready_server['eth%d_ip_addr' % x] = \
						razor_json[item]['eth%d_ip' % x]
					except:
						pass

					try:
						ready_server['eth%d_mac' % x] = \
						razor_json[item]['eth%d_mac' % x]
					except:
						pass

				servers.append(ready_server)

		return servers

	def broker_success(self, razor_json):
		"""
		This method will return all the online broker complete servers
		"""

		servers = []
		# step through the json and gather simplified information
		for item in razor_json:
			if 'broker_success' in razor_json[item]['current_state']:
				ready_server = {'description': razor_json[item]['description'],
								'node_uuid': razor_json[item]['node_uuid'],
								'am_uuid': razor_json[item]['am_uuid'],
								'root_passwd': razor_json[item]['root_password'],
								'broker': razor_json[item]['broker'],
								'bind_number': item['@model']['@counter'],
								'hostname_prefix': item['@model']['@hostname_prefix'],
								'domain': item['@model']['@domainname']
								}
				for x in range(0, razor_json[item]['nic_count']):
					try:
						ready_server['eth%d_ip_addr' % x] = \
						razor_json[item]['eth%d_ip' % x]
					except:
						pass

					try:
						ready_server['eth%d_mac' % x] = \
						razor_json[item]['eth%d_mac' % x]
					except:
						pass

				servers.append(ready_server)

		return servers

	def remove_active_models(self, am_uuids):
		"""
		This function will loop through a list of am uuids and remove each one
		"""

		removed_servers = []
		for uuid in am_uuids:
			removed_servers.append(remove_active_model(uuid))

		return removed_servers


	def remove_active_model(self, am_uuid):
		"""
		This function will remove an active model from Razor.
		"""
		
		# Call the Razor RESTful API to get a list of models
		headers = {'content-type': 'application/json'}
		r = requests.delete(
			self.url + '/active_model/%s' % am_uuid, headers=headers)
		
		return {'status': r.status_code, 'content': json.loads(r.content)}

	def get_active_model_pass(self, am_uuid):
		""" This function will get an active models password """
		headers = {'content-type': 'application/json'}
		r = requests.get(
			self.url + '/active_model/%s' % am_uuid, headers=headers)

		passwd = ''
		if r.status_code == 200:
			content_json = json.loads(r.content)
			passwd = content_json['response'][0]['@model']['@root_password']

		return {'status_code': r.status_code, 'password': passwd}
