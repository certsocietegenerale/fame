#!/usr/bin/env bash

echo "[+] Setting up git user and email"
git config --global user.name "FAME Web"
git config --global user.email "fame-web@example.com"

echo "[+] Ensuring presence of temp dir"
mkdir -p temp && chown fame:fame temp/

if [ -f /run/secrets/ssh_priv_key ]; then
    echo "[+] Copying SSH private key"
    mkdir -p conf
    cp /run/secrets/ssh_priv_key conf/id_rsa
    chown fame:fame conf -R
    chmod 600 conf/id_rsa
fi

if [ -e /var/run/docker.sock ]; then
    gid="$(stat -c %g /var/run/docker.sock)"
    echo "[+] Creating docker_fame group with gid $gid and adding user 'fame' to it"
    groupadd -g $gid docker_fame
    usermod -aG docker_fame fame
fi

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
