#!/bin/bash
cd /opt/fame
utils/run.sh "utils/install.py" "$1" "--not-interactive"

if [ "$1" == "web" ]; then
  utils/run.sh webserver.py
elif [ "$1" == "worker" ]; then
  sudo rm -f /var/run/docker.sock /var/run/docker/containerd/containerd.sock /var/run/docker.pid /var/run/docker/containerd/containerd.pid
  sudo dockerd &> /dev/null &
  utils/run.sh worker.py unix
elif [ "$1" == "updater" ]; then
  utils/run.sh worker.py updates
fi
