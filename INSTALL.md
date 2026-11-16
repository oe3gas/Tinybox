# TinyBox installieren (Windows-Release-Paket)

Das Release-Paket ist eine ZIP-Datei für Windows 10/11 mit allem, was TBClient, TinyBox und den
brocast-Listener betreibt – inklusive des Direwolf-Forks `direwolf-tinybox.exe`. Nicht enthalten
sind die GeoSphere-Wetterskripte, der DX-Cluster-Sammler (dxfeed), der NanoPi-Build und die
Entwicklungswerkzeuge (Tests, Simulatoren, Planungsunterlagen).

## Installieren

1. `TinyBox-<Version>.zip` ganz entpacken (Rechtsklick → *Alle extrahieren*).
2. Im entpackten Ordner `install.bat` doppelklicken. Der Installer
   - fragt nach dem Installationsordner (Vorschlag `C:\TinyBox`),
   - installiert **Git** und **Python 3.12** über `winget`, falls sie fehlen,
   - kopiert die Dateien samt Git-Daten (für spätere Updates) und den Direwolf-Fork nach `direwolf\`,
   - installiert die Python-Pakete (`release\requirements.txt`),
   - startet den **Konfigurationsdialog** und legt auf Wunsch die Desktop-Verknüpfung *TinyBox Start*
     (mit TinyBox-Logo, `release\tinybox.ico`) an,
   - zeigt am Ende die Browser-Adressen von Client, brocast-Listener und TinyBox.

### Konfigurationsdialog

`release\konfig.py` fragt Rufzeichen, Locator, QTH, was auf dem PC laufen soll (TinyBox ja/nein,
brocast-Listener ja/nein), die SSIDs von Client und Mailbox und die **Funkanbindung**:

1. **Direwolf** – Soundkarten-Modem (Interface wie SignaLink, Digirig), AGW,
2. **KISS** – TNC oder Funkgerät mit eingebautem TNC, VARA (über `kisshub`).

Bei **KISS** zeigt der Dialog die TNC-Profile aus `kisshub.conf.example` (PK-232, TM-D710,
DR-635, TNC7multi, TH-D74/75, TNC2, VARA FM/HF …); der Anwender wählt seinen TNC und dann die
COM-Schnittstelle und die Baudrate PC ↔ TNC (bei VARA den Rechner, auf dem VARA läuft). modem73
steht nur in der Liste, wenn `modem73.exe` im Installationsordner liegt.

Für Direwolf listet er die Soundkarten (Eingang und Ausgang getrennt, mit den Windows-Nummern, die Direwolf
in `ADEVICE` erwartet) und die COM-Schnittstellen für die PTT (RTS/DTR) zur Auswahl; dazu CM108
und VOX. Außerdem fragt er 1200 oder 9600 Bd. Daraus entstehen aus den `*.conf.example`:

| Datei | Inhalt |
|---|---|
| `tbclient.conf` | Rufzeichen, Locator, Ziel-TinyBox, AGW über Direwolf |
| `tinybox.conf` | Mailbox-Rufzeichen (Rufzeichen + SSID), Sysop, QTH, Frequenz, Locator; `[brocast] publish = no` |
| `brocast\brocastd.conf` | `mode = listener` |
| `direwolf\direwolf.conf` | nur bei Direwolf: ADEVICE, MODEM, PTT, MYCALL, AGWPORT 8000, KISSPORT 8001 |
| `kisshub.conf` | nur bei KISS: `[kisshub] profile` = gewählter TNC, in dessen Abschnitt `device` und `serial_baud` (VARA: `host`) |
| `tbstart.conf` | Einstellungen der Steuerkonsole: welche Programme laufen (yes/no), Direwolf-Pfad, TNC-Profil |

Bei KISS stellt der Dialog in `tbclient.conf`, `tinybox.conf` und `brocastd.conf`
`[radio] interface = kiss` und `[kiss] port` auf den Port von kisshub (8101), sonst
`interface = agw`.

Geändert werden nur die gefragten Werte, alle Kommentare der Vorlagen bleiben. Ruft man den
Dialog erneut auf, schlägt er die Werte von heute vor (Rufzeichen, Locator, QTH, Heimat-Box,
Mailbox-SSID, Frequenz, Direwolf-Ordner, Soundkarte, Baudrate, PTT, TNC-Profil, COM-Port …) –
Enter behält sie, `-` leert einen optionalen Wert. Eine vorhandene Datei bekommt die Antworten
eingetragen, alle anderen Einstellungen darin bleiben; neu aus der Vorlage nur auf Wunsch
(Auswahl `n`). Alles Weitere (Chat-Boards, Bake, Rubriken,
Funkwerte des TNC …) direkt in den `.conf`-Dateien – siehe MANUAL.md. Der Dialog lässt sich jederzeit in der
Steuerkonsole mit **k** wiederholen.

## Starten und aktualisieren

`TinyBox-Start.bat` (oder die Desktop-Verknüpfung) öffnet die **Steuerkonsole** (CR138): ein
Fenster, das alle Programme der Station startet, überwacht, anhält und neu startet. Vorher holt
sie mit `git pull` den neuesten Stand von GitHub und zeigt die Neuerungen.

```
┌─ TinyBox Steuerkonsole  PC1 · Release 1.1.0 ────────────────────── 11:20:42 ─┐
│  Nr Programm  Rolle      Zustand     Port          PID    Laufzeit Fehler    │
│   1 Direwolf  Modem      läuft       AGW :8000 ✓   5124   3h12m    0         │
│   3 TinyBox   OE3XHU     läuft       Web :8080 ✓   5390   3h11m    1         │
│   4 TBClient  OE3GAS-12  läuft       Web :7744 ✓   5402   3h10m    0         │
│   5 brocastd  Listener   aus         Web :7733     –      –        0         │
├─ Letzte Meldungen ───────────────────────────────────────────────────────────┤
│ [tinyb] 11:20:40 OE3GAS-12 connected (client mode)                           │
├─ Letzter Fehler – 3 TinyBox (1 von 1) ───────────────────────────────────────┤
│ …                                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

