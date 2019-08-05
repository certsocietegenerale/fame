#!/usr/bin/env bash

if [ ! -f conf/fame.conf ]; then
    echo "[-] Cannot find config file: $PWD/conf/fame.conf"
    exit 1
fi

echo "[+] Setting up git user and email"
git config --global user.name "FAME Web"
git config --global user.email "fame-web@example.com"

echo "[+] Ensuring presence of temp dir"
mkdir -p temp && chown fame:fame temp/

TIMEOUT=60

echo "[+] Waiting $TIMEOUT seconds for MongoDB to come up"
python docker/wait-for.py fame-mongo 27017 $TIMEOUT
if [ "$?" -ne "0" ]; then
    echo "[X] Could not connect to MongoDB instance - is it up and running?"
    exit 1
fi

echo "[+] Waiting $TIMEOUT seconds for web server to come up"
python docker/wait-for.py fame-web 8080 $TIMEOUT
if [ "$?" -ne "0" ]; then
    echo "[X] Could not connect to web server instance - is it up and running?"
    exit 1
fi

exec utils/run.sh worker.py -r 5 -c -- '--uid fame --gid fame'
