# TinyBox – Handbuch

Betrieb von TinyBox, TinyBox-Client, kisshub und den Hilfsprogrammen: welche Teile es gibt,
wie sie zusammenhängen, wie man sie konfiguriert und wie man die Funkstrecke misst.

Weitere Unterlagen: `README.md` (Start, Telnet-Test, Sysop-Konsole), `logging_manual.md`
(Log-Datei lesen), `docs/kiss-mode-konzept.md` (KISS-Mode, VARA, Messungen),
`docs/client-change-requests.md` (alle Änderungen), `PLANUNG.md` (Entscheidungen).

Stand: 18.10.2026

---

## 1. Die Teile

| Programm | Aufgabe | Start | Konfiguration |
|---|---|---|---|
| **TinyBox** | die Mailbox (BBS): Post, Bulletins, Chat, Forwarding, Web-GUI für den Sysop | `tinybox.bat` | `tinybox.conf` |
| **TinyBox-Client** (`tbclient`) | Programm für Benutzer: Chat, Post, Monitor, APRS – im Browser | `tbclient.bat` | `tbclient.conf` |
| **kisshub** | besitzt den KISS-TNC (PK-232, Kenwood, Direwolf-KISS, VARA FM) und teilt ihn per KISS-TCP; misst die Verbindungsqualität | `kisshub.bat` bzw. `python -m kisshub -c <datei>` | `kisshub.conf` |
| **Direwolf** | Soundkarten-Modem (AFSK 1200/9600) mit eigenem AX.25 (AGW) oder als reiner KISS-TNC | `direwolf.exe` | `direwolf.conf` (eigener Ordner, z. B. `E:\direwolf`) |
| **VARA FM** | Soundkarten-Modem von EA5HVK, hier als KISS-TNC (Port 8100) | `VARAFM.exe` | im Programm (Settings → VARA Setup) |
| **brocastd** | sendet/empfängt brocast-Seiten (UI-Frames) | `brocast\…` | `brocast\brocastd.conf` |
| **dxfeed** | DX-Cluster → tägliches DX-Bulletin in die TinyBox | `dxfeed.bat` | `dxfeed.conf` |
| **fwdsim** | Testpartner für das Forwarding | `fwdsim.bat` | `fwdsim.conf` |

**PCs im Testaufbau:** PC1 (`E:\Tinybox`, TS-790) – TinyBox. PC2 (`C:\Tinybox`, FT-818) –
Client. Auf jedem PC, der einen KISS-TNC nutzt, läuft ein eigener kisshub.

Die `*.conf` gehören nie ins Repo; im Repo liegen nur die `*.conf.example`.

### 1.1 Zwei Betriebsarten

```
AGW:   TinyBox / Client ──AGW 8000──► Direwolf (macht AX.25 selbst) ──► Funkgerät

KISS:  TinyBox / Client ──KISS 8101──► kisshub ──► TNC ──► Funkgerät
       (machen AX.25 selbst)                       ├─ PK-232 / Kenwood (seriell)
                                                   ├─ Direwolf (KISS-TCP 8001)
                                                   └─ VARA FM  (KISS-TCP 8100, Tunnel)
```

| | AGW | KISS |
|---|---|---|
| Wer macht AX.25 (T1, T2, Fenster, Wiederholungen)? | Direwolf (`direwolf.conf`) | TinyBox / Client selbst |
| Wo stehen Funkrate, TXDELAY? | `direwolf.conf` | kisshub (Profil, `kisshub.conf`, bei VARA gemessen) |
| Verbindungsqualität | nur mit Direwolf-Fork (`Q`) | eingebaut, dazu kisshub-Auswertung (CR67) |
| Mehrere Programme am selben TNC | ja (AGW-Clients) | ja (alle über den kisshub) |

### 1.2 Ports (alle nur 127.0.0.1, außer Web-GUIs)

