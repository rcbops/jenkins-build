from time import sleep
from ssh_helper import run_cmd
from razor_api import razor_api
from modules.OSConfig import OSConfig as config


class OSRazor:
    def __init__(self, url=None):
        url = url or config['razor']['url']
        self.api = razor_api(url)

    def razor_password(self, id):
        return self.api.get_active_model_pass(id)['password']

    def remove_broker_fail(self, policy):
        active_models = self.razor.simple_active_models(policy)
        for active in active_models:
            data = active_models[active]
            if 'broker_fail' in data['current_state']:
                print "!!## -- Removing active model  (broker_fail) -- ##!!"
                password = self.razor_password(data['am_uuid'])
                ip = data['eth1_ip']
                user = "root"
                run = run_cmd(ip, 'reboot 0', user=user, passowrd=password)
                if run['success']:
                    self.razor.remove_active_model(data['am_uuid'])
                    sleep(15)
                else:
                    print "!!## -- Trouble removing broker fail -- ##!!"
                    print run
