#!/usr/bin/env bash

TIMEOUT=60

echo "[+] Waiting $TIMEOUT seconds for MongoDB to come up"
python docker/wait-for.py fame-mongo 27017 $TIMEOUT
if [ "$?" -ne "0" ]; then
    echo "[X] Could not connect to MongoDB instance - is it up and running?"
    exit 1
fi

utils/run.sh utils/install_docker.py

chown fame:fame /fame -R

echo "[+] Running webserver"
exec /fame/env/bin/uwsgi -H /fame/env --uid fame --http :8080 -w webserver --callable app