#Environments and features in json

base_env = {
    "name": "<NAME>", "description": "",
    "cookbook_versions": {}, "json_class": "Chef::Environment",
    "chef_type": "environment", "default_attributes": {},
    "override_attributes": {
        "package_component": "<PACKAGE_COMPONENT>",
        "keystone": {
            "admin_user": "admin",
            "users": {"demo": {"roles": {"Member": ["demo"]}, "default_tenant": "demo", "password": "ostackdemo"},
                      "admin": {"roles": {"admin": ["admin", "demo"]}, "password": "ostackdemo"}},
            "tenants": ["admin", "service", "demo"]
        },
        "monitoring": {"metric_provider": "collectd", "procmon_provider": "monit"},
        "mysql": {"root_network_acl": "%", "allow_remote_root": True},
        "nova": {
            "apply_patches": True,
            "networks": {"public": {"num_networks": "1", "bridge": "br0", "label": "public", "dns1": "8.8.8.8",
                          "dns2": "8.8.4.4", "bridge_dev": "eth1", "network_size": "254", "ipv4_cidr": "172.31.0.0/24", 
                          "label":"public"}}
        },
        "osops": {"apply_patches": True},
        "developer_mode": False,
        "osops_networks": {"management": "198.101.133.0/24", "nova": "198.101.133.0/24", "public": "198.101.133.0/24"},
        "glance": {"image_upload": True, "images": ["cirros", "precise"]}
    }
}

openldap = {
    "keystone": {
        "debug": "True",
        "auth_type": "ldap",
        "ldap": {
            "user_mail_attribute": "mail",
            "user_enabled_emulation": "True",
            "user_tree_dn": "ou=Users,dc=rcb,dc=me",
            "user_attribute_ignore": "tenantId",
            "tenant_enabled_emulation": "True",
            "url": "ldap://<LDAP_IP>",
            "user": "cn=admin,dc=rcb,dc=me",
            "role_objectclass": "organizationalRole",
            "tenant_objectclass": "groupOfNames",
            "group_attribute_ignore": "enabled",
            "tenant_attribute_ignore": "tenantId",
            "tenant_tree_dn": "ou=Groups,dc=rcb,dc=me",
            "allow_subtree_delete": "false",
            "password": "<LDAP_ADMIN_PASS>",
            "suffix": "dc=rcb,dc=me",
            "user_objectclass": "inetOrgPerson",
            "domain_attribute_ignore": "enabled",
            "use_dumb_member": "True",
            "role_tree_dn": "ou=Roles,dc=rcb,dc=me"
        },
        "admin_user": "admin",
        "users": {"demo": {"roles": {"Member": ["demo"]}, "default_tenant": "demo", "password": "ostackdemo"},
                  "admin": {"roles": {"admin": ["admin", "demo"]}, "password": "ostackdemo"}},
        "tenants": ["admin", "service", "demo"]
    }
}


ha = { "vips": {
          "mysql-db": "198.101.133.154",
          "rabbitmq-queue": "198.101.133.155",
          "cinder-api": "198.101.133.156", "glance-api": "198.101.133.156",
          "glance-registry": "198.101.133.156", "horizon-dash": "198.101.133.156",
          "horizon-dash_ssl": "198.101.133.156", "keystone-admin-api": "198.101.133.156",
          "keystone-internal-api": "198.101.133.156", "keystone-service-api": "198.101.133.156",
          "nova-api": "198.101.133.156", "nova-ec2-public": "198.101.133.156", 
          "nova-novnc-proxy": "198.101.133.156", "nova-xvpvnc-proxy": "198.101.133.156", 
          "swift-proxy": "198.101.133.156",
          "config": {
            "198.101.133.154": { "vrid": 10, "network": "public" },
            "198.101.133.155": { "vrid": 11, "network": "public" },
            "198.101.133.156": { "vrid": 12, "network": "public" }
          }
        }
    }


"""
This class will build a environment based of of features that are enabled
"""


class Environment(object):
    """
    Represents a RCBOPS Chef Environment
    @param name The name of the chef environment
    @type name String
    @param description A description of what the environment is (LDAP, HA, etc.)
    @type description String
    @param cookbook_versions The version of cookbooks that are being used
    @type cookbook_versions dict
    @type json_class
    """
    def __init__(self, name=None, description=None, cookbook_versions=None,
                 json_class="Chef::Environment", chef_type="environment",
                 default_attributes=None, override_attributes=None):
        self.name = name
        self.description = description
        self.cookbook_versions = cookbook_versions
        self.json_class = json_class
        self.chef_type = chef_type
        self.default_attributes = default_attributes
        self.override_attributes = override_attributes


class DefaultAttributes(object):
    def __init__(self):
        raise(NotImplementedError)


class OverrideAttributes(object):
    """
    """

    def __init__(self, package_component=None, keystone=None, monitoring=None,
                 mysql=None, nova=None, osops=None, horizon=None,
                 developer_mode=False, osops_networks=None, glance=None):
        self.package_component = package_component
        self.keystone = keystone
        self.monitoring = monitoring
        self.mysql = mysql
        self.nova = nova
        self.osops = osops
        self.horizon = horizon
        self.developer_mode = developer_mode
        self.osops_networks = osops_networks
        self.glance = glance


class NovaAttributes(object):
    """
    """

    def __init__(self, apply_patches=False, network=None, networks=None):
        self.apply_patches = apply_patches
        self.network = network
        self.networks = networks


class NovaNetworkAttributes(object):
    """
    """

    def __init__(self, dmz_cidr=None, fixed_range=None):
        self.dmz_cidr = dmz_cidr
        self.fixed_range = fixed_range


class NovaNetworksAttributes(list):
    """
    """

    def __init__(self, networks=None):
        super(NovaNetworksAttributes, self).__init__()
        self.extend(networks)


class NetworkAttributes(object):
    def __init__(self, num_networks=None, bridge=None, label=None,
                 dns1=None, dns2=None, bridge_dev=None, network_size=None,
                 ipv4_cidr=None):
        self.num_networks = num_networks
        self.bridge = bridge
        self.label = label
        self.dns1 = dns1
        self.dns2 = dns2
        self.bridge_dev = bridge_dev
        self.network_size = network_size
        self.ipv4_cidr = ipv4_cidr


class KeystoneAttributes(object):
    """
    "keystone": {
        "debug": "True",
        "auth_type": "ldap",
        "ldap": {
            "user_mail_attribute": "mail",
            "user_enabled_emulation": "True",
            "user_tree_dn": "ou=Users,dc=rcb,dc=me",
            "user_attribute_ignore": "tenantId",
            "tenant_enabled_emulation": "True",
            "url": "ldap://<LDAP_IP>",
            "user": "cn=admin,dc=rcb,dc=me",
            "role_objectclass": "organizationalRole",
            "tenant_objectclass": "groupOfNames",
            "group_attribute_ignore": "enabled",
            "tenant_attribute_ignore": "tenantId",
            "tenant_tree_dn": "ou=Groups,dc=rcb,dc=me",
            "allow_subtree_delete": "false",
            "password": "<LDAP_ADMIN_PASS>",
            "suffix": "dc=rcb,dc=me",
            "user_objectclass": "inetOrgPerson",
            "domain_attribute_ignore": "enabled",
            "use_dumb_member": "True",
            "role_tree_dn": "ou=Roles,dc=rcb,dc=me"
        },
        "admin_user": "admin",
        "users": {"demo": {"roles": {"Member": ["demo"]}, "default_tenant": "demo", "password": "ostackdemo"},
                  "admin": {"roles": {"admin": ["admin", "demo"]}, "password": "ostackdemo"}},
        "tenants": ["admin", "service", "demo"]
    }
    """
    def __init__(self, admin_user=None, users=None, tenants=None,
                 debug=False, auth_type=None, ldap=None):
        self.admin_user = admin_user
        self.users = users
        self.tenants = tenants
        self.debug = debug
        self.auth_type = auth_type
        self.ldap = ldap


class Users(object):
    """
    "users": {
        "demo": {
          "roles": {
            "Member": [
              "demo"
            ]
          },
          "default_tenant": "demo",
          "password": "ostackdemo"
        },
        "admin": {
          "roles": {
            "admin": [
              "admin",
              "demo"
            ]
          },
          "password": "ostackdemo"
        }
      }
    """

    def __init__(self, users=None):
        super(Users, self).__init__()
        self.extend(users)


class User(object):
    """
    "demo": {
      "roles": {
        "Member": [
          "demo"
        ]
      },
      "default_tenant": "demo",
      "password": "ostackdemo"
    }
    """

    def __init__(self, roles=None, default_tenant=None, password=None):
        self.roles = roles
        self.default_tenant = default_tenant
        self.password = password


class Roles(object):
    """
    "roles": {
        "admin": [
          "admin",
          "demo"
        ]
      }
    """
    def __init__(self, roles=None):
        super(Roles, self).__init__()
        self.extend(roles)


class Role(object):
    """
     "admin": ["admin", "demo"]
    """

    def __init__(self, role=None):
        super(Role, self).__init__()
        self.extend(role)


