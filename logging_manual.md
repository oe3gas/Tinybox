# TinyBox – Logging-Handbuch

Wie das Logfile eingeschaltet, gelesen und zum Debuggen benutzt wird.
Umsetzung: CR32 in `docs/client-change-requests.md`, Code in `tinybox/logsetup.py`.

**Zweck:** Eine Datei, aus der sich der Ablauf ohne Rückfragen rekonstruieren
lässt – auch von jemandem, der den Rechner nicht sieht.

---

## 1. Einschalten

In `tinybox.conf` (PC-spezifisch, nicht im Repo):

```ini
[logging]
level     = INFO        # DEBUG, INFO, WARNING, ERROR
monitor   = yes         # Sitzungsverkehr (< und >) mitschreiben
log_dir   = logs        # leer = kein Logfile. Ordner muss existieren!
keep_days = 14          # ältere Tagesdateien löschen (0 = alle behalten)
debug     =             # zusätzliches DEBUG je Komponente, z. B. agw,fwd
```

Der Ordner wird **nicht** angelegt – vorher `mkdir logs`. Fehlt er oder ist er
nicht beschreibbar, startet TinyBox nicht und sagt warum.

Dann `RESTART` in der Sysop-Konsole (oder TinyBox neu starten). Danach steht der
Pfad im Startblock und in der Ausgabe von `LOG`.

**Empfehlung für den Alltag:** `level = INFO`, `monitor = yes`, `debug` leer.
DEBUG schaltet man erst ein, wenn man einen bestimmten Fehler jagt – siehe
Abschnitt 6.

---

## 2. Welche Dateien entstehen

| Datei | Inhalt |
|---|---|
| `logs\tinybox-2026-10-13.log` | alles von diesem Kalendertag |
| `logs\tinybox-2026-10-13.2.log` | Fortsetzung, wenn ein Tag über 20 MB geht |
| `logs\tinybox_debug_2026-10-13_20-08-31.txt` | Übergabepaket von `LOG BUNDLE` |

**Eine Datei pro Tag, nicht pro Start.** Ein Neustart hängt an dieselbe Datei an.
Das ist Absicht: nach `git pull` + `RESTART` stehen Ursache (geänderte Version,
geänderte Konfiguration) und Wirkung (der Fehler danach) in derselben Datei.

Neustarts sind trotzdem zu erkennen – die `-----`-Zeilen trennen die Läufe:

```
2026-10-13 20:08:31.648 I core  #0 - ----- stop: SHUTDOWN, 2s, 2 sessions, ... -----
2026-10-13 20:08:48.903 I core  #0 - ----- TinyBox 0.1.0 (f3bee5c) start -----
```

Dateien älter als `keep_days` werden beim Start und beim Tageswechsel gelöscht.
Andere Dateien im Ordner bleiben unberührt – gelöscht wird nur `tinybox-*.log`.

Logfiles gehören **nie ins Repo** (`.gitignore`). Sie müssen also aktiv
weitergegeben werden, siehe Abschnitt 5.

---

## 3. Eine Zeile lesen

```
2026-10-13 20:08:29.944 I session  #1 OE3TEC    < L
└──── Zeit mit ms ────┘  │ └─ Komp.┘ └─ Session ┘ └ Meldung
                      Level
```

| Spalte | Bedeutung |
|---|---|
| Zeit | lokale Zeit mit Millisekunden. Über Funk ist fast jeder Fehler ein Zeitproblem (T1, Retries), darum die ms. |
| Level | `D` Debug, `I` Info, `W` Warnung, `E` Fehler |
| Komponente | welcher Teil der TinyBox (Liste in Abschnitt 6) |
| Session | `#1 OE3TEC` = laufende Nummer der Verbindung + Rufzeichen. `#0 -` = gehört zu keiner Verbindung. |
| Meldung | der Text |

### Zeichen in der Meldung

| Zeichen | Bedeutung |
|---|---|
| `<` | Eingabe **der Station** an die TinyBox |
| `>` | Ausgabe **der TinyBox** an die Station |
| `<<` / `>>` | AGW-Frame mit Typ und Bytezahl (nur mit `LOG DEBUG agw`) |
| `(312ms)` | Dauer – dort ist die Zeit geblieben |
| `-----` | Anfang oder Ende eines Laufs |
| `===== MARK: ... =====` | vom Sysop gesetzte Marke |
| `12c 'Test subject'` | gekürzter Mail-Text: 12 Zeichen, so fängt er an |

Die Unterscheidung `<`/`>` gegen `<<`/`>>` ist beim Debuggen von Abbrüchen das
Entscheidende: fehlt eine Zeile auf Textebene oder schon auf Frameebene?

