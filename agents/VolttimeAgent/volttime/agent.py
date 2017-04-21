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

import pandas as pd


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
        self.index = 0
        self.json_time = {'timeseries' : []}
        self.starttime = settings.VTIME_START
        self.endtime = settings.VTIME_STOP
        et = pd.to_datetime(self.endtime)
        st = pd.to_datetime(self.starttime)
        self.json_time['timeseries'].append(st)
        while st< et:
            st  =  st + timedelta(0,1)
            self.json_time['timeseries'].append(st)



    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']

    @Core.periodic(settings.HEARTBEAT_PERIOD)
    def publish_heartbeat(self):
        if self.index <= len(self.json_time['timeseries']):
            try:
                headers = {
                    'AgentID': self._agent_id,
                    headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                    headers_mod.DATE: utils.get_aware_utc_now().isoformat(' ') + 'Z',
                }

                value = {}
                value['timestamp'] = {'Readings': str(self.json_time['timeseries'][self.index]),'Units':'ts'}
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
