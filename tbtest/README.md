# tbtest – Testbed für TinyBox

tbtest startet eine **eigene Test-TinyBox** und lässt **1 bis 30 simulierte User** mit ihr
arbeiten, alles über AXUDP auf diesem PC. Dazwischen sitzt ein **simulierter Funkkanal**
(1200 Bd, eine gemeinsame Frequenz, User mit unterschiedlicher Verbindungsqualität). Du kannst
dich mit deinem eigenen TinyBox-Client dazuhängen. Am Ende prüft tbtest Ende zu Ende, ob alles
angekommen ist, und schreibt einen Bericht. Konzept und Entscheidungen: `PLANUNG.md` 27.

```
tbtest (ein Prozess)                                         Test-TinyBox OE3TBX-1
  Terminal-User  OE1TBA …  ─┐                                (eigener Prozess, eigene DB)
  Client-User    DL3TBF …  ─┼─ AXUDP ─► Funkkanal ─ AXUDP ─►  AXUDP 10193
  dein Client    OE3GAS    ─┘          10192/udp              Web 8180, Telnet 6400
                                       1200 Bd, CSMA,
                                       Kollisionen, Verlust
```

- **Terminal-User** verbinden sich mit dem eigenen AX.25 von `prcore` und tippen
  Mailbox-Befehle wie ein Mensch: Prompt abwarten, Befehl, Antwort lesen.
- **Client-User** sind der echte Client-Kern (`tbclient.core.ClientCore`) ohne Web-GUI.
  Sie machen dieselben Aufrufe wie die Web-GUI: Verbinden, Ausgang + Senden, Sync,
  Text holen, Löschen, Chat, Bilder.
- Die **Rufzeichen sind fiktiv** (OE…TB… / DL…TB…, 30 Stück) und laufen nur über Loopback.
- Die Test-Box ist **vollständig getrennt** von deiner TinyBox: eigene Konfiguration,
  eigene Datenbank, eigene Ports. tbtest importiert nichts aus `tinybox` – die Box wird von
  außen geprüft (wie bei fwdsim).

## Der simulierte Funkkanal

Alle AXUDP-Pakete zwischen Box und Usern gehen durch ein Relais in tbtest (Port 10192). Es
verhält sich wie **eine gemeinsame Halbduplex-Frequenz** mit einem TNC pro Station:

| Was | Wie |
|---|---|
| Bitrate | 1200 oder 9600 Bd (`--air`, Standard `air_baud` in `tbtest.conf`); Sendezeit = (Bytes + FCS) · 8 · 1,03 / Baud |
| TNC | jede Station hat eine Sendewarteschlange; ein Tastendruck = TXDELAY + alle wartenden Frames (max. 7) hintereinander |
| Kanalzugriff | Carrier Sense + p-Persistence (`persist`, `slottime`) |
| Kollisionen | ein Frame geht verloren, wenn beim Empfänger gleichzeitig ein anderer sendet, den er hört – oder er selbst sendet (Halbduplex) |
| Versteckte Stationen | ein „hidden“ User hört die anderen User nicht und sie ihn nicht: keine Rücksicht, Kollisionen an der Box. Die Box hört alle, alle hören die Box. |
| Qualität | Profil je User: **good** 1 %, **medium** 8 %, **poor** 25 % Frame-Verlust (für 256 Byte, je Richtung); kurze Frames gehen seltener verloren (Bitfehlerrate) |
| Mithören | wer den Sender hört, bekommt eine Kopie des Frames (nicht an ihn adressiert): sein AX.25 sieht den belegten Kanal und hält T1 an – wie über Funk |

Verteilung der Profile: `mix` und `hidden` in `tbtest.conf` (Standard 50 % good, 30 % medium,
20 % poor, 20 % hidden), gemischt mit dem Seed des Laufs; einzelne Rufzeichen fest in
`[quality]` (z. B. `OE1TBA = poor hidden`). Der Bericht nennt bei jedem User sein Profil.

Damit Box, User und Clients über diesen langsamen Weg vernünftig arbeiten, läuft ihr AX.25
über AXUDP **mit Sendezeit** (Fenster und T1 je Bitrate, siehe unten), T1 erst nach dem eigenen
Senden, gehörte Frames halten T1 an (dafür nimmt der AXUDP-Endpunkt in diesem Modus auch Frames
anderer Stationen an, die nicht an ihn gehen – nur zum Mithören). Dafür gibt es neu `[axudp] air_baud / txdelay_ms` in
`tinybox.conf` und `[tinybox] axudp_air_baud / axudp_maxframe …` in `tbclient.conf`;
`tbtest init` trägt alles ein.