### Die Session-Nummer

Jede Verbindung bekommt eine Nummer, die in **jeder** Zeile dieser Verbindung
steht – auch in denen von `store`, `chat` und `sync`. Damit liefert eine Suche
nach `#1` die Verbindung vollständig, quer über alle Komponenten, auch wenn drei
Stationen gleichzeitig arbeiten.

Zwei gleichzeitige Verbindungen derselben Station (Funk und Telnet) sind so
auseinanderzuhalten – vorher war das unmöglich.

Nach einem Neustart zählt TinyBox über die höchste Nummer der Tagesdatei weiter.
`#7` bleibt also in der ganzen Datei eine Verbindung, nicht nur in einem Lauf.

### Der Startblock

Die ersten Zeilen jedes Laufs beantworten, was man beim Debuggen zuerst wissen
muss: welche Version läuft und was ist überhaupt eingeschaltet.

```
----- TinyBox 0.1.0 (f3bee5c) start -----
python 3.13.16 win32, Windows-10-..., pid 7312
config C:\Tinybox\tinybox.conf, data C:\Tinybox\data, log C:\Tinybox\logs\tinybox-2026-10-13.log
station mailbox OE3GAS-1, bbs OE3GAS, sysop OE3GAS
agw 127.0.0.1:8000 port 0, max_users 3
adapters: telnet=on web=on brocast=on inbox=on forward=off mqtt=off console=on
brocast token unset, level INFO, debug -, keep_days 14
```

`(f3bee5c)` ist der eingecheckte Git-Commit – damit ist eindeutig, welcher Code
lief. Token stehen **nie** im Log, nur `set` oder `unset`; die Web-Login-URL
bleibt wie bisher nur in der Konsole.

### Die Schlusszeile

```
----- stop: SHUTDOWN, 1h33m, 7 sessions, 412/388 frames in/out, 3 fwd, 2 warnings, 0 errors -----
```

Grund (`SHUTDOWN`, `RESTART`, `Ctrl+C`, `crash`), Laufzeit und Zähler. Damit ist
ein Lauf als sauber oder unsauber erkennbar, ohne die Datei zu lesen. Fehlt die
Schlusszeile ganz, ist der Prozess hart gestorben (Stromausfall, Task beendet).

---

## 4. Die Befehle in der Sysop-Konsole

Nur im **TinyBox-Fenster auf PC2**, nicht über Funk und nicht über Telnet.

| Befehl | Wirkung |
|---|---|
| `LOG` | Level, eingeschaltete Debug-Komponenten, Dateipfad und Dateigröße |
| `LOG DEBUG agw` | zusätzliches DEBUG für eine Komponente, sofort, ohne Neustart |
| `LOG DEBUG agw,fwd` | mehrere auf einmal |
| `LOG OFF agw` | diese Komponente zurück auf den normalen Level |
| `LOG OFF` | **alle** Debug-Komponenten aus |
| `LOG MARK <Text>` | schreibt `===== MARK: <Text> =====` in die Datei |
| `LOG BUNDLE` | Übergabepaket schreiben (siehe Abschnitt 5) |

Beispiel:

```
LOG
Level INFO, extra DEBUG: -
Log file: C:\Tinybox\logs\tinybox-2026-10-13.log (284 kB)
```

Was mit `LOG DEBUG` eingeschaltet wird, gilt für Datei **und** Konsole – man
liest also live mit. `MON OFF` schaltet wie bisher nur die Konsolenanzeige des
Sitzungsverkehrs ab, nicht das Logfile; dafür ist `[logging] monitor = no` da.

Ein unbekannter Komponentenname wird abgelehnt und die Liste ausgegeben.

---

## 5. Arbeitsablauf: einen Fehler mit Claude debuggen

Das ist der eigentliche Zweck. Fünf Schritte.

### Schritt 1 – Marke setzen

In der Sysop-Konsole, **bevor** der Fehler ausgelöst wird:

```
LOG MARK Sync bricht ab, Versuch 1
```

Das ist der Griff, der am meisten Zeit spart. Danach genügt „ab der Marke" statt
Uhrzeiten zu suchen.

### Schritt 2 – falls nötig DEBUG einschalten

Nur die Komponente, um die es geht (Zuordnung in Abschnitt 6):

```
LOG DEBUG sync
```

Nicht `LOG DEBUG all` – das schüttet die Datei mit Verkehr zu und macht sie
unlesbar.

### Schritt 3 – Fehler auslösen

Den Vorgang machen, der schiefgeht. Danach gleich wieder ausschalten:

