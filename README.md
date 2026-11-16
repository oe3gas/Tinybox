# TinyBox

**Eine kleine Packet-Radio-Mailbox (BBS) mit eigenem Client – damit Packet Radio wieder Spaß macht.**

TinyBox ist eine schlanke BBS für AX.25 Packet Radio, geschrieben in Python. Sie
läuft auf einem normalen Windows- oder Linux-PC neben [Direwolf](https://github.com/wb2osz/direwolf)
oder an einem KISS-TNC und bietet Post, Bulletins, Chat-Boards, Spiele, Forwarding und eine
Sysop-Weboberfläche. Dazu gibt es den **TBClient** (`tbclient`): ein Packet-Radio-Programm im
Browser mit Chat, Mailbox (auch offline), Monitor, APRS und Terminal – der TBClient funktioniert
auch ganz ohne eigene TinyBox.

*English: TinyBox is a small AX.25 packet radio BBS (mail, bulletins, chat boards, games,
FBB-style forwarding, sysop web GUI) for Direwolf (AGW) or KISS TNCs, plus a
browser-based client. Documentation is in German; questions in English are welcome.*

## Was ist drin?

| Teil | Wofür |
|---|---|
| **TinyBox** | die Mailbox: Post, Bulletins, Chat-Boards, Spiele (Prefix raten, CQ Contest), Forwarding (FBB/B1, mit LinBPQ getestet), Sysop-Konsole und Web-GUI, Eingangsordner für Skripte |
| **TBClient** (`tbclient`) | für Benutzer: Chat, Mailbox mit Offline-Abgleich, bis 10 Verbindungen, Client zu Client (Bilder, Dateien, Schach, QSL), Monitor, APRS-Statistik, Terminal, Verbindungslogbuch (CSV/ADIF) – im Browser, auch am Handy |
| **kisshub** | teilt einen KISS-TNC (PK-232, TM-D710, DR-635, TNC7multi, TH-D74/75, Direwolf-KISS, VARA FM/HF, modem73) zwischen mehreren Programmen und misst die Verbindungsqualität |
| **brocast** (`brocastd`) | kompaktes Seitenprotokoll (Wetter, Warnungen, DX, Bilder) als UI-Frames: die **Station** sendet die Bulletins der TinyBox als Seiten, der **Listener** zeigt empfangene Seiten im Browser |
| **Steuerkonsole** (`tbstart`) | ein Fenster, das alle Programme einer Station startet, überwacht und neu startet, mit Update per `git pull` |
| **dxfeed** | DX-Cluster-Spots als Zusammenfassung und „DX jetzt“-Bulletins statt Live-Spots |
| **GeoSphere-Skripte** | Wetter, Warnungen und Prognosen von GeoSphere Austria als Bulletins (`geosphere_*.py`) |
| **Feeder-Pi** | optional: dxfeed und GeoSphere auf einem Raspberry Pi, die TinyBox holt die Bulletins ab |

## Schnellstart

### Windows: Release-Paket (empfohlen)

Unter [Releases](https://github.com/oe3gas/Tinybox/releases) das ZIP laden, entpacken,
`install.bat` starten. Der Installer holt Git und Python, fragt im Konfigurationsdialog
Rufzeichen und Funkanbindung (Direwolf oder KISS-TNC) ab und legt die Verknüpfung
*TinyBox Start* für die Steuerkonsole an. Alles Weitere: [`INSTALL.md`](INSTALL.md).

### Aus dem Git-Repo (Windows und Linux)

1. **Python 3.10 oder neuer** installieren.
   - Windows: https://www.python.org, beim Installieren „Add python.exe to PATH“ anhaken.
   - Linux: meist schon da, prüfen mit `python3 --version`; sonst `sudo apt install python3`.
2. **TinyBox holen:** `git clone https://github.com/oe3gas/Tinybox.git`
3. **Python-Pakete:** `py -3 -m pip install -r release/requirements.txt` (Linux:
   `python3 -m pip install …` oder die Pakete unten). TinyBox und TBClient laufen zur Not auch
   ohne; dann fehlen die schnelle Signaturprüfung und LoTW (`cryptography`), serielle TNCs
   (`pyserial`) und brocast (`cbor2`, `PyYAML`, für Bilder `Pillow`).
   Debian/Ubuntu/Raspberry Pi OS: `sudo apt install python3-serial python3-cbor2 python3-yaml
   python3-cryptography python3-pil`.
4. **Konfiguration anlegen:**
   - Windows: `py -3 release\konfig.py` – der Dialog schreibt `tbclient.conf`, `tinybox.conf`,
     `brocastd.conf`, `direwolf.conf` bzw. `kisshub.conf` und `tbstart.conf`.
   - Von Hand (auch Linux): `tinybox.conf.example` nach `tinybox.conf` kopieren (für den
     TBClient: `tbclient.conf.example` nach `tbclient.conf`) und überall `OE3GAS` (das
     Rufzeichen des Autors) durch das eigene ersetzen. Die `.example`-Dateien erklären jeden Wert.
5. **Starten:**
   - Alles in einem Fenster: `TinyBox-Start.bat` (Linux: `python3 -m tbstart`) – die
     Steuerkonsole, siehe [`INSTALL.md`](INSTALL.md).
   - Einzeln: `tinybox.bat`, `tbclient.bat`, `kisshub.bat`, `brocast\brocastd.bat` (Linux:
     `tinybox.sh`, `tbclient.sh`, `kisshub.sh`, `brocast/brocastd.sh`).

   Die Web-GUI des TBClients: http://127.0.0.1:7744/ – die TinyBox zeigt in ihrem Fenster den
   Login-Link ihrer Sysop-Web-GUI.
6. **Ohne Funk ausprobieren:** per Telnet auf `127.0.0.1`, Port `6300` – unter Windows mit
   PuTTY, unter Linux mit `telnet 127.0.0.1 6300`.

**Linux-Hinweise**
- Die `.bat`-Dateien sind nur für Windows; Gegenstücke sind `tinybox.sh`, `tbclient.sh`,
  `kisshub.sh` und `brocast/brocastd.sh`. Alles andere startet man mit
  `python3 -m <programm> -c <programm>.conf` (`dxfeed` genauso, fwdsim mit `python3 -m fwdsim`,
  das Testbed mit `python3 -m tbtest`). Die Steuerkonsole läuft auch im Terminal (per SSH).
- Pfade in den Beispielen wie `C:\Tinybox` oder `data\` sind unter Linux `~/Tinybox` bzw. `data/`.
- Direwolf: `sudo apt install direwolf`.
- Serieller TNC über kisshub: in `kisshub.conf` bei `device` z. B. `/dev/ttyUSB0` eintragen und
  den eigenen Benutzer in die Gruppe `dialout` aufnehmen: `sudo usermod -aG dialout $USER`
  (danach neu anmelden).
- `RESTART` in der Sysop-Konsole funktioniert auch unter Linux: TinyBox startet sich im selben
  Terminal selbst neu.
- VARA FM/HF gibt es nur für Windows.
- Dauerbetrieb als Dienst (dxfeed und GeoSphere als systemd-Timer): fertige Units in
  `deploy/systemd/`, die Installation beschreibt [`PRODUCTION.md`](PRODUCTION.md).

## Unterlagen

| Datei | Inhalt |
|---|---|
| [`INSTALL.md`](INSTALL.md) | Windows-Release-Paket: Installer, Konfigurationsdialog, Steuerkonsole, Updates |
| [`MANUAL.md`](MANUAL.md) | **Handbuch:** die Teile und wie sie zusammenhängen, Woher die Inhalte kommen, Konfiguration aller Programme, Betriebsrezepte (Direwolf, KISS-TNCs, VARA, modem73, AXUDP), Rechte und Schlüssel, Sysop-Konsole, Spiele, Messen, Fehlersuche |
| [`tbclient/FEATURES.txt`](tbclient/FEATURES.txt) | was der TBClient kann |
| [`brocast/README.md`](brocast/README.md) | brocast im Detail: Frames, Wiederholung, Listener, Bilder, Wetterseite, Dictionary |
| [`logging_manual.md`](logging_manual.md) | Log-Dateien lesen, Fehler eingrenzen |
| [`PRODUCTION.md`](PRODUCTION.md) | Betrieb auf einem NanoPi/Linux mit systemd (englisch) |
| [`feederpi/README.md`](feederpi/README.md) | dxfeed und GeoSphere auf einem Raspberry Pi |
| [`tbtest/README.md`](tbtest/README.md), [`fwdsim/README.md`](fwdsim/README.md) | Testbed (simulierte User) und Forwarding-Testpartner |
| [`CHANGELOG.md`](CHANGELOG.md) | Änderungen je Release |
| [`PLANUNG.md`](PLANUNG.md), [`docs/`](docs/) | Entscheidungen, Konzepte, Change Requests (Entwicklung) |
| [`GIT-ANLEITUNG.md`](GIT-ANLEITUNG.md) | Updates mit Git, Release veröffentlichen |

## Tests

Windows: Doppelklick auf `runtests.bat`. Linux: `python3 -m unittest discover -s tests -t .`
(brocast: `brocast/runtests.bat` bzw. im Ordner `brocast` dasselbe).

## Mitmachen und Kontakt

Rückmeldungen, Fehlerberichte und Ideen gerne als
[Issue](https://github.com/oe3gas/Tinybox/issues). Wer eine TinyBox in die Luft
bringt: Bescheid sagen, dann connecten wir uns!

73 de **OE3GAS** (Gerhard) und **OE3TEC** (Tobias)

## Lizenz

GNU General Public License v3.0 – siehe [`LICENSE`](LICENSE).
