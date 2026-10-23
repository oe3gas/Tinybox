#!/bin/sh
# Start kisshub (owns the KISS TNC) from the TinyBox folder (Linux counterpart of kisshub.bat).
# Needs pyserial once:  sudo apt install python3-serial   (or: pip install pyserial)
# Serial port access:   sudo usermod -aG dialout $USER   (then log in again)
cd "$(dirname "$0")" || exit 1
exec python3 -m kisshub -c kisshub.conf "$@"