class Ldap(object):
    """
    "ldap": {
            "user_mail_attribute": "mail",
            "user_enabled_emulation": "True",
            "user_tree_dn": "ou=Users,dc=rcb,dc=me",
            "user_attribute_ignore": "tenantId",
            "tenant_enabled_emulation": "True",
            "url": "ldap://<LDAP_IP>",
            "user": "cn=admin,dc=rcb,dc=me",
            "role_objectclass": "organizationalRole",
            "tenant_objectclass": "groupOfNames",
            "group_attribute_ignore": "enabled",
            "tenant_attribute_ignore": "tenantId",
            "tenant_tree_dn": "ou=Groups,dc=rcb,dc=me",
            "allow_subtree_delete": "false",
            "password": "<LDAP_ADMIN_PASS>",
            "suffix": "dc=rcb,dc=me",
            "user_objectclass": "inetOrgPerson",
            "domain_attribute_ignore": "enabled",
            "use_dumb_member": "True",
            "role_tree_dn": "ou=Roles,dc=rcb,dc=me"
        }
    """

    def __init__(self,
                 user_mail_attribute=None,
                 user_enabled_emulation=None,
                 user_tree_dn=None,
                 user_attribute_ignore=None,
                 tenant_enabled_emulation=None,
                 url=None,
                 user=None,
                 role_objectclass=None,
                 tenant_objectclass=None,
                 group_attribute_ignore=None,
                 tenant_attribute_ignore=None,
                 tenant_tree_dn=None,
                 allow_subtree_delete=None,
                 password=None,
                 suffix=None,
                 user_objectclass=None,
                 domain_attribute_ignore=None,
                 use_dumb_member=None,
                 role_tree_dn=None):

        self.user_mail_attribute = user_mail_attribute
        self.user_enabled_emulation = user_enabled_emulation
        self.user_tree_dn = user_tree_dn
        self.user_attribute_ignore = user_attribute_ignore
        self.tenant_enabled_emulation = tenant_enabled_emulation
        self.url = url
        self.user = user
        self.role_objectclass = role_objectclass
        self.tenant_objectclass = tenant_objectclass
        self.group_attribute_ignore = group_attribute_ignore
        self.tenant_attribute_ignore = tenant_attribute_ignore
        self.tenant_tree_dn = tenant_tree_dn
        self.allow_subtree_delete = allow_subtree_delete
        self.password = password
        self.suffix = suffix
        self.user_objectclass = user_objectclass
        self.domain_attribute_ignore = domain_attribute_ignore
        self.use_dumb_member = use_dumb_member
        self.role_tree_dn = role_tree_dn


class Monitoring(object):
    """
    "monitoring": {"metric_provider": "collectd", "procmon_provider": "monit"}
    """

    def __init__(self, metric_provider=None, procmon_provider=None):
        self.metric_provider=metric_provider
        self.procmon_provider=procmon_provider


class Mysql(object):
    """
    "mysql": {"root_network_acl": "%", "allow_remote_root": True}
    """

    def __init__(self, root_network_acl=None, allow_remote_root=None):
        self.root_network_acl = root_network_acl
        self.allow_remote_root = allow_remote_root


class Osops(object):
    """
    "osops": {"apply_patches": True}
    """

    def __init__(self, apply_patches=None):
        self.apply_patches = apply_patches


class Horizon(object):
    """
    "horizon": {"theme": "Rackspace"}
    """

    def __init__(self, theme=None):
        self.theme = theme


class Glance(object):
    """
    "glance": {
      "api": {
            "default_store": "swift",
            "swift_store_user": "<TENANT_ID>:<TENANT_NAME>",
            "swift_store_key": "<TENANT_PASSWORD>",
            "swift_store_auth_version": "2",
              "swift_store_auth_address": "https://identity.api.rackspacecloud.com/v2.0"
        },
      "image_upload": true,
      "images": [
        "cirros",
        "precise"
      ]
    }
    """

    def __init__(self, api=None, image_upload=None, images=None):
        self.api = api
        self.image_upload = image_upload
        self.images = images


class GlanceApi(object):
    """
    "api": {
            "default_store": "swift",
            "swift_store_user": "<TENANT_ID>:<TENANT_NAME>",
            "swift_store_key": "<TENANT_PASSWORD>",
            "swift_store_auth_version": "2",
              "swift_store_auth_address": "https://identity.api.rackspacecloud.com/v2.0"
        }
    """

    def __init__(self, default_store=None, swift_store_user=None,
                 swift_store_key=None, swift_store_auth_version=None,
                 swift_store_auth_address=None):
        self.default_store = default_store
        self.swift_store_user = swift_store_user
        self.swift_store_key = swift_store_key
        self.swift_store_auth_version = swift_store_auth_version
        self.swift_store_auth_address = swift_store_auth_address


class Images(list):
    """
    "images": ["cirros","precise"]
    """

    def __init__(self, image=None):
        super(Images, self).__init__()
        self.extend(image)
