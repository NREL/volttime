ACES-Volttime® 
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
 
###Radiothermostat relay agent: 
This repo also conntains an example relay agent  to test the Volttime setup. 
____________________________________________________________________

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

```



 