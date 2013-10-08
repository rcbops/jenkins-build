#! /usr/bin/env python
import sys
import argh
from chef import Environment
from modules.Config import Config
from modules.rpcsqa_helper import rpcsqa_helper
from modules.Deployments import ChefRazorDeployment


@argh.arg('-f', "--features", nargs="+", type=str)
def destroy(name="autotest", os="precise", branch="grizzly",
            razor_ip="198.101.133.3", features=[]):
    features = features or ['default']
    print "Destroying your cloud now!!!"
    qa = rpcsqa_helper()
    env = qa.prepare_environment(name,
                                 os,
                                 branch,
                                 features,
                                 branch)
    qa.cleanup_environment(env)
    qa.delete_environment(env)


def test(environment="autotest-precise-grizzly-glance-cf",
         log_level="error"):
    """
    Tests an openstack cluster with tempest
    """
    qa = rpcsqa_helper()
    env = Environment(environment)
    if 'remote_chef' in env.override_attributes:
        api = qa.remote_chef_client(environment)
        env = Environment(environment, api=api)
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
            print "Updating tempest cookbooks"
            qa.update_tempest_cookbook(env)
            print "Running chef-client"
            qa.run_chef_client(controller, num_times=2,
                               log_level=log_level)
            cmd = "python /opt/tempest/tools/install_venv.py"
            qa.run_command_on_node(controller, cmd)
    qa.feature_test(controllers[0], environment)

    # if len(controllers) > 1:
    #     for i, controller in enumerate(controllers):
    #         qa.disable_controller(controller)
    #         time.sleep(180)
    #         qa.test(controller[0], environment)
    #         qa.enable_controller(controller)


def v3(name="precise-default", branch="grizzly", template_path=None,
       config=None):
    config = Config(config)
    deployment = ChefRazorDeployment.fromfile(name, branch, config,
                                              template_path)
    print deployment

if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([v3])
    parser.dispatch()
