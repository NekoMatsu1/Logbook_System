"""Boot helper: no GUI, no student storage; supervises periods with no OS user session.

Run deliberately as SYSTEM/root using supplied startup templates. Never run alongside
another helper for the same machine. Interactive warnings belong to the desktop agent.
"""
import argparse
import json
import logging
import time
from .api import API
from .platforms import load
from .state import Timers
from .instance import acquire
from .credentials import load_config

class Helper:
    def __init__(self, api, adapter, clock=time.monotonic):
        self.api, self.adapter = api, adapter
        self.timers = Timers(clock)
        self.clock = clock
        self.present = True
        self.next_poll = 0
        self.confirmed = False
        self.last_warning = None

    def step(self):
        present = self.adapter.interactive_present()
        if present:
            self.present = True
            self.confirmed = False
            self.timers.reset()
            return
        if self.present:
            self.present = False
            self.timers.reset()
        if self.clock() >= self.next_poll:
            self.next_poll = self.clock()+10
            try:
                # Recheck before reporting OS absence.
                if self.adapter.interactive_present():
                    return
                reply = self.api.call('POST','/api/helper/absent',dict(confirmed_no_interactive_session=True))
                self.timers.configure(reply['settings'])
                self.confirmed = True
            except Exception as error:
                logging.warning('Helper communication failure: %s',error)
        if not self.confirmed:
            return  # Never power down before server settings have been loaded.
        action = self.timers.tick()
        countdown = self.timers.countdown()
        if countdown != self.last_warning:
            self.last_warning = countdown
            if countdown is not None:
                logging.warning('No OS user session: shutdown in %s seconds. Warning is service-log-only.',countdown)
        if action == 'shutdown' and not self.adapter.interactive_present():
            if not self.adapter.simulation:
                logging.error('Shutdown suppressed: secure OS greeter warning and mouse cancellation are not implemented')
                return
            try:
                self.api.call('POST','/api/events',dict(kind='helper_shutdown',detail='simulation' if self.adapter.simulation else 'requested without interactive session'))
            except Exception:
                logging.warning('Shutdown event not centrally acknowledged')
            self.adapter.action('shutdown')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',default='config/client.json')
    args = parser.parse_args()
    config = load_config(args.config)
    if type(config.get('simulation',True)) is not bool:
        raise ValueError('simulation must be a JSON boolean')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    instance_lock = acquire('helper')
    helper = Helper(API(config),load(config.get('simulation',True)))
    logging.warning('Helper started: %s', 'SIMULATION' if helper.adapter.simulation else 'LIVE')
    while True:
        try:
            helper.step()
        except Exception:
            logging.exception('Helper failed safely; no power action this cycle')
        time.sleep(1)

if __name__ == '__main__':
    main()