| Port | wer lauscht | wofür |
|---|---|---|
| 8000 | Direwolf | AGW (`AGWPORT`) |
| 8001 | Direwolf | KISS-TCP (`KISSPORT`) |
| 8100 | VARA FM | KISS-Interface |
| 8300 / 8301 | VARA FM | Befehls-/Datenport (kisshub liest 8300 nur mit) |
| 8101 | kisshub | KISS-TCP für TinyBox, Client, brocastd |
| 8102 | kisshub | Status (`GET /status`, JSON) – immer kisshub-Port + 1 |
| 6300 | TinyBox | Telnet-Testport |
| 8080 | TinyBox | Sysop-Web-GUI |
| 7744 | Client | Web-GUI des Clients |
| 8090 | brocastd | Ingest (TinyBox meldet Bulletins) |

---

## 2. Konfiguration

> **Stand:** Der Aufbau aus CR70 ist umgesetzt (kisshub 2026.10.18.7, tbclient 2026.10.18.3,
> TinyBox, brocastd, dxfeed, fwdsim; `PLANUNG.md` 17.2). Die `*.conf.example` folgen ihm.
> Alte Schlüssel werden weiter gelesen – die Tabelle in 2.8 zeigt alt → neu.

### 2.1 Grundregel: jeder Wert hat genau einen Besitzer

| Wert | Besitzer | alle anderen |
|---|---|---|
| Funkrate, TXDELAY, Persistence, SlotTime | **AGW:** `direwolf.conf` – **KISS:** kisshub | lesen ihn von dort |
| AX.25-Werte (paclen, Fenster, T1, T2 …) | **AGW:** `direwolf.conf` (PACLEN, MAXFRAME, EMAXFRAME, FRACK, RETRY) – **KISS:** Profil des kisshub | `[ax25]` nur zum Überschreiben |
| kisshub-Adresse | `kisshub.conf [server] port` | nur `[kiss] port`; Host immer 127.0.0.1, Status = Port + 1 |
| Direwolf-Ports | `direwolf.conf` (AGWPORT, KISSPORT) | `[agw] direwolf_conf` zeigt auf die Datei |
| Station, Mailbox-Call, Inbox-Ordner | `tinybox.conf` | dxfeed, fwdsim lesen `tinybox.conf` mit |

**`direwolf_conf`** darf ein **Ordner** (`E:\direwolf` → dort `direwolf.conf`) oder eine
**Datei** sein. Gelesen werden: `AGWPORT`, `KISSPORT`, `MODEM`, `TXDELAY`, `PERSIST`,
`SLOTTIME`, `PACLEN`, `MAXFRAME`, `EMAXFRAME`, `FRACK`, `RETRY` (die letzten beiden nur zur
Anzeige). Steht Direwolf auf einem anderen PC oder fehlt der Eintrag, gelten die Standardwerte
bzw. `[ax25]`.

Jedes Programm zeigt beim Start, **woher** jeder Funkwert kommt (`kisshub`, `gemessen`,
`direwolf.conf`, `conf`).

### 2.2 `tinybox.conf` (Funk- und Verbindungsteil)

```ini
[radio]
interface = agw                ; agw | kiss

[agw]                          ; nur bei interface = agw
direwolf_conf = E:\direwolf    ; Ordner oder Datei; daraus: AGWPORT, PACLEN, EMAXFRAME/MAXFRAME
; host    = 127.0.0.1          ; Standard; nur wenn Direwolf auf einem anderen PC läuft
; port    = 8000               ; Standard: AGWPORT aus direwolf.conf, sonst 8000
channel   = 0                  ; Direwolf-Kanal (CHANNEL n in direwolf.conf)
reconnect_sec = 5
; Verbindungsqualität (nur mit Direwolf-Fork, AGW 'Q')
quality_poll_sec      = 30     ; 0 = aus
quality_window_frames = 50
quality_window_min    = 30
quality_min_frames    = 20
quality_steps         = 5, 10, 20, 35, 50

[kiss]                         ; nur bei interface = kiss
port = 8101                    ; kisshub; Status automatisch auf port + 1, Host immer 127.0.0.1

[ax25]                         ; OPTIONAL – nur eintragen, um etwas zu überschreiben
; paclen       =               ; agw: Standard PACLEN aus direwolf.conf (sonst 256)
;                              ; kiss: Standard aus dem kisshub-Profil
; maxframe     =               ; agw: = max_outstanding, Standard EMAXFRAME/MAXFRAME
; maxframe_ext =               ; nur kiss (Modulo 128)
; version      = 2.2           ; nur kiss: 2.2 | 2.0
; srej         = yes           ; nur kiss
; n2 / t1_min_sec / t1_max_sec / t2_sec / t3_sec   ; nur kiss, Standard aus dem kisshub-Profil
```

