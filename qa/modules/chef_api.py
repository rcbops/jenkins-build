from chef import autoconfigure

class chef_api:

    def __init__(self, local=None, remote=None, server=None):
        self.local = local or autoconfigure()
        self.remote = remote
        self.api = remote or local
        self.server = server

    def __setattr__(self, item, value):
        """
        Keep api current with which to use
        """
        self.__dict__[item] = value
        if item == "remote":
            self.api = self.remote

    def __str__(self):
        return ("local:{0} - remote:{1} - "
                "api:{2} - server:{3}").format(self.local, self.remote,
                                               self.api, self.server)
