#!/usr/bin/env python

import sys
import time
import argh
from chef import Environment
from modules.rpcsqa_helper import rpcsqa_helper


def main(environment="autotest-precise-grizzly-glance-cf",
         razor_ip="198.101.133.3", log_level="error"):
    qa = rpcsqa_helper(razor_ip=razor_ip)
    env = Environment(environment)
    if 'remote_chef' in env.override_attributes:
        api = qa.remote_chef_client(env)
        env = Environment(environment, api=api)
        qa.update_tempest_cookbook(env)
    else:
        api = qa.chef
    query = ("chef_environment:{0} AND "
             "(run_list:*ha-controller* OR "
             "run_list:*single-controller*)").format(environment)
    controllers = list(qa.node_search(query, api=api))
    if not controllers:
        print "No controllers in environment"
        sys.exit(1)

    for controller in controllers:
        if 'recipe[tempest]' not in controller.run_list:
            print "Adding tempest to controller run_list"
            controller.run_list.append('recipe[tempest]')
            controller.save()
            print "Running chef-client"
            qa.run_chef_client(controller, num_times=2,
                               log_level=log_level)
            cmd = "python /opt/tempest/tools/install_venv.py"
            qa.run_command_on_node(controller, cmd)
    qa.test(controllers[0], environment)

    # if len(controllers) > 1:
    #     for i, controller in enumerate(controllers):
    #         qa.disable_controller(controller)
    #         time.sleep(180)
    #         qa.test(controller[0], environment)
    #         qa.enable_controller(controller)

argh.dispatch_command(main)
