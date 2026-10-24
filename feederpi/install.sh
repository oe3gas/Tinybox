#!/bin/sh
# shellcheck disable=SC2086,SC1091   # word lists on purpose; os-release only on the Pi
# Feeder-Pi: install or update the content jobs on a Raspberry Pi (model 1 and up).
#   dxfeed   (DX cluster collector + daily digest 05:00)
#   GeoSphere weather (hourly), warnings (15 min), forecast (3 h)
# The results land in /run/tinybox/ausgang (RAM); the PC fetches them over SSH
# (pi_abholung.py) into the TinyBox inbox. Details: feederpi/README.md
#
# Run as root from the folder that pi_sd_vorbereiten.py prepared, e.g. on the
# SD card's boot partition:
#     sudo sh /boot/firmware/feederpi/install.sh
# Options (environment):  NO_APT=1   skip installing unattended-upgrades
#
# Replaced on every run: program files, systemd units, system drop-ins.
# Only written on the first install (machine data, edit them on the Pi):
#   /opt/tinybox/dxfeed.conf, /etc/default/feederpi
# The PC key (abholung.pub) is replaced whenever the folder carries one.
# Never touched: /opt/tinybox/data/ (spot database), GeoSphere state files.
# Packages: python3-yaml (needed by dxfeed), unattended-upgrades (optional).
set -eu

SRC=$(cd "$(dirname "$0")" && pwd)
CODE=$SRC/code
DEST=/opt/tinybox
SVC_USER=tinybox
PC_USER=abholer
PC_HOME=/var/lib/abholer
PC_CMD=/usr/local/lib/feederpi/abholung.sh   # root-owned, outside /opt/tinybox
UNITS="dxfeed.service dxfeed-digest.service dxfeed-digest.timer
geosphere-wetter.service geosphere-wetter.timer
geosphere-warnungen.service geosphere-warnungen.timer
geosphere-prognose.service geosphere-prognose.timer"
TIMERS="geosphere-wetter.timer geosphere-warnungen.timer geosphere-prognose.timer"
DXFEED="dxfeed.service dxfeed-digest.timer"

say()  { printf '\n=== %s\n' "$*"; }
hint() { printf 'HINWEIS: %s\n' "$*"; }
die()  { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }

# copy a text file and strip Windows line ends (the SD card was written on Windows)
put() {    # put MODE SRC DEST
    install -m "$1" "$2" "$3"
    sed -i 's/\r$//' "$3"
}

[ "$(id -u)" -eq 0 ] || die "bitte als root starten: sudo sh $0"
[ -d "$CODE/dxfeed" ] && [ -f "$CODE/brocast/brocast-core.yaml" ] || die "Programmdateien in $CODE fehlen - Ordner mit pi_sd_vorbereiten.py erstellen"

say "Pruefen"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || die "Python 3.10 oder neuer noetig, gefunden: $(python3 --version 2>&1)"
echo "Python:  $(python3 --version 2>&1)"
echo "System:  $(. /etc/os-release && echo "$PRETTY_NAME"), $(uname -m)"
[ -f /etc/ssl/certs/ca-certificates.crt ] \
    || die "Stammzertifikate fehlen (Paket ca-certificates) - GeoSphere braucht TLS-Pruefung"
[ -f "$SRC/VERSION" ] && sed 's/^/Stand:   /' "$SRC/VERSION"

# dxfeed reads the DXCC list of the brocast dictionary (YAML) for the brocast page
APT_DONE=0
if ! python3 -c 'import yaml' 2>/dev/null; then
    say "PyYAML installieren (fuer die DXCC-Liste von dxfeed)"
    apt-get update && APT_DONE=1
    apt-get install -y --no-install-recommends python3-yaml \
        || die "python3-yaml nicht installiert - Netz pruefen und install.sh erneut starten"
fi

# --- time: Europe/Vienna, NTP, timers wait for a synced clock -----------------
say "Zeit (NTP, Zeitzone)"
timedatectl set-timezone Europe/Vienna
mkdir -p /etc/systemd/timesyncd.conf.d
put 644 "$SRC/timesyncd-feederpi.conf" /etc/systemd/timesyncd.conf.d/feederpi.conf
systemctl enable systemd-timesyncd.service systemd-time-wait-sync.service >/dev/null 2>&1 || true
systemctl restart systemd-timesyncd.service \
    || die "systemd-timesyncd fehlt - sudo apt install systemd-timesyncd, dann erneut starten"
timedatectl set-ntp true || true
# OnCalendar timers have After=time-sync.target; with time-wait-sync that target
# is only reached once NTP has set the clock (no 05:00 run with a 1970 clock).
timedatectl show -p NTPSynchronized --value 2>/dev/null | grep -q yes \
    && echo "Uhr synchron: $(date)" \
    || echo "Uhr noch nicht synchron (dauert nach dem Start bis zu einer Minute): $(date)"

