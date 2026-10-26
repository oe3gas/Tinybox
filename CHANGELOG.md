# Changelog

## Unveröffentlicht

- Live-Monitore mit **Millisekunden** (`HH:MM:SS.mmm`): TinyBox-Web-GUI (Monitor und
  Frame-Monitor), Client 2026.10.26 (Monitor), brocastd (Empfangslog; neue Zeilen speichern
  `ts` mit ms, ältere zeigen `.000`).
- kisshub 2026.10.25.3: **RTS/CTS-Flusssteuerung** zum TM-D710 (`[tnc] rtscts`, Standard `yes`
  bei `tm-d710`, sonst `no`). Das Funkgerät bremst den kisshub über CTS, wenn sein
  TNC-Puffer voll ist; geschrieben wird in 64-Byte-Stücken, Strg+C hängt nie. Warnung bei
  CTS länger als 5 s tief, Zähler `cts_waits` / `cts_wait_s` in Status und Statuszeile.
- kisshub 2026.10.25.2: TM-D710 wahlweise mit **1200 oder 9600 Bd** auf dem Funk –
  `[kiss.tm-d710] air_baud = 9600` schickt `HBAUD 9600` an den TNC (bisher fest `HBAUD 1200`).
  Andere Werte werden beim Start abgelehnt. Bei 9600 eigene AX.25-Empfehlung (Fenster 7,
  T1 1,5–15 s, T2 0,5 s). 9600 noch nicht am Funk getestet.
- Update-Hinweis (PLANUNG 24): TinyBox, Client, brocastd und kisshub fragen einmal am Tag bei
  GitHub nach dem neuesten Release (`prcore/release.py`, Cache mit ETag, still ohne
  Internet, nichts wird installiert). Eine Release-Version für das ganze Repo (`RELEASE`).
  TinyBox: Hinweis im Log, bei `STATUS` und in der Web-GUI, dazu genau **ein** Bulletin pro
  Release in TBNEWS (`[update] announce`), Konsolenbefehle `UPDATE` und `UPDATE NEWS`.
  Client 2026.10.25: Banner mit Link. brocastd: Statusseite. kisshub 2026.10.25: Logzeile.
  Neuer Abschnitt `[update]` in allen vier `*.conf.example` (Vorgabe `check = yes`).
- brocast Karussell (PLANUNG 23): **Fehler behoben** – die Alterung (`aging`) griff nie, weil der
  stündliche Sync das Alter zurücksetzte; alte Bulletins liefen dauerhaft alle 30 min. Das Alter
  zählt jetzt ab der Revision bzw. ab `born` (neues Ingest-Feld, TinyBox schickt das
  Bulletin-Datum). Neue Vorgabe `aging = 24:120, 72:360, 168:1440`. Datenbank-Schema 4
  (`pages.rev_t`, wird automatisch nachgezogen).
- TinyBox `[brocast] air_days`: Bulletins nur n Tage nach dem Schreiben über brocast, in der
  Mailbox bleiben sie länger (0 = wie bisher).
- dxfeed live (PLANUNG 16c): „DX jetzt“ (letzte 2 h, nur bei Änderung), „Bänder jetzt“
  (letzte Stunde nach Kontinent der DX-Station, alle Gebiete) und „Neu auf dem Band“
  (seltenes DX, gedrosselt) als eigene, sich selbst ersetzende Bulletins; Aufgabe/Timer
  alle 10 min. Die 24-Stunden-Übersicht läuft gleitend alle 3 Stunden.
- brocast Dictionary v5: `dxsum` kind, path und Spalte qrg; Listener zeigt das Alter der
  DX-Seiten, die Pfad-Matrix und den Neu-Hinweis.
- Feeder-Pi (PLANUNG 22, `feederpi/README.md`): dxfeed und GeoSphere laufen auf einem
  Raspberry Pi (ab Modell 1, Raspberry Pi OS Lite 32-bit) mit systemd; der TinyBox-PC holt die
  Bulletins alle 5 Minuten per SSH in den Eingang (`pi_abholung.py`, eingeschränkter Benutzer
  `abholer`). Neu: `pi_sd_vorbereiten.bat`, `pi_abholung_einrichten.bat`,
  `pi_abholung_entfernen.bat`, `feederpi/install.sh`.
- Benutzerprofil (CR73, PLANUNG 21): Name, Locator, Home-BBS je Rufzeichen in der
  TinyBox. Terminal fragt nach dem Login nach fehlenden Angaben (`[mailbox]
  ask_profile`), Befehle `N`, `NL`, `NH`, `I call`; `/W` im Chat mit Name und Locator;
  Sysop-Web-GUI zeigt die Profile bei den Stationen. Client-Protokoll `PROF`
  (`prof=` im `//OK`, `//PROF`, `//WHOIS`). Client 2026.10.24: Formular „My profile“,
  Einladungsbalken, Teilnehmerliste mit Name, Locator und Entfernung.
