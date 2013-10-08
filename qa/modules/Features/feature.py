"""
Base Feature
"""

class Feature(object):
    """ Represents a OpenStack Feature
    """

    def __init__(self, config=None):
        self.config = config

    def __repr__(self):
        """ print current instace of class
        """
        feature = 'Feature  {0}:'.format(self.__class__.__name__)
        return feature

    def update_environment(self):
        pass

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass
