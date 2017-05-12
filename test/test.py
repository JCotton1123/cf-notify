#!/usr/bin/env python

import os
import sys
import json

sys.path.append("../src")
import lambda_notify

if len(sys.argv) != 2:
    print "usage: %s <event.json>" % sys.argv[0]
    print "ex: %s fixtures/scheduled_event.json" % sys.argv[0]
    sys.exit(1)

os.environ['DEBUG'] = 'true'

with open(sys.argv[1]) as data_file:
    event_data = json.load(data_file)
    lambda_notify.lambda_handler(event_data, {})
