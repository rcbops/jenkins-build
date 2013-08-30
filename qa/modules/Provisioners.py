class Provisioner():
    def tear_down(self):
        raise NotImplementedError


class RazorProvisioner(Provisioner):
    def __init__(self, razor, id):
        self.razor = razor
        self._id = id

    def tear_down(self):
        self.razor.remove_active_model(self._id)

    def get_password(self):
        return self.razor.get_active_model_pass(self._id)['password']
