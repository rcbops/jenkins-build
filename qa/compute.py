#! /usr/bin/env python

"""
Command Line interface for Building Openstack clasuters
"""

import sys
import argh
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
    util.logger.info(deployment)

    try:
        deployment.build()
    except Exception:
        util.logger.error(traceback.print_exc())
        deployment.destroy()
        sys.exit(1)

    util.logger.info(deployment)
    if destroy:
        deployment.destroy()


def destroy(name="precise-default", config=None):
    config = Config(config)
    deployment = ChefRazorDeployment.from_chef_environment(name, config)
    print deployment
    # deployment.destroy()


if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy])
    parser.dispatch()
