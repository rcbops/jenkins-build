"""Gathers application config"""

import os
from yaml import load


class OSConfig(object):
    """Application config object"""
    def __init__(self, file=None):
        if not file:
            file = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                                os.pardir,
                                                'config.yaml'))
        f = open(file)
        self.config = load(f)

    def __getitem__(self, name):
        return self.config[name]

if __name__ == "__main__":
    OSConfig()
    print OSConfig()['features']
