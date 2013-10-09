import json
import requests


class razor_api:

    def __init__(self, rzrip, rzrport='8026'):
        """ Initilizer for razor_api class"""
        self.ip = rzrip
        self.port = rzrport
        self.url = 'http://' + rzrip + ':' + rzrport + '/razor/api'

    def __repr__(self):
        """ Print out current instnace of razor_api"""
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
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

        # loop through all the nodes and take the simple info from them
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
            model = item['@model']
            node = model['@node']
            active_model = {'node_uuid': item['@node_uuid'],
                            'am_uuid': item['@uuid'],
                            'description': model['@description'],
                            'root_password': model['@root_password'],
                            'current_state': model['@current_state'],
                            'final_state': model['@final_state'],
                            'broker': broker,
                            'bind_number': model['@counter'],
                            'hostname_prefix':
                            model['@hostname_prefix'],
                            'domain': model['@domainname']
                            }
            try:
                hdwnic_count = int(node['@attributes_hash']['mk_hw_nic_count'])
                active_model['nic_count'] = hdwnic_count
                # Get the active network interface ips
                for i in range(0, hdwnic_count):
                    try:
                        mac_eth_str = 'macaddress_eth%d' % i
                        mac_eth = node['@attributes_hash'][mac_eth_str]
                        active_model['eth%d_mac' % i] = mac_eth
                    except KeyError:
                        pass

                    try:
                        eth_str = 'ipaddress_eth%d' % i
                        eth_ip = node['@attributes_hash'][eth_str]
                        active_model['eth%d_ip' % i] = eth_ip
                    except KeyError:
                        pass
            except:
                print "Error getting nic count"
                print "Model: %s " % model
        return active_model

    def active_ready(self, razor_json):
        """
        This method will return all the online complete servers
        """

        servers = []

        # step through the json and gather simplified information
        for item in razor_json:
            r_item = razor_json[item]
            model = item['@model']
            if 'complete' in r_item['current_state']:
                ready_server = {'description': r_item['description'],
                                'node_uuid': r_item['node_uuid'],
                                'am_uuid': r_item['am_uuid'],
                                'root_passwd': r_item['root_password'],
                                'broker': r_item['broker'],
                                'bind_number': model['@counter'],
                                'hostname_prefix': model['@hostname_prefix'],
                                'domain': model['@domainname']
                                }
                for x in range(0, r_item['nic_count']):
                    try:
                        eth_ip = r_item['eth%d_ip' % x]
                        ready_server['eth%d_ip_addr' % x] = eth_ip
                    except:
                        pass
                    try:
                        eth_mac = r_item['eth%d_mac' % x]
                        ready_server['eth%d_mac' % x] = eth_mac
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
            r_item = razor_json[item]
            model = item['@model']
            if 'broker_success' in r_item['current_state']:
                ready_server = {'description': r_item['description'],
                                'node_uuid': r_item['node_uuid'],
                                'am_uuid': r_item['am_uuid'],
                                'root_passwd': r_item['root_password'],
                                'broker': r_item['broker'],
                                'bind_number': model['@counter'],
                                'hostname_prefix': model['@hostname_prefix'],
                                'domain': model['@domainname']
                                }
                for x in range(0, r_item['nic_count']):
                    try:
                        eth_ip = r_item['eth%d_ip' % x]
                        ready_server['eth%d_ip_addr' % x] = eth_ip
                    except:
                        pass
                    try:
                        eth_mac = r_item['eth%d_mac' % x]
                        ready_server['eth%d_mac' % x] = eth_mac
                    except:
                        pass

                servers.append(ready_server)

        return servers

    def remove_active_model(self, am_uuid):
        """
        This function will remove an active model from Razor.
        """

        # Call the Razor RESTful API to get a list of models
        headers = {'content-type': 'application/json'}
        r = requests.delete(
            self.url + '/active_model/%s' % am_uuid, headers=headers)

        return {'status': r.status_code, 'content': json.loads(r.content)}

    def remove_active_models(self, am_uuids):
        """
        This function will loop through a list of am uuids and remove each one
        """

        removed_servers = []
        for uuid in am_uuids:
            removed_servers.append(self.remove_active_model(uuid))

        return removed_servers

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
