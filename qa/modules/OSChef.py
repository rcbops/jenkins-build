import sys
from time import sleep
from chef import autoconfigure, Search


class OSChef:
    def __init__(self, api):
        self.api = api or autoconfigure()

    def node_search(self, query=None, api=None, tries=10):
        api = api or self.chef
        search = None
        while not search and tries > 0:
            search = Search("node", api=api).query(query)
            sleep(10)
            tries = tries - 1
        return (n.object for n in search)

    # Python 3 compatibility
    def __next__(self):
        return self.next()

    def next(self):
        in_image_pool = "name:qa-%s-pool*" % self.image
        is_default_environment = "chef_environment:_default"
        is_ifaced = """run_list:recipe\[network-interfaces\]"""
        query = "%s AND %s AND %s" % (in_image_pool,
                                      is_default_environment,
                                      is_ifaced)
        nodes = self.node_search(query)
        fails = 0
        try:
            yield next(nodes)
        except StopIteration:
            if fails > 10:
                print "No available chef nodes"
                sys.exit(1)
            fails += 1
            sleep(15)
            nodes = self.node_search(query)
