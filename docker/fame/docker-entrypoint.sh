#!/usr/bin/env bash

echo "[+] Ensuring empty __init__.py in modules directory"
touch /fame/fame/modules/__init__.py

echo "[+] Adjusting permissions"
chown fame:fame /fame -R

exec "$@"