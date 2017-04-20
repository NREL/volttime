"""

NREL modifed actuator to work with volttime


"""
__docformat__ = 'reStructuredText'

import collections
import datetime
import logging
import sys
from datetime import datetime as dt
from time import mktime

import pytz

import time
from actuator.scheduler import ScheduleManager

from tzlocal import get_localzone
from volttron.platform.agent import utils
from volttron.platform.jsonrpc import RemoteError
from volttron.platform.messaging import topics
from volttron.platform.messaging.utils import normtopic
from volttron.platform.vip.agent import Agent, Core, RPC, Unreachable, compat, PubSub


VALUE_RESPONSE_PREFIX = topics.ACTUATOR_VALUE()
REVERT_POINT_RESPONSE_PREFIX = topics.ACTUATOR_REVERTED_POINT()
REVERT_DEVICE_RESPONSE_PREFIX = topics.ACTUATOR_REVERTED_DEVICE()
ERROR_RESPONSE_PREFIX = topics.ACTUATOR_ERROR()

WRITE_ATTEMPT_PREFIX = topics.ACTUATOR_WRITE()

SCHEDULE_ACTION_NEW = 'NEW_SCHEDULE'
SCHEDULE_ACTION_CANCEL = 'CANCEL_SCHEDULE'

SCHEDULE_RESPONSE_SUCCESS = 'SUCCESS'
SCHEDULE_RESPONSE_FAILURE = 'FAILURE'

SCHEDULE_CANCEL_PREEMPTED = 'PREEMPTED'

ACTUATOR_COLLECTION = 'actuators'

_log = logging.getLogger(__name__)
utils.setup_logging()
__version__ = "0.5"


class LockError(StandardError):

    """
    Error raised when the user does not have a device scheuled
    and tries to use methods that require exclusive access.
    """

    pass


def actuator_agent(config_path, **kwargs):
    """
    Parses the Actuator Agent configuration and returns an instance of
    the agent created using that configuation.

    :param config_path: Path to a configuation file.

    :type config_path: str
    :returns: Actuator Agent
    :rtype: ActuatorAgent
    """
    try:
        config = utils.load_config(config_path)
    except StandardError:
        config = {}

    if not config:
        _log.info("Using Actuator Agent defaults for starting configuration.")

    heartbeat_interval = int(config.get('heartbeat_interval', 60))
    schedule_publish_interval = int(
        config.get('schedule_publish_interval', 3000))
    preempt_grace_time = config.get('preempt_grace_time', 6000)
    driver_vip_identity = config.get('driver_vip_identity', 'platform.driver')

    return ActuatorAgent(heartbeat_interval, schedule_publish_interval,
                         preempt_grace_time,
                         driver_vip_identity, **kwargs)


