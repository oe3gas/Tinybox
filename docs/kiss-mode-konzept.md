# KISS-Mode für TinyBox – Konzept

Stand: 14.10.2026 (3. Fassung) · Status: **entschieden, bereit für K1**

## 0. Entscheidungen (14.10.2026)

| # | Frage | Entscheidung |
|---|---|---|
| 1 | Welche TNCs? | PK-232, TNC2, Kenwood TH-D74/TH-D75, TM-D710 (Abschnitt 5); **Schwerpunkt PK-232 und Kenwood**, TNC2 nur der Vollständigkeit halber |
| 2 | Hub in der TinyBox oder eigener Prozess? | **eigener Prozess `kisshub`** (Variante B, Abschnitt 4) |
| 3 | Plattform | Windows (PC2) **und Raspberry Pi**; NanoPi nicht als Ziel |
| 4 | AX.25-Umfang | **gleich v2.2** (Modulo 128, SREJ, XID), mit Rückfall auf v2.0 |
| 5 | Digipeater/APRS von Direwolf | wird nicht genutzt → im KISS-Mode nichts zu ersetzen |
| 6 | Sprache des Layer-2-Automaten | **Python** (Abschnitt 7) |
| 7 | TNC2 | nur mit **reinem KISS-EPROM** (sofort in KISS, keine Init-Zeilen) |
| 8 | Erstes Gerät im Funktest | **PK-232** |
| 9 | Funktests | **nur VHF, 1200 Bd** (beim PK-232 der VHF-Port) |

## 1. Ziel

TinyBox soll wahlweise ohne Direwolf direkt an einem **KISS-tauglichen TNC**
laufen. Alles oberhalb der Verbindung – Sitzungen, Befehle, Chat,
TBCHAT-UI-Frames, Client-Abgleich, Forwarding, Verbindungsqualität – bleibt
unverändert. Umschaltung nur über die `tinybox.conf`:

```ini
[radio]
interface = agw          ; agw = wie bisher über Direwolf, kiss = KISS-Adapter
```

## 2. Der entscheidende Unterschied

| | AGW (heute) | KISS (neu) |
|---|---|---|
| Wer macht AX.25 Connected Mode? | Direwolf | **TinyBox selbst** |
| Was geht über die Schnittstelle? | fertige Verbindungen (`C`, `D`, `d`, `Y`) | rohe AX.25-Frames (SABM(E), UA, I, RR, REJ, SREJ, XID, DISC …) |
| Quittungen, Wiederholungen, Timer | Direwolf | TinyBox |
| Flusskontrolle | Abfrage `Y` alle 0,5 s | direkt bekannt (V(S) − V(A)) |
| Verbindungsqualität | nur mit Direwolf-Fork (`Q`) | **eingebaut**, ohne Fork |
| Rufzeichenfilter | Direwolf (`X`-Registrierung) | TinyBox |
| Kanalzugriff (CSMA, TXDELAY, P, SlotTime) | Direwolf | TNC (TinyBox setzt nur die Parameter) |

Ein KISS-TNC ist nur ein Modem mit HDLC-Rahmung. Den AX.25-Sicherungsschicht-
Automaten („Data Link State Machine“) bringt TinyBox selbst mit – das ist der
Kern und der größte Aufwand.

## 3. Architektur

```
 ┌──────────────────────────────────────────────────────────────────┐
 │ Session · Chat · Forward · Client-Sync · Sysop · Web (unverändert) │
 └───────────────┬──────────────────────────────────────────────────┘
                 │ Transport (write / write_bytes / close / abort_output)
                 │ + LinkAdapter (connect, send_ui, ask_quality …)
       ┌─────────┴──────────┐
 ┌─────▼──────┐   ┌─────────▼────────────────────────────────────┐
 │ AgwAdapter │   │ KissAdapter                                   │
 │ (heute)    │   │  Ax25Link (pro Verbindung, Layer-2-Automat)   │
 └─────┬──────┘   │  UI-Dienst (TBCHAT-n)                         │
       │          │  Frame-Router (Rufzeichen-/Pfadfilter)        │
       │          └─────────┬────────────────────────────────────┘
       │                    │ KISS (TCP oder seriell – je nach Hub-Variante)
       ▼                    ▼
   Direwolf          KISS-Hub ──▶ TNC (seriell / USB / Bluetooth-SPP)
                        └──────▶ brocastd (KISS-TCP, unverändert)
```

