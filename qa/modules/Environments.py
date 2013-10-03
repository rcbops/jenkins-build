"""
OpenStack Environments
"""


class Environment(object):

    def __init__(self, name, description):
        self.name = name
        self.description = description

    def __repr__(self):
        """ print current instace of class
        """
        outl = 'class :' + self.__class__.__name__
        for attr in self.__dict__:
            outl += '\n\t' + attr + ' : ' + str(getattr(self, attr))