Welche Programme laufen, steht in `tbstart.conf` (`yes`/`no` je Programm, vom
Konfigurationsdialog geschrieben): `direwolf`, `kisshub`, `tinybox`, `tbclient`, `brocast`,
`dxfeed`. brocastd läuft als Station **oder** Listener – das steht in `brocast\brocastd.conf`
und wird nur angezeigt.

| Taste | |
|---|---|
| `1`–`9` | Programm wählen (Meldungen und Fehler nur von ihm), `a` alle |
| `s` / `x` / `r` | gewähltes Programm starten / stoppen / neu starten |
| `R` | alle neu starten (Direwolf bzw. kisshub zuerst) |
| `d` | gewähltes Programm dauerhaft deaktivieren bzw. wieder aktivieren (`tbstart.conf`) |
| `w` | Web-GUI des gewählten Programms im Browser (TinyBox: mit Login-Link) |
| `e` | nur Fehler und Warnungen zeigen |
| `↑` / `↓` | durch die Fehlerblöcke blättern (älter / neuer) |
| `u` | Update: alles stoppen, `git pull`, wieder starten |
| `k` | Konfigurationsdialog |
| `q` | alles sauber beenden (auch Strg+C) – je Programm eine Meldung, wann und wie es endete |

- Start in der richtigen Reihenfolge: zuerst Direwolf bzw. kisshub; die anderen starten, sobald
  dessen AGW- bzw. KISS-Port offen ist (höchstens 20 s warten).
- Endet ein Programm unerwartet, startet es nach 15 s neu, höchstens 5-mal hintereinander –
  dann steht „Fehler“ in der Zeile. Exit 0 (z. B. SHUTDOWN der Box) und Konfigurationsfehler
  werden nicht neu gestartet, RESTART der TinyBox sofort.
- Stoppen ist sauber: das Programm bekommt Strg+Break, trennt seine Verbindungen und schließt die
  Datenbank; nur wenn es nach 10 s noch läuft, wird es hart beendet.
- Beim Beenden (`q`, Strg+C) meldet die Konsole jedes Programm einzeln: „wird beendet“, dann
  „sauber beendet“ bzw. „hart beendet“ mit Exit-Code und Dauer (Modem zuletzt); ein zweites
  Strg+C beendet den Rest sofort hart. Die Meldungen bleiben 10 s stehen und stehen auch im Log.
- Schließt man das Fenster, enden alle Programme mit.
- Ein Programm, das schon außerhalb der Konsole läuft (Port belegt), wird nicht doppelt
  gestartet („extern“).
- Jede Zeile aller Programme steht zusätzlich in `logs\tbstart-<Datum>.log`; die Programme
  schreiben ihre eigenen Logs wie bisher.
- Ohne Internet startet die vorhandene Version. Ändert ein Update die Python-Pakete, werden sie
  nachinstalliert; ändert es die Steuerkonsole selbst, startet sie sich neu.
- Einmal am Start und dann alle 6 Stunden schaut sie nach, ob es einen neuen Stand gibt (Hinweis
  unten im Fenster, `u` holt ihn).
- Für den Autostart ein Profil nur für diesen Lauf: `TinyBox-Start.bat 4` (1 nur TBClient,
  2 + TinyBox, 3 + brocast, 4 alle).
- Die Sysop-Konsole der TinyBox (Eingaben im TinyBox-Fenster) gibt es unter der Steuerkonsole
  nicht – dafür die Web-GUI (`w`). Wer sie braucht, startet `tinybox.bat` allein.
- Jedes Programm lässt sich weiter auch allein starten (`tinybox.bat`, `tbclient.bat` …).

Konfiguration, Datenbanken und Logs bleiben bei Updates unberührt (sie stehen in `.gitignore`).
Neue Einstellungen kommen in die `*.conf.example`; bei Bedarf von Hand übernehmen.
Der Direwolf-Fork wird nicht über `git pull` aktualisiert, sondern mit einem neuen Release-Paket.

## Paket bauen (Sysop/Entwicklung)

```sh
release/build_release.sh /pfad/zu/direwolf-tinybox.exe
```

Baut `release-out/TinyBox-<RELEASE>-<hash>.zip` aus dem Zweig `main` **auf GitHub** (also vorher
pushen). Inhalt:

```
TinyBox-1.0.0-abc1234/
  install.bat  LIESMICH.txt  VERSION.txt
  direwolf/direwolf-tinybox.exe
  payload/        flacher Git-Clone, reduziert nach release/sparse-checkout.txt
```

Was in eine Installation gehört, steht allein in `release/sparse-checkout.txt` (Git
sparse-checkout, gitignore-Syntax). Dieselbe Datei gilt auch für jedes spätere `git pull` der
Installation – neue Dateien im Repo-Wurzelordner kommen automatisch mit, solange sie dort nicht
mit `!` ausgeschlossen sind. Das Skript bricht ab, wenn GeoSphere- oder dxfeed-Dateien im
Paket landen würden oder Kernprogramme fehlen. `release-out/` ist lokal (`.gitignore`).
