#!/bin/bash

# Log start time
START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "Start time: $START_TIME"

# Run `hey` POST request
hey -n 2000 -c 5 \
  -m POST \
  -T "application/json" \
  -H "Authorization: 675efbd1-bd4f-4d25-878d-bb4e3feb6be0" \
  -d '{"first_name":"John","last_name":"Doe","email":"john@example.com","phone":"08123456789"}' \
  http://localhost:81/api/contacts

# Log end time
END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "End time: $END_TIME"

