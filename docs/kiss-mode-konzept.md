# KISS-Mode für TinyBox – Konzept

Stand: 14.10.2026 · Status: **Entwurf, noch nicht entschieden**

## 1. Ziel

TinyBox soll wahlweise ohne Direwolf direkt an einem **KISS-tauglichen TNC**
laufen (Hardware-TNC am seriellen/USB-Port oder ein KISS-TCP-Port).
Alles oberhalb der Verbindung – Sitzungen, Befehle, Chat, TBCHAT-UI-Frames,
Client-Abgleich, Forwarding, Verbindungsqualität – bleibt unverändert.

Umschaltung nur über die `tinybox.conf`:

```ini
[radio]
interface = agw          ; agw = wie bisher über Direwolf, kiss = KISS-Adapter
```

## 2. Der entscheidende Unterschied

| | AGW (heute) | KISS (neu) |
|---|---|---|
| Wer macht AX.25 Connected Mode? | Direwolf | **TinyBox selbst** |
| Was geht über die Schnittstelle? | fertige Verbindungen (`C`, `D`, `d`, `Y`) | rohe AX.25-Frames (SABM, UA, I, RR, REJ, DISC …) |
| Quittungen, Wiederholungen, Timer | Direwolf | TinyBox |
| Flusskontrolle | Abfrage `Y` alle 0,5 s | direkt bekannt (V(S) − V(A)) |
| Verbindungsqualität | nur mit Direwolf-Fork (`Q`) | **eingebaut**, ohne Fork |
| Rufzeichenfilter | Direwolf (`X`-Registrierung) | TinyBox |
| Kanalzugriff (CSMA, TXDELAY, P, SlotTime) | Direwolf | TNC (TinyBox setzt nur die Parameter) |

Ein KISS-TNC ist nur ein Modem mit HDLC-Rahmung. Den ganzen
AX.25-Sicherungsschicht-Automaten (Layer 2, „Data Link State Machine“) muss
TinyBox deshalb selbst mitbringen. Das ist der Kern dieses Konzepts – und der
größte Aufwand.

## 3. Architektur

```
 ┌────────────────────────────────────────────────────────────────────┐
 │  Session · Chat · Forward · Client-Sync · Sysop · Web   (unverändert) │
 └───────────────┬────────────────────────────────────────────────────┘
                 │  Transport-Schnittstelle (write / write_bytes / close /
                 │  abort_output / feed) + LinkAdapter (connect, send_ui …)
       ┌─────────┴──────────┐
       │                    │
 ┌─────▼──────┐   ┌─────────▼──────────────────────────────────────────┐
 │ AgwAdapter │   │ KissAdapter                                         │
 │ (heute)    │   │  ┌──────────────┐  ┌───────────────────────────┐   │
 └─────┬──────┘   │  │ Ax25Link (n) │  │ UI-Dienst (TBCHAT, Beacon)│   │
       │          │  │ Layer-2-     │  └─────────────┬─────────────┘   │
       │          │  │ Automat,     │                │                 │
       │          │  │ Timer, Zähler│                │                 │
       │          │  └──────┬───────┘                │                 │
       │          │         └────────┬───────────────┘                 │
       │          │          ┌───────▼────────┐                        │
       │          │          │ Frame-Router   │ Rufzeichen-/Pfadfilter │
       │          │          └───────┬────────┘                        │
       │          │          ┌───────▼────────┐   ┌──────────────────┐ │
       │          │          │ KISS-Hub       │──▶│ KISS-TCP-Server  │─┼─▶ brocastd
       │          │          │ (Rahmung, Init)│   │ 127.0.0.1:8001   │ │   (Monitor)
       │          │          └───────┬────────┘   └──────────────────┘ │
       │          └──────────────────┼───────────────────────────────────┘
       ▼                             ▼
   Direwolf                 TNC: seriell / USB / KISS-TCP
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
| `describe()` | Text für STATUS/Web („AGW 127.0.0.1:8000“ bzw. „KISS COM3 9600“) | Sysop, Web |

`app.agw` wird zu `app.link` (mit Übergangs-Alias). Die Verbindungsobjekte
(`AgwConnection` / `KissConnection`) erfüllen weiter das bestehende
`Transport`-Protokoll aus `session.py` – Session, Forward-Link und Chat
merken keinen Unterschied.

### 3.2 Neue Module

```
tinybox/
  adapters/
    kiss.py          KissAdapter + KissConnection (Gegenstück zu agw.py)
  ax25/
    frame.py         AX.25-Codec: alle Frame-Typen (I, S, U), Adressen, Pfad
    link.py          Ax25Link: Layer-2-Automat für EINE Verbindung
    timers.py        T1 (mit SRT-Schätzung), T2, T3
    kissio.py        KISS-Rahmung, Init/Exit, seriell + TCP
    hub.py           Hub: ein Port-Besitzer, mehrere Abnehmer, KISS-TCP-Server
