# brocast

Kompaktes Seitenprotokoll über AX.25 Packet Radio: CBOR mit Integer-Keys,
die Bedeutung der Nummern steht im lokalen Dictionary.

Spezifikation (lebendes Dokument):
https://claude.ai/code/artifact/bf4b91a7-7807-42d7-b72e-5739d9c257bd

## Dateien

| Datei | Inhalt |
| --- | --- |
| `brocast-core.yaml` | Kern-Dictionary Version 2 (Umschlag, Bausteine, Enums, Wetter); v1 als Referenz in `tests\data` |
| `brocast.cddl` | Schema zur Validierung |
| `brocast/` | Codec (`codec.py`) und brocastd (`daemon.py`, `station.py`, `carousel.py`, `ingest.py`, `agw.py`, `kiss.py`, `ax25.py`, `store.py`, `splitter.py`) |
| `brocastd.conf`, `brocastd.bat` | Konfiguration und Start |
| `tests/` | Tests (`runtests.bat`) |
| `dictionary-empfehlung.md` | Momentaufnahme der Spezifikation |

## Einrichten

Python 3.10 oder neuer, dazu zwei Pakete:

```
cd /d E:\Tinybox\brocast
py -3 -m pip install -r requirements.txt
```

## Ausprobieren

```
py -3 -m brocast demo              Beispiel-Wetterseite (57 Bytes) anzeigen
py -3 -m brocast decode <hex>      eine empfangene Seite dekodieren
py -3 -m brocast dict              Dictionary-Version und Hash
```

## brocastd starten (Meilenstein M1)

In `direwolf.conf` muss der AGW-Port aktiv sein (Direwolf-Standard, TinyBox
nutzt ihn ebenfalls):

```
AGWPORT 8000
```

Wer brocastd über KISS anbindet (`interface = kiss`, siehe unten), braucht
stattdessen `KISSPORT 8001`.

Dann `brocastd.bat` doppelklicken oder:

```
py -3 -m brocast.daemon -c brocastd.conf
```

Einstellungen in `brocastd.conf` (Modus `station` oder `listener`, Rufzeichen
`OE3GAS-5`, Airtime-Budget …). Daten liegen unter `data\brocastd.db`.

Seite von Hand einspielen (Ingest-API, z. B. mit curl):

```
curl -X PUT -H "Content-Type: application/json" ^
  http://127.0.0.1:8090/api/v1/pages/test/wetter ^
  -d "{\"typ\":\"wx\",\"ti\":\"Wetter Hollabrunn\",\"dat\":{\"temp\":12.5,\"hum\":65}}"
```

Status: `http://127.0.0.1:8090/api/v1/status` im Browser.

## Verbindung zu Direwolf: AGW oder KISS

brocastd spricht mit Direwolf **entweder über AGW oder über KISS**, nie über
beide gleichzeitig. Gewählt wird in `brocastd.conf`:

```
[direwolf]
interface = agw        ; agw (empfohlen) oder kiss
agw_port  = 8000
kiss_port = 8001
channel   = 0
```

Eine alte `brocastd.conf` mit Abschnitt `[kiss]` (ohne `[direwolf]`) läuft
unverändert weiter, und zwar über KISS.

### Sendepausen (`burst_frames`, `burst_gap_s`)

Direwolf sendet alles, was in seiner Sendewarteschlange liegt, in **einer**
Aussendung (ein PTT-Zyklus). Eine Seite mit vielen Teilen, z. B. das Dictionary
mit ca. 15 Frames, würde die Frequenz sonst eine halbe Minute am Stück belegen.
brocastd teilt deshalb selbst auf:

```
[station]
burst_frames = 4       ; höchstens 4 Frames pro Aussendung (0 = keine Aufteilung)
burst_gap_s  = 3       ; danach 3 s Pause, Kanal frei für andere Stationen
```

Bei 1200 Bd sind 4 volle Frames rund 8 s Sendezeit. In der Pause können andere
Stationen senden; Direwolf prüft vor der nächsten Aussendung wieder den Kanal
(DCD, `DWAIT`, `SLOTTIME`, `PERSIST`). Mehr Frames pro Block und kürzere Pausen
sind schneller, aber weniger kanalfreundlich.

### Der Unterschied: wer weiß, wann gesendet wurde?

**AGW (empfohlen).** brocastd fragt Direwolf (AGW-Abfrage `y`), wie viele
Frames noch in der Warteschlange liegen, und schickt den nächsten Block erst,
wenn sie leer ist – plus Sendezeit des letzten Frames, ein kleiner Zuschlag für
TXTAIL und `burst_gap_s`. Die Pause gilt damit auch, wenn der Kanal belegt war
und Direwolf warten musste. Der Takt kommt von Direwolf.

**KISS.** Über KISS meldet Direwolf nicht, wann eine Aussendung zu Ende ist.
brocastd **berechnet** das Ende aus Baudrate, `txdelay_ms` und Framelänge und
nimmt dabei an, dass Direwolf sofort senden konnte. Folgen:

