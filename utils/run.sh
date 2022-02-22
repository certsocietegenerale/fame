#! /bin/sh

UTILS_ROOT=$(dirname "$0")
FAME_ROOT=$(dirname "$UTILS_ROOT")
VIRTUALENV="$FAME_ROOT/env"

if [ -d "$VIRTUALENV" ]; then
    echo "[+] Using existing virtualenv."
    . "$VIRTUALENV/bin/activate"
else
    echo "[+] Creating virtualenv..."
    python3 -m virtualenv -p python3 "$VIRTUALENV" > /dev/null
    . "$VIRTUALENV/bin/activate"
    pip3 install -r "$FAME_ROOT"/requirements.txt
fi


echo ""
if [ -n "$*" ]; then
    progname=$1
    shift
    args="$*"
    python "$progname" $args
fi
