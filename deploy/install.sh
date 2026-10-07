#!/bin/sh
# Install or update TinyBox + brocastd + GeoSphere scripts on the NanoPi.
# Run as root from the copied production folder:   sudo sh deploy/install.sh
#
# Program files are replaced on every run. Never overwritten (machine data):
#   tinybox.conf, brocast/brocastd.conf, brocast/brocast-core.yaml,
#   data/, brocast/data/, .geosphere_warnungen_*.json
# Transient files (inbox, Sendeprotokoll, journal) live in RAM, see PRODUCTION.md.
set -eu

SRC=$(cd "$(dirname "$0")/.." && pwd)
DEST=/opt/tinybox
SVC_USER=tinybox
UNITS="tinybox.service brocastd.service geosphere-wetter.service geosphere-wetter.timer geosphere-warnungen.service geosphere-warnungen.timer"
ENABLE="brocastd.service tinybox.service geosphere-wetter.timer geosphere-warnungen.timer"

[ "$(id -u)" -eq 0 ] || { echo "Please run as root: sudo sh $0"; exit 1; }
[ -f "$SRC/VERSION" ] || { echo "No VERSION file in $SRC - run from a production folder."; exit 1; }

# --- Python 3.10+ and the two brocast packages ------------------------------
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || { echo "Python 3.10 or newer required, found: $(python3 --version 2>&1)"; exit 1; }
if ! python3 -c 'import cbor2, yaml' 2>/dev/null; then
    echo "Installing python3-cbor2 and python3-yaml ..."
    apt-get update
    apt-get install -y --no-install-recommends python3-cbor2 python3-yaml
fi

# --- service user ------------------------------------------------------------
if ! id "$SVC_USER" >/dev/null 2>&1; then
    adduser --system --group --home "$DEST" --no-create-home "$SVC_USER"
fi

# --- stop running services before replacing the code ------------------------
for u in $ENABLE; do systemctl stop "$u" 2>/dev/null || true; done

# --- program files (always replaced) -----------------------------------------
mkdir -p "$DEST/brocast"
rm -rf "$DEST/tinybox" "$DEST/brocast/brocast"
cp -R "$SRC/tinybox" "$DEST/tinybox"
cp -R "$SRC/brocast/brocast" "$DEST/brocast/brocast"
cp "$SRC/geosphere_station.py" "$SRC/geosphere_warnungen.py" "$SRC/tinybox.conf.example" "$SRC/VERSION" "$DEST/"
cp "$SRC/brocast/brocastd.conf.example" "$SRC/brocast/requirements.txt" "$DEST/brocast/"

# --- machine files (only on first install) -----------------------------------
FIRST=0
# eMMC: transient files go to the RAM folders from tmpfiles-tinybox.conf
if [ ! -f "$DEST/tinybox.conf" ]; then
    sed 's|^dir *=.*|dir      = /run/tinybox/eingang  # NanoPi: RAM, same folder as the geosphere units|' \
        "$DEST/tinybox.conf.example" > "$DEST/tinybox.conf"
    FIRST=1
fi
if [ ! -f "$DEST/brocast/brocastd.conf" ]; then
    sed -e 's/^log_dir *=.*/log_dir   =                   ; NanoPi: leer = nur Journal (journalctl -u brocastd)/' \
        -e 's|^txlog_dir *=.*|txlog_dir = /run/tinybox/sendeprotokoll  ; NanoPi: RAM, weg nach Neustart|' \
        "$DEST/brocast/brocastd.conf.example" > "$DEST/brocast/brocastd.conf"
    FIRST=1
fi
[ -f "$DEST/brocast/brocast-core.yaml" ] || cp "$SRC/brocast/brocast-core.yaml" "$DEST/brocast/"

# precompile once: faster first start on the small CPU
python3 -m compileall -q "$DEST/tinybox" "$DEST/brocast/brocast" "$DEST"/geosphere_*.py >/dev/null || true
chown -R "$SVC_USER:$SVC_USER" "$DEST"

# --- systemd -----------------------------------------------------------------
# RAM folders under /run (recreated at every boot)
install -m 644 "$SRC/deploy/tmpfiles-tinybox.conf" /etc/tmpfiles.d/tinybox.conf
systemd-tmpfiles --create /etc/tmpfiles.d/tinybox.conf
# journal only in RAM
JCONF=/etc/systemd/journald.conf.d/tinybox.conf
if ! cmp -s "$SRC/deploy/journald-tinybox.conf" "$JCONF"; then
    mkdir -p "$(dirname "$JCONF")"
    install -m 644 "$SRC/deploy/journald-tinybox.conf" "$JCONF"
    systemctl restart systemd-journald
fi
for u in $UNITS; do install -m 644 "$SRC/deploy/systemd/$u" /etc/systemd/system/; done
systemctl daemon-reload
systemctl enable $ENABLE

# --- eMMC hints (system settings, not changed here) --------------------------
findmnt -no OPTIONS / | grep -q noatime \
    || echo "HINT: root filesystem without noatime - add it in /etc/fstab (fewer eMMC writes)."
if swapon --noheadings --show=NAME 2>/dev/null | grep -qv zram; then
    echo "HINT: swap on a disk is active - prefer zram or no swap (eMMC wear)."
fi

echo
echo "Installed $(grep '^commit=' "$DEST/VERSION") to $DEST"
if [ "$FIRST" -eq 1 ]; then
    echo
    echo "First install: edit the configuration, then start:"
    echo "  $DEST/tinybox.conf            (calls, sysop, [chat_boards], ...)"
    echo "  $DEST/brocast/brocastd.conf   (mode = station, callsign, ...)"
    echo "  sudo systemctl start $ENABLE"
else
    for u in $ENABLE; do systemctl start "$u"; done
    echo "Services restarted. Status: systemctl status tinybox brocastd"
fi
