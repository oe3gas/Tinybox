# Feeder-Pi – Inhalte für die TinyBox auf einem Raspberry Pi

Der Feeder-Pi übernimmt die Content-Lieferanten, die bisher auf dem TinyBox-PC liefen:

| Job | Zeitplan | Ergebnis |
|---|---|---|
| dxfeed-Sammler (`dxfeed collect`) | Dauerbetrieb | Spots in `/opt/tinybox/data/dxfeed.db` |
| DX-Zusammenfassung (`dxfeed digest`) | alle 3 Stunden (02:00, 05:00 …) | Bulletins an `DX` (gleitend 24 h) |
| DX live (`dxfeed live`) | alle 10 min | DX jetzt, Bänder jetzt, Neu auf dem Band (PLANUNG 16c) |
| GeoSphere-Wetter (`--region`) | stündlich xx:05 | 24 Einzelberichte + Überblick an `WX` |
| GeoSphere-Warnungen | alle 15 min | Bulletin an `WARN` (nur bei Änderung) |
| GeoSphere-Prognose | alle 3 h, xx:35 | je Locator ein Bulletin an `WX` |

Die Programme sind dieselben wie auf dem PC (`dxfeed/`, `geosphere_*.py`), nur gestartet von
systemd statt von der Windows-Aufgabenplanung. Die Bulletin-Dateien landen am Pi im
**Ausgang** `/run/tinybox/ausgang` (im RAM). Der TinyBox-PC holt sie alle 5 Minuten per SSH ab
(`pi_abholung.py`) und legt sie in den TinyBox-Eingang. Die brocast-Seiten stecken wie bisher
in der Kopfzeile `Brocast:` der Bulletins, brocast braucht also nichts Eigenes.

```
Feeder-Pi                                   TinyBox-PC
 dxfeed / geosphere ──► /run/tinybox/ausgang ◄── pi_abholung.py (alle 5 min, SSH)
                                                    │
                                                    ▼
                                              eingang\  ──► TinyBox ──► brocast
```

## Was du brauchst

- Raspberry Pi 1 (B oder B+), 512 MB, LAN-Kabel, gutes 5-V-Netzteil
- SD-Karte ab 4 GB. Das Betriebssystem braucht rund 2,7 GB, es bleibt etwa 1 GB frei;
  der Feeder-Pi selbst braucht unter 5 MB.
- **Betriebssystem: Raspberry Pi OS Lite (32-bit)**, aktuelle Ausgabe (Debian 13 „trixie“).
  Nur die 32-bit-Ausgabe läuft auf dem Pi 1 (ARMv6). „Lite“ = ohne Desktop.
  Sie bringt Python 3, OpenSSH und die Stammzertifikate schon mit; zusätzlich installiert
  `install.sh` nur `python3-yaml` (dxfeed liest damit die DXCC-Liste aus dem brocast-Dictionary)
  und `unattended-upgrades` (automatische Sicherheitsupdates).

## Einrichten

### 1. Betriebssystem schreiben (Raspberry Pi Imager, am PC)

- Gerät: **Raspberry Pi 1** · OS: *Raspberry Pi OS (other)* → **Raspberry Pi OS Lite (32-bit)**
- Anpassungen:
  - Hostname: `feederpi`
  - Benutzer und Passwort: dein Admin-Benutzer (z. B. `oe3gas`)
  - Zeitzone `Europe/Vienna`, Tastatur `de`
  - **SSH aktivieren**, am besten „nur Public-Key“ mit deinem eigenen Schlüssel.
    Hat dein Admin einen Schlüssel, schaltet `install.sh` die SSH-Passwörter ab.
  - WLAN: leer lassen (der Pi 1 hat keines)

### 2. Feeder-Pi-Ordner auf die Karte (am PC, auf dem die TinyBox läuft)

Karte nach dem Schreiben neu einstecken. Windows zeigt das Laufwerk **bootfs**. Dann im
TinyBox-Ordner:

```
pi_sd_vorbereiten.bat
```