- dxfeed: Most-Wanted-Rang wirkt jetzt (Club Log liefert ADIF-Nummern, nicht
  Präfixe); mindestens 10 Stationen auf der brocast-Seite (`brocast_min_rows`);
  Modes aus dem Bandplan auch für Digital-Segmente (DIGI), Region-2-Phonie und FM.
- dxfeed: Bandaktivität zählt dieselben relevanten Spots wie die Stationsliste.
- brocast Dictionary v4: Seitentyp `dxsum` (DX-Zusammenfassung), Listen `band`,
  `mode` und `dxcc` (alle DXCC-Gebiete mit ADIF-Nummer), Feldtyp `rows`,
  Blockart `data` (PLANUNG 16b). dxfeed sendet Stationen und Bandaktivität als
  zwei Bulletins mit je einer Seite in einem Frame (vorher drei Frames); der
  Most-Wanted-Rang findet jetzt auch Gebiete, die Club Log anders schreibt (1A0, IS0 ...).
- dxfeed: Relevanz der DX-Meldungen nach Club Log Most Wanted und Spotterzahl
  (Stufen A/B/C, PLANUNG 16a), neuer Befehl `mw-update`; Tabelle alphabetisch,
  Bandaktivität je Mode mit den anderen Modes namentlich. Das DX-Bulletin trägt
  eine brocast-Seite (nur Stufe A+B); der Listener zeigt sie als Band/Mode-Raster
  mit Heatmap der Bandaktivität.
- Konsole aller vier Programme (TinyBox, tbclient, kisshub, brocastd) einheitlich:
  `[ERROR]` (rot) und `[WARN]` (gelb) vor Fehlern und Warnungen, stehende
  Verbindungen grün, Startzeile hervorgehoben. Farben nur in einem echten
  Konsolenfenster, nicht in Log-Dateien; abschalten mit `[console] color = no`
  oder der Umgebungsvariable `NO_COLOR`.
- tbclient 2026.10.23: übersichtlicher Startblock (Call, Locator, TinyBox,
  Autoconnect, Verbindungsweg, Web-GUI); technische Details nur mit `-v`.
- TinyBox, kisshub und brocastd: Startblock im selben Muster (Beschriftung: Wert),
  Adressen von Web-GUI und Ports als eigene Zeilen; Inhalt unverändert.
- „Nicht erreichbar“ (Direwolf, KISS, TNC) wird nur noch einmal gemeldet, als `[ERROR]`.
- Linux-Startskripte `tinybox.sh`, `tbclient.sh`, `kisshub.sh`, `brocast/brocastd.sh`.

## v1.0.0 – 22.10.2026

Erste öffentliche Version.

**TinyBox** (Mailbox, Version 1.0.0)
- Post und Bulletins mit Rubriken, Suche (`F`), Eingangsordner für automatische Bulletins
- Chat-Boards (`C`) mit einstellbarer Aufbewahrung, auch „live“ ohne Speicherung
- Forwarding als optionales Modul: FBB-ASCII und B1 (komprimiert), Zeitplan,
  HOLD/REL, hierarchische Adressen, BID, R:-Zeilen; mit LinBPQ getestet
- Anbindung über Direwolf (AGW) oder KISS (eigenes AX.25 v2.2 mit SREJ/XID),
  auch über Digipeater; Telnet-Testport für den Betrieb ohne Funk
- Sysop-Konsole (Monitor, `SHUTDOWN`/`RESTART` mit Vorwarnung) und Sysop-Weboberfläche
- Log-Datei pro Tag mit Debug-Komponenten und `LOG BUNDLE` für Fehlerberichte

**TinyBox-Client** (`tbclient`, Version 2026.10.18.7)
- Web-Oberfläche für PC und Handy: Chat, Mailbox mit Offline-Abgleich, Suche
- bis zu 5 Verbindungen gleichzeitig, Terminal für beliebige Stationen, Monitor
- Verbindungslogbuch mit Export als CSV und ADIF
- Bilder im Chat, Post-Hinweis, Neuigkeiten als Bulletin (TBNEWS)

**Dazu**
- kisshub: ein KISS-TNC (PK-232, TM-D710, Direwolf-KISS, VARA FM) für mehrere
  Programme, mit Messung der Verbindungsqualität
- brocast: kompaktes Seitenprotokoll über UI-Frames (Wetter, Warnungen, Bilder)
- dxfeed: tägliche DX-Zusammenfassung als Bulletin
- fwdsim: Testpartner für das Forwarding

Voraussetzung: Python 3.10 oder neuer. Anleitung: `README.md` und `MANUAL.md`.