### 3.1 Gemeinsame Schnittstelle (`LinkAdapter`)

Heute greifen `forward.py`, `web.py`, `sysop.py` und der Chat direkt auf
`app.agw` zu. Diese Zugriffe werden zu einer kleinen Schnittstelle
zusammengefasst, die beide Adapter erfüllen:

| Element | Zweck | Heute genutzt von |
|---|---|---|
| `run()` | Hauptschleife inkl. Reconnect | `__main__` |
| `connected` (Event) | Schnittstelle oben? | Web, Sysop, Forward |
| `conns` | aktive Verbindungen | Web, Qualität |
| `connect(remote, attach, via, timeout)` | ausgehender Connect | Forward |
| `send_ui(dest, text)` | UI-Frame senden | Chat (TBCHAT-n) |
| `ask_quality(remote)` / `q_supported` | Verbindungsqualität | Chat, Web |
| `describe()` | Text für STATUS/Web („AGW 127.0.0.1:8000“ bzw. „KISS TM-D710 COM3“) | Sysop, Web |

`app.agw` wird zu `app.link` (mit Übergangs-Alias). Die Verbindungsobjekte
erfüllen weiter das bestehende `Transport`-Protokoll aus `session.py`.

### 3.2 Neue Module

```
tinybox/
  adapters/kiss.py   KissAdapter + KissConnection (Gegenstück zu agw.py)
  ax25/
    frame.py         AX.25-Codec: I, S (RR/RNR/REJ/SREJ), U (SABM/SABME/UA/DM/DISC/FRMR/UI/XID/TEST)
    link.py          Ax25Link: Layer-2-Automat für EINE Verbindung (rein, ohne I/O)
    timers.py        T1 (mit SRT-Schätzung), T2, T3
    xid.py           XID-Aushandlung (v2.2-Parameter)
    kissio.py        KISS-Rahmung, Parameterbefehle, seriell + TCP
kisshub/             nur bei Hub-Variante B (Abschnitt 4)
```

Basis: `brocast/brocast/kiss.py` (KISS-Codec, TCP-Link) und
`brocast/brocast/ax25.py` (Adressen, UI-Frames) sind getestet und werden
übernommen und erweitert.

### 3.3 Frame-Router

Direwolf filtert heute über die `X`-Registrierung. Im KISS-Mode sieht die
TinyBox **jeden** Frame auf der Frequenz und entscheidet selbst:

| Frame | Ziel | Aktion |
|---|---|---|
| beliebig | nicht Mailbox-Call, keine laufende Verbindung | ignorieren (nur Monitor) |
| Pfad mit Digis, noch nicht alle H-Bits gesetzt | – | ignorieren (Frame noch unterwegs) |
| SABM / SABME | Mailbox-Call | neue `Ax25Link` → `_on_connect()` wie heute |
| I / S / U | Mailbox-Call, bekannte Verbindung | an deren `Ax25Link` |
| I / S / DISC | Mailbox-Call, unbekannt | DM zurück |
| UI an TBCHAT-n / Mailbox-Call | – | an Chat-/Client-Logik |

Rückweg bei Connects über Digis: Pfad umgedreht, H-Bits gelöscht.

### 3.4 Layer-2-Automat (`Ax25Link`) – AX.25 v2.2

Umsetzung nach der Zustandsbeschreibung (SDL) der AX.25-2.2-Spezifikation
(Rev. 2017). Direwolfs `ax25_link.c` setzt dieselbe SDL um und dient als
Referenz zum Verständnis und für Interop-Tests.

- Zustände: *Disconnected*, *Awaiting Connection*, *Awaiting v2.2 Connection*,
  *Connected*, *Timer Recovery*, *Awaiting Release*.
- **v2.2:** SABME → Modulo 128, Fenster k bis 127 (praktisch 7–32), **SREJ**
  (nur Fehlendes wird wiederholt), **XID** für PACLEN (N1), Fenster (k),
  T1/N2 und Halb-/Vollduplex.