Alle übrigen Abschnitte (`[station]`, `[mailbox]`, `[telnet]`, `[web]`, `[logging]`, `[chat]`,
`[rubrics]`, `[forward]` …) bleiben wie in `tinybox.conf.example`.

### 2.3 `tbclient.conf`

```ini
[station]
mycall  = OE3GAS
locator = JN88bn

[tinybox]
call         = OE3GAS-1        ; die eigene TinyBox (Mailbox)
ui           = auto            ; auto | yes | no – Chat-Ereignisse als UI-Frames
auto_connect = no
telnet_host  = 127.0.0.1       ; nur für interface = telnet
telnet_port  = 6300

[radio]
interface = kiss               ; agw | kiss | telnet

[agw]                          ; nur bei interface = agw
direwolf_conf = C:\direwolf    ; daraus AGWPORT, MODEM + TXDELAY (Zeitschätzung für Bilder)
channel   = 0
; port    = 8000               ; Standard: AGWPORT aus direwolf.conf

[kiss]                         ; nur bei interface = kiss
port = 8101

[ax25]                         ; OPTIONAL, wie bei der TinyBox (nur kiss)

[images]
target_bytes  = 4096
; bytes_per_sec =              ; Standard: aus der Funkrate geschätzt (kisshub bzw. direwolf.conf)
```

`[web]`, `[sync]`, `[storage]` wie in `tbclient.conf.example`.

### 2.4 `kisshub.conf` – der einzige Ort für TNC und Modem

```ini
[tnc]
profile   = vara-fm            ; pk232 | tm-d710 | th-d74 | th-d75 | tnc2-kiss | generic
                               ; | vara-fm | vara-hf | direwolf (liest direwolf.conf)
transport = tcp                ; serial | tcp
; device / serial_baud         ; nur serial (z. B. COM3 / 9600)
; host = 127.0.0.1             ; nur tcp
; port                         ; nur tcp; Standard je Profil: vara 8100, direwolf = KISSPORT
; direwolf_conf = E:\direwolf  ; nur profile = direwolf
; vara_tunnel = connected      ; nur VARA: no | connected | all
; vara_bundle_ms = 0           ; nur VARA: Bündelung (Experiment, bringt bei Narrow nichts)
; vara_bundle_max = 4000
; exit_kiss_on_stop / init_lines / reconnect_sec   ; siehe kisshub.conf.example

[kiss]                         ; alle Werte OPTIONAL, Standard aus dem Profil
; air_baud    =                ; vara-fm: 350 | direwolf: aus MODEM | pk232: 1200
; txdelay_ms  =                ; vara-fm: 2700 | direwolf: TXDELAY | sonst 300
; persist / slottime_ms        ; nur Hardware-TNC
; send_params =                ; Standard je Profil (vara/direwolf: no – bei VARA verboten)
; max_lead_ms =                ; vara: 12000 | sonst 1500

[ax25]                         ; OPTIONAL: Empfehlung an TinyBox/Client überschreiben
; paclen / maxframe / maxframe_ext / t1_min_sec / t2_sec ...
;                              ; Standard je Profil, z. B. vara-fm: 256 / 4 / 4 / 18 / 0.3

[server]
port = 8101                    ; Status automatisch auf 8102

[log]
level = INFO                   ; DEBUG: jedes Byte des TNC-Dialogs
file  = kisshub.log            ; leer = nur Konsole (wird beim Start gemeldet)
trace = no                     ; yes: jedes Byte zum/vom TNC in hex (Konsole: LOG TRACE)
status_every_sec = 600
links_file = kisshub-links.jsonl   ; eine JSON-Zeile je beendeter Verbindung; leer = aus

[vara]                         ; nur Profil vara-fm / vara-hf
monitor  = no                  ; yes: VARA-Befehlsport mitlesen (sendet nichts) – SN, PTT, BUSY
cmd_port = 8300
sn_window_ms = 1500
```

