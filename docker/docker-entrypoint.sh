#!/bin/bash
cd /opt/fame
sudo -E -H -u fame utils/run.sh "utils/install.py" "$1"
if [ "$1" == "web" ]; then
  sudo -E -H -u fame utils/run.sh webserver.py
elif [ "$1" == "worker" ]; then
  dockerd &> /dev/null &
  sudo -E -H -u fame utils/run.sh worker.py unix
elif [ "$1" == "updater" ]; then
  sudo -E -H -u fame utils/run.sh worker.py updates
fi