- **Rückfall auf v2.0 ist Pflicht, nicht Option:** Die eingebauten TNCs der
  PK-232, TNC2 und der Kenwood-Geräte sprechen nur v2.0. Ablauf:
  - Gegenstation sendet SABME → v2.2.
  - Gegenstation sendet SABM → v2.0 (Modulo 8, REJ statt SREJ).
  - TinyBox ruft aus (Forwarding): erst SABME; kommt DM oder FRMR → SABM.
  - Merken pro Rufzeichen, was die Gegenstation kann (spart beim nächsten
    Mal den Fehlversuch).
- Empfangsseitig RNR, wenn die Session nicht nachkommt.
- Timer: **T1** dynamisch aus der Umlaufzeit (SRT), Startwert pro
  Digipeater-Hop erhöht; **T2** sammelt Quittungen (ein RR für mehrere
  I-Frames); **T3** Leerlauf-Polling; **N2** max. Wiederholungen.
- Callbacks wie heute die AGW-Ereignisse: `on_connected` (= `C`),
  `on_data` (= `D`), `on_disconnected(reason)` (= `d`, „RETRYOUT“ →
  `lost=True`).
- Der Automat hat **kein eigenes I/O und keine eigene Uhr**: Er bekommt
  Frames und Zeitpunkte, er gibt Frames und Timer-Wünsche zurück. Dadurch
  ist er ohne Funk und Netzwerk testbar (Simulator mit Paketverlust) – und
  ließe sich später isoliert in eine andere Sprache übertragen (Abschnitt 7).

### 3.5 Flusskontrolle

`KissConnection.pump()` wartet auf das Ereignis „Fenster frei“ des Automaten
statt alle 0,5 s per `Y` zu fragen. `_drain_and_disconnect()` wartet, bis
alles quittiert ist, und sendet dann DISC.

### 3.6 Verbindungsqualität ohne Fork

Der Automat führt dieselben Zähler wie der Direwolf-Fork (`i_new`,
`i_retry`, `bytes_new`, `bytes_retry`, `i_rx`, `retry_rx`, `rej_rx`,
`rej_tx`, `t1_exp`, `rnr_rx`, `srt`, `t1v`, `unack`, `bytes_rx`,
`tx_busy_ms`, `baud`), zusätzlich `srej_rx`/`srej_tx`. `ask_quality()`
liefert sie direkt im Format von `linkq.parse()`. Balken, `%Q` und `stat`
funktionieren unverändert, `q_supported` ist immer `True`.
`tx_busy_ms` wird aus Funk-Baudrate (conf) und gesendeten Bytes geschätzt –
ein KISS-TNC meldet keine Sendezeit.

## 4. KISS-Hub: in der TinyBox oder eigener Prozess?

**Das Problem:** Ein serieller Port (COM3, `/dev/ttyUSB0`, Bluetooth-SPP)
kann nur von **einem** Programm geöffnet werden. Am TNC wollen aber TinyBox
**und** brocastd hängen. Einer muss den Port besitzen und für den anderen
verteilen.

### Variante A – Hub in der TinyBox

```
TNC ──seriell── TinyBox [Hub + Layer 2] ──KISS-TCP :8001── brocastd
```

Die TinyBox öffnet den TNC selbst und bietet brocastd einen KISS-TCP-Port an.

### Variante B – eigener Hub-Prozess `kisshub`

```
TNC ──seriell── kisshub ──KISS-TCP :8001──┬── TinyBox [Layer 2]
                                          └── brocastd
```

Ein kleines, eigenständiges Programm (geschätzt 300–400 Zeilen) besitzt den
TNC, initialisiert ihn und verteilt die Frames an alle KISS-TCP-Teilnehmer.
TinyBox und brocastd sind beide nur KISS-TCP-Clients.

### Gegenüberstellung

