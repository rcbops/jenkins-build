from chef import autoconfigure

class chef_api:

    def __init__(self, local=None, remote=None):
	self.local = local or autoconfigure()
	self.remote = remote
