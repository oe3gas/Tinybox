# TinyBox

Kleine lokale Packet-Radio-Mailbox für Direwolf. Planung: `PLANUNG.md`.

## Voraussetzung

Python 3.10 oder neuer (https://www.python.org). Für M1 sind keine Zusatzpakete nötig.

## Starten

Doppelklick auf `tinybox.bat`, oder in der Eingabeaufforderung:

```
cd /d E:\Tinybox
py -3 -m tinybox -c tinybox.conf
```

Beenden mit `SHUTDOWN` (oder Ctrl+C). Die Daten liegen unter `data\`.

Log-Datei: in `tinybox.conf` unter `[logging]` einen vorhandenen Ordner bei
`log_dir` eintragen (z. B. `logs`). Jeder Start legt dort
`Tinybox_log_<Datum>_<Uhrzeit>.log` an. Leer = keine Log-Datei.

## Ohne Funk testen (Telnet-Testport)

PuTTY: Host `127.0.0.1`, Port `6300`, Connection type **Telnet**.
Als Rufzeichen z. B. `OE1ABC` eingeben. Mit dem Sysop-Call (`OE3GAS`) hast du Sysop-Rechte.

## Mit Direwolf

In `direwolf.conf`:

```
MYCALL OE3GAS          # Direwolf selbst; die Mailbox nutzt OE3GAS-1
AGWPORT 8000
```

Erst Direwolf starten, dann TinyBox. Die Reihenfolge ist nicht kritisch:
TinyBox versucht es alle `reconnect_sec` Sekunden erneut und verbindet sich
auch nach einem Direwolf-Neustart selbst wieder.

Im Log sollte stehen:

```
connected to Direwolf AGW 127.0.0.1:8000
Direwolf AGW version 1.x
mailbox call OE3GAS-1 registered with Direwolf
```

Danach von einer zweiten Station (oder einem zweiten Direwolf/TNC) `C OE3GAS-1` connecten.

## Sysop-Weboberfläche

Beim Start zeigt das TinyBox-Fenster den Login-Link:

```
  Web GUI login:  http://127.0.0.1:8080/login?token=...
```

Link im Browser öffnen (am besten als Lesezeichen speichern). Der Token liegt in
`data\web.token` und bleibt über Neustarts gleich. Neuer Token: Datei löschen und
TinyBox neu starten. Konsolenbefehl `WEB` zeigt den Link erneut.

Die Oberfläche ist nur am eigenen PC erreichbar (127.0.0.1). Einstellungen unter `[web]`.

## Sysop-Konsole

Im TinyBox-Fenster tippen. Es gelten alle Mailbox-Befehle mit Sysop-Rechten
(`L`, `R n`, `K n`, `E n ...`, `S call`, `SB ALL` ...), dazu:

| Befehl | Funktion |
|---|---|
| `W` | Wer ist verbunden |
| `MON [ON\|OFF]` | Laufende Sitzungen mitlesen (ohne Argument: umschalten) |
| `DISC call` | Benutzer trennen (ohne SSID: alle SSIDs dieses Calls) |
| `STATUS` | Direwolf-Verbindung, Benutzer, Nachrichten |
| `WEB` | Login-Link der Weboberfläche anzeigen |
| `SHUTDOWN` | TinyBox sauber beenden (Benutzer werden verabschiedet) |

Nachricht beenden mit `/EX`. Log-Meldungen und Monitor erscheinen
zwischen den Eingaben – das ist normal.

## Chat

Eingeloggte Benutzer (Funk, Telnet) wechseln mit `C` in den Chat: `C` zeigt die
Boards, `C TREFF` oder `C 1` betritt eines. Dort ist jede Zeile Chat-Text,
Befehle beginnen mit `/`: `/Q` (oder `/EX`, `^Z`) zurück zur Mailbox, `/W` wer ist
da, `/L` Boards, `/J board` wechseln, `/H` Hilfe.

Die Boards legt der Sysop in `tinybox.conf` unter `[chat_boards]` fest
(`NAME = Aufbewahrung Beschreibung`):

```
[chat_boards]
TREFF = 7d    General meeting point
DX    = 24h   DX spots and news
RUNDE = live  Live round, nothing is stored
```

`live` = nichts wird gespeichert, nur wer gerade im Board ist, liest mit.
`12h`/`7d` = Verlauf so lange aufbewahren; beim Betreten werden die letzten
`history_lines` Zeilen gezeigt (`[chat]`). Ältere Zeilen löscht TinyBox
automatisch. Im Chat gilt kein Idle-Timeout (Mitlesen ist erlaubt), zurück in
der Mailbox wieder `idle_timeout_min`. Änderungen an den Boards wirken nach einem Neustart. Konsole (`W`)
und Weboberfläche zeigen, wer in welchem Board ist; mitchatten nur über die Mailbox.

## Tests

Doppelklick auf `runtests.bat`.

## Stand

- M1 (lokale Mailbox + Telnet): fertig
- M2 (Direwolf über AGW): fertig, Funktest erfolgreich
- M3 (Sysop-Konsole, Monitor): fertig
- M3b (Sysop-Weboberfläche): fertig
- M3c–M3f (DICT, brocast-Anbindung, Eingangsordner, Kopfzeile Brocast:): fertig
- Chat-Boards (Befehl C): fertig
- Forwarding (optionales Modul): F1–F5 fertig (Empfangen, Senden, B1 komprimiert, Zeitplan, HOLD/REL), mit LinBPQ getestet; als Nächstes F6 (Anschluss ans Netz)
- M4 (Limits, Rate-Limit, Dauerbetrieb): offen
- TinyBox-Client (C0–C3): umgesetzt – Post-Hinweis, Chat per UI-Broadcast, Offline-Mailbox mit Abgleich (`tbclient.bat`)

Details und Meilensteine: `PLANUNG.md` (Rev. 4).