```

Wiederverwendung: `brocast/brocast/kiss.py` (KISS-Codec, TCP-Link) und
`brocast/brocast/ax25.py` (Adresscodierung, UI-Frames) sind schon getestet
und werden als Basis übernommen und um S- und U-Frames erweitert.

### 3.3 KISS-Hub (Port-Besitzer)

Ein serieller Port kann nur von **einem** Programm geöffnet werden. Heute
hängen aber TinyBox und brocastd an Direwolf. Deshalb übernimmt die TinyBox
den TNC exklusiv und reicht ihn weiter:

- liest/schreibt den TNC (seriell via `pyserial`, oder KISS-TCP),
- verteilt jeden empfangenen Frame an den Frame-Router **und** an alle
  Teilnehmer des eingebauten **KISS-TCP-Servers** (`127.0.0.1:8001`),
- nimmt Frames von TCP-Teilnehmern an und sendet sie über den TNC.

Damit läuft **brocastd unverändert** weiter: In `brocastd.conf` steht schon
heute `interface = kiss` / `kiss_port` zur Verfügung. Nebenbei lässt sich am
Hub jeder KISS-Monitor (z. B. ein Paket-Dekoder) anhängen.

Sende-Reihenfolge im Hub: Layer-2-Steuerframes (RR/REJ/UA/DM) vor I-Frames,
vor UI-Frames, vor Frames von TCP-Teilnehmern. Eine Quittung soll nie hinter
einer langen brocast-Seite warten.

Init/Exit pro TNC (konfigurierbar):
- Parameter per KISS-Befehl: TXDELAY (`0x01`), P (`0x02`), SlotTime (`0x03`),
  TXtail (`0x04`), FullDuplex (`0x05`).
- Optionale Init-Zeilen im Terminalmodus, bevor der TNC in KISS geht
  (z. B. PK-232: `KISS ON` / `RESTART`, TNC2 mit TheFirmware: `@K`).
- Beim Beenden optional `C0 FF C0` (KISS verlassen).

### 3.4 Frame-Router

Direwolf filtert heute über die `X`-Registrierung. Im KISS-Mode sieht die
TinyBox **jeden** Frame auf der Frequenz und entscheidet selbst:

| Frame | Ziel | Aktion |
|---|---|---|
| beliebig | nicht Mailbox-Call, keine laufende Verbindung | nur an Monitor/Hub |
| Pfad mit Digis, noch nicht alle H-Bits gesetzt | – | ignorieren (Frame ist noch unterwegs) |
| SABM / SABME | Mailbox-Call | neue `Ax25Link` anlegen → `_on_connect()` wie heute |
| I/S/U | Mailbox-Call, bekannte Verbindung | an deren `Ax25Link` |
| I/S/DISC | Mailbox-Call, unbekannt | mit DM antworten |
| UI an TBCHAT-n / Mailbox-Call | – | an Chat-/Client-Logik (wie AGW `k`) |

Rückweg bei Connects über Digis: Pfad umgedreht, H-Bits gelöscht.

### 3.5 Layer-2-Automat (`Ax25Link`)

Umsetzung nach der Zustandsbeschreibung (SDL) der AX.25-2.2-Spezifikation,
im ersten Schritt aber **im Umfang von AX.25 v2.0**:

- Zustände: *Disconnected*, *Awaiting Connection*, *Connected*,
  *Timer Recovery*, *Awaiting Release*.
- Modulo 8, Fenster k = 1–7 (heute `max_outstanding`), PACLEN wie heute.
- REJ (Go-Back-N). Kein SREJ, kein Modulo 128 in v1.
- SABME und XID werden mit DM bzw. FRMR beantwortet → Gegenstationen (auch
  Direwolf 1.x) fallen automatisch auf v2.0 zurück.
- Empfangsseitig RNR, wenn die Session nicht nachkommt (z. B. Bild-Upload).
- Timer:
  - **T1** (Wiederholung): dynamisch aus der gemessenen Umlaufzeit (SRT),
    Startwert pro Digipeater-Hop erhöht, Ober-/Untergrenze in der conf.
  - **T2** (Quittungsverzögerung): sammelt mehrere I-Frames in einem RR –
    spart Kanalzeit.
  - **T3** (Leerlauf-Polling), **N2** (max. Wiederholungen).
- Die Callbacks entsprechen den heutigen AGW-Ereignissen:
  `on_connected` (= `C`), `on_data` (= `D`), `on_disconnected(reason)`
  (= `d`, inkl. „RETRYOUT“ → `lost=True`).

Weil der Automat ein eigenes, abgeschlossenes Stück ist, ist er **ohne Funk
und ohne Netzwerk** testbar (Zeit und Kanal werden simuliert).

### 3.6 Flusskontrolle

`KissConnection.pump()` wird einfacher als heute: statt alle 0,5 s per `Y` zu
fragen, wartet die Pumpe auf ein Ereignis des Automaten („Fenster frei“).
`_drain_and_disconnect()` wartet, bis alle I-Frames quittiert sind, und sendet
dann DISC.

### 3.7 Verbindungsqualität ohne Fork

Der Automat führt genau die Zähler, die heute der Direwolf-Fork über `Q`
liefert (`i_new`, `i_retry`, `bytes_new`, `bytes_retry`, `i_rx`, `retry_rx`,
`rej_rx`, `rej_tx`, `t1_exp`, `rnr_rx`, `srt`, `t1v`, `unack`, `bytes_rx`,
`tx_busy_ms`, `baud`). `ask_quality()` liefert sie direkt als dict im Format
von `linkq.parse()` → `conn.quality.add()`. Balken, `%Q`-Statusframe und
`stat` funktionieren dadurch unverändert, `q_supported` ist immer `True`.

`tx_busy_ms` und `baud` kommen aus der conf (Baudrate des TNC) plus
gezählten Bytes, da ein KISS-TNC keine Sendezeit meldet.

## 4. Konfiguration (Vorschlag)

```ini
[radio]
interface = kiss             ; agw | kiss