- Bei freiem Kanal funktioniert die Aufteilung wie bei AGW.
- **Bei belegtem Kanal** hält Direwolf den ersten Block zurück. brocastd
  rechnet trotzdem weiter und reicht nach Ablauf der Pause den nächsten Block
  nach. Beide liegen dann gemeinsam in Direwolfs Warteschlange und gehen **in
  einer langen Aussendung** hinaus – die Aufteilung ist genau dann wirkungslos,
  wenn auf der Frequenz viel los ist.
- Stimmen `baud` oder `txdelay_ms` in `brocastd.conf` nicht mit `direwolf.conf`
  überein, sind die berechneten Pausen zu kurz oder zu lang.

KISS ist sinnvoll, wenn kein AGW-Port verfügbar ist (z. B. ein Hardware-TNC
oder ein anderes Programm statt Direwolf). Beim Start schreibt brocastd im
Modus `station` mit KISS einen Hinweis ins Log.

### Sonderfälle bei AGW

- Beantwortet Direwolf die Abfrage nicht (sehr alte Version), schreibt brocastd
  einmal eine Warnung ins Log und rechnet die Pausen wie bei KISS.
- Hält Direwolf Frames länger als 60 s zurück (Kanal dauerhaft belegt, DCD
  hängt), steht eine Warnung im Log; brocastd schickt bis dahin nichts nach.
- TinyBox und brocastd teilen sich den AGW-Port; Direwolf erlaubt mehrere
  AGW-Programme gleichzeitig. Die Abfrage `y` zählt die Frames des ganzen
  Kanals, also voraussichtlich auch die von TinyBox – brocastd wartet dann auch
  auf TinyBox-Aussendungen (beim ersten Funktest im Debug-Log prüfen).

## Listener (Meilenstein M2)

brocastd hält empfangene Seiten wie Teletext: gelesen/ungelesen, „aktualisiert“
bei neuer Revision, Favoriten, Löschen bis zur nächsten Revision, Ablauf,
Höchstzahlen, Abo mit Opt-out, Warnungen immer sichtbar. Eine Station zeigt
auch ihre eigenen Seiten.

**Oberfläche (M3):** bei laufendem brocastd im Browser `http://127.0.0.1:7733/` öffnen.
Rubriken/Stationen links, Seitenliste in der Mitte, Seite rechts; Suche,
Seitennummer-Eingabe, Einstellungen (Abo, Grenzen) und Status oben bzw. links unten.

Seiten mit mehreren Unterseiten lassen sich auf drei Arten anzeigen (Umschalter
„Ansicht“, wird im Browser gemerkt): **Fließtext**, **Mit Trennlinien**, **Teletext**
(ein Teil, blättern mit den Chips oder ◀ ▶). Testseiten: `test\senden.bat bulletin`
(ein langer Text in 4 Teilen) und `test\senden.bat magazin` (3 thematische Teile).

Die Rohdaten liefert weiterhin die JSON-API:

| Adresse | Inhalt |
| --- | --- |
| `http://127.0.0.1:7733/api/v1/status` | Status |
| `http://127.0.0.1:7733/api/v1/categories` | Rubriken mit Anzahl/ungelesen |
| `http://127.0.0.1:7733/api/v1/stations` | gehörte Stationen |
| `http://127.0.0.1:7733/api/v1/pages?cat=dx` | Seiten einer Rubrik (auch `station=`, `unread=1`, `favorite=1`, `q=`) |
| `http://127.0.0.1:7733/api/v1/pages/OE3GAS-5/25?raw=1` | eine Seite, mit Rohansicht |

Schreibende Aufrufe (lesen/ungelesen, Favorit, löschen, Einstellungen, Abo)
brauchen den Header `X-Brocast-Client: 1`; Details in `brocast/listener_api.py`.

**Zugriff aus dem LAN/WLAN** (z. B. vom Handy): in `brocastd.conf`

```
[listener]
web_host  = 0.0.0.0
allow_lan = yes
lan_names = pc2.fritz.box     ; nur nötig, wenn der Browser einen anderen Namen benutzt
```

Dann im Browser `http://<IP-Adresse des PCs>:7733/` oder `http://<Rechnername>:7733/`.
Die Oberfläche hat **keine Anmeldung** – jedes Gerät im Netz kann Seiten löschen
und Einstellungen ändern. Deshalb in der Windows-Firewall TCP 7733 eingehend nur
für das Heimnetz freigeben (PowerShell als Administrator, Netz anpassen):

```
New-NetFirewallRule -DisplayName "brocastd Listener" -Direction Inbound -Protocol TCP -LocalPort 7733 -RemoteAddress 192.168.1.0/24 -Action Allow
```

Aufrufe mit fremden Domainnamen im Host-Header werden weiter abgewiesen
(Schutz gegen DNS-Rebinding). Die Ingest-API (Port 8090) bleibt immer auf
127.0.0.1 – über sie wird gesendet.

