#! /usr/bin/env python
import sys
import argh
import traceback
from modules.Config import Config
from modules.Deployments import ChefRazorDeployment


def v3(name="precise-default", branch="grizzly", template_path=None,
       config=None, destroy=True):
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

if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([v3])
    parser.dispatch()
