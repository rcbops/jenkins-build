#! /usr/bin/env python

"""
Command Line interface for Building Openstack clasuters
"""

import sys
import argh
import logging
import traceback
from modules import util
from modules.Config import Config
from modules.Deployments import ChefRazorDeployment


def build(name="precise-default", branch="grizzly", template_path=None,
          config=None, destroy=True):
    """
    Builds an OpenStack Cluster
    """

    config = Config(config)
    deployment = ChefRazorDeployment.fromfile(name,
                                              branch,
                                              config,
                                              template_path)
    print deployment

    try:
        deployment.build()
    except Exception:
        print traceback.print_exc()
        deployment.destroy()
        sys.exit(1)

    if destroy:
        deployment.destroy()


def destroy():
    pass


if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build])
    parser.dispatch()