class ActuatorAgent(Agent):
    """
        The Actuator Agent regulates control of devices by other agents. Agents
        request a schedule and then issue commands to the device through
        this agent.

        The Actuator Agent also sends out the signal to drivers to trigger
        a device heartbeat.

        :param heartbeat_interval: Interval in seonds to send out a heartbeat
            to devices.
        :param schedule_publish_interval: Interval in seonds to publish the
            currently active schedules.
        :param schedule_state_file: Name of the file to save the current schedule
            state to. This file is updated every time a schedule changes.
        :param preempt_grace_time: Time in seconds after a schedule is preemted
            before it is actually cancelled.
        :param driver_vip_identity: VIP identity of the Master Driver Agent.

        :type heartbeat_interval: float
        :type schedule_publish_interval: float
        :type preempt_grace_time: float
        :type driver_vip_identity: str

    """

    def __init__(self, heartbeat_interval=60, schedule_publish_interval=6000,
                 preempt_grace_time=60,
                 driver_vip_identity='platform.driver', **kwargs):

        super(ActuatorAgent, self).__init__(**kwargs)
        _log.debug("vip_identity: " + self.core.identity)

        self._update_event = None
        self._device_states = {}

        self.schedule_state_file = "_schedule_state"
        self.heartbeat_greenlet = None
        self.heartbeat_interval = heartbeat_interval
        self._schedule_manager = None
        self.schedule_publish_interval = schedule_publish_interval
        self.subscriptions_setup = False

        self.default_config = {"heartbeat_interval": heartbeat_interval,
                              "schedule_publish_interval": schedule_publish_interval,
                              "preempt_grace_time": preempt_grace_time,
                              "driver_vip_identity": driver_vip_identity}


        self.vip.config.set_default("config", self.default_config)
        self.vip.config.subscribe(self.configure, actions=["NEW", "UPDATE"], pattern="config")

    def configure(self, config_name, action, contents):
        config = self.default_config.copy()
        config.update(contents)

        _log.debug("Configuring Actuator Agent")

        try:
            driver_vip_identity = str(config["driver_vip_identity"])
            schedule_publish_interval = float(config["schedule_publish_interval"])

            heartbeat_interval = float(config["heartbeat_interval"])
            preempt_grace_time = float(config["preempt_grace_time"])
        except ValueError as e:
            _log.error("ERROR PROCESSING CONFIGURATION: {}".format(e))
            #TODO: set a health status for the agent
            return

        self.driver_vip_identity = driver_vip_identity
        self.schedule_publish_interval = schedule_publish_interval

        _log.debug("MasterDriver VIP IDENTITY: {}".format(self.driver_vip_identity))
        _log.debug("Schedule publish interval: {}".format(self.schedule_publish_interval))

        #Only restart the heartbeat if it changes.
        if (self.heartbeat_interval != heartbeat_interval or
                    action == "NEW" or
                    self.heartbeat_greenlet is None):
            if self.heartbeat_greenlet is not None:
                self.heartbeat_greenlet.kill()

            self.heartbeat_interval = heartbeat_interval

            self.heartbeat_greenlet = self.core.periodic(self.heartbeat_interval, self._heart_beat)

        _log.debug("Heartbeat interval: {}".format(self.heartbeat_interval))
        _log.debug("Preemption grace period: {}".format(preempt_grace_time))



        if self._schedule_manager is None:
            try:
                config = self.default_config.copy()
                config.update(contents)
                state_string = self.vip.config.get(self.schedule_state_file)
                preempt_grace_time = float(config["preempt_grace_time"])
                self._setup_schedule(preempt_grace_time, state_string)
            except KeyError:
                state_string = None

        else:
            self._schedule_manager.set_grace_period(preempt_grace_time)


        if not self.subscriptions_setup and self._schedule_manager is not None:
            #Do this after the scheduler is setup.
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_GET(),
                                      callback=self.handle_get)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_SET(),
                                      callback=self.handle_set)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_SCHEDULE_REQUEST(),
                                      callback=self.handle_schedule_request)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_REVERT_POINT(),
                                      callback=self.handle_revert_point)

            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=topics.ACTUATOR_REVERT_DEVICE(),
                                      callback=self.handle_revert_device)

            self.subscriptions_setup = True


    def _heart_beat(self):
        _log.debug("sending heartbeat")
        try:
            self.vip.rpc.call(self.driver_vip_identity, 'heart_beat').get(
                timeout=5.0)
        except Unreachable:
            _log.warning("Master driver is not running")
        except Exception as e:
            _log.warning(''.join([e.__class__.__name__, '(', e.message, ')']))


    def _schedule_save_callback(self, state_file_contents):
        _log.debug("Saving schedule state")
        self.vip.config.set(self.schedule_state_file, state_file_contents)


    def _setup_schedule(self, preempt_grace_time, initial_state=None):

        now = self.volttime

        self._schedule_manager = ScheduleManager(
            preempt_grace_time,
            now=now,
            save_state_callback=self._schedule_save_callback,
            initial_state_string=initial_state)

        self._update_device_state_and_schedule(now)

    def _update_device_state_and_schedule(self, now):
        _log.debug("_update_device_state_and_schedule")
        # Sanity check now.
        # This is specifically for when this is running in a VM that gets
        # suspended and then resumed.
        # If we don't make this check a resumed VM will publish one event
        # per minute of
        # time the VM was suspended for.
        # test_now = utils.get_aware_utc_now()
        test_now = self.volttime

        if test_now - now > datetime.timedelta(minutes=3):
            now = test_now

        _log.debug("In _update_device_state_and_schedule: now is {}".format(
            now))
        self._device_states = self._schedule_manager.get_schedule_state(now)
        _log.debug("device states is {}".format(
            self._device_states))
        schedule_next_event_time = self._schedule_manager.get_next_event_time(
            now)
        _log.debug("schedule_next_event_time is {}".format(
            schedule_next_event_time))
        new_update_event_time = self._get_adjusted_next_event_time(
            now,
            schedule_next_event_time)
        _log.debug("new_update_event_time is {}".format(
            new_update_event_time))
        for device, state in self._device_states.iteritems():
            _log.debug("device, state -  {}, {}".format(device, state))
            header = self._get_headers(state.agent_id,
                                       time=utils.format_timestamp(now),
                                       task_id=state.task_id)
            header['window'] = state.time_remaining
            topic = topics.ACTUATOR_SCHEDULE_ANNOUNCE_RAW.replace('{device}',
                                                                  device)
            self.vip.pubsub.publish('pubsub', topic, headers=header)


        temp_sec = new_update_event_time -  self.volttime
        self._update_event = self.core.spawn_later(temp_sec.total_seconds(),self._update_schedule_state,new_update_event_time)


    def _get_adjusted_next_event_time(self, now, next_event_time):
        _log.debug("_get_adjusted_next_event_time")
        # now = self.volttime
        latest_next = now + datetime.timedelta(
            seconds=self.schedule_publish_interval)
        # Round to the next second to fix timer goofyness in agent timers.
        # TODO: Improved scheduler should no longer require this.
        # if latest_next.microsecond:
        #     latest_next = latest_next.replace(
        #         microsecond=0) + datetime.timedelta(seconds=1)
        if next_event_time is None or latest_next < next_event_time:
            return latest_next
        return next_event_time

    def _update_schedule_state(self, now):
        self._update_device_state_and_schedule(now)

    def _handle_remote_error(self, ex, point, headers):
        try:
            exc_type = ex.exc_info['exc_type']
            exc_args = ex.exc_info['exc_args']
        except KeyError:
            exc_type = "RemoteError"
            exc_args = ex.message
        error = {'type': exc_type, 'value': str(exc_args)}
        self._push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                     point, headers, error)

        _log.debug('Actuator Agent Error: ' + str(error))

    def _handle_standard_error(self, ex, point, headers):
        error = {'type': ex.__class__.__name__, 'value': str(ex)}
        self._push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                     point, headers, error)
        _log.debug('Actuator Agent Error: ' + str(error))

    def handle_get(self, peer, sender, bus, topic, headers, message):
        """
        Requests up to date value of a point.

        To request a value publish a message to the following topic:

        ``devices/actuators/get/<device path>/<actuation point>``

        with the fallowing header:

        .. code-block:: python

            {
                'requesterID': <Ignored, VIP Identity used internally>
            }

        The ActuatorAgent will reply on the **value** topic
        for the actuator:

        ``devices/actuators/value/<full device path>/<actuation point>``

        with the message set to the value the point.

        """
        point = topic.replace(topics.ACTUATOR_GET() + '/', '', 1)
        requester = sender
        headers = self._get_headers(requester)
        try:
            value = self.get_point(point)
            self._push_result_topic_pair(VALUE_RESPONSE_PREFIX,
                                         point, headers, value)
        except RemoteError as ex:
            self._handle_remote_error(ex, point, headers)
        except StandardError as ex:
            self._handle_standard_error(ex, point, headers)


    @PubSub.subscribe('pubsub', 'datalogger/log/volttime')
    def match_all(self, peer, sender, bus, topic, headers, message):
        '''
            Subscribe to volttime and synchronize
        '''
        str_time = message['timestamp']['Readings']

        volttime = time.strptime(str_time, "%Y-%m-%d %H:%M:%S")
        volttime = dt.fromtimestamp(mktime(volttime))
        self.volttime = pytz.utc.localize(volttime)
        # print "VOLTTIME at Actuator : ",self.volttime



    def handle_set(self, peer, sender, bus, topic, headers, message):
        """
            Set the value of a point.

            To set a value publish a message to the following topic:

            ``devices/actuators/set/<device path>/<actuation point>``

            with the fallowing header:

            .. code-block:: python

                {
                    'requesterID': <Ignored, VIP Identity used internally>
                }

            The ActuatorAgent will reply on the **value** topic
            for the actuator:

            ``devices/actuators/value/<full device path>/<actuation point>``

            with the message set to the value the point.

            Errors will be published on

            ``devices/actuators/error/<full device path>/<actuation point>``

            with the same header as the request.

        """
        if sender == 'pubsub.compat':
            message = compat.unpack_legacy_message(headers, message)

        point = topic.replace(topics.ACTUATOR_SET() + '/', '', 1)
        requester = sender
        headers = self._get_headers(requester)
        if not message:
            error = {'type': 'ValueError', 'value': 'missing argument'}
            _log.debug('ValueError: ' + str(error))
            self._push_result_topic_pair(ERROR_RESPONSE_PREFIX,
                                         point, headers, error)
            return

        try:
            self._set_point(requester, point, message)
        except RemoteError as ex:
            self._handle_remote_error(ex, point, headers)
        except StandardError as ex:
            self._handle_standard_error(ex, point, headers)

    @RPC.export
    def get_point(self, topic, **kwargs):
        """
        RPC method

        Gets up to date value of a specific point on a device.
        Does not require the device be scheduled.

        :param topic: The topic of the point to grab in the
                      format <device topic>/<point name>
        :param \*\*kwargs: Any driver specific parameters
        :type topic: str
        :returns: point value
        :rtype: any base python type"""
        topic = topic.strip('/')
        _log.debug('handle_get: {topic}'.format(topic=topic))
        path, point_name = topic.rsplit('/', 1)
        return self.vip.rpc.call(self.driver_vip_identity, 'get_point', path,
                                 point_name, **kwargs).get()

    @RPC.export
    def set_point(self, requester_id, topic, value, **kwargs):
        """RPC method

        Sets the value of a specific point on a device.
        Requires the device be scheduled by the calling agent.

        :param requester_id: Ignored, VIP Identity used internally
        :param topic: The topic of the point to set in the
                      format <device topic>/<point name>
        :param value: Value to set point to.
        :param \*\*kwargs: Any driver specific parameters
        :type topic: str
        :type requester_id: str
        :type value: any basic python type
        :returns: value point was actually set to. Usually invalid values
                cause an error but some drivers (MODBUS) will return a
                different
                value with what the value was actually set to.
        :rtype: any base python type

        .. warning:: Calling without previously scheduling a device and not
        within
                     the time allotted will raise a LockError"""

        rpc_peer = bytes(self.vip.rpc.context.vip_message.peer)
        return self._set_point(rpc_peer, topic, value, **kwargs)

    def _set_point(self, sender, topic, value, **kwargs):
        topic = topic.strip('/')
        _log.debug('handle_set: {topic},{sender}, {value}'.
                   format(topic=topic, sender=sender, value=value))

        path, point_name = topic.rsplit('/', 1)

        if not isinstance(sender, str):
            raise TypeError("Agent id must be a nonempty string")

        if self._check_lock(path, sender):
            result = self.vip.rpc.call(self.driver_vip_identity, 'set_point',
                                       path, point_name, value, **kwargs).get()

            headers = self._get_headers(sender)
            self._push_result_topic_pair(WRITE_ATTEMPT_PREFIX,
                                         topic, headers, value)
            self._push_result_topic_pair(VALUE_RESPONSE_PREFIX,
                                         topic, headers, result)
        else:
            raise LockError(
                "caller ({}) does not have this lock".format(sender))

        return result

    @RPC.export
    def set_multiple_points(self, requester_id, topics_values, **kwargs):
        """RPC method

        Set multiple points on multiple devices. Makes a single
        RPC call to the master driver per device.

        :param requester_id: Ignored, VIP Identity used internally
        :param topics_values: List of (topic, value) tuples
        :param \*\*kwargs: Any driver specific parameters

        :returns: Dictionary of points to exceptions raised.
                  If all points were set successfully an empty
                  dictionary will be returned.

        .. warning:: calling without previously scheduling *all* devices
                     and not within the time allotted will raise a LockError
        """
        requester_id = bytes(self.vip.rpc.context.vip_message.peer)
        devices = collections.defaultdict(list)
        for topic, value in topics_values:
            topic = topic.strip('/')
            device, point_name = topic.rsplit('/', 1)
            devices[device].append((point_name, value))

        for device in devices:
            if not self._check_lock(device, requester_id):
                raise LockError("caller ({}) does not lock for device {}".format(requester_id, device))

        results = {}
        for device, point_names_values in devices.iteritems():
            r = self.vip.rpc.call(self.driver_vip_identity,
                                  'set_multiple_points',
                                  device,
                                  point_names_values,
                                  **kwargs).get()
            results.update(r)

        return results

    def handle_revert_point(self, peer, sender, bus, topic, headers, message):
        """
        Revert the value of a point.

        To revert a value publish a message to the following topic:

        ``actuators/revert/point/<device path>/<actuation point>``

        with the fallowing header:

        .. code-block:: python

            {
                'requesterID': <Ignored, VIP Identity used internally>
            }

        The ActuatorAgent will reply on

        ``devices/actuators/reverted/point/<full device path>/<actuation
        point>``

        This is to indicate that a point was reverted.

        Errors will be published on

        ``devices/actuators/error/<full device path>/<actuation point>``

        with the same header as the request.
        """
        point = topic.replace(topics.ACTUATOR_REVERT_POINT() + '/', '', 1)
        requester = sender
        headers = self._get_headers(requester)

        try:
            self._revert_point(requester, point)
        except RemoteError as ex:
            self._handle_remote_error(ex, point, headers)
        except StandardError as ex:
            self._handle_standard_error(ex, point, headers)

    def handle_revert_device(self, peer, sender, bus, topic, headers, message):
        """
        Revert all the writable values on a device.

        To revert a device publish a message to the following topic:

        ``devices/actuators/revert/device/<device path>``

        with the fallowing header:

        .. code-block:: python

            {
                'requesterID': <Ignored, VIP Identity used internally>
            }

        The ActuatorAgent will reply on the **value** topic
        for the actuator:

        ``devices/actuators/reverted/device/<full device path>``

        to indicate that a point was reverted.

        Errors will be published on

        ``devices/actuators/error/<full device path>/<actuation point>``

        with the same header as the request.
        """
        point = topic.replace(topics.ACTUATOR_REVERT_DEVICE() + '/', '', 1)
        requester = sender
        headers = self._get_headers(requester)

        try:
            self._revert_device(requester, point)
        except RemoteError as ex:
            self._handle_remote_error(ex, point, headers)
        except StandardError as ex:
            self._handle_standard_error(ex, point, headers)

    @RPC.export
    def revert_point(self, requester_id, topic, **kwargs):
        """
        RPC method

        Reverts the value of a specific point on a device to a default state.
        Requires the device be scheduled by the calling agent.

        :param requester_id: Ignored, VIP Identity used internally
        :param topic: The topic of the point to revert in the
                      format <device topic>/<point name>
        :param \*\*kwargs: Any driver specific parameters
        :type topic: str
        :type requester_id: str

        .. warning:: Calling without previously scheduling a device and not
        within
                     the time allotted will raise a LockError"""

        rpc_peer = bytes(self.vip.rpc.context.vip_message.peer)
        return self._revert_point(rpc_peer, topic, **kwargs)

    def _revert_point(self, sender, topic, **kwargs):
        topic = topic.strip('/')
        _log.debug('handle_revert: {topic},{sender}'.
                   format(topic=topic, sender=sender))

        path, point_name = topic.rsplit('/', 1)

        if self._check_lock(path, sender):
            self.vip.rpc.call(self.driver_vip_identity, 'revert_point', path,
                              point_name, **kwargs).get()

            headers = self._get_headers(sender)
            self._push_result_topic_pair(REVERT_POINT_RESPONSE_PREFIX,
                                         topic, headers, None)
        else:
            raise LockError("caller does not have this lock")

    @RPC.export
    def revert_device(self, requester_id, topic, **kwargs):
        """
        RPC method

        Reverts all points on a device to a default state.
        Requires the device be scheduled by the calling agent.

        :param requester_id: Ignored, VIP Identity used internally
        :param topic: The topic of the device to revert
        :param \*\*kwargs: Any driver specific parameters
        :type topic: str
        :type requester_id: str

        .. warning:: Calling without previously scheduling a device and not
        within
                     the time allotted will raise a LockError"""
        rpc_peer = bytes(self.vip.rpc.context.vip_message.peer)
        return self._revert_device(rpc_peer, topic, **kwargs)

    def _revert_device(self, sender, topic, **kwargs):
        topic = topic.strip('/')
        _log.debug('handle_revert: {topic},{sender}'.
                   format(topic=topic, sender=sender))

        path = topic

        if self._check_lock(path, sender):
            self.vip.rpc.call(self.driver_vip_identity, 'revert_device', path,
                              **kwargs).get()

            headers = self._get_headers(sender)
            self._push_result_topic_pair(REVERT_DEVICE_RESPONSE_PREFIX,
                                         topic, headers, None)
        else:
            raise LockError("caller does not have this lock")

    def _check_lock(self, device, requester):
        _log.debug('_check_lock: {device}, {requester}'.format(
            device=device,
            requester=requester))
        device = device.strip('/')
        if device in self._device_states:
            device_state = self._device_states[device]
            return device_state.agent_id == requester
        return False

    def handle_schedule_request(self, peer, sender, bus, topic, headers,
                                message):
        """
        Schedule request pub/sub handler

        An agent can request a task schedule by publishing to the
        ``devices/actuators/schedule/request`` topic with the following header:

        .. code-block:: python

            {
                'type': 'NEW_SCHEDULE',
                'requesterID': <Ignored, VIP Identity used internally>,
                'taskID': <unique task ID>, #The desired task ID for this
                task. It must be unique among all other scheduled tasks.
                'priority': <task priority>, #The desired task priority,
                must be 'HIGH', 'LOW', or 'LOW_PREEMPT'
            }

        The message must describe the blocks of time using the format
        described in `Device Schedule`_.

        A task may be canceled by publishing to the
        ``devices/actuators/schedule/request`` topic with the following header:

        .. code-block:: python

            {
                'type': 'CANCEL_SCHEDULE',
                'requesterID': <Ignored, VIP Identity used internally>,
                'taskID': <unique task ID>, #The task ID for the canceled Task.
            }

        requesterID
            The name of the requesting agent. Automatically replaced with VIP id.
        taskID
            The desired task ID for this task. It must be unique among all
            other scheduled tasks.
        priority
            The desired task priority, must be 'HIGH', 'LOW', or 'LOW_PREEMPT'

        No message is requires to cancel a schedule.

        """
        if sender == 'pubsub.compat':
            message = compat.unpack_legacy_message(headers, message)

        request_type = headers.get('type')
        _log.debug('handle_schedule_request: {topic}, {headers}, {message}'.
                   format(topic=topic, headers=str(headers),
                          message=str(message)))

        requester_id = sender
        task_id = headers.get('taskID')
        priority = headers.get('priority')

        if request_type == SCHEDULE_ACTION_NEW:
            try:
                if len(message) == 1:
                    requests = message[0]
                else:
                    requests = message

                self._request_new_schedule(requester_id, task_id, priority,
                                           requests)
            except StandardError as ex:
                return self._handle_unknown_schedule_error(ex, headers,
                                                           message)

        elif request_type == SCHEDULE_ACTION_CANCEL:
            try:
                self._request_cancel_schedule(requester_id, task_id)
            except StandardError as ex:
                return self._handle_unknown_schedule_error(ex, headers,
                                                           message)
        else:
            _log.debug('handle-schedule_request, invalid request type')
            self.vip.pubsub.publish('pubsub',
                                    topics.ACTUATOR_SCHEDULE_RESULT(), headers,
                                    {'result': SCHEDULE_RESPONSE_FAILURE,
                                     'data': {},
                                     'info': 'INVALID_REQUEST_TYPE'})

    @RPC.export
    def request_new_schedule(self, requester_id, task_id, priority, requests):
        """
        RPC method

        Requests one or more blocks on time on one or more device.

        :param requester_id: Ignored, VIP Identity used internally
        :param task_id: Task name.
        :param priority: Priority of the task. Must be either "HIGH", "LOW",
        or "LOW_PREEMPT"
        :param requests: A list of time slot requests in the format
        described in `Device Schedule`_.

        :type requester_id: str
        :type task_id: str
        :type priority: str
        :returns: Request result
        :rtype: dict

        :Return Values:

            The return values are described in `New Task Response`_.
        """
        rpc_peer = bytes(self.vip.rpc.context.vip_message.peer)
        return self._request_new_schedule(rpc_peer, task_id, priority, requests)

    def _request_new_schedule(self, sender, task_id, priority, requests):


        now = self.volttime
        topic = topics.ACTUATOR_SCHEDULE_RESULT()
        headers = self._get_headers(sender, task_id=task_id)
        headers['type'] = SCHEDULE_ACTION_NEW
        local_tz = get_localzone()
        try:
            if requests and isinstance(requests[0], basestring):
                requests = [requests]

            tmp_requests = requests
            requests = []
            for r in tmp_requests:
                device, start, end = r

                device = device.strip('/')
                start = utils.parse_timestamp_string(start)
                end = utils.parse_timestamp_string(end)

                if start.tzinfo is None:
                    start = local_tz.localize(start)
                if end.tzinfo is None:
                    end = local_tz.localize(end)

                requests.append([device, start, end])

        except StandardError as ex:
            return self._handle_unknown_schedule_error(ex, headers, requests)

        _log.debug("Got new schedule request: {}, {}, {}, {}".
                   format(sender, task_id, priority, requests))

        if self._schedule_manager is None:

            config = self.default_config.copy()
            # config.update(contents)
            state_string = self.vip.config.get(self.schedule_state_file)
            preempt_grace_time = float(config["preempt_grace_time"])
            self._setup_schedule(preempt_grace_time, state_string)

            if not self.subscriptions_setup and self._schedule_manager is not None:
                #Do this after the scheduler is setup.
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=topics.ACTUATOR_GET(),
                                          callback=self.handle_get)

                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=topics.ACTUATOR_SET(),
                                          callback=self.handle_set)

                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=topics.ACTUATOR_SCHEDULE_REQUEST(),
                                          callback=self.handle_schedule_request)

                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=topics.ACTUATOR_REVERT_POINT(),
                                          callback=self.handle_revert_point)

                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=topics.ACTUATOR_REVERT_DEVICE(),
                                          callback=self.handle_revert_device)

                self.subscriptions_setup = True


        result = self._schedule_manager.request_slots(sender, task_id,
                                                      requests, priority, now)
        success = SCHEDULE_RESPONSE_SUCCESS if result.success else \
            SCHEDULE_RESPONSE_FAILURE

        # Dealing with success and other first world problems.
        if result.success:
            self._update_device_state_and_schedule(now)
            for preempted_task in result.data:
                preempt_headers = self._get_headers(preempted_task[0],
                                                    task_id=preempted_task[1])
                preempt_headers['type'] = SCHEDULE_ACTION_CANCEL
                self.vip.pubsub.publish('pubsub', topic,
                                        headers=preempt_headers,
                                        message={
                                            'result':
                                                SCHEDULE_CANCEL_PREEMPTED,
                                            'info': '',
                                            'data': {'agentID': sender,
                                                     'taskID': task_id}})

        # If we are successful we do something else with the real result data
        data = result.data if not result.success else {}

        results = {'result': success,
                   'data': data,
                   'info': result.info_string}
        self.vip.pubsub.publish('pubsub', topic, headers=headers,
                                message=results)

        return results

    def _handle_unknown_schedule_error(self, ex, headers, message):
        _log.error(
            'bad request: {header}, {request}, {error}'.format(header=headers,
                                                               request=message,
                                                               error=str(ex)))
        results = {'result': "FAILURE",
                   'data': {},
                   'info': 'MALFORMED_REQUEST: ' + ex.__class__.__name__ +
                           ': ' + str(
                       ex)}
        self.vip.pubsub.publish('pubsub', topics.ACTUATOR_SCHEDULE_RESULT(),
                                headers=headers, message=results)
        return results

    @RPC.export
    def request_cancel_schedule(self, requester_id, task_id):
        """RPC method

        Requests the cancelation of the specified task id.

        :param requester_id: Ignored, VIP Identity used internally
        :param task_id: Task name.

        :type requester_id: str
        :type task_id: str
        :returns: Request result
        :rtype: dict

        :Return Values:

        The return values are described in `Cancel Task Response`_.

        """
        rpc_peer = bytes(self.vip.rpc.context.vip_message.peer)
        return self._request_cancel_schedule(rpc_peer, task_id)

    def _request_cancel_schedule(self, sender, task_id):

        now = self.volttime
        headers = self._get_headers(sender, task_id=task_id)
        headers['type'] = SCHEDULE_ACTION_CANCEL

        result = self._schedule_manager.cancel_task(sender, task_id, now)
        success = SCHEDULE_RESPONSE_SUCCESS if result.success else \
            SCHEDULE_RESPONSE_FAILURE

        topic = topics.ACTUATOR_SCHEDULE_RESULT()
        message = {'result': success,
                   'info': result.info_string,
                   'data': {}}
        self.vip.pubsub.publish('pubsub', topic,
                                headers=headers,
                                message=message)

        if result.success:
            self._update_device_state_and_schedule(now)

        return message

    def _get_headers(self, requester, time=None, task_id=None):
        headers = {}
        if time is not None:
            headers['time'] = time
        else:

            utcnow = self.volttime
            headers = {'time': utils.format_timestamp(utcnow)}
        if requester is not None:
            headers['requesterID'] = requester
        if task_id is not None:
            headers['taskID'] = task_id
        return headers

    def _push_result_topic_pair(self, prefix, point, headers, value):
        topic = normtopic('/'.join([prefix, point]))
        self.vip.pubsub.publish('pubsub', topic, headers, message=value)


def main():
    """Main method called to start the agent."""
    utils.vip_main(actuator_agent, identity='platform.actuator')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
