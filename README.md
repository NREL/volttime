ACES-Volttime
====


```
Copyright (c) 2017, Alliance for Sustainable Energy, LLC
All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted provided
that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice, this list of conditions
and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions
and the following disclaimer in the documentation and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or
promote products derived from this software without specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

```


__This example setup assumes you know how to build and install volttron agents and have a basic understanding of the Volttron Driver Framework__

**VOLTTRON Installation**
Please follow the steps at [http://volttron.readthedocs.io/en/master/install.html](http://volttron.readthedocs.io/en/master/install.html)

**Volttime** enables running a VOLTTRON experiment/simulation at a specific but arbitrary date, hour, minute, second and at faster or slower than actual time.

**Requirements**

* Volttron Platform compatible with the driver framework
* pandas; you can get it by sourcing the volttron environment and `pip install pandas`

____________________________________________________________________
This repository has two sets of agents:
the core agents which enable using Volttime and an example agents which shows how to interact with these agents.
____________________________________________________________________


## Core Agents:

### Volttime Agent :
This agent can be configured to publish Volttime at different rates.


### Actuator Agent:
This agent is a modified version of the ActuatorAgent available in Volttron. This agent uses Volttime as the main time server.
This agent enables using Volttime in the VOLTTRON driver framework.
The VIP IDENTITY of this agent is `platform.d.actuator`
____________________________________________________________________

## Example Agent:


#### Test agent:
This agent has examples of scheduling the fake device provided with VOLTTRON and setting a value on it. This works based on the updated Volttime.


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

## Building/Installing the agents:

This repo has a Makefile to help with the agent installation, you can use your own setup if you prefer:

Please set your `VOLTTRON_HOME` environment variable before using this Makefile.
Make sure the platform is up and running before you `make` the agents.

```
volttron-ctl log&  
make all

# add the configuration store for the modified actuator agent
volttron-ctl config store platform.d.actuator schedule_state_file platform.d.actuator

```

Build the master driver agent configured with the fake device;

* The Master driver can be found here : volttron/services/core/MasterDriverAgent in the main VOLTTRON repo
* The configuration files for the Fake device can be found here : volttron/examples/configurations/drivers in the main VOLTTRON repo

____________________________________________________________________
## Volttime


### Agent setup

The start-time, stop-time and the rate at which this time would be published
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

* Please make sure the Platform is up and running
* `volttron -vv -l volttron.log&`
* Start the Master driver agent configured with the fake device.

* Start the Modified Actuator Agent `volttron-ctl start --tag actuator-v`
* Start the TestAgent  `volttron-ctl start --tag test-v`
* Start the Volttime agent  `volttron-ctl start --tag volttime`
* **Please make sure you start the Volttime agent after all the other agents have been started**
* You can now tail the log file to see the progress
* `tail -f volttron.log`


____________________________________________________________________