`--air 0` schaltet den Kanal ab: die Pakete gehen sofort durch – ein schneller Funktionstest
wie im ersten Testbed.

## Werte je Bitrate: `[air.<baud>]`

`tbtest.conf` hat für jede Bitrate einen eigenen Abschnitt. Ein Lauf nimmt **alle** Werte aus dem
Abschnitt seiner Bitrate – `tbtest run --air 9600` also `[air.9600]`, ohne `--air` den Abschnitt
von `[radio] air_baud` (Standard 1200):

| Wert | `[air.0]` (kein Kanal) | `[air.1200]` | `[air.9600]` | wofür |
|---|---|---|---|---|
| `txdelay_ms` | – | 300 | 150 | Kanal: Tastzeit je Sendung |
| `persist` / `slottime_ms` | – | 63 / 100 | 63 / 50 | Kanal: p-Persistence |
| `paclen` | 256 | 256 | 256 | AX.25 von Box, Usern, deinem Client |
| `maxframe` | 32 | 4 | 7 | Fenster |
| `t1_sec` | 3 | 6 | 3 | T1 von diesem Wert bis zum Vierfachen |
| `n2` | 10 | 10 | 10 | Wiederholungen |
| `think` | 2-10 | 30-180 | 10-60 | Pause der User zwischen zwei Aktionen (s) |
| `stay` | 15-45 | 60-180 | 30-120 | Aufenthalt in einem Chat-Board (s) |
| `timeout` | 60 | 300 | 120 | ein Schritt einer Aktion höchstens (s) |
| `msg_max` / `img_max` | 7000 / 7500 | 3000 / 2000 | 7000 / 5000 | größte Nachricht / größtes Bild (Byte) |
| `minutes` | 5 | 15 | 10 | Dauer ohne `-t` |

Die Werte dürfen geändert werden (danach `tbtest init`), etwa `txdelay_ms` auf den Wert deiner
echten 9600-Station. Weitere Bitraten (300, 2400, 4800) bekommen einen eigenen Abschnitt
`[air.2400]` usw. Die Test-Box bekommt für einen Lauf mit anderer Bitrate als dem Standard eine
eigene `tinybox.conf` im Laufordner. `--think`, `--stay` und `-t` überschreiben die Werte für
einen Lauf.

## Dein eigener Client

`tbtest init` erzeugt je Bitrate eine Client-Konfiguration: `tbclient-testbed-1200.conf`,
`tbclient-testbed-9600.conf`, `tbclient-testbed-0.conf`. Nimm die, die zum laufenden Testbed
passt – die erste Zeile eines Laufs nennt sie:

```
tbtest.bat run -u 20 -t 0 --air 9600
tbclient.bat -c E:\tinybox-testbed\tbclient-testbed-9600.conf
```

und im Browser http://127.0.0.1:7745/ öffnen. Du bist dort **OE3GAS** (nicht Sysop – Sysop der
Test-Box ist OE3TBS), mit eigenem Datenordner `guest\`; dein normaler Client und seine Daten
bleiben unberührt. Du hängst mit der Qualität aus `[guest] quality` (Standard good) am selben
simulierten Kanal wie die User, kannst im Chat mitschreiben, Post an die Test-User schicken
usw. Deine Nachrichten zählen nicht zur Ende-zu-Ende-Prüfung. Der Client braucht immer auch
einen Funk-Port – im Testbed ist das die Funk-Attrappe von tbtest, die alles schluckt; es
geht nichts in die Luft.

Für eine lange Sitzung zum Mitspielen: `tbtest run -u 20 -t 0` – läuft bis Strg+C.

## Testbed-Verzeichnis

Standard: `tinybox-testbed` **neben** dem Repo, also bei `E:\Tinybox` → `E:\tinybox-testbed`.
Anders mit `-D <ordner>` vor dem Befehl oder der Umgebungsvariable `TBTEST_DIR`.

```
E:\tinybox-testbed\
  tbtest.conf             User, Ports, Kanal, Qualität, Gast – von `tbtest init`, darf geändert werden
  tinybox.conf            die Test-Box – ERZEUGT aus tbtest.conf
  tbclient-testbed-<baud>.conf   dein Client im Testbed, je Bitrate – ERZEUGT aus tbtest.conf
  data\                   Datenbank der Test-Box
  logs\                   Log-Dateien der Test-Box
  users\<CALL>\           Daten der Client-User
  guest\                  Daten deines Testbed-Clients
  runs\<zeit>\            je Lauf: report.txt, result.json, tinybox.out, tbtest.log