| Kriterium | A: Hub in TinyBox | B: eigener `kisshub` |
|---|---|---|
| Prozesse / Start | einer weniger, einfacher zu starten | ein Prozess mehr (Startskript, Dienst auf dem Raspi) |
| TinyBox-Neustart (`git pull`, Update, Absturz) | **TNC weg für alle** – brocastd sendet nicht, der TNC wird bei jedem Start neu initialisiert (PK-232/D710: `KISS ON` + `RESTART`) | TNC bleibt offen, brocastd sendet weiter, TinyBox verbindet sich einfach neu |
| Fehlerisolierung | ein Fehler in Chat/Forward/Web kann den Funkzugang mitreißen | Hub ist klein und ändert sich selten → sehr stabil |
| Code in der TinyBox | seriell **und** TCP, TNC-Init, Server | **nur KISS-TCP** – derselbe Code wie gegen Direwolfs KISS-Port |
| Test ohne Hardware | eigene Testumgebung für den seriellen Teil | TinyBox gegen Direwolf-KISS-Port = exakt wie gegen den Hub |
| TNC-Eigenheiten (Init, Exit, Port-Wahl, Bluetooth-Abbrüche) | in der TinyBox | gekapselt im Hub, TinyBox weiß nichts davon |
| Latenz | direkt | + einmal localhost-TCP (< 1 ms, bei 1200 Bd belanglos) |
| Priorität (Quittungen vor brocast-Seiten) | einfach, alles in einem Prozess | Hub muss das Steuerbyte lesen und sortieren – einfach, AX.25-Control ist ein Byte |
| Weitere Abnehmer (Monitor, Paket-Dekoder, APRS-Tool) | über den TCP-Port | über den TCP-Port |
| Wiederverwendung | nur mit TinyBox | jedes KISS-Programm (auch ohne TinyBox) |
| Konfiguration | alles in `tinybox.conf` | eigene `kisshub.conf` (TNC-Typ, Port, Parameter) |

**Entschieden: Variante B** (14.10.2026). Ausschlaggebend sind drei Punkte:

1. TinyBox wird laufend weiterentwickelt und oft neu gestartet. Mit A hängt
   jedes Mal der Funkzugang samt brocastd mit, und die Kenwood-/PK-232-TNCs
   müssen jedes Mal neu in KISS geschaltet werden.
2. Die TinyBox kennt nur **eine** Art TNC: KISS über TCP. Ob dahinter der
   Hub mit PK-232 oder Direwolfs KISS-Port steckt, ist ihr gleich. Das
   halbiert den Testaufwand.
3. Alles Gerätespezifische (Init-Sequenzen, Bluetooth-Abbrüche beim TH-D74/75,
   USB-Wackler) bleibt in einem kleinen Programm, das selten angefasst wird.

Der Preis ist ein zusätzlicher Prozess – auf PC2 eine Zeile in
`start_alles.bat`, auf dem Raspi ein systemd-Dienst.

### Exkurs: Linux-Kernel-AX.25 (`kissattach`)

Auf dem Raspi gäbe es noch den AX.25-Stack im Linux-Kernel. Er scheidet aus:
nicht unter Windows, kein vollständiges v2.2, keine Qualitätszähler, und die
TinyBox müsste zwei völlig verschiedene Wege pflegen.

### Aufgaben des Hubs (Variante B)

- TNC öffnen (seriell / USB / Bluetooth-SPP), bei Verlust selbst neu öffnen
  und neu initialisieren.
- Geräteprofil anwenden: Init-Sequenz, KISS-Parameter, Exit beim Beenden.
- Jeden empfangenen Frame an alle TCP-Teilnehmer verteilen.
- Sendewarteschlange mit Priorität: U/S-Frames (UA, DM, RR, RNR, REJ, SREJ)
  vor I-Frames vor UI-Frames. Eine Quittung wartet nie hinter einer langen
  brocast-Seite.
- Eigene gesendete Frames an die **anderen** Teilnehmer spiegeln (wie ein
  Monitor) – brocastd und der Monitor sehen dann auch, was die TinyBox sendet.
- Status für Sysop/Web: TNC verbunden?, Frames rx/tx, Warteschlange.

## 5. Die vorgesehenen TNCs

| Gerät | Anschluss | In KISS schalten | KISS verlassen | Besonderheiten |
|---|---|---|---|---|
| **PK-232 / PK-232MBX** (AEA/Timewave) | RS-232 | Terminal: `KISS ON`, dann `RESTART` | `C0 FF C0` | zwei Funkports (HF/VHF): Port vor dem Umschalten wählen, im Test prüfen; Firmware-Stand prüfen |
| **TNC2** (bzw. Nachbauten) – nur der Vollständigkeit halber | RS-232 | **reines KISS-EPROM vorausgesetzt**: TNC ist nach dem Einschalten sofort in KISS, keine Init-Zeilen | – | andere EPROMs (TAPR mit `KISS ON`, TheFirmware/Hostmode) werden nicht unterstützt |
| **Kenwood TM-D710** | COM-Buchse am Bedienteil (PG-5G) | TNC in Packet-Mode schalten, dann Terminal: `KISS ON` + `RESTART` | `C0 FF C0` | 1200/9600 Bd; Datenband A/B im Menü; kleiner Puffer → PACLEN/Fenster vorsichtig |
| **Kenwood TH-D74** | USB (virtueller COM) oder Bluetooth-SPP | im Gerätemenü KISS-Mode einschalten (keine Init-Zeilen) | Menü | 1200/9600 Bd; Datenband im Menü; Bluetooth-Abbrüche → Hub muss neu verbinden |
| **Kenwood TH-D75** | USB oder Bluetooth-SPP | wie TH-D74, Menü | Menü | Firmware-Stand prüfen (KISS-Verhalten über USB) |

