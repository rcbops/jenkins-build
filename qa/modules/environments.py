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
        "networks": [{"num_networks": "1", "bridge": "br0", "label": "public", "dns1": "8.8.8.8",
                      "dns2": "8.8.4.4", "bridge_dev": "eth1", "network_size": "254", "ipv4_cidr": "172.31.0.0/24"}]
        },
        "osops": {"apply_patches": True},
        "horizon": {"theme": "Rackspace"},
        "developer_mode": False,
        "osops_networks": {"management": "198.101.133.0/24", "nova": "198.101.133.0/24", "public": "198.101.133.0/24"},
        "glance": {"image_upload": True, "images": ["cirros", "precise"]}
    }
}

openldap = {"keystone": {
            "debug": "True",
            "auth_type": "ldap",
            "ldap": {
                "user_mail_attribute": "mail",
                "user_enabled_emulation": "True",
                "user_tree_dn": "ou=Users,dc=rcb,dc=me",
                "user_attribute_ignore": "tenantId,email",
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