**Profile und ihre Standardwerte:**

| Profil | Weg | air_baud | txdelay_ms | send_params | max_lead_ms | AX.25-Empfehlung |
|---|---|---|---|---|---|---|
| `pk232` | seriell, Init-Dialog | 1200 | 300 | yes | 1500 | 1200-Bd-Werte |
| `tm-d710`, `th-d74`, `th-d75`, `tnc2-kiss`, `generic` | seriell/tcp | 1200 | 300 | yes | 1500 | 1200-Bd-Werte |
| `direwolf` | tcp, KISSPORT | aus MODEM | aus TXDELAY | no | 1500 | 1200-Bd-Werte |
| `vara-fm`, `vara-hf` | tcp 8100, Tunnel | 350 | 2700 | **no** | 12000 | 256 B, Fenster 4, T1 18–90 s, T2 0,3 s |

*1200-Bd-Werte:* paclen 256, Fenster 4 (Modulo 8) / 7 (Modulo 128), T1 3–30 s, T2 1,5 s.
Beim Profil `direwolf` kommen paclen und Fenster aus PACLEN/MAXFRAME/EMAXFRAME.
Die VARA-Werte sind am 18.10.2026 gemessen (Konzept 8d).

**So kommen die Werte bei TinyBox und Client an:** Beide fragen den kisshub-Status
(`http://127.0.0.1:<port + 1>/status`, Block `radio`) alle 30 s ab und übernehmen Funkrate,
TXDELAY und die AX.25-Empfehlung für jede **neue** Verbindung. Im Log steht dann
`radio values from kisshub (profile vara-fm): air_baud 350, txdelay 2700 ms, …`. Was in der
eigenen `[ax25]` steht (oder als alter Schlüssel in `[kiss]`), bleibt und gewinnt.

### 2.5 `brocastd.conf`

```ini
[radio]
interface = agw                ; agw | kiss

[agw]
direwolf_conf = E:\direwolf    ; AGWPORT, MODEM, TXDELAY
channel = 0

[kiss]
port = 8101                    ; kisshub (oder Direwolf-KISSPORT direkt, z. B. 8001)

[station]
; baud / txdelay_ms            ; entfallen: aus direwolf.conf bzw. kisshub
airtime_percent = 15           ; Rest wie in brocastd.conf.example
```

### 2.6 `dxfeed.conf`

```ini
[tinybox]
conf = tinybox.conf            ; daraus der Inbox-Ordner ([inbox] dir)

[digest]
; inbox =                      ; nur noch zum Überschreiben
```

`[cluster]`, `[data]`, Rest von `[digest]`, `[log]` wie in `dxfeed.conf.example`.

### 2.7 `fwdsim.conf`

```ini
[tinybox]
conf = tinybox.conf            ; daraus mailbox_call, haddress, Telnet-Port, DB-Pfad
forward_host = 127.0.0.1       ; Testdaten bleiben hier
forward_port = 0
forward_password =
telnet_user  = OE3XTC

[agw]
direwolf_conf = E:\direwolf    ; paclen, max_outstanding, Port
channel = 0
via     =
```

