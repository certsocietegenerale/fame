#!/usr/bin/env bash

if [ ! -f conf/fame.conf ]; then
    utils/run.sh utils/install.py
fi

echo "[+] Ensuring presence of uwsgi"
utils/run.sh -m pip install uwsgi > /dev/null

TIMEOUT=60

echo "[+] Waiting $TIMEOUT seconds for MongoDB to come up"
python docker/wait-for.py fame-mongo 27017 $TIMEOUT
if [ "$?" -ne "0" ]; then
    echo "[X] Could not connect to MongoDB instance - is it up and running?"
    exit 1
fi

echo "[+] Running webserver"
chown fame:fame /fame -R
exec /fame/env/bin/uwsgi -H /fame/env --uid fame --http :8080 -w webserver --callable app