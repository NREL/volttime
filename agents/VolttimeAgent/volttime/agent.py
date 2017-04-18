"""
NREL volttime agent

"""

from __future__ import absolute_import

from datetime import datetime
import logging
import sys
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
import json
import os
import time

from . import settings

import random
import itemc

import simpy
from datetime import timedelta
from functools import partial

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)

class VolttimeAgent(Agent):
    '''Listens to everything and publishes a heartbeat according to the
    heartbeat period specified in the settings module.
    '''

    def __init__(self, config_path, **kwargs):
        super(VolttimeAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.path = os.path.join(os.environ['ITEMC_DATA_HOME'], os.environ['ITEMC_FR'])
        itemc_handle = itemc.Itemc(data=self.path, working_dir=".")
        # publish every second
        self.df = itemc_handle.df.resample(rule='1S', fill_method='ffill').reset_index()
        self.vtime_start = time.strptime(settings.VTIME_START, "%Y-%m-%d %H:%M:%S")
        self.vtime_stop = time.strptime(settings.VTIME_STOP, "%Y-%m-%d %H:%M:%S")
        self.index = 0

        current_data = self.df.ix[self.index]
        timestamp=time.strptime(str(current_data['index']),"%Y-%m-%d %H:%M:%S")
        while(timestamp < self.vtime_start):
            self.index += 1
            current_data = self.df.ix[self.index]
            timestamp=time.strptime(str(current_data['index']),"%Y-%m-%d %H:%M:%S")


    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']

    @Core.periodic(settings.HEARTBEAT_PERIOD)
    def publish_heartbeat(self):
        if self.index <= len(self.df):
            try:
                current_data = self.df.ix[self.index]
                timestamp=time.strptime(str(current_data['index']),"%Y-%m-%d %H:%M:%S")

                # should start right away bc self.index ---> vtime_start
                if(timestamp>=self.vtime_start and  timestamp<=self.vtime_stop):
                    # Every 1 second...
                    if ((timestamp.tm_sec)%1 == 0 and (timestamp.tm_min)%1 == 0):

                        headers = {
                            'AgentID': self._agent_id,
                            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                            headers_mod.DATE: utils.get_aware_utc_now().isoformat(' ') + 'Z',
                        }

                        value = {}
                        value['timestamp'] = {'Readings': str(current_data['index']),'Units':'ts'}
                        self.vip.pubsub.publish('pubsub', 'datalogger/log/volttime', headers, value)


                self.index += 1
            except KeyError:
                pass



def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(VolttimeAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':

    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
