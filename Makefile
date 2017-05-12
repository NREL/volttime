#!/bin/bash
all: volttime actuator-v test-v

volttime:
		volttron-ctl remove --force --tag volttime
		volttron-pkg package agents/VolttimeAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/volttimeagent-3.0-py2-none-any.whl agents/VolttimeAgent/config
		volttron-ctl install $(VOLTTRON_HOME)/packaged/volttimeagent-3.0-py2-none-any.whl --tag=volttime

actuator-v:
		volttron-ctl remove --force --tag actuator-v
		volttron-pkg package agents/ActuatorAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/actuatoragent-0.5-py2-none-any.whl agents/ActuatorAgent/actuator-deploy.service
		volttron-ctl install $(VOLTTRON_HOME)/packaged/actuatoragent-0.5-py2-none-any.whl --tag=actuator-v

test-v:
		volttron-ctl remove --force --tag test-v
		volttron-pkg package agents/TestAgent/
		volttron-pkg configure $(VOLTTRON_HOME)/packaged/testvagent-3.0-py2-none-any.whl agents/TestAgent/config
		volttron-ctl install $(VOLTTRON_HOME)/packaged/testvagent-3.0-py2-none-any.whl --tag=test-v
