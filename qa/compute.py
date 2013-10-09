#! /usr/bin/env python
import argh
from modules.Config import Config
from modules.Deployments import ChefRazorDeployment


def v3(name="precise-default", branch="grizzly", template_path=None,
       config=None):
    config = Config(config)
    deployment = ChefRazorDeployment.fromfile(name,
                                              branch,
                                              config,
                                              template_path)
    print deployment

if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([v3])
    parser.dispatch()