`[fwdsim]`, `[hop]`, `[remote]` wie in `fwdsim.conf.example`.

### 2.8 Alt → neu

Alte Schlüssel werden weiter gelesen. Steht einer noch in der Datei, gilt er als bewusste
Überschreibung; beim Start erscheint ein Hinweis (z. B. `[kiss] air_baud = 1200 überschreibt
den kisshub-Wert 350 – kann entfernt werden`).

| alt | neu |
|---|---|
| tinybox `[direwolf] agw_host / agw_port / agw_radio_port` | `[agw] host / port / channel` |
| tinybox `[direwolf] paclen / max_outstanding` | aus `direwolf.conf`, sonst `[ax25] paclen / maxframe` |
| tinybox `[direwolf] quality_*` | `[agw] quality_*` |
| tinybox / tbclient `[kiss] air_baud / txdelay_ms` | kisshub (Profil bzw. kisshub `[kiss]`) |
| tinybox / tbclient `[kiss] host / status_port / channel` | fest 127.0.0.1 / `port + 1` / 0 |
| tbclient `[tinybox] link` | `[radio] interface` |
| tbclient `[direwolf] agw_host / agw_port / radio_port` | `[agw] host / port / channel` |
| kisshub `[server] listen / status_port` | fest 127.0.0.1 / `port + 1` |
| brocastd `[direwolf] interface / agw_port / kiss_port / channel` | `[radio] interface`, `[agw]`, `[kiss]` |
| brocastd `[station] baud / txdelay_ms` | aus `direwolf.conf` bzw. kisshub |
| tbclient `[images] bytes_per_sec` | geschätzt aus der Funkrate (70 %), danach gemessen |
| fwdsim `[agw] radio_port / port / paclen / max_outstanding` | `[agw] channel`, Rest aus `direwolf.conf` |
| dxfeed `[digest] inbox` | aus `tinybox.conf` |
| fwdsim `[tinybox] call / haddress / ax25_call / telnet_* / db` | aus `tinybox.conf` |

---

## 3. Betriebsrezepte

### 3.1 Packet 1200 Bd über Direwolf (AGW) – der Standardbetrieb

1. Direwolf starten (Fenster zeigt „Ready to accept AGW client application … on port 8000“).
2. `tinybox.conf`: `[radio] interface = agw`, `[agw] direwolf_conf = E:\direwolf`.
3. `tbclient.conf` auf dem anderen PC: `[radio] interface = agw`, `[agw] direwolf_conf = C:\direwolf`.
4. TinyBox, dann Client starten.

AX.25-Einstellungen (PACLEN, MAXFRAME, EMAXFRAME, FRACK, RETRY, TXDELAY) stehen hier nur in
der `direwolf.conf`.

### 3.2 KISS mit Hardware-TNC (PK-232)

1. `kisshub.conf`: `profile = pk232`, `transport = serial`, `device = COM3`.
2. kisshub starten → „TNC answers …“, die Init-Zeilen, „TNC in KISS mode – ready“.
3. TinyBox/Client: `[radio] interface = kiss`, `[kiss] port = 8101`.
4. Ende mit Strg+C im kisshub-Fenster: der PK-232 verlässt KISS (pk232py findet ihn wieder).

### 3.3 KISS mit Direwolf als Modem (für Messungen und den Vergleich mit VARA)

Gleicher AX.25-Automat wie bei VARA, nur das Modem ist anders – dafür gedacht, Modems zu
vergleichen.

1. Direwolf läuft, KISSPORT 8001 offen. **VARA geschlossen** (gleiche Soundkarte!).
2. `kisshub.conf`: `profile = direwolf`, `direwolf_conf = E:\direwolf` – Port (KISSPORT),
   Funkrate (MODEM), TXDELAY, PACLEN und Fenster kommen aus der `direwolf.conf`; die
   Startzeilen des kisshub zeigen sie.
3. TinyBox/Client auf `interface = kiss`, Port 8101.

