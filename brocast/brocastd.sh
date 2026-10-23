#!/bin/sh
# Start brocastd from the brocast folder (Linux counterpart of brocastd.bat).
# Needs once:  sudo apt install python3-cbor2 python3-yaml
#              (or: pip install -r requirements.txt)
cd "$(dirname "$0")" || exit 1
exec python3 -m brocast.daemon -c brocastd.conf "$@"