```
LOG OFF
```

### Schritt 4 – übergeben

Zwei Wege, je nachdem wie die Claude-Sitzung läuft:

**a) Sitzung ist mit dem PC verbunden.** Dann genügt der Hinweis:

> Schau in `C:\Tinybox\logs\tinybox-2026-10-13.log` ab der Marke
> „Sync bricht ab, Versuch 1". Session `#4`.

**b) Sitzung ist nicht verbunden** (oder es soll alles auf einmal mit).
`LOG BUNDLE` in der Konsole, dann die entstandene
`logs\tinybox_debug_<Datum>_<Zeit>.txt` in den Chat hängen. Darin steht:

- der Startblock (Version, Commit, Adapter)
- Laufzeit und Zähler
- `tinybox.conf` **ohne Token und Passwörter**
- Verzeichnisübersicht von `data`
- die letzten 400 Zeilen des Logs

Ohne laufende TinyBox geht dasselbe von der Kommandozeile:

```
cd /d C:\Tinybox
py -3 -m tinybox -c tinybox.conf --debugbundle
```

Ist das Log größer als das Bundle hergibt, zusätzlich die Tagesdatei anhängen –
oder den Ausschnitt, siehe Abschnitt 7.

### Schritt 5 – was gesagt werden sollte

Hilfreich sind drei Angaben, alles andere steht im Log:

1. **Was erwartet war** und was stattdessen passiert ist.
2. **Die Marke** oder die Uhrzeit.
3. **Die Session-Nummer**, wenn es um eine Verbindung geht.

Nicht nötig: Version, Konfiguration, welche Adapter laufen, welcher Commit – das
liest Claude aus dem Startblock.

---

## 6. Welche Komponente für welches Problem

| Komponente | Zuständig für |
|---|---|
| `core` | Start, Konfiguration, Neustart, Shutdown |
| `agw` | Direwolf/AGW: Connects, Frames, Retries, Disconnects |
| `session` | Sitzungsablauf, Terminal-Ein- und Ausgabe, Mail schreiben |
| `cmd` | Befehlsausführung, Laufzeiten langsamer Befehle |
| `svc` | Nachrichtenregeln, Rechte, BID-Prüfung, angelegte Nachrichten |
| `store` | Datenbank |
| `chat` | Chat-Boards, Ereignisse, Bilder im Chat |
| `sync` | Client-Protokoll, Mail- und Bulletin-Abgleich (`//SYNC`, `//GET`) |
| `fwd` | Forwarding zu Partner-Mailboxen |
| `linkq` | Verbindungsqualität (Balken, `STAT`) |
| `web` | Sysop-Weboberfläche |
| `brocast` | Meldung der Bulletins an brocastd |
| `inbox` | Eingangsordner (Skripte, GeoSphere) |
| `news` | Client-News-Bulletins |
| `notify` | Mail-Benachrichtigung an Clients |
| `telnet` | Telnet-Testport |
| `sysop` | Sysop-Konsole |
| `bus` | Event-Bus |

Typische Zuordnung:

| Symptom | DEBUG auf |
|---|---|
| Verbindung bricht ab, Station hört nicht mehr | `agw` |
| Client synchronisiert nicht, holt dasselbe mehrfach | `sync` |
| Forwarding bleibt hängen oder wiederholt sich | `fwd` |
| Chat-Ereignisse kommen nicht an | `chat` |
| Befehl dauert auffällig lange | `cmd` |
| Bulletins erscheinen nicht in brocast | `brocast` |

`all` gibt es auch, ist aber nur für kurze, gezielte Versuche gedacht.

---

## 7. Rezepte zum Suchen

Windows-Eingabeaufforderung, im Ordner `C:\Tinybox`:

```bat
rem Alle Fehler und Warnungen
findstr /C:" E " /C:" W " logs\tinybox-2026-10-13.log

rem Eine Verbindung vollständig
findstr /C:"#4 " logs\tinybox-2026-10-13.log

rem Nur eine Komponente
findstr /C:" fwd " logs\tinybox-2026-10-13.log

rem Läufe und Marken: der Überblick über den Tag
findstr /C:"-----" /C:"MARK:" logs\tinybox-2026-10-13.log

rem Alles ab einer Zeit in eine Datei zum Anhängen
findstr /C:"2026-10-13 20:" logs\tinybox-2026-10-13.log > auszug.txt
```

PowerShell, wenn es mehr sein soll:

