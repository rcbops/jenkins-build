"""Gathers application config"""

import os
import logging
from yaml import load


class Config(object):
    """Application config object"""
    def __init__(self, file=None):
        if not file:
            file = os.path.join(os.path.dirname(__file__),
                                os.pardir,
                                'config.yaml')
        f = open(file)
        self.config = load(f)

    def __getitem__(self, name):
        return self.config[name]
