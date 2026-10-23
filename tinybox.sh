#!/bin/sh
# Start TinyBox from its own folder (Linux counterpart of tinybox.bat).
# RESTART in the sysop console ends TinyBox with code 3: it starts again here.
cd "$(dirname "$0")" || exit 1
export TINYBOX_LAUNCHER=1
while :; do
    python3 -m tinybox -c tinybox.conf "$@"
    rc=$?
    [ "$rc" -eq 3 ] || exit "$rc"
    echo "[tinyb] Restart ..."
done
