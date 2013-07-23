from opencenterclient.client import OpenCenterEndpoint
import StringIO
from chef import Search, Node, rsa, ChefAPI
import sys

env_format = "%s-%s-opencenter"


# Make sure environment exists
def validate_environment(chef, name='test', os='ubuntu'):
    env = env_format % (name, os)
    if not Search("environment").query("name:%s" % env):
        print "environment %s not found" % env
        sys.exit(1)


# Return client endpoint of opencenter server
def opencenter_endpoint(chef, name='test', os='ubuntu'):
    validate_environment(chef, name=name, os=os)
    env = env_format % (name, os)
    query = "in_use:\"server\" AND chef_environment:%s" % env
    server = next(Node(node['name']) for node in
                  Search('node').query(query))
    ep_url = "https://%s:8443" % server['ipaddress']
    return OpenCenterEndpoint(ep_url,
                              user="admin",
                              password="password")


# Return IP of openstack cluster endpoints inside opencenter
def openstack_endpoints(opencenter_endpoint):
    ep = opencenter_endpoint
    infrastructure_nodes = ep.nodes.filter('name = "Infrastructure"')
    for node_id in infrastructure_nodes.keys():
        ha = infrastructure_nodes[node_id].facts["ha_infra"]
        endpoint = None
        if ha:
            endpoint = infrastructure_nodes[node_id].facts["nova_api_vip"]
        else:
            name = next(node.name for node in ep.nodes
                        if "nova-controller" in node.facts["backends"])
            endpoint = Node(name)['ipaddress']
        return endpoint


def opencenter_chef(opencenter_endpoint):
    ep = opencenter_endpoint
    filter = 'facts.chef_server_uri != None and facts.chef_server_pem != None'
    chef_node = ep.nodes.filter(filter).first()
    pem = chef_node['facts']['chef_server_client_pem']
    key = rsa.Key(StringIO.StringIO(pem))
    url = chef_node['facts']['chef_server_uri']
    name = chef_node['facts']['chef_server_client_name']
    return ChefAPI(url, key, name)
