"""
Example Control Agent

April 2016
NREL

"""

from __future__ import absolute_import
from datetime import datetime
import logging
import sys
import time
import random
import json
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod
from . import settings

import time
from datetime import datetime as dt
from time import mktime
import pytz


utils.setup_logging()
_log = logging.getLogger(__name__)

class TestAgent(Agent):
    '''
    Publishes example control signals to control the Thermostat Relay
    '''
    def __init__(self, config_path, **kwargs):
        ''' TestAgent initialization function'''
        super(TestAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.volttime = ""

    @Core.receiver('onsetup')
    def setup(self, sender, **kwargs):
        '''Test setup function'''
        # Demonstrate accessing a value from the config file
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        self.cea_ctl = ['emergency','normal','shed']
        self.tasks = 100


    @Core.receiver('onstart')
    def begining(self, sender, **kwargs):
        '''on start'''
        pass

    @Core.receiver('onstop')
    def ending(self, sender, **kwargs):
        ''' at the end'''
        pass

    @PubSub.subscribe('pubsub', 'datalogger/log/volttime')
    def match_all(self, peer, sender, bus, topic, headers, message):
        '''
            Subscribe to volttime and synchronize
        '''
        # self.task = self.task + 1
        str_time = message['timestamp']['Readings']
        timestamp = time.strptime(str_time, "%Y-%m-%d %H:%M:%S")
        self.volttime = message['timestamp']['Readings']
        value_db = self.vip.rpc.call('platform.d.actuator','get_point',"fake/PowerState").get()
        headers = {
            'AgentID': self._agent_id,
            headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
            headers_mod.DATE: datetime.now().isoformat(' ') + 'Z',
        }
        # publish cooling_setpoint from itemc
        value = {'PowerState':  { 'Readings': value_db, 'Units': 'KW' },
                 'timestamp': { 'Readings': message['timestamp']['Readings'],
                                   'Units': 'ts'}}
        self.vip.pubsub.publish('pubsub', 'datalogger/log/fake/State', headers, value)

        if (timestamp.tm_sec % 20) == 0 and (timestamp.tm_min % 1) == 0:
            headers = {
                'AgentID': self._agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                headers_mod.DATE: datetime.now().isoformat(' ') + 'Z',
            }
            query = {}
            name = ""
            msg = {}
            start_time = self.volttime
            timestamp=time.strptime(start_time,"%Y-%m-%d %H:%M:%S")
            end_time = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.mktime(timestamp) + 10))
            st= time.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            st = dt.fromtimestamp(mktime(st))
            start_time = str(pytz.utc.localize(st))
            et= time.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            et = dt.fromtimestamp(mktime(et))
            end_time = str(pytz.utc.localize(et))
            msgs = [
                        ["fake", #First time slot.
                         start_time,     #Start of time slot.
                         end_time]   #End of time slot.
                    ]

                    #     "campus": "campus",
                        # "building": "building",
                        # "unit": "fake_device",
            self.tasks = self.tasks + 1
            print "tasks being scheduled : ",self.tasks
            print self.vip.rpc.call('platform.d.actuator','request_new_schedule','rpc_ctl',str(self.tasks),'LOW',msgs).get()
            # print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fake/PowerState",12).get()
            #
            # print "Tasks being cancelled : ",self.tasks
            #
            # print self.vip.rpc.call('platform.d.actuator','request_cancel_schedule','rpc_ctl',str(self.tasks)).get()
            # print "successfully cancelled task"
            # print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fakedriver/fake/PowerState",13).get()
            value = {'Lock':  { 'Readings': 1, 'Units': 'KW' },
                     'timestamp': { 'Readings': message['timestamp']['Readings'],
                                       'Units': 'ts'}}
            self.vip.pubsub.publish('pubsub', 'datalogger/log/Controller/Lock', headers, value)

        if (timestamp.tm_sec % 21) == 0 and (timestamp.tm_min % 1) == 0:
            headers = {
                'AgentID': self._agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                headers_mod.DATE: datetime.now().isoformat(' ') + 'Z',
            }
            query = {}
            name = ""
            msg = {}
            start_time = self.volttime
            timestamp=time.strptime(start_time,"%Y-%m-%d %H:%M:%S")
            end_time = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.mktime(timestamp) + 10))
            st= time.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            st = dt.fromtimestamp(mktime(st))
            start_time = str(pytz.utc.localize(st))
            et= time.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            et = dt.fromtimestamp(mktime(et))
            end_time = str(pytz.utc.localize(et))
            msgs = [
                        ["fake", #First time slot.
                         start_time,     #Start of time slot.
                         end_time]   #End of time slot.
                    ]

                    #     "campus": "campus",
                        # "building": "building",
                        # "unit": "fake_device",
            # self.tasks = self.tasks + 1
            # print "tasks being scheduled : ",self.tasks
            # print self.vip.rpc.call('platform.d.actuator','request_new_schedule','rpc_ctl',str(self.tasks),'LOW',msgs).get()
            temps = random.randint(1,100)
            print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fake/PowerState",temps).get()

            # print "Tasks being cancelled : ",self.tasks
            #
            # print self.vip.rpc.call('platform.d.actuator','request_cancel_schedule','rpc_ctl',str(self.tasks)).get()
            # print "successfully cancelled task"
            # print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fakedriver/fake/PowerState",13).get()
            value = {'PowerState':  { 'Readings': temps, 'Units': 'KW' },
                     'timestamp': { 'Readings': message['timestamp']['Readings'],
                                       'Units': 'ts'}}
            self.vip.pubsub.publish('pubsub', 'datalogger/log/fake/Set', headers, value)


        if (timestamp.tm_sec % 22) == 0 and (timestamp.tm_min % 1) == 0:
            headers = {
                'AgentID': self._agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                headers_mod.DATE: datetime.now().isoformat(' ') + 'Z',
            }
            query = {}
            name = ""
            msg = {}
            start_time = self.volttime
            timestamp=time.strptime(start_time,"%Y-%m-%d %H:%M:%S")
            end_time = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.mktime(timestamp) + 10))
            st= time.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            st = dt.fromtimestamp(mktime(st))
            start_time = str(pytz.utc.localize(st))
            et= time.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            et = dt.fromtimestamp(mktime(et))
            end_time = str(pytz.utc.localize(et))
            msgs = [
                        ["fake", #First time slot.
                         start_time,     #Start of time slot.
                         end_time]   #End of time slot.
                    ]

                    #     "campus": "campus",
                        # "building": "building",
                        # "unit": "fake_device",
            # self.tasks = self.tasks + 1
            # print "tasks being scheduled : ",self.tasks
            # print self.vip.rpc.call('platform.d.actuator','request_new_schedule','rpc_ctl',str(self.tasks),'LOW',msgs).get()
            # print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fake/PowerState",12).get()

            print "Tasks being cancelled : ",self.tasks

            print self.vip.rpc.call('platform.d.actuator','request_cancel_schedule','rpc_ctl',str(self.tasks)).get()
            print "successfully cancelled task"
            value = {'Lock':  { 'Readings': 0, 'Units': 'KW' },
                     'timestamp': { 'Readings': message['timestamp']['Readings'],
                                       'Units': 'ts'}}
            self.vip.pubsub.publish('pubsub', 'datalogger/log/Controller/Lock', headers, value)
            # print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fakedriver/fake/PowerState",13).get()

        if (timestamp.tm_sec % 23) == 0 and (timestamp.tm_min % 1) == 0:
            headers = {
                'AgentID': self._agent_id,
                headers_mod.CONTENT_TYPE: headers_mod.CONTENT_TYPE.PLAIN_TEXT,
                headers_mod.DATE: datetime.now().isoformat(' ') + 'Z',
            }
            query = {}
            name = ""
            msg = {}
            start_time = self.volttime
            timestamp=time.strptime(start_time,"%Y-%m-%d %H:%M:%S")
            end_time = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.mktime(timestamp) + 10))
            st= time.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            st = dt.fromtimestamp(mktime(st))
            start_time = str(pytz.utc.localize(st))
            et= time.strptime(end_time, "%Y-%m-%d %H:%M:%S")
            et = dt.fromtimestamp(mktime(et))
            end_time = str(pytz.utc.localize(et))
            msgs = [
                        ["fake", #First time slot.
                         start_time,     #Start of time slot.
                         end_time]   #End of time slot.
                    ]

                    #     "campus": "campus",
                        # "building": "building",
                        # "unit": "fake_device",
            # self.tasks = self.tasks + 1
            # print "tasks being scheduled : ",self.tasks
            # print self.vip.rpc.call('platform.d.actuator','request_new_schedule','rpc_ctl',str(self.tasks),'LOW',msgs).get()
            # print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fake/PowerState",12).get()
            #
            # print "Tasks being cancelled : ",self.tasks
            #
            # print self.vip.rpc.call('platform.d.actuator','request_cancel_schedule','rpc_ctl',str(self.tasks)).get()
            # print "successfully cancelled task"
            temps = random.randint(1,100)
            try:
                print self.vip.rpc.call('platform.d.actuator','set_point','rpc_ctl',"fakedriver/fake/PowerState",temps).get()
            except :
                print "Can't set point, You don't have this lock"
                
            value = {'PowerState':  { 'Readings': temps, 'Units': 'KW' },
                     'timestamp': { 'Readings': message['timestamp']['Readings'],
                                       'Units': 'ts'}}
            self.vip.pubsub.publish('pubsub', 'datalogger/log/fake/Set', headers, value)


def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(TestAgent)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
