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
| `tbstart.conf` | Einstellungen des Startmenüs (Direwolf oder kisshub mitstarten, Pfad, TNC-Profil) |

Bei KISS stellt der Dialog in `tbclient.conf`, `tinybox.conf` und `brocastd.conf`
`[radio] interface = kiss` und `[kiss] port` auf den Port von kisshub (8101), sonst
`interface = agw`.

Geändert werden nur die gefragten Werte, alle Kommentare der Vorlagen bleiben. Eine vorhandene
Datei wird nur nach Rückfrage ersetzt. Alles Weitere (Chat-Boards, Bake, Rubriken,
Funkwerte des TNC …) direkt in den `.conf`-Dateien – siehe MANUAL.md. Der Dialog lässt sich jederzeit im
Startmenü mit **K** wiederholen.

## Starten und aktualisieren

`TinyBox-Start.bat` (oder die Desktop-Verknüpfung) zeigt:

| Wahl | startet |
|---|---|
| 1 | nur TBClient |
| 2 | TBClient + TinyBox |
| 3 | TBClient + brocast-Listener |
| 4 | alle drei |

Nach der Wahl holt das Startmenü mit `git pull` den neuesten Stand von GitHub, zeigt die
Neuerungen und startet dann Direwolf bzw. kisshub (falls in `tbstart.conf` eingeschaltet und
noch nicht laufend), danach die gewählten Programme, jedes in einem eigenen Fenster. TinyBox und brocast
laufen im Dauerbetrieb (Neustart nach Absturz). Der Browser öffnet den Client unter
http://127.0.0.1:7744/ (brocast-Listener: http://127.0.0.1:7733/).

- Ohne Internet startet die vorhandene Version.
- Ändert ein Update die Python-Pakete, werden sie automatisch nachinstalliert.
- Ändert ein Update das Startmenü selbst, startet es sich neu.
- Programme, die schon laufen, werden nicht doppelt gestartet.
- Ohne Menü, z. B. für den Autostart: `TinyBox-Start.bat 4`.

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
