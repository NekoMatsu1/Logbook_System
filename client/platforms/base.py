import logging

class Adapter:
    def __init__(self, simulation=True):
        self.simulation = simulation

    def action(self, name):
        if self.simulation:
            logging.warning('SIMULATION: intended OS %s; no power command executed', name)
            return
        self.real_action(name)

    def attach_signout(self, root, callback):
        return False