### 3.4 KISS mit VARA FM

**VARA einrichten** (beide PCs): Settings → VARA Setup → **KISS interface** anhaken, KISS-Port
**8100**; Soundkarte und PTT einstellen; FM System NARROW (Mikrofon/Lautsprecher) bzw. WIDE
(9600er-Datenport). VARA neu starten, `netstat -an | findstr 8100` muss LISTENING zeigen.

**Wichtig zu VARA am KISS-Port** (gemessen 17./18.10.2026):
- VARA nimmt als normalen KISS-Frame (Typ 0) **nur UI-Frames**; SABM/SABME und alles für
  Verbindungen lehnt es mit „Wrong KISS frame“ ab. Der kisshub tunnelt diese Frames deshalb in
  VARAs Typ 2 („Generic Data“). **Beide Stationen brauchen den kisshub** mit Profil `vara-fm`.
- **Keine KISS-Parameter an VARA** (KISS-Kommando 1/2 = VARA-Rahmentyp 1/2 – würde gesendet).
  Das Profil verhindert es; `send_params = yes` wird abgewiesen.
- VARA FM und Direwolf **nie gleichzeitig** an derselben Soundkarte.

**kisshub** (`kisshub-varafm.conf`, beide PCs):

```ini
[tnc]
profile   = vara-fm            ; transport tcp, Port 8100, air_baud 350, txdelay 2700 ms,
                               ; max_lead 12000 ms und die AX.25-Empfehlung kommen vom Profil
[server]
port = 8101

[log]
file       = kisshub-vara.log
links_file = links-vara.jsonl

[vara]
monitor = yes                  ; beim ersten Mal jemand ans Funkgerät (PTT-Hänger möglich)
```

Start: `python -m kisshub -c kisshub-varafm.conf`. Erwartet: `vara-fm`,
`radio: air_baud 350 (profile vara-fm), txdelay 2700 ms …`, „VARA tunnel connected …“,
„VARA monitor: listening …“.

**TinyBox / Client:** nur `[radio] interface = kiss` und `[kiss] port = 8101` – **kein**
`[ax25]` nötig. Die Werte (paclen 256, Fenster 4/4, T1 18–90 s, T2 0,3 s, Funkrate,
TXDELAY) kommen vom kisshub; im Log erscheint `radio values from kisshub …`. Stehen noch
alte Einträge (`[kiss] air_baud`, `[ax25] t1_min_sec` …) in der conf, gelten sie weiter und
der Start meldet `config hint: …` – entfernen, damit der kisshub bestimmt.

**Pegel:** Im VARA-Fenster S/N und Konstellation beobachten. Vier enge Punktwolken, S/N
25–30 dB auf kurzer Strecke. Ein deutlich niedrigerer Wert in einer Richtung heißt meist:
TX-Pegel des sendenden Geräts zu niedrig (Lauf 1: TS-790, 15 % Frameverlust).

**Was zu erwarten ist** (18.10.2026, kurze Strecke, VHF): VARA FM Narrow über KISS ist
verlustfrei, aber rund halb so schnell wie Direwolf 1200 Bd (22 gegen 40 B/s): VARA sendet
KISS-Verkehr mit ~300–500 bit/s und 2–4 s Aufwand je Burst.

---

## 4. Verbindungsqualität messen (kisshub, CR67)

Der kisshub wertet jede AX.25-Verbindung, die durch ihn läuft, passiv aus – für jeden TNC gleich,
so lassen sich Modems vergleichen.

**Konsole des kisshub:**

| Befehl | zeigt |
|---|---|
| `L` / `LINKS` | laufende und letzte Verbindungen: Wiederholungen, REJ/SREJ, Polls, Quittungszeit, Antwortabstand, Rate, S/N |
| `V` / `VARA` | VARA-Befehlsport: Bursts (Dauer, Wartezeit), gemessener Aufwand + Rate, BUSY-Anteil, S/N |
| `STATIONS` | gehörte Stationen mit Frames und S/N |
| `LOG MARK text` | Marke ins Log (vor jedem Testschritt) |
| `LOG TRACE` | jedes Byte zum/vom TNC |
| `S` | Kurzstatus TNC, Warteschlange, Clients |

