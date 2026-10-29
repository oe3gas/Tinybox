# tbtest – Testbed für TinyBox

tbtest startet eine **eigene Test-TinyBox** und lässt **1 bis 10 simulierte User** mit ihr
arbeiten, alles über AXUDP auf diesem PC. Am Ende prüft es Ende zu Ende, ob alles
angekommen ist, und schreibt einen Bericht. Konzept und Entscheidungen: `PLANUNG.md` 27.

```
tbtest (ein Prozess)                                  Test-TinyBox OE3TBX-1 (eigener Prozess)
  Terminal-User  OE1TBA …  ─┐                           eigene tinybox.conf, eigene DB
  (tippen S, L, R, K, C …)  ├── AXUDP 127.0.0.1 ──►    AXUDP 10193, Web 8180, Telnet 6400
  Client-User    DL3TBF …  ─┘                           Funk: KISS an die Funk-Attrappe
  (echter tbclient-Kern)
  Funk-Attrappe 10190 ◄──── schluckt jeden Frame (Box und Clients), nichts geht in die Luft
```

- **Terminal-User** verbinden sich mit dem eigenen AX.25 von `prcore` und tippen
  Mailbox-Befehle wie ein Mensch: Prompt abwarten, Befehl, Antwort lesen.
- **Client-User** sind der echte Client-Kern (`tbclient.core.ClientCore`) ohne Web-GUI.
  Sie machen dieselben Aufrufe wie die Web-GUI: Verbinden, Ausgang + Senden, Sync,
  Text holen, Löschen, Chat, Bilder.
- Die **Rufzeichen sind fiktiv** (OE…TB… / DL…TB…) und laufen nur über Loopback.
- Die Test-Box ist **vollständig getrennt** von deiner TinyBox: eigene Konfiguration,
  eigene Datenbank, eigene Ports. Ihr „Funk“ ist die Funk-Attrappe von tbtest. tbtest
  importiert nichts aus `tinybox` – die Box wird von außen geprüft (wie bei fwdsim).

## Testbed-Verzeichnis

Standard: `tinybox-testbed` **neben** dem Repo, also bei `E:\Tinybox` → `E:\tinybox-testbed`.
Anders mit `-D <ordner>` vor dem Befehl oder der Umgebungsvariable `TBTEST_DIR`.

```
E:\tinybox-testbed\
  tbtest.conf      User-Rufzeichen und Ports – von `tbtest init`, darf geändert werden
  tinybox.conf     die Test-Box – von `tbtest init` aus tbtest.conf ERZEUGT
  data\            Datenbank der Test-Box
  logs\            Log-Dateien der Test-Box
  users\<CALL>\    Daten der Client-User (Postfach, Bilder …)
  runs\<zeit>\     je Lauf: report.txt, result.json, tinybox.out, tbtest.log
```

## Bedienung

```
tbtest init                  Verzeichnis anlegen (einmal; nach Änderung von tbtest.conf wieder)
tbtest run                   4 User, alle Funktionen, 5 Minuten
tbtest run -u 10 -t 10m      10 User, 10 Minuten
tbtest run -u 6 --terminal 2 -f conn,send,read -t 3m
tbtest run -u 10 -f chat,img --stay 30-90
tbtest report                Bericht des letzten Laufs nochmals anzeigen
tbtest box                   nur die Test-Box starten (Telnet, Web-GUI, eigener Client), Strg+C beendet
tbtest reset                 Datenbank der Test-Box und Client-Daten leeren (Logs, Läufe bleiben)
tbtest funcs                 Funktionen auflisten
```

Unter Windows `tbtest.bat …`, unter Linux `python3 -m tbtest …` (aus dem Repo-Ordner).

| Option | Bedeutung | Standard |
|---|---|---|
| `-u N` | Anzahl User (1–10) | 4 |
| `--terminal N` | davon Terminal-User, der Rest Client-User | die Hälfte (aufgerundet) |
| `-f LISTE` | Funktionen, z. B. `conn,send,read` oder `all` | `all` |
| `-t ZEIT` | Dauer: `90s`, `10m`, `1h` | `5m` |
| `-r N` | Aktionen je User (endet früher, wenn erreicht) | – |
| `--think A-B` | Pause zwischen zwei Aktionen in Sekunden | `2-10` |
| `--stay A-B` | Aufenthalt in einem Chat-Board in Sekunden | `15-45` |
| `--seed N` | gleiche Zufallsauswahl wie ein früherer Lauf (steht im Bericht) | zufällig |
| `--fresh` | vor dem Lauf Test-Box und Client-Daten leeren | – |
| `--no-final` | keine Schlussrunde (siehe unten) | – |

## Funktionen

