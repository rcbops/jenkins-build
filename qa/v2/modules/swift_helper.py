#!/usr/bin/python

'''
Swift helper module
'''

class swift_helper:

    def __init__(self, repo_tag=None, keystone_ip=None):
        """
        Basic swift cluster information and objects
        """

        self.cookbooks = [
            {
                "url": "https://github.com/rcbops-cookbooks/swift-private-cloud.git",
                "branch": "master",
                "tag": repo_tag
            }
        ]

        self.roles = {
            "controller": "spc-starter-controller",
            "proxy": "spc-starter-proxy",
            "storage": "spc-starter-storage"
        }

        self.keystone = {
            "keystone": {
                "swift_admin_url": 
                    "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(
                        keystone_ip),
                "swift_public_url": 
                    "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(
                        keystone_ip),
                "swift_internal_url": 
                    "http://{0}:8080/v1/AUTH_%(tenant_id)s".format(
                        keystone_ip),
                "auth_password": "secrete",
                "admin_password": "secrete"
            }
        }

    def __repr__(self):
        """
        Print out current instance of swift_helper
        """
        outl = 'class :' + self.__class__.__name__

        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))

        return outl
