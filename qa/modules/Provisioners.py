from chef import autoconfigure
from collections.abc import Iterable


class Provisioner(Iterable):
    pass


class ChefRazorProvisioner(Provisioner):
    def __init__(self, chef=None, razor=None):
	self.chef = chef or autoconfigure
	self.razor = razor or config.razor_ip