```

Nach einer Änderung an `tbtest.conf` wieder `tbtest init`. Eine `tbtest.conf` der ersten
Version (ohne `[radio]` oder ohne `[air.<baud>]`) erneuert `tbtest init` selbst, die Ports bleiben.

## Bedienung

```
tbtest init                  Verzeichnis anlegen bzw. erzeugte Dateien erneuern
tbtest run                   6 User, alle Funktionen, 1200 Bd, 15 Minuten
tbtest run -u 20 -t 30m      20 User, 30 Minuten
tbtest run -u 30 -t 0        30 User, bis Strg+C (zum Mitspielen mit deinem Client)
tbtest run -u 10 --air 9600  10 User auf 9600 Bd (Werte aus [air.9600])
tbtest run -u 10 --air 0 -t 5m        ohne Funkkanal: schneller Funktionstest
tbtest run -u 6 --terminal 2 -f conn,send,read
tbtest report                Bericht des letzten Laufs nochmals anzeigen
tbtest box                   nur Test-Box + Kanal (Telnet, Web-GUI, dein Client), Strg+C beendet
tbtest reset                 Datenbank der Test-Box und Daten der Client-User leeren
tbtest funcs                 Funktionen auflisten
```

Unter Windows `tbtest.bat …`, unter Linux `python3 -m tbtest …` (aus dem Repo-Ordner).

| Option | Bedeutung | Standard |
|---|---|---|
| `-u N` | Anzahl User (1–30) | 6 |
| `--terminal N` | davon Terminal-User, der Rest Client-User | die Hälfte (aufgerundet) |
| `-f LISTE` | Funktionen, z. B. `conn,send,read` oder `all` | `all` |
| `-t ZEIT` | Dauer: `90s`, `10m`, `1h`; `0` = bis Strg+C | `minutes` der Bitrate |
| `-r N` | Aktionen je User (endet früher, wenn erreicht) | – |
| `--air BAUD` | Bitrate: 1200, 9600; 0 = kein Kanal | `[radio] air_baud` |
| `--think A-B` | Pause zwischen zwei Aktionen in Sekunden | `think` der Bitrate |
| `--stay A-B` | Aufenthalt in einem Chat-Board in Sekunden | `stay` der Bitrate |
| `--seed N` | gleiche Auswahl und Qualitäten wie ein früherer Lauf (steht im Bericht) | zufällig |
| `--fresh` | vor dem Lauf Test-Box und Client-Daten leeren | – |
| `--no-final` | keine Schlussrunde (siehe unten) | – |

**Strg+C:** das erste beendet die Aktionen (laufende werden fertig), dann folgen Schlussrunde
und Bericht; das zweite bricht sofort ab (Ergebnis „ABORTED“).

## Funktionen

| Funktion | Wer | Was passiert | Was geprüft wird |
|---|---|---|---|
| `conn` | T, C | alle 1–5 Aktionen neu verbinden, Login, Trennen (`B`) | Connect, Prompt bzw. `//OK`, sauberes Trennen; Zeiten |
| `send` | T, C | persönliche Nachricht an einen anderen Test-User (über Funk 60 B – 3 KB) | gespeichert (`Msg n saved.` / `//SENT`) |
| `bull` | T, C | Bulletin an die Rubrik `TBTEST` | gespeichert |
| `read` | T, C | T: `LM`, `L> TBTEST`, `R n` – C: Sync, Text holen, öffnen | Nachricht da, Prüfsumme des Textes stimmt |
| `kill` | T, C | gelesene eigene Nachricht löschen (T: `K n`, C: Löschen + Sync) | danach wirklich weg |
| `info` | T | `V H L LB LP F I N NL J QSO C` und ein unbekannter Befehl | erwartete Antwort |
| `chat` | T, C | Board betreten, 1–4 Zeilen schreiben, verlassen | jede Zeile erreicht jeden, der gerade im Board ist; Client sieht seine eigene Zeile zurück |
| `img` | C | Bild in TREFF oder TECH; andere Clients dort holen es | Bild kommt unverändert an |