```powershell
# Eine Verbindung aus allen Tagesdateien
Select-String -Path logs\tinybox-*.log -Pattern '#4 ' -SimpleMatch

# Die letzten 200 Zeilen mitlesen, während etwas passiert
Get-Content logs\tinybox-2026-10-13.log -Tail 200 -Wait

# Alles zwischen zwei Marken
$t = Get-Content logs\tinybox-2026-10-13.log
$a = ($t | Select-String 'MARK: Versuch 1').LineNumber
$t[($a-1)..($t.Count-1)] | Set-Content auszug.txt
```

Merksätze:

- Zuerst `" E "` und `" W "` – und die Schlusszeile, die sagt, ob es welche gab.
- Dann die Session-Nummer greppen, nicht das Rufzeichen: bei zwei Verbindungen
  derselben Station liefert das Rufzeichen beide durcheinander.
- Ein `>` ohne folgendes `<` innerhalb von Sekunden heißt: die Station ist weg.
- Zahl in Klammern: dort ist die Zeit geblieben.

---

## 8. Was absichtlich nicht im Log steht

| Nicht drin | Warum |
|---|---|
| Token und Passwörter | nur `set`/`unset`. Auch im Bundle ersetzt durch `<removed>`. |
| Web-Login-URL | enthält das Geheimnis, bleibt nur in der Konsole |
| Volltext von Mails | nur `12c 'Test subject'`. Das Log landet in Chats, fremde persönliche Post soll nicht mitfahren. |

Den Mail-Volltext bekommt man bei Bedarf mit `LOG DEBUG session`. Befehle,
Antworten und Chat-Zeilen stehen immer vollständig drin – sonst wäre das
Protokoll nicht mehr zu lesen, und Chat hören die Mitlauscher ohnehin mit.

Wer gar keinen Sitzungsverkehr im Log will: `[logging] monitor = no`. Dann
bleiben Ereignisse, Warnungen und Fehler, aber `<` und `>` fehlen.

---

## 9. Dauerbetrieb und Platz

- Jede Zeile wird sofort geschrieben (`flush`), damit nach einem Absturz die
  letzte Zeile noch da ist. Das kostet Schreibzugriffe.
- Auf dem **Appliance-Gerät mit eMMC** darum `log_dir` leer lassen und das
  Journal nutzen. Zum Fehlersuchen vorübergehend `log_dir = /run/tinybox/logs`
  setzen – das liegt im RAM. Siehe `PRODUCTION.md`.
- Größe: eine Zeile ist rund 100 Byte, und bei `monitor = yes` erzeugt jede
  Terminalzeile einer Station eine. Eine Sitzung mit `L` und ein paar Befehlen
  kostet also einige kB. Mit `LOG DEBUG agw` kommt pro Frame eine Zeile dazu.
  Ab 20 MB am Tag läuft es in `.2` weiter. Nach der ersten Woche lohnt ein Blick
  auf die tatsächliche Größe (`LOG` zeigt sie) und ein passendes `keep_days`.
- `keep_days = 14` ist der Standard. Bei knappem Platz kleiner setzen, z. B. `3`.

---

## 10. Wenn das Logging selbst nicht tut

| Beobachtung | Ursache |
|---|---|
| Keine Datei im Ordner | `log_dir` leer, oder TinyBox seit der Änderung nicht neu gestartet. `LOG` zeigt, was gilt. |
| TinyBox startet nicht, Meldung zu `log_dir` | Ordner fehlt oder ist nicht beschreibbar |
| `LOG` sagt „log_dir is empty" | `log_dir` ist nicht gesetzt |
| Keine `D`-Zeilen trotz `LOG DEBUG` | richtige Komponente? `LOG` zeigt die eingeschalteten. Manche Vorgänge schreiben nur auf INFO. |
| Keine `<`/`>`-Zeilen | `[logging] monitor = no` |
| `LOG` gibt es nicht | der Befehl läuft nur in der lokalen Sysop-Konsole, nicht über Funk oder Telnet |
| Datei wächst nach Mitternacht nicht weiter | Tagesdatei gewechselt: die neue heißt nach dem neuen Datum |
| Session-Nummern springen | normal nach einem Neustart: es wird über die höchste Nummer des Tages weitergezählt |

---

## 11. Kurzfassung

```
mkdir logs                       einmalig
[logging] log_dir = logs         in tinybox.conf, dann RESTART

LOG                              Status
LOG MARK <Text>                  Marke vor dem Versuch
LOG DEBUG <komp>  /  LOG OFF     gezielt mehr Details
LOG BUNDLE                       eine Datei zum Weitergeben

findstr /C:" E " logs\tinybox-<Datum>.log      Fehler zuerst
findstr /C:"#4 " logs\tinybox-<Datum>.log      eine Verbindung
```
