#!/bin/bash
cd /opt/fame
service docker start
mongod -f /etc/mongod.conf &
utils/run.sh utils/install.py
screen -dmS "web"  bash -c "utils/run.sh webserver.py"
screen -dmS "worker" bash -c "utils/run.sh worker.py"
/bin/bash
