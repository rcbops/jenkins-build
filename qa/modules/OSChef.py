class OSChef:
    def __init__(self, api):
	self.api = api or autoconfigure

    def node_search(self, query=None, api=None, tries=10):
	api = api or self.chef
	search = None
	while not search and tries > 0:
	    search = Search("node", api=api).query(query)
	    time.sleep(10)
	    tries = tries - 1
	return (n.object for n in search)