Alle fünf sprechen **nur AX.25 v2.0** – v2.2 bringt nur etwas, wenn auf der
Gegenseite ebenfalls ein v2.2-fähiges System läuft (Direwolf, ein zweiter
TinyBox-KISS-Mode, ggf. LinBPQ). Gegen Terminalbenutzer mit diesen TNCs
greift immer der v2.0-Rückfall.

Die Tabelle beruht auf den Handbüchern bzw. bekannten Abläufen; Details
(Port-Wahl beim PK-232, Puffergrößen der Kenwood-TNCs, Verhalten von
TXDELAY-Befehlen im Kenwood-KISS) werden im Funktest je Gerät bestätigt und
dann als **Geräteprofil** im Hub abgelegt:

```ini
; kisshub.conf (Variante B)
[tnc]
profile = pk232              ; pk232 | tm-d710 | th-d74 | th-d75 | tnc2-kiss | generic
device = COM3                ; Raspi: /dev/ttyUSB0, Bluetooth: /dev/rfcomm0
serial_baud = 9600
channel = 0
air_baud = 1200
txdelay_ms = 300
persist = 63
slottime_ms = 100
exit_kiss_on_stop = no

[server]
listen = 127.0.0.1
port = 8001
```

```ini
; tinybox.conf
[radio]
interface = kiss

[kiss]
host = 127.0.0.1             ; kisshub oder Direwolf-KISS-Port
port = 8001
air_baud = 1200

[ax25]
version = 2.2                ; 2.2 = SABME versuchen, Rückfall 2.0
paclen = 128
maxframe = 4                 ; v2.0 (Modulo 8)
maxframe_ext = 16            ; v2.2 (Modulo 128)
t1_min_sec = 3
t1_max_sec = 30
t2_sec = 1.5
t3_sec = 300
n2 = 10
```

## 6. Plattform

- **Windows (PC2)** und **Raspberry Pi**. Seriell über `pyserial`, auf dem
  Raspi auch `/dev/rfcomm0` für Bluetooth-SPP der TH-D74/75.
- Rechenlast: Bei 1200 Bd kommen höchstens rund 5 Frames pro Sekunde über
  den Kanal, bei 9600 Bd rund 40. Ein Python-Automat braucht pro Frame
  Mikrosekunden – die CPU-Last bleibt auf dem Raspi im Promille-Bereich.
  Auch ein NanoPi wäre dafür **nicht** zu schwach; dessen Engpass war der
  eMMC-Verschleiß (PLANUNG.md, offener Punkt 9), nicht die Rechenleistung.

## 7. Sprache: Python oder C?

Frage: Sollte der Layer-2-Automat aus Gründen der Performance und
Verlässlichkeit in C geschrieben werden?

**Entschieden: Python** (14.10.2026), mit sauber abgekapseltem Automaten.

| Kriterium | C | Python |
|---|---|---|
| Performance | weit mehr als nötig | ausreichend mit großem Abstand: Timer im Sekundenbereich, asyncio-Jitter im Millisekundenbereich, ≤ 40 Frames/s |
| Speichersicherheit | Frames kommen **ungeprüft aus der Luft** (fremde Eingabe) – jeder Längen-/Indexfehler kann zu Pufferüberlauf, Absturz oder schlimmer führen | Längen-/Indexfehler werden zur Ausnahme, die pro Frame abgefangen wird (wie heute im AGW-Adapter) |
| Verlässlichkeit | hängt an der Korrektheit des Automaten, nicht an der Sprache | dto. – erreicht durch Spezifikation + Simulator-Tests |
| Testbarkeit | eigenes Testgerüst, Anbindung an pytest über Bindings | direkt im bestehenden pytest-Bestand, Simulator mit Paketverlust in wenigen Zeilen |
| Einbindung | Build für Windows **und** Raspi (ARM), Python-Bindings (ctypes/cffi), Compiler auf beiden PCs | keine – `git pull` genügt wie bisher |
| Pflege / Lernen | zweite Sprache im Projekt | eine Sprache für alles |
| Fehlersuche | Debugger, Speicherfehler schwer zu finden | Log + Traceback, wie im übrigen Code |