**Links-Datei** (`[log] links_file`): je beendeter Verbindung eine JSON-Zeile mit TNC-Profil,
Einstellungen, VARA-Messwerten, Tunnel-Zählern und allen Kennzahlen. Für einen Vergleich je Lauf
einen eigenen Dateinamen setzen, auf **beiden** PCs.

**Kennzahlen lesen:**

| Kennzahl | bedeutet | Hinweis auf |
|---|---|---|
| Wiederholungen (`retrans`) | I-Frame nochmals gesendet | Verluste auf dem Weg zur Gegenstelle |
| Polls | S-Frame mit P=1 ≈ T1 abgelaufen | T1 zu kurz oder Frame verloren |
| Quittungszeit (`ack`) | I-Frame bis zur Quittung | Laufzeit über das Modem (+ T2 der Gegenstelle) |
| Antwortabstand (`answers after`) | Frame der Gegenstelle nach dem eigenen | ein „Hin und Her“ |
| Vergleich gesendet ↔ angekommen | Frames bei A gesendet, bei B empfangen | Verluste je Richtung (beide Logs nötig) |
| S/N (VARA) | dem empfangenen Frame zugeordnet, Bezug 2500 Hz | Pegel/Hub, Reserve |

Statusabfrage für Programme: `GET http://127.0.0.1:8102/status` (Blöcke `tnc`, `radio`,
`queue`, `quality`, `vara`). `radio` enthält Profil, `air_baud`, `txdelay_ms`, `max_lead_ms`,
die AX.25-Empfehlung (`ax25`) und je Wert die Herkunft (`source`).

---

## 5. Fehlersuche

| Meldung / Beobachtung | Ursache | Abhilfe |
|---|---|---|
| kisshub-Startzeile zeigt alte Version oder `generic` statt `vara-fm` | kein `git pull` bzw. falsches Profil | `git pull`, Profil in der kisshub-conf |
| VARA: „Wrong KISS frame“ | Verbindungs-Frames als Typ 0 an VARA | Profil `vara-fm` (Tunnel) auf **beiden** Seiten |
| kisshub: „type-2 data that is not ours … ignored“ | Gegenseite sendet Bündel/Format, das diese Version nicht kennt | gleiche kisshub-Version auf beiden PCs |
| VARA: „Soundcard … missing in action“ | Audio-Gerät nicht gefunden | Settings → Soundcard neu wählen, VARA neu starten |
| Viele Polls, Quittungen über T1 | T1 zu kurz für das Modem | Log: fehlt `radio values from kisshub`? kisshub ≥ 2026.10.18.7 und alte `[kiss]`/`[ax25]`-Werte entfernen |
| Start meldet `config hint: … overrides …` | alter Schlüssel in der conf überschreibt den Besitzer | Schlüssel entfernen (Tabelle 2.8), außer die Überschreibung ist gewollt |
| `[agw] direwolf_conf: direwolf.conf not readable` | Pfad falsch | Ordner oder Datei angeben, z. B. `E:\direwolf` |
| `[kiss] txdelay_ms … must be between 0 and 2550` | alte TinyBox | `git pull` (Grenze jetzt 10 000 ms) |
| Mail bleibt im Postausgang trotz Aussendung | alter Client (vor 2026.10.18) | `git pull`; CR68/CR69 |
| `not reachable … 8100` | VARA nicht gestartet oder KISS-Interface aus | VARA starten, Häkchen „KISS interface“ |
| PTT bleibt gedrückt | bekannter VARA-Fehler mit KISS + Befehlsport | kisshub mit Strg+C beenden, `[vara] monitor = no` |