## Dauerbetrieb (PC2) und Sendeprotokoll

- `..\start_alles.bat` startet Direwolf, brocastd und TinyBox in eigenen Fenstern
  (Direwolf-Pfad oben in der Datei einmal anpassen). brocastd und TinyBox werden
  nach einem Absturz automatisch neu gestartet.
- Autostart: Verknüpfung zu `start_alles.bat` in den Autostart-Ordner legen
  (Win+R → `shell:startup`).
- `logs\brocastd_log_<Datum>_<Zeit>.log`: Programm-Log, eine Datei pro Start.
- `logs\Sendeprotokoll_<JJJJ-MM>.txt`: jeder gesendete Frame mit Zeit (UTC),
  Rufzeichen, Seite, Revision, Teil, Bytes, Sendezeit, Lieferant und Titel.
  Nachweis für den Betrieb, wird nie automatisch gelöscht.

## Wetterseite (GeoSphere, typ wx)

`geosphere_station.py --tinybox` (im TinyBox-Ordner) legt den Wetterbericht wie
bisher als Bulletin in den TinyBox-Eingang, dazu in der Kopfzeile `Brocast:` die
fertige Wetterseite. Die Mailbox zeigt den Text, der brocast-Adapter von TinyBox
reicht die Seite an brocastd weiter (PLANUNG.md, Abschnitt 6d). Gesendet werden
nur Zahlen (Dictionary `wx`, ab Version 2), dazu der Temperaturverlauf 24 h als
Zeitreihe (ein Wert je 2 h). Das ergibt normalerweise **einen** Frame
(~205 Bytes, ca. 1,9 s bei 1200 Bd) statt mehrerer Textseiten.

```
py -3 geosphere_station.py --tinybox     Mailbox (Text) + brocast (Wetterseite)
py -3 geosphere_station.py --brocast     nur zum Testen ohne TinyBox: direkt an brocastd
py -3 geosphere_station.py --region --tinybox
                                         24 Stationen Wein-/Waldviertel: Einzelberichte
                                         + Gesamtueberblick (Tabellenseite, 4-5 Frames)
```

Die Listener-Oberfläche zeigt Seiten vom typ `wx` als Kacheln (Temperatur mit
24-h-Spanne, Windrose, Luftdruck mit Tendenz, Feuchte, Verlauf, Niederschlag).
Felder, die die Ansicht nicht kennt, erscheinen darunter als einfache Werte.
Offline-Vorschau ohne laufenden brocastd: `mockup\wx-vorschau.html`.

## Dictionary über Funk (gepackt)

Eine Station sendet ihr Dictionary zusätzlich gepackt über Funk (zlib über die
CBOR-Form, ~2,8 kB statt ~12 kB): ca. 15 Frames, rund 30 s bei 1200 Bd. Gleich
nach dem Start bzw. einer neuen Version, 15 min später noch einmal, danach alle
`dict_broadcast_hours` Stunden (`brocastd.conf`, Standard 24, 0 = aus).

Ein Listener braucht dafür kein Rufzeichen. Er sammelt die Teile auch über
mehrere Aussendungen, prüft dann Länge, Prüfsumme, Version und dass nur Einträge
dazukommen. Installiert wird

- automatisch, wenn die Station unter Einstellungen → „Dictionary über Funk
  automatisch übernehmen von“ eingetragen ist (z. B. `OE3GAS-5`),
- sonst nach Klick auf „Installieren“ im gelben Hinweis.

Die alte Datei bleibt als `brocast-core.v<alt>.bak.yaml` erhalten.

## Dictionary aktualisieren (über TinyBox)

1. Station: neue `brocast-core.yaml` (höhere `version`, nur Ergänzungen) in den
   brocast-Ordner legen. TinyBox bietet sie sofort mit dem Befehl `DICT` an
   (`[brocast] dict_file` in `tinybox.conf`), brocastd kündigt sie an
   (`dict_source` in `brocastd.conf`, brocastd neu starten).
2. Listener: gelber Hinweis „Dictionary v2 erhältlich …“. Mailbox connecten,
   `DICT` eingeben, Ausgabe mitschneiden.
3. Im Listener „Importieren“ → Mitschnitt-Datei wählen oder einfügen →
   „Prüfen und installieren“. Die alte Datei bleibt als
   `brocast-core.v1.bak.yaml` erhalten, ein Neustart ist nicht nötig.

## In Python

```python
from brocast import Codec

codec = Codec()
data = codec.encode({"id": 7, "t": 1790000000, "typ": "wx",
                     "dat": {"temp": 12.5, "hum": 65}})
page = codec.decode(data, ax25_src="OE3GAS-10")
print("\n".join(codec.describe(page)))
```

## Regeln fürs Dictionary

- Eine vergebene Nummer wird nie umgedeutet.
- Neue Einträge nur mit neuer `version`; Versionen sind additiv.
- Keys 0–23 und −1…−24 (1 Byte) nur für die Kern-Spezifikation.
