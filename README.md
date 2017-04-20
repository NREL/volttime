ACES-Volttime ®/™/© ??
====


```
Copyright (c) ...<>
```


__This assumes you know how to build an dinstall volttron agents and a basic understanding of how the Volttron Driver Framework works__

**Volttime** enables running a VOLTTRON experiment/simulation at a specific but arbitrary date, hour, minute, second and at faster or slower than actual time. 


**ITEMC** Internet of Things Energy Management Controller

[https://github.com/NREL/itemc](https://github.com/NREL/itemc)


____________________________________________________________________
This repository has two sets of agents: 
the core agents which enable using Volttime and example agents which show you how to interatct with these agents. 
____________________________________________________________________


##Core Agents:

###Volttime Agent : 
This agent uses the ITEMC interface to publish timestamps on the  Volttron bus.
This agent can be configured to publish time at different graularities and different rates. 


###Actuator Agent: 
This agent is a modified version of the Actuator available in Volttron. This agent uses Volttime as the main time server. 
This agent enables using Volttime in the Vollttron driver framewrok. 
____________________________________________________________________

##Example Agents:


####Supervisory Controller agent: 
This agent has examples of scheduling a device and setting values on it. This works based on the updated Volttime. 


##Note:
Control agents need a few extra lines of code to enable them to sync with Volttime. 


###Subscribing to Volttime
```
    @PubSub.subscribe('pubsub', 'datalogger/log/volttime')
    def match_all(self, peer, sender, bus, topic, headers, message):
        '''
            Subscribe to volttime and synchronize
        '''
        str_time = message['timestamp']['Readings']

        volttime = time.strptime(str_time, "%Y-%m-%d %H:%M:%S")
        volttime = dt.fromtimestamp(mktime(volttime))
        self.volttime = pytz.utc.localize(volttime)

```
##Building/Installling the agents: 
 
This repo has a Makefile to help with the agent installation, you can use your own setup if you prefer: 

Please set your `VOLTTRON_HOME` enviroment variable before you build/install. 
`VOLTTRON_HOME` defaults to `$HOME/.volttron`

____________________________________________________________________

##Volttime 


###Agent setup

The starttime, stoptime and the rate at whcih this time would be published 
can be controlled by the setting.py file. The file to use for streaming timestamps on the bus can also be set in this file.

```
ITEMC_JSON = "itemc_house_0.json"
VTIME_START = "2013-07-01 18:00:00"
VTIME_STOP = "2013-07-02 18:00:00"
HEARTBEAT_PERIOD = 1.0
```
Here's an example of what the Volttime message from this agent looks like: 

```
Text here
```

____________________________________________________________________

##Example setup

* Please make sure the Platfrom is up and running
* `volttron -vv -l volttron.log&`
* Start the Master driver agent configured with the fake decive. 
* The Master driver can be found here : volttron/services/core/MasterDriverAgent
* The configuration files for the Fake device can be found here : volttron/examples/configurations/drivers
* Start the Modified Actuator Agent
* Start the TestAgent
* Start the Volttime agent
* **Please keep in mind to start the Volttime agent after all the other agents have been started**
* You can now tail the log file to see the progress
* `tail -f volttron.log`




 