Das Skript findet die Boot-Partition selbst (sonst `--ziel F:\`) und legt dort `feederpi\` an:
die Programme, `install.sh`, die systemd-Units, das brocast-Dictionary dieses PCs
(`brocast/brocast-core.yaml`, für die DXCC-Liste von dxfeed), deine `dxfeed.conf` (mit Rufzeichen), den
Locator aus `geosphere_aufgaben_einrichten.bat` und den **öffentlichen Schlüssel dieses PCs**
(`abholung.pub`). Fehlt der Schlüssel, legt es ihn an: `%USERPROFILE%\.ssh\tinybox_feederpi`.
Andere Locators: `pi_sd_vorbereiten.bat --locator JN88BN,JN78WM`.

### 3. Pi starten und installieren

Karte in den Pi, LAN anstecken, Strom. Der erste Start dauert auf dem Pi 1 einige Minuten.
Die IP-Adresse steht in den DHCP-Leases des Routers (MikroTik). **Gib dem Pi dort eine feste
Zuordnung**, die Abholung arbeitet mit dieser Adresse.

```
ssh oe3gas@<IP-des-Pi>
sudo sh /boot/firmware/feederpi/install.sh
```

`install.sh` richtet ein: Zeit (NTP, Europe/Vienna), Journal im RAM, keine Auslagerungsdatei,
die Benutzer `tinybox` (Jobs) und `abholer` (nur für den PC), den SSH-Zugang des PCs, die
Programme in `/opt/tinybox`, die Zeitpläne und die automatischen Sicherheitsupdates. Das
dauert auf dem Pi 1 rund 10 Minuten, vor allem wegen `apt`. Danach laufen sofort ein
Wetter- und ein Warnungsabruf; „DX jetzt“ und „Bänder jetzt“ kommen nach 10–60 Minuten, die DX-Zusammenfassung alle 3 Stunden (vollständig nach einem Tag Sammeln).

### 4. Abholung einrichten (am TinyBox-PC)

```
pi_abholung_einrichten.bat
```

Fragt nach der IP des Pi, testet die Verbindung (beim ersten Mal merkt sich der PC den
Schlüssel des Pi), legt die Aufgabe **TinyBox\Pi-Abholung** an (alle 5 Minuten, ohne Fenster)
und schaltet auf Wunsch die bisherigen GeoSphere-/DX-Aufgaben des PCs ab. Den dxfeed-Sammler
schaltet es ab, indem es `dxfeed.conf` in `dxfeed.conf.vor-feederpi` umbenennt
(`start_alles.bat` startet ihn nur, wenn `dxfeed.conf` da ist). Sonst kämen die Bulletins doppelt.

### 5. Prüfen

- Am PC: `py -3 pi_abholung.py --host <IP> --test` zeigt, was am Pi wartet.
- Am PC: `logs\pi_abholung.log` – jede Abholung mit Dateinamen, Ausfälle einmal pro Ausfall,
  nach 60 min ohne Abholung einmal eine `WARNUNG`.

### Wenn der PC nicht abholt

Am Pi staut sich nichts: Jeder Job schreibt pro Thema eine Datei und überschreibt sie beim
nächsten Lauf. Holt der PC später ab, zieht `pi_abholung.py` das Alter der Datei von ihrem
`Valid:` ab. Was schon abgelaufen ist, kommt nicht mehr in die TinyBox. Startet der Pi in der
Zwischenzeit neu, ist der Ausgang leer (RAM), und die nächsten Läufe füllen ihn wieder.
- Am Pi: `systemctl list-timers 'geosphere*' 'dxfeed*'` und `journalctl -u dxfeed -n 30`.

## Betrieb am Pi

| Aufgabe | Befehl |
|---|---|
| Zeitpläne | `systemctl list-timers 'geosphere*' 'dxfeed*'` |
| Sammler | `systemctl status dxfeed` · `journalctl -u dxfeed -f` |
| Logs eines Jobs | `journalctl -u geosphere-wetter -n 30` (ebenso `geosphere-warnungen`, `geosphere-prognose`, `dxfeed-digest`, `dxfeed-live`) |
| Job sofort laufen lassen | `sudo systemctl start geosphere-prognose.service` |
| DX-Zusammenfassung ansehen | `cd /opt/tinybox && sudo -u tinybox python3 -m dxfeed -c dxfeed.conf digest` |
| Was wartet auf Abholung | `ls -l /run/tinybox/ausgang` |
| Uhrzeit synchron? | `timedatectl` (Zeile `System clock synchronized: yes`) |
| Locator ändern | `sudo nano /etc/default/feederpi` (wirkt beim nächsten Lauf) |
| dxfeed-Einstellungen | `sudo nano /opt/tinybox/dxfeed.conf`, dann `sudo systemctl restart dxfeed` |
| Installierter Stand | `cat /opt/tinybox/VERSION` |

## Neue Programmversion auf den Pi

Nach `git pull` am PC den Ordner in ein beliebiges Verzeichnis erzeugen und per `scp` hinüber
(die Karte muss dafür nicht raus):

```
pi_sd_vorbereiten.bat --ziel C:\Temp
scp -r C:\Temp\feederpi oe3gas@<IP-des-Pi>:/tmp/
ssh oe3gas@<IP-des-Pi> "sudo sh /tmp/feederpi/install.sh && rm -rf /tmp/feederpi"
```

Das gilt auch nach einem **neuen brocast-Dictionary** (neue DXCC-Einträge): der Pi bekommt
es nur auf diesem Weg.

`install.sh` ersetzt Programme, Dictionary, Units und Systemeinstellungen. Es überschreibt nie
`/opt/tinybox/dxfeed.conf`, `/etc/default/feederpi`, die Spot-Datenbank und die
GeoSphere-Zustandsdateien. Ein vorhandener PC-Schlüssel wird durch `abholung.pub` ersetzt.

## Sicherheit

- Der PC meldet sich als **`abholer`** mit eigenem Schlüssel an und darf nur drei Dinge:
  `list`, `bundle` (alle fertigen `*.txt` als tar) und `ack` (abgeholte verschieben) –
  `abholung.sh`, erzwungen in `authorized_keys` (`command=…,restrict`) **und** in sshd
  (`ForceCommand`). Kein Passwort, keine Shell, kein Tunnel. Die Schlüsseldatei gehört root.
- Der Schlüssel hat kein Passwort (die Aufgabenplanung läuft unbeaufsichtigt); er kann nur
  Bulletins abholen. Am PC liegt er im Benutzerprofil (`%USERPROFILE%\.ssh`).
- Beim ersten Verbinden merkt sich der PC den Host-Schlüssel des Pi (`accept-new`); ändert er
  sich später, verweigert die Abholung die Verbindung.
- Der PC prüft jede Datei: nur einfache Namen `*.txt`, keine Pfade oder Links, höchstens 512 KB.
- Die Jobs laufen als Benutzer `tinybox` mit systemd-Härtung (`ProtectSystem=strict`, schreiben
  nur in `/opt/tinybox` und den Ausgang). GeoSphere mit TLS-Prüfung (Systemzertifikate).
- Netz: Der Pi baut nur ausgehende Verbindungen auf – TCP 7300 (DX-Cluster), TCP 443
  (GeoSphere, cty.dat, Club Log, Updates), UDP 123 (NTP). Eingehend nur TCP 22 vom PC.
- `unattended-upgrades` spielt Sicherheitsupdates automatisch ein.

## SD-Karte schonen

| Was | Wo |
|---|---|
| Ausgang (Bulletin-Dateien) | RAM, `/run/tinybox/ausgang`; abgeholte 2 Tage in `abgeholt/` |
| Journal (alle Programmausgaben) | RAM, höchstens 16 MB |
| Auslagerung | abgeschaltet (512 MB reichen, die Jobs brauchen zusammen unter 100 MB) |
| Python-Bytecode | einmal von `install.sh` übersetzt, zur Laufzeit nichts |
| Spot-Datenbank | SD-Karte, etwa einmal pro Minute, 7 Tage (< 1 MB) |
| cty.dat, Most Wanted, Warnungszustand | SD-Karte, selten |

## Grenzen

- Die Bulletins kommen bis zu 5 Minuten später in die TinyBox als bisher.
- Ist der PC aus, warten die Dateien am Pi. Gleichnamige Dateien (z. B. das Wetter einer
  Station) ersetzen sich dabei, es wartet also immer nur der letzte Stand. Startet der Pi neu,
  sind wartende Dateien weg (RAM) – beim Wetter egal, die DX-Zusammenfassung fehlt dann einen Tag.
- `Valid:` zählt ab dem Eintreffen in der TinyBox. Nach einem langen PC-Ausfall gilt ein altes
  Wetter-Bulletin also noch einmal 2 Stunden, bis das nächste kommt.
