#!/bin/sh
# Start the TinyBox client from its own folder (Linux counterpart of tbclient.bat).
# Log output appears in this terminal; stop with Ctrl+C.
cd "$(dirname "$0")" || exit 1
exec python3 -m tbclient -c tbclient.conf "$@"