Ohne `conn` bleibt jeder User den ganzen Lauf über verbunden. Bei `chat` und `img` gehen die
User zur Hälfte dorthin, wo schon andere sind. Schlägt bei einem Terminal-User eine Aktion
fehl, trennt er die Verbindung und fängt mit einer neuen Sitzung an (wie ein Mensch, der nicht
mehr weiß, wo die Box gerade steht). Kommt lange nichts (ein Viertel des Timeouts), drückt er
Enter – nach einem Reset der Verbindung ist der Prompt oft verloren.

**Schlussrunde:** Nach Ablauf der Zeit verbindet sich jeder User noch einmal und liest alles,
was er noch nicht gelesen hat. Erst danach zählt eine Nachricht als „verloren“.

## Ende-zu-Ende-Prüfung

Jede Nachricht trägt in der ersten Zeile eine Marke `TBTEST <schlüssel> <prüfsumme>`, der
Betreff ist `tbt <lauf> <CALL>#<n>`. Der Leser rechnet die Prüfsumme nach. Persönliche Post
muss beim Empfänger ankommen, jedes Bulletin bei jedem anderen User. Nachrichten früherer Läufe
werden ignoriert. Chat-Zeilen beginnen mit `tbt <schlüssel>`: wer im Board war, bevor die Zeile
geschickt wurde, und noch drin war, als die Box sie weitergab (spätestens, als der Erste sie
bekam), muss sie bekommen.

**Bestanden** ist ein Lauf, wenn keine Aktion fehlschlug, nichts verloren oder verfälscht ist,
keine Chat-Zeile fehlt, die Funk-Attrappe keinen Connected-Mode-Frame gesehen hat und die
Test-Box keine Fehlerzeile ausgegeben hat. Exit-Code 0 = bestanden, 1 = nicht bestanden,
2 = Bedienfehler. Auf einem vollen 1200-Bd-Kanal mit schlechten und versteckten Stationen ist
„nicht bestanden“ ein Ergebnis, kein Fehler von tbtest – der Bericht zeigt, wo es hakt.

## Bericht

Neben den Zeiten je Funktion, den Usern (mit Qualität) und der Ende-zu-Ende-Bilanz gibt es den
Abschnitt **Simulated channel**.
Beispiel (10 User, 1200 Bd, Auszug):

```
1200 Bd, TXDELAY 300 ms, persist 63, slottime 100 ms - channel busy 58.7% of 703 s
station    quality        frames     kB  air s repeat lost:noise collis. wait avg   max
OE3TBX-1   box               347   24.4    227     47          9       0     1.2s   11s
OE1TBA     good hidden        32    0.8     15      4          0      14     0.7s    2s
DL1TBB     medium hidden      58    1.2     24      5          0      19     1.2s    7s
OE3TBC     good               32    0.8     15      4          0       2     1.8s    8s
```

`frames` = gesendet inkl. Wiederholungen, `repeat` = dasselbe I-Frame nochmals (Retry),
`lost` = Frames dieser Station, die beim Empfänger nicht ankamen (Rauschen / Kollision),
`wait` = Zeit in der Sendewarteschlange, weil der Kanal belegt war.

## Hinweise

- Während eines Laufs ist die Web-GUI der Test-Box unter dem Link aus der ersten Zeile
  erreichbar (Login-Token steht auch in `runs\<zeit>\tinybox.out`).
- Die Ports in `tbtest.conf` dürfen sich nicht mit der echten TinyBox und deinem echten
  Client überschneiden (Standard: Box 10193, Kanal 10192, User 10201–10230, Gast 10240,
  Funk-Attrappe 10190, Web 8180, Telnet 6400, Gast-Web 7745).
- Die Test-Box behält Post und Chat früherer Läufe. Über Funk werden Listen (`LM`,
  `L> TBTEST`) und Login-Syncs dadurch mit der Zeit länger und teurer – für vergleichbare
  Läufe `--fresh` verwenden.
- Stirbt die Test-Box während des Laufs, endet der Lauf sofort (Exit-Code steht im Bericht).
- Über AXUDP schickt die Box Chat-Ereignisse als I-Frames an jeden Teilnehmer, nicht als
  UI-Frame an alle wie über Funk – der Fan-out kostet hier also mehr Sendezeit als auf einer
  echten Frequenz.
- Noch nicht Teil des Tests: Forwarding.
