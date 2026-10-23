# Changelog

## Unveröffentlicht

- Konsole aller vier Programme (TinyBox, tbclient, kisshub, brocastd) einheitlich:
  `[ERROR]` (rot) und `[WARN]` (gelb) vor Fehlern und Warnungen, stehende
  Verbindungen grün, Startzeile hervorgehoben. Farben nur in einem echten
  Konsolenfenster, nicht in Log-Dateien; abschalten mit `[console] color = no`
  oder der Umgebungsvariable `NO_COLOR`.
- tbclient 2026.10.23: übersichtlicher Startblock (Call, Locator, TinyBox,
  Autoconnect, Verbindungsweg, Web-GUI); technische Details nur mit `-v`.
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