[kiss]
transport = serial           ; serial | tcp
device = COM3                ; Windows: COM3, Linux/NanoPi: /dev/ttyUSB0
serial_baud = 9600           ; Baudrate PC <-> TNC
host = 127.0.0.1             ; nur bei transport = tcp
port = 8001
channel = 0                  ; KISS-Port bei Mehrport-TNCs
air_baud = 1200              ; Funk-Baudrate (für Durchsatz/tx_busy_ms)
txdelay_ms = 300
persist = 63
slottime_ms = 100
init_lines =                 ; optional, z. B. KISS ON | RESTART
exit_kiss_on_stop = no
server_port = 8001           ; KISS-TCP-Server für brocastd, 0 = aus

[ax25]
paclen = 128                 ; ersetzt [direwolf] paclen
maxframe = 4                 ; k, ersetzt [direwolf] max_outstanding
t1_min_sec = 3
t1_max_sec = 30
t2_sec = 1.5
t3_sec = 300
n2 = 10
```

Der Abschnitt `[direwolf]` bleibt für `interface = agw` gültig. Die
Qualitäts-Parameter (`quality_*`) wandern in einen eigenen Abschnitt
`[quality]`, mit Rückfall auf die alten Namen.

## 5. Was im KISS-Mode wegfällt

Direwolf erledigt heute nebenbei Dinge, die ein Hardware-TNC nicht kann:

- **Digipeater** und **APRS-Baken / iGate** von Direwolf – nicht mehr da,
  falls genutzt.
- **Soft-Modem-Qualitäten** (mehrere Dekoder, FX.25, Fehlerkorrektur) – der
  TNC dekodiert nur, was sein Modem kann.
- Der **TinyBox-Client** auf PC1 bleibt bei Direwolf/AGW (er liest Frames
  roh mit `k`). KISS für den Client ist ein eigenes späteres Thema.

## 6. Umsetzung in Schritten

| # | Inhalt | Prüfung |
|---|---|---|
| K1 | AX.25-Codec (alle Frame-Typen), KISS-I/O seriell + TCP, Hub | Unit-Tests, Mitschnitt gegen Direwolf-KISS |
| K2 | `Ax25Link` eingehend (SABM → Sitzung → DISC) | Simulator mit Verlustrate 0 / 10 / 30 % |
| K3 | `KissAdapter` als zweiter `LinkAdapter`, `app.agw` → `app.link`, UI für TBCHAT | alle bestehenden Tests grün mit beiden Adaptern |
| K4 | ausgehende Connects inkl. via (Forwarding) | Forward gegen LinBPQ |
| K5 | Qualitätszähler aus dem Automaten | Balken wie mit Fork |
| K6 | KISS-TCP-Server, brocastd hängt am Hub | brocastd + TinyBox an einem TNC |
| K7 | Funktest mit echtem Hardware-TNC | Dauerlauf |
| K8 (opt.) | AX.25 2.2: SABME, Modulo 128, SREJ, XID | nur wenn Bedarf |

**Testtrick für K1–K3 ohne Hardware-TNC:** Direwolf selbst bietet einen
KISS-TCP-Port. TinyBox auf PC2 spricht KISS mit Direwolf („Direwolf als dummer
TNC“), die Gegenstation auf PC1 läuft mit Direwolf/AGW und Terminalprogramm.
So wird der eigene Layer-2-Automat gegen Direwolfs Implementierung getestet,
bevor ein Hardware-TNC ins Spiel kommt.

## 7. Risiken

- **Layer-2-Automat ist der Hauptaufwand.** Fehler zeigen sich als hängende
  oder abbrechende Verbindungen. Gegenmittel: Simulator mit Paketverlust,
  Interop-Tests gegen Direwolf, LinBPQ und einen klassischen TNC.
- **Timing:** Python-asyncio genügt für 1200/9600 Bd locker, T1/T2 liegen im
  Sekundenbereich.
- **Neue Abhängigkeit:** `pyserial` (bzw. `pyserial-asyncio`) – auch für
  NanoPi/Produktion einplanen.
- **Hub als Single Point of Failure:** Stürzt die TinyBox ab, ist auch
  brocastd vom TNC getrennt. Alternative wäre ein separater kleiner
  Hub-Prozess (siehe offene Fragen).

## 8. Offene Fragen

1. Welche(r) TNC konkret? (Typ, Firmware, KISS-Init, Baudrate, Mehrport?)
2. Hub in der TinyBox oder als eigener kleiner Prozess, an dem TinyBox *und*
   brocastd per KISS-TCP hängen?
3. Soll `interface = kiss` auch auf dem NanoPi (Produktion) laufen oder nur
   als Alternative auf PC2?
4. Reicht AX.25 v2.0 (K1–K7) oder wird 2.2 (Modulo 128, SREJ) gebraucht?
5. Wird von Direwolf heute Digipeater/APRS genutzt, das im KISS-Mode
   ersetzt werden müsste?