Wo C wirklich angebracht wäre: im Betriebssystemkern, auf einem
Mikrocontroller (z. B. ein eigener TNC) oder bei Baudraten weit jenseits
dessen, was im Amateurfunk-Packet üblich ist. Nichts davon trifft hier zu.

**Sicherheitsnetz:** Der Automat ist rein (Abschnitt 3.4: keine Uhr, kein
I/O). Sollte sich je herausstellen, dass er schneller sein muss, lässt er
sich als Ganzes übertragen – dann eher nach **Rust** als nach C, weil Rust
die Speichersicherheit behält. Der Python-Simulator prüft dann beide
Fassungen gegen dieselben Testfälle.

## 8. Umsetzung in Schritten

| # | Inhalt | Prüfung |
|---|---|---|
| K1 | AX.25-Codec (alle Frame-Typen, Modulo 8 und 128), KISS-I/O | Unit-Tests, Mitschnitte von Direwolf |
| K2 | `Ax25Link` v2.0 eingehend (SABM → Sitzung → DISC), REJ | Simulator mit 0 / 10 / 30 % Verlust |
| K3 | v2.2: SABME, Modulo 128, SREJ, XID, Rückfall-Logik | Simulator, beide Seiten v2.2 und gemischt |
| K4 | `KissAdapter` als zweiter `LinkAdapter`, `app.agw` → `app.link`, UI für TBCHAT | alle bestehenden Tests grün mit beiden Adaptern |
| K5 | ausgehende Connects inkl. via (Forwarding), Merken der Gegenstations-Version | Forward gegen LinBPQ und Direwolf |
| K6 | Qualitätszähler aus dem Automaten | Balken wie mit Fork |
| K7 | `kisshub` (eigener Prozess), brocastd daran | brocastd + TinyBox an einem TNC |
| K8 | Geräteprofil + Funktest **PK-232** (erstes Gerät) | Dauerlauf, auch auf dem Raspi |
| K9 | Geräteprofile + Funktest TM-D710, TH-D74, TH-D75 | je Gerät |
| K10 | TNC2 mit KISS-EPROM (Profil `generic`/`tnc2-kiss`) | Kurztest, wenn Gerät verfügbar |

**Testtrick für K1–K6 ohne Hardware-TNC:** Direwolf auf PC2 mit KISS-TCP-Port
als „dummer TNC“, die Gegenstation auf PC1 mit Direwolf/AGW und
Terminalprogramm. So wird der eigene Automat gegen Direwolfs v2.2-
Implementierung getestet, bevor ein Hardware-TNC dazukommt. Bei Variante B
ändert sich für die TinyBox beim Wechsel zum Hub nichts.

## 9. Risiken

- **Layer-2-Automat ist der Hauptaufwand**, v2.2 mit SREJ und XID deutlich
  mehr als v2.0. Fehler zeigen sich als hängende oder abbrechende
  Verbindungen. Gegenmittel: reiner Automat, Simulator mit Paketverlust,
  Interop gegen Direwolf, LinBPQ und die echten TNCs.
- **v2.2-Nutzen begrenzt:** Mit den vorgesehenen TNCs auf beiden Seiten
  läuft immer v2.0. v2.2 wirkt nur gegen moderne Gegenstellen.
- **Kenwood-TNCs:** kleine Puffer, Bluetooth-Abbrüche – Werte je Gerät im
  Funktest ermitteln.
- **Neue Abhängigkeit:** `pyserial` – auch für Raspi/Produktion einplanen.

## 10. Offene Fragen

1. PK-232: welche Firmware-Version?
2. Raspi: welches Modell und welche Anbindung je TNC (USB-Seriell-Adapter, Bluetooth)?
