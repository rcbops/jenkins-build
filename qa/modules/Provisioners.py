from chef import autoconfigure, Search
from collections.abc import Iterable


class NodeFactory(Iterable):
    pass


class ChefRazorFactory(NodeFactory):
    def __init__(self, chef=None, razor=None, image="precise"):
        self.chef = chef or autoconfigure
        self.razor = razor or config.razor_ip
        self.image = image

    def next(self):
        in_image_pool = "name:qa-%s-pool*" % self.image
        is_default_environment = "chef_environment:_default"
        is_ifaced = """run_list:recipe\[network-interfaces\]"""
        query = "%s AND %s AND %s" % (in_image_pool,
                                      is_default_environment,
                                      is_ifaced)
        nodes =