| Funktion | Wer | Was passiert | Was geprüft wird |
|---|---|---|---|
| `conn` | T, C | alle 1–5 Aktionen neu verbinden, Login, Trennen (`B`) | Connect, Prompt bzw. `//OK`, sauberes Trennen; Zeiten |
| `send` | T, C | persönliche Nachricht an einen anderen Test-User (60 B – 7 KB) | gespeichert (`Msg n saved.` / `//SENT`) |
| `bull` | T, C | Bulletin an die Rubrik `TBTEST` | gespeichert |
| `read` | T, C | T: `LM`, `L> TBTEST`, `R n` – C: Sync, Text holen, öffnen | Nachricht da, Prüfsumme des Textes stimmt |
| `kill` | T, C | gelesene eigene Nachricht löschen (T: `K n`, C: Löschen + Sync) | danach wirklich weg |
| `info` | T | `V H L LB LP F I N NL J QSO C` und ein unbekannter Befehl | erwartete Antwort |
| `chat` | T, C | Board betreten, 1–4 Zeilen schreiben, verlassen | jede Zeile erreicht jeden, der gerade im Board ist; Client sieht seine eigene Zeile zurück |
| `img` | C | Bild in TREFF oder TECH; andere Clients dort holen es | Bild kommt unverändert an |

Ohne `conn` bleibt jeder User den ganzen Lauf über verbunden. Bei `chat` und `img` gehen die
User zur Hälfte dorthin, wo schon andere sind – so gibt es genug Überschneidungen für den
Fan-out-Test.

**Schlussrunde:** Nach Ablauf der Zeit verbindet sich jeder User noch einmal und liest alles,
was er noch nicht gelesen hat. Erst danach zählt eine Nachricht als „verloren“.

## Ende-zu-Ende-Prüfung

Jede Nachricht trägt in der ersten Zeile eine Marke `TBTEST <schlüssel> <prüfsumme>`, der
Betreff ist `tbt <lauf> <CALL>#<n>`. Der Leser rechnet die Prüfsumme nach. Persönliche Post
muss beim Empfänger ankommen, jedes Bulletin bei jedem anderen User. Nachrichten früherer Läufe
werden ignoriert. Chat-Zeilen beginnen mit `tbt <schlüssel>`: Wer beim Senden im Board war
(mit 2 s Spielraum nach dem Betreten und vor dem Verlassen), muss die Zeile bekommen.

**Bestanden** ist ein Lauf, wenn keine Aktion fehlschlug, nichts verloren oder verfälscht ist,
keine Chat-Zeile fehlt, die Funk-Attrappe keinen Connected-Mode-Frame gesehen hat (alles
zwischen User und Box muss über AXUDP gehen) und die Test-Box keine Fehlerzeile ausgegeben
hat. Exit-Code 0 = bestanden, 1 = nicht bestanden, 2 = Bedienfehler.

## Bericht (Beispiel)

```
Functions (times of the successful, non-idle actions):
  function              n    ok  fail  idle      min    avg    p95    max  (ms)
  connect+login        59    59     0     0        5    513   1066   1071
  send personal        35    35     0     0        7     76    258    259
  read + check         28    28     0     8        8    100    264    266
  chat join            26    26     0     0        1     29     51     52
  picture fetch        20    20     0     0       51     51     52     52
End to end:
  personal mail  stored 35, arrived intact 35, corrupt 0, missing 0
  bulletins      stored 7, reads intact 63 of 63, corrupt 0, missing 0
  chat           60 lines, delivered 191 of 191, own echo missing 0, delay avg 6 ms, p95 10 ms
  pictures       sent 7, fetched by others 20, intact 20
Dummy radio:   24 frame(s), 24 UI frame(s) of the box, 0 connected-mode frame(s) (must be 0)
RESULT: PASSED
```

`idle` = es gab nichts zu tun (z. B. keine ungelesene Post); diese Aktionen zählen nicht in die
Zeiten. Die UI-Frames auf der Funk-Attrappe sind die TBMAIL-Hinweise der Box.

## Hinweise

- Während eines Laufs ist die Web-GUI der Test-Box unter dem Link aus der ersten Zeile
  erreichbar (Login-Token steht auch in `runs\<zeit>\tinybox.out`).
- Die Ports in `tbtest.conf` dürfen sich nicht mit der echten TinyBox überschneiden
  (Standard: Box-AXUDP 10193, User 10201–10210, Funk-Attrappe 10190, Web 8180, Telnet 6400).
- Strg+C bricht ab; der Bericht wird trotzdem geschrieben (Ergebnis „ABORTED“).
- Stirbt die Test-Box während des Laufs, endet der Lauf sofort (Exit-Code steht im Bericht).
- Noch nicht Teil des Tests (nächster Schritt): Funkstrecke (Verlust, 1200/9600 Bd), mehr als
  10 User, Forwarding.