# --- SD card: journal in RAM, no swap file ------------------------------------
say "SD-Karte schonen (Journal im RAM, keine Auslagerungsdatei)"
JCONF=/etc/systemd/journald.conf.d/feederpi.conf
mkdir -p /etc/systemd/journald.conf.d
if ! cmp -s "$SRC/journald-feederpi.conf" "$JCONF"; then
    put 644 "$SRC/journald-feederpi.conf" "$JCONF"
    systemctl restart systemd-journald
fi
if systemctl list-unit-files dphys-swapfile.service >/dev/null 2>&1 \
        && systemctl is-enabled dphys-swapfile.service >/dev/null 2>&1; then
    dphys-swapfile swapoff 2>/dev/null || true
    systemctl disable --now dphys-swapfile.service >/dev/null 2>&1 || true
    rm -f /var/swap
    echo "Auslagerungsdatei (dphys-swapfile) abgeschaltet - 512 MB RAM reichen."
fi
if swapon --noheadings --show=NAME 2>/dev/null | grep -qv zram; then
    hint "Auslagerung auf der SD-Karte aktiv ($(swapon --noheadings --show=NAME | tr '\n' ' ')) - besser zram oder keine."
fi
findmnt -no OPTIONS / | grep -q noatime \
    || hint "Root-Dateisystem ohne noatime - in /etc/fstab ergaenzen (weniger Schreibzugriffe)."

# --- users ---------------------------------------------------------------------
say "Benutzer"
if ! id "$SVC_USER" >/dev/null 2>&1; then
    adduser --system --group --home "$DEST" --no-create-home "$SVC_USER"
    echo "Dienstbenutzer $SVC_USER angelegt"
fi
if ! id "$PC_USER" >/dev/null 2>&1; then
    # login only with the PC key, only for abholung.sh (sshd-feederpi.conf)
    useradd --system --home-dir "$PC_HOME" --create-home --shell /bin/sh \
            --gid "$SVC_USER" "$PC_USER"
    echo "Abholbenutzer $PC_USER angelegt"
fi
usermod -p '*' "$PC_USER"            # no password at all (key login still works)

# --- program files (always replaced) --------------------------------------------
say "Programm nach $DEST"
for u in $DXFEED; do systemctl stop "$u" 2>/dev/null || true; done
mkdir -p "$DEST/data" "$(dirname "$PC_CMD")"
rm -rf "$DEST/dxfeed"
cp -R "$CODE/dxfeed" "$DEST/dxfeed"
find "$DEST/dxfeed" -name '__pycache__' -prune -exec rm -rf {} +
cp "$CODE"/geosphere_station.py "$CODE"/geosphere_prognose.py \
   "$CODE"/geosphere_warnungen.py "$CODE"/dxfeed.conf.example "$DEST/"
mkdir -p "$DEST/brocast"            # dictionary: DXCC list (ADIF numbers) for dxfeed
cp "$CODE/brocast/brocast-core.yaml" "$DEST/brocast/brocast-core.yaml"
[ -f "$SRC/VERSION" ] && cp "$SRC/VERSION" "$DEST/VERSION"
put 755 "$SRC/abholung.sh" "$PC_CMD"
FIRST_DX=0
if [ ! -f "$DEST/dxfeed.conf" ]; then
    if [ -f "$CODE/dxfeed.conf" ]; then
        cp "$CODE/dxfeed.conf" "$DEST/dxfeed.conf"
        echo "dxfeed.conf vom PC uebernommen"
    else
        cp "$CODE/dxfeed.conf.example" "$DEST/dxfeed.conf"
        echo "dxfeed.conf aus der Vorlage angelegt"
    fi
    # no log file (SD card, and a Windows path makes no sense here): journal only
    sed -i -e 's/\r$//' -e 's/^\([[:space:]]*file[[:space:]]*=\).*/\1/' "$DEST/dxfeed.conf"
    echo "  [log] file geleert: Meldungen nur ins Journal (journalctl -u dxfeed)"
    FIRST_DX=1
fi
# one-time bytecode: faster starts on the slow CPU, nothing written at runtime
python3 -m compileall -q "$DEST/dxfeed" "$DEST"/geosphere_*.py >/dev/null || true
chown -R "$SVC_USER:$SVC_USER" "$DEST"

if [ ! -f /etc/default/feederpi ]; then
    if [ -f "$SRC/feederpi.env" ]; then
        put 644 "$SRC/feederpi.env" /etc/default/feederpi
    else
        put 644 "$SRC/feederpi.env.example" /etc/default/feederpi
    fi
fi
echo "Locator(s): $(sed -n 's/^LOCATOR=//p' /etc/default/feederpi)   (/etc/default/feederpi)"

