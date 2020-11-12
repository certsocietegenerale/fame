#! /bin/sh

UTILS_ROOT=$(dirname "$0")
FAME_ROOT=$(dirname "$UTILS_ROOT")
VIRTUALENV="$FAME_ROOT/env"

if [ -d "$VIRTUALENV" ]; then
    echo "[+] Using existing virtualenv."
else
    echo "[+] Creating virtualenv..."
    python -mvirtualenv -p python3.7 "$VIRTUALENV" > /dev/null
fi

. "$VIRTUALENV/bin/activate"

echo ""
python "$@"
