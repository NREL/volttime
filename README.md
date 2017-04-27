ACES-Volttime ®/™/© ??
====


```
Copyright (c) ...<>
```


__This example setup assumes you know how to build and install volttron agents and have a basic understanding of the Volttron Driver Framework__


**Volttime** enables running a VOLTTRON experiment/simulation at a specific but arbitrary date, hour, minute, second and at faster or slower than actual time. 

**Requirements**
Volttron Platfrom compatible with the driver framewrok
pandas; you can get it by sourceing the volttron environment and `pip install pandas`

____________________________________________________________________
This repository has two sets of agents: 
the core agents which enable using Volttime and an example agents which shows how to interatct with these agents. 
____________________________________________________________________


## Core Agents:

### Volttime Agent : 
This agent can be configured to publish time at different rates. 


### Actuator Agent: 
This agent is a modified version of the Actuator available in Volttron. This agent uses Volttime as the main time server. 
This agent enables using Volttime in the Vollttron driver framewrok. 
The VIP IDENTITY of this agent is `platform.d.actuator`
____________________________________________________________________

## Example Agent:


#### Test agent: 
This agent has examples of scheduling the fake debvice provided with Volttron and setting a value on it. This works based on the updated Volttime. 


## Note:
Test agent needs a few extra lines of code to enable it to sync with Volttime. 


### Subscribing to Volttime
Volttime will be used as the timeserver for the agents that would like to run in the simulated time. 

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

## Building/Installling the agents: 
 
This repo has a Makefile to help with the agent installation, you can use your own setup if you prefer: 

Please set your `VOLTTRON_HOME` enviroment variable before using this Makefile.
Make sure the platform is up and running before you `make` the agents. 

```
volttron -l log&  
make all

```

____________________________________________________________________
## Volttime 


### Agent setup

The starttime, stoptime and the rate at which this time would be published 
can be controlled by the settings.py file. 

```
VTIME_START = "2013-07-01 18:00:00" #Simulation start time
VTIME_STOP = "2013-07-02 18:00:00" # simulation stop time
HEARTBEAT_PERIOD = 1.0 # Simulation rate

```
Here's an example of what the Volttime message from this agent looks like: 

```
Peer: 'pubsub', Sender: 'volttimeagent-3.0_2':, Bus: u'', Topic: 'datalogger/log/volttime',\
Headers: {'Date': '2017-04-25 14:01:10.684195+00:00Z', 'max_compatible_version': u'', \
'min_compatible_version': '3.0', 'AgentID': 'Volt_time', 'Content-Type': 'text/plain'},\
Message: {'timestamp': {'Units': 'ts', 'Readings': '2013-07-01 18:02:56'}}

```

____________________________________________________________________

## Example setup

* Please make sure the Platfrom is up and running
* `volttron -vv -l volttron.log&`
* Start the Master driver agent configured with the fake device. 
* The Master driver can be found here : volttron/services/core/MasterDriverAgent in the main VOLTTRON repo
* The configuration files for the Fake device can be found here : volttron/examples/configurations/drivers in the main VOLTTRON repo
* Start the Modified Actuator Agent `volttron-ctl start --tag actuator-v`
* Start the TestAgent  `volttron-ctl start --tag test-v`
* Start the Volttime agent  `volttron-ctl start --tag volttime`
* **Please make sure you start the Volttime agent after all the other agents have been started**
* You can now tail the log file to see the progress
* `tail -f volttron.log`


____________________________________________________________________


 