# --- SSH: key of the PC, forced command ----------------------------------------
say "SSH-Zugang fuer den PC ($PC_USER)"
AK=$PC_HOME/.ssh/authorized_keys
if [ -f "$SRC/abholung.pub" ]; then
    key=$(tr -d '\r' < "$SRC/abholung.pub" | head -n 1)
    case $key in
        ssh-ed25519\ *|ssh-rsa\ *|ecdsa-sha2-*) ;;
        *) die "abholung.pub enthaelt keinen oeffentlichen SSH-Schluessel" ;;
    esac
    mkdir -p "$PC_HOME/.ssh"
    # root owns the key file: abholer cannot change its own access
    printf 'restrict,command="%s" %s\n' "$PC_CMD" "$key" > "$AK"
    chown root:root "$PC_HOME/.ssh" "$AK"
    chmod 755 "$PC_HOME/.ssh"
    chmod 644 "$AK"
    echo "Schluessel eingetragen: $(printf '%s' "$key" | cut -d' ' -f3-)"
elif [ ! -f "$AK" ]; then
    hint "abholung.pub fehlt - der PC kann noch nichts abholen (pi_sd_vorbereiten.py legt ihn an)."
fi
mkdir -p /etc/ssh/sshd_config.d
put 644 "$SRC/sshd-feederpi.conf" /etc/ssh/sshd_config.d/feederpi.conf
# admin logins with key only, once the admin has a key (set in Raspberry Pi Imager)
ADMIN=${SUDO_USER:-}
NOPW=/etc/ssh/sshd_config.d/00-feederpi-nopassword.conf
if [ -n "$ADMIN" ] && [ "$ADMIN" != root ] \
        && [ -s "$(getent passwd "$ADMIN" | cut -d: -f6)/.ssh/authorized_keys" ]; then
    printf '# feederpi/install.sh: %s has an SSH key, passwords are off\nPasswordAuthentication no\nKbdInteractiveAuthentication no\n' \
        "$ADMIN" > "$NOPW"
    echo "SSH-Passwoerter abgeschaltet ($ADMIN meldet sich mit Schluessel an)"
else
    hint "kein SSH-Schluessel fuer ${ADMIN:-den Admin} - Passwort-Anmeldung bleibt erlaubt."
fi
sshd -t || die "sshd-Konfiguration fehlerhaft - nichts neu geladen"
systemctl try-reload-or-restart ssh.service 2>/dev/null \
    || systemctl try-reload-or-restart sshd.service 2>/dev/null || true

# --- systemd ---------------------------------------------------------------------
say "Dienste und Zeitplaene"
put 644 "$SRC/tmpfiles-feederpi.conf" /etc/tmpfiles.d/feederpi.conf
systemd-tmpfiles --create /etc/tmpfiles.d/feederpi.conf
for u in $UNITS; do put 644 "$SRC/systemd/$u" "/etc/systemd/system/$u"; done
systemctl daemon-reload
systemctl enable $TIMERS >/dev/null 2>&1
for u in $TIMERS; do systemctl restart "$u"; done

if grep -Eq '^[[:space:]]*login[[:space:]]*=[[:space:]]*[A-Za-z0-9]' "$DEST/dxfeed.conf"; then
    systemctl enable $DXFEED >/dev/null 2>&1
    for u in $DXFEED; do systemctl restart "$u"; done
    echo "dxfeed laeuft (Sammler + Zusammenfassung 05:00)"
    DX_OK=1
else
    systemctl disable $DXFEED >/dev/null 2>&1 || true
    DX_OK=0
fi

# --- automatic security updates ------------------------------------------------------
if [ "${NO_APT:-0}" != 1 ] && ! dpkg -s unattended-upgrades >/dev/null 2>&1; then
    say "Automatische Sicherheitsupdates (auf dem Pi 1 dauert das einige Minuten)"
    if { [ "$APT_DONE" -eq 1 ] || apt-get update; } \
            && apt-get install -y --no-install-recommends unattended-upgrades; then
        echo "unattended-upgrades installiert"
    else
        hint "unattended-upgrades nicht installiert (kein Netz?) - spaeter: sudo apt install unattended-upgrades"
    fi
fi

# --- first runs (in the background), summary --------------------------------------
systemctl start --no-block geosphere-warnungen.service geosphere-wetter.service

say "Fertig"
echo "Ausgang:   /run/tinybox/ausgang   (der PC holt alle 5 Minuten ab)"
echo "Status:    systemctl list-timers 'geosphere*' 'dxfeed*'"
echo "Logs:      journalctl -u geosphere-wetter -u dxfeed -n 30"
echo "Abholbar:  sudo -u $PC_USER env SSH_ORIGINAL_COMMAND=list $PC_CMD"
if [ "$DX_OK" -eq 0 ]; then
    echo
    hint "dxfeed ist aus: in $DEST/dxfeed.conf unter [cluster] login das Rufzeichen eintragen,"
    echo "         dann: sudo systemctl enable --now $DXFEED"
elif [ "$FIRST_DX" -eq 1 ]; then
    echo "dxfeed:    erste Zusammenfassung morgen 05:00 (der Sammler braucht 24 Stunden Spots)"
fi
