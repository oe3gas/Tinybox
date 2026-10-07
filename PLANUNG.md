# TinyBox – Planung

Kleine, eigenständige Packet-Radio-Mailbox für Direwolf.
Bedienersprache: **Englisch**. Kein Forwarding. Speicherung komplett am PC.
Vorbereitet für die Anbindung an MQTT-Broker.

Stand: 01.10.2026 (Rev. 3) · OE3GAS

**Änderungen gegenüber Rev. 2**

- Neuer Befehl `DICT` für die Zusammenarbeit mit brocast (Abschnitt 2). TinyBox bleibt bis auf Weiteres eine kleine Text-BBS ohne Dateiablage.

**Änderungen gegenüber Rev. 1**

- Der PK-232 MailDrop dient nur noch als Orientierung beim Entwurf der Befehle. Es gibt keine Abhängigkeit und keine Kompatibilitätsanforderung.
- Die Konfiguration steht in der Datei `tinybox.conf` (INI-Format), dort auch Mailbox-Call und SSID.
- Direwolf läuft immer auf demselben PC (AGW auf `127.0.0.1`).
- Python ist bestätigt.
- Neu: MQTT-Anbindung ist in der Architektur vorgesehen (Abschnitt 6).

---

## 1. Ziele & Abgrenzung

**Ziele**

- Anrufer verbinden sich per AX.25 (connected mode) mit dem Mailbox-Call aus `tinybox.conf`.
- Nachrichten lesen, schreiben, löschen und auflisten.
- SYSOP-Zugang lokal am PC (Konsole), ohne Funk.
- Persistente Speicherung am PC.
- Nachrichten können später auch über MQTT eingespielt und ausgegeben werden.
- Einfacher, gut lesbarer Code (Lernprojekt).

**Nicht im Umfang (v1)**

- Kein BBS-Forwarding (keine SID-Aushandlung, kein Austausch mit anderen Mailboxen über Funk).
- Keine Dateiablage / kein YAPP.
- MQTT: in v1 nur die Schnittstellen vorbereiten, die Umsetzung folgt in einem eigenen Meilenstein.

---

## 2. Befehlssatz

Orientiert sich am klassischen WORLI/MailDrop-Stil, den Packet-Nutzer kennen. Die Einzelheiten legt TinyBox selbst fest.

| Befehl | Funktion |
|---|---|
| `A` | Laufende Ausgabe abbrechen |
| `B` | Abmelden, Verbindung trennen |
| `H` / `?` | Hilfe |
| `J` | Zuletzt verbundene Stationen |
| `K n` | Nachricht n löschen (eigene oder an mich) |
| `KM` | Alle gelesenen Nachrichten an mich löschen |
| `L` | Nachrichten auflisten |
| `LM` | Nur Nachrichten an mich |
| `R n` | Nachricht n lesen |
| `RM` | Alle ungelesenen Nachrichten an mich lesen |
| `S call` / `SP call` | Private Nachricht an `call` |
| `SB call` | Bulletin (z. B. `SB ALL`) |
| `V` | Version |
| `E n` | Nachrichtenkopf ändern (nur SYSOP) |
| `DICT` | brocast-Dictionary als Text ausgeben (für den Import im brocast-Listener) |

**`DICT` (Zusammenarbeit mit brocast):** TinyBox bleibt eine Textmailbox ohne Dateiablage. Das brocast-Dictionary ist reiner Text (YAML) und wird deshalb einfach ausgegeben: zwischen den Zeilen `#BROCAST-DICT BEGIN v<Version> lines=<n> sha256=<Prüfsumme>` und `#BROCAST-DICT END`, ohne Kommentar- und Leerzeilen, rein ASCII (Umlaute in Anführungszeichen als `\uXXXX`). Der Nutzer speichert den Mitschnitt seines Terminals und importiert ihn im brocast-Listener, der Zeilenzahl und SHA-256 prüft. Die Datei liest TinyBox direkt von der Platte (`[brocast] dict_file` in `tinybox.conf`), eine neue Version ist sofort verfügbar.

Eingabe einer Nachricht: zuerst wird der Betreff abgefragt, dann der Text. Ende mit **`/EX`** in eigener Zeile oder **CTRL-Z**.

**Rechte**

- **User**: liest Bulletins und die eigenen Privatnachrichten. Löscht nur Nachrichten, die an ihn gerichtet oder von ihm sind.
- **SYSOP** (lokal): darf alles lesen und löschen, dazu `E n`.
- `third_party = yes` (Standard): jeder darf an jeden schreiben. Mit `no` dürfen Remote-User nur an den Sysop schreiben.

**Typ/Status**: Typ `P` (privat) oder `B` (Bulletin); Status `N` (ungelesen) oder `Y` (gelesen).

---

## 3. Bedienoberfläche (English)

```
*** CONNECTED to OE3GAS-1
Welcome to TinyBox OE3GAS-1, hello OE1ABC.
You have 2 new message(s).
TinyBox (A,B,H,J,K,L,R,S,V,?) >
```

```
MSG# TS SIZE TO     FROM   DATE   SUBJECT
  12 PN  340 OE1ABC OE3GAS 260927 Sked 80m tonight
  11 BY  812 ALL    OE3XYZ 260926 Direwolf notes
```

```
> S OE3GAS
Subject: Test from the field
Enter message, end with /EX or ^Z:
...
/EX
Msg 13 saved.
```

Fehlermeldungen: `Unknown command. Type H for help.` · `No such message.` · `Not allowed.`
Alle Texte stehen zentral in `texts.py`.

---

## 4. Architektur

```
                        ┌──────────────────── TinyBox (Python, asyncio) ────────────────────┐
 Funk ─ Direwolf ─AGW──►│ AGW-Adapter ─┐                                                    │
       (127.0.0.1:8000) │              ├─► Session/Commands ─► MessageService ─► Store      │
 Telnet (Test) ────────►│ Telnet-Adapt.┘                          │   ▲         (SQLite)   │
                        │                                         ▼   │                    │
 Sysop-Konsole ────────►│ Sysop ────────────────────────────► Event-Bus                     │
                        │                                         │   ▲                    │
                        │                                         ▼   │                    │
 MQTT-Broker(s) ◄──────►│                                     MQTT-Adapter (später)          │
                        └───────────────────────────────────────────────────────────────────┘
```

**Kernidee für MQTT:** Keine Quelle schreibt direkt in die Datenbank. Funk, Telnet, Sysop und später MQTT gehen alle über den **MessageService**. Der prüft die Eingaben, speichert und meldet Ereignisse an einen internen **Event-Bus**. Der MQTT-Adapter muss sich dann nur am Bus anmelden. Am Kern ändert sich dafür nichts.

Interne Ereignisse (ab v1 vorhanden, auch ohne MQTT):

| Event | Auslöser |
|---|---|
| `message.created` | neue Nachricht gespeichert (egal aus welcher Quelle) |
| `message.read` | Nachricht gelesen |
| `message.deleted` | Nachricht gelöscht |
| `session.connected` / `session.disconnected` | Verbindung auf- oder abgebaut |

### 4.1 Direwolf über das AGW-Protokoll

Direwolf übernimmt den AX.25-Connected-Mode (Layer 2). TinyBox verwendet folgende Frames:

| Kind | Richtung | Zweck |
|---|---|---|
| `X` | → DW | Mailbox-Call registrieren |
| `C` | ← DW | eingehende Verbindung |
| `D` | ↔ | Nutzdaten |
| `d` | ↔ | Trennen |
| `Y` | → DW | Anzahl ausstehender Frames (Flusskontrolle) |
| `R` | → DW | Version abfragen (Startprüfung) |

Da Direwolf immer mitläuft, prüft TinyBox beim Start die AGW-Verbindung. Geht sie verloren, verbindet TinyBox sich automatisch neu (Backoff). Die Sitzungen gehen dabei verloren, die Daten nicht.

### 4.2 Test ohne Funk

Telnet-Testport auf `127.0.0.1`. Er nutzt dieselbe Sitzungslogik, das Rufzeichen wird beim Login abgefragt.

---

## 5. Konfiguration: `tinybox.conf`

INI-Format (Python `configparser`, Standardbibliothek). Beispiel:

```ini
[station]
mailbox_call   = OE3GAS-1
sysop_call     = OE3GAS

sysop_via_radio = no           ; Sysop-Rechte nur lokal (Rufzeichen über Funk sind nicht authentisiert)

[direwolf]
agw_host        = 127.0.0.1
agw_port        = 8000
agw_radio_port  = 0
reconnect_sec   = 5
paclen          = 128          ; max. Bytes pro gesendetem Paket
max_outstanding = 4            ; max. unbestätigte Pakete bei Direwolf

[mailbox]
welcome_enabled = yes
welcome_text    = Welcome to TinyBox. Amateur radio use only, no encryption.
third_party     = yes
max_users       = 3
max_msg_bytes   = 8192
idle_timeout_min = 10
bulletin_expire_days = 30

[telnet]
enabled = yes
host    = 127.0.0.1
port    = 6300

[storage]
data_dir = data                ; relativ zur tinybox.conf

[logging]
level   = INFO
monitor = yes

[brocast]
dict_file  = brocast/brocast-core.yaml   # Befehl DICT; leer = nicht angeboten
publish    = yes                         # Bulletins an brocastd melden
ingest_url = http://127.0.0.1:8090/api/v1
max_bytes  = 4096                        # längere Bulletins gekürzt
destinations =                           # leer = alle Bulletins
rubrics    =                             # zusätzliche Paare ZIEL:Rubrik
sync_min   = 60                          # Abgleich alle n Minuten
alert_destinations = WARN                # diese Bulletins werden Warnseiten in brocast

[inbox]
enabled  = yes                 # Skripte legen *.txt ab, TinyBox macht Bulletins
dir      = eingang
poll_sec = 10

[mqtt]
enabled   = no
host      = 127.0.0.1
port      = 8883
tls       = yes
client_id = tinybox-oe3gas
username  = tinybox
password_file = E:\Tinybox\secrets\mqtt.pw
topic_root = tinybox/OE3GAS-1
```

Die Datei wird beim Start geprüft: Rufzeichen-Format, Ports, Pfade. Fehler werden klar gemeldet, dann bricht TinyBox ab. Passwörter stehen nicht in der `.conf`, sondern in einer eigenen Datei.

---

## 6b. brocast-Anbindung (Bulletins als Seiten)

Ein Adapter meldet sich am Event-Bus an und ruft die Ingest-API von brocastd auf demselben PC auf (`[brocast] ingest_url`, nur Standardbibliothek). **Private Nachrichten gehen nie auf die Luft.**

| Ereignis | Aufruf |
|---|---|
| Bulletin erstellt / geändert | `PUT /pages/tinybox/<Nr>` |
| Bulletin gelöscht / abgelaufen (`message.expired`, neu) / zu privat geändert | `DELETE /pages/tinybox/<Nr>` |
| Start und alle `sync_min` Minuten | `PUT /pages/tinybox` mit allen Bulletins (Abgleich) |

Abbildung: Titel = Betreff (max. 40 Zeichen, sonst voller Betreff als Überschrift), Rubrik aus dem Bulletin-Ziel (`[brocast] rubrics`, unbekannte Ziele = eigene Rubrik), Quelle „TinyBox, Autor“, Gültigkeit = Lebensdauer der Bulletins, Text in Absätzen. Über `max_bytes` (4 kB) wird gekürzt, mit Hinweis „Vollständig in der Mailbox OE3GAS-1: R n“. Optional nur bestimmte Ziele (`destinations`). Läuft brocastd nicht, schreibt TinyBox eine Warnung und gleicht beim nächsten Abgleich nach.

## 6c. Eingangsordner für Skripte (`[inbox]`)

Skripte auf diesem PC (z. B. GeoSphere-Wetter und -Warnungen) legen Textdateien in `eingang\` ab, TinyBox macht daraus Bulletins (Herkunft `inbox`). Nur Bulletins, keine privaten Nachrichten. Format wie eine E-Mail, UTF-8:

```
To: WX                        Pflicht: Bulletin-Ziel
Subject: Wetter 19:00         Pflicht: Betreff (max. 60)
From: OE3GAS                  optional, Standard: Sysop-Rufzeichen
Replace: geosphere-wetter     optional: gleichnamiges Bulletin aktualisieren (gleiche Nummer)
Valid: 6h                     optional: 90m / 6h / 2d, danach gelöscht

Text ...
```

- Nur `*.txt` (Skripte schreiben `*.tmp` und benennen dann um), Dateien jünger als 2 s werden noch nicht angefasst.
- Erfolgreich → `eingang\erledigt\<Zeitstempel>_<Name>`, abgelehnt → `eingang\fehler\` plus `.err` mit dem Grund.
- `Replace:` aktualisiert ein vorhandenes Bulletin mit gleicher Nummer, es gilt wieder als ungelesen (Ereignis `message.edited`, brocast: neue Revision derselben Seite).
- `Valid:` setzt ein eigenes Ablaufdatum; die Aufräumroutine läuft jetzt jede Minute und meldet `message.expired` (brocast zieht die Seite zurück).
- Datenbank: Schema 2 mit den Spalten `replace_key` und `expires`; ältere Datenbanken werden beim Start automatisch ergänzt.
- Kommt per `Replace:` exakt derselbe Inhalt noch einmal, verlängert TinyBox nur die Gültigkeit (kein „ungelesen“, keine neue brocast-Revision).

**Erste Lieferanten: GeoSphere-Skripte** (Windows-Aufgabenplanung, `geosphere_aufgaben_einrichten.bat`)

| Skript | Takt | Bulletin |
|---|---|---|
| `geosphere_station.py --tinybox` | stündlich xx:05 | an `WX`, `Replace: geosphere-wetter-11334`, `Valid: 2h`, mit `Brocast:` (Wetterseite `typ wx`, Abschnitt 6d) |
| `geosphere_warnungen.py --tinybox` | alle 15 min | an `WARN` nur bei Änderung, gültig bis Warnungsende; bei vorzeitiger Aufhebung „Entwarnung“ (3 h) |

Bulletins an `WARN` werden in brocast zu Warnseiten (`[brocast] alert_destinations`, Rubrik Notfunk) und im Listener immer angezeigt und hervorgehoben.

### 6d. Kopfzeile `Brocast:` – eine Datei, zwei Zielsysteme

Ein Skript kann zum Text eine fertige brocast-Seite mitliefern. Die Mailbox speichert und zeigt nur den Text; der brocast-Adapter reicht statt der Textseite die mitgelieferte Seite weiter. So bleibt TinyBox die einzige Drehscheibe (Skript → TinyBox → brocast), und `Replace:`, `Valid:` und Löschen gelten für beide Darstellungen.

```
To: WX
Subject: Wetter Schoengrabern 18:00
Replace: geosphere-wetter-11334
Valid: 2h
Brocast: {"typ":"wx","dat":{"temp":21.3,"hum":31,"qff":1028.5},"blk":[{"k":"series","u":"Cel","sc":-1,"dt":7200,"v":[100,71,60]}]}

  Temperatur     21.3 °C
  ...
```

- **Inhalt:** ein JSON-Objekt in **einer** Zeile, genau im Format der brocast-Ingest-API (Namen statt Nummern, wie `PUT /pages/...`). Pflicht ist `typ`. Höchstens 8 kB.
- **Prüfung im Eingang:** nur, ob es gültiges JSON und ein Objekt mit `typ` ist; sonst landet die Datei in `fehler\`. Die inhaltliche Prüfung macht brocastd.
- **Speicherung:** neue Spalte `brocast` in `messages` (Schema 3, ältere Datenbanken werden beim Start ergänzt). `Replace:` ersetzt auch die Seite; „gleicher Inhalt“ heißt gleicher Text **und** gleiche Seite.
- **Adapter:** Hat ein Bulletin eine Seite, wird sie gesendet. TinyBox ergänzt nur, was fehlt: `ti` (Betreff), `cat` (Rubrik aus dem Ziel), `exp` (wie bei Textseiten). `to` und `src` setzt TinyBox hier nicht, das entscheidet das Skript.
- **Rückfall:** Lehnt brocastd die Seite ab (z. B. Feld nicht im Dictionary), sendet der Adapter stattdessen die Textseite und schreibt eine Warnung ins Log. Ohne `Brocast:` bleibt alles wie bisher.
- In der Mailbox ist die Kopfzeile unsichtbar (Funkamateure lesen Betreff und Text).

## 6. MQTT (vorbereitet, Umsetzung später)

**Richtungen**

- **Eingang:** Nachrichten vom Broker werden in TinyBox abgelegt, z. B. Bulletins aus einem anderen System.
- **Ausgang:** TinyBox veröffentlicht Ereignisse wie neue Nachrichten, Status oder Connects.

**Topic-Entwurf** (`<root>` = `topic_root`)

| Topic | Richtung | Inhalt |
|---|---|---|
| `<root>/in/message` | Broker → TB | neue Nachricht (JSON) |
| `<root>/out/message` | TB → Broker | `message.created` (JSON) |
| `<root>/out/event` | TB → Broker | Connect/Disconnect/Read/Delete |
| `<root>/status` | TB → Broker | `online`/`offline` (retained, Last Will) |

**Nachrichtenformat (JSON)**

```json
{ "msgid": "uuid", "type": "B", "to": "ALL", "from": "OE3GAS",
  "subject": "...", "body": "...", "created": "2026-09-27T20:00:00Z" }
```

**Schon ab v1 im Datenmodell berücksichtigt**

- `origin` pro Nachricht: `radio`, `telnet`, `sysop` oder `mqtt`
- `msgid` (UUID) pro Nachricht, damit Duplikate erkannt werden (MQTT QoS 1 kann doppelt zustellen)
- Event-Bus und MessageService wie in Abschnitt 4

**Technik:** Bibliothek `paho-mqtt` (oder `aiomqtt` für asyncio). Das ist die einzige externe Abhängigkeit, und sie wird erst mit dem MQTT-Meilenstein nötig. Die Struktur erlaubt später mehrere Broker (je einen `[mqtt.xyz]`-Abschnitt).

**Sicherheit und Recht**

- TLS, Anmeldung am Broker, eigener Topic-Bereich (ACL am Broker).
- Eingehende Daten gelten als nicht vertrauenswürdig: Schema prüfen, Größe begrenzen, Rufzeichen prüfen, Rate-Limit.
- Was über MQTT hereinkommt, kann über Funk ausgelesen werden. Deshalb nur Absender mit gültigem Amateurfunk-Rufzeichen annehmen und eine Absender-Allowlist in der Konfiguration führen. Die Verantwortung liegt beim Sysop (AFV/AFG beachten: Inhalte, Drittverkehr).

---

## 7. Datenhaltung

`data_dir` (Standard `E:\Tinybox\data\`)

- `tinybox.db` (SQLite)
  - `messages(id, msgid, type, status, to_call, from_call, subject, body, size, origin, created, read_at, replace_key, expires, brocast)`
  - `jlog(call, first_seen, last_seen, count)`
  - `users(call, last_login)`
- Log-Datei optional: `[logging] log_dir` (Ordner muss existieren und beschreibbar sein), pro Start eine Datei `Tinybox_log_<JJJJ-MM-TT_hh-mm-ss>.log`, reiner Text

Nachrichtennummern laufen fortlaufend und werden nie wiederverwendet. Für ein Backup genügt es, den Ordner zu kopieren.

---

## 8. Projektstruktur

```
E:\Tinybox\
  PLANUNG.md
  tinybox.conf
  tinybox.bat            Start
  tinybox\
    __main__.py          Start, Konfiguration laden
    config.py            tinybox.conf lesen und prüfen
    events.py            Event-Bus
    service.py           MessageService (Regeln, Rechte)
    store.py             SQLite
    session.py           Sitzungs-Zustandsautomat
    commands.py          Befehle
    texts.py             englische Ausgabetexte
    adapters\
      agw.py             Direwolf/AGW
      telnet.py          Testport
      sysop.py           lokale Konsole
      mqtt.py            (später)
  tests\
  data\
  secrets\
```

Sitzungszustände: `COMMAND` → `SEND_SUBJECT` → `SEND_BODY` → `COMMAND`. Wird die Verbindung während `SEND_BODY` getrennt, wird die Nachricht verworfen.

---

## 9. Sicherheit & Betrieb

- Zeilenlänge und Nachrichtengröße begrenzen, Rate-Limit pro Call.
- Rufzeichen validieren (SSID 0–15), in Großbuchstaben speichern.
- SQL nur mit Parametern.
- Idle-Timeout.
- Telnet nur auf `127.0.0.1`.
- Kein Schreibzugriff außerhalb von `data_dir`.

---

## 10. Meilensteine

| # | Inhalt | Ergebnis |
|---|---|---|
| M1 ✅ | config, store, service, events, Befehle, Telnet (inkl. `E n`) | Mailbox lokal bedienbar – erledigt 27.09.2026, 15 Tests grün |
| M2 ✅ | AGW-Adapter mit Direwolf | Fertig, Funktest mit echtem Direwolf erfolgreich (27.09.2026) |
| M3 ✅ | Sysop-Konsole (W, MON, DISC, STATUS, SHUTDOWN), Monitor | Fertig 28.09.2026, 29 Tests grün |
| M3b ✅ | Sysop-Web-GUI (nur 127.0.0.1, Token, Host-Check, POST+Token für Änderungen), Light Theme mit kräftig dunkler Schrift | Fertig 28.09.2026 nach freigegebenem Mockup, 36 Tests grün |
| M3c ✅ | Befehl `DICT` (brocast-Dictionary als Text), `[brocast] dict_file` | Fertig 01.10.2026, 43 Tests grün |
| M3d ✅ | brocast-Adapter: Bulletins an brocastd melden (Abschnitt 6b) | Fertig 02.10.2026, 55 Tests grün |
| M3e ✅ | Eingangsordner für Skripte mit `Replace:` und `Valid:` (Abschnitt 6c) | Fertig 02.10.2026, 65 Tests grün |
| M3f ✅ | Kopfzeile `Brocast:` im Eingang, Seite statt Text an brocastd (Abschnitt 6d) | Fertig 03.10.2026 |
| M4 | Limits, Timeouts, Logging, Tests | Dauerbetrieb |
| M5 | MQTT-Adapter (Ein-/Ausgang) | Anbindung an Broker |
| M6 (opt.) | Beacon (UI-Frame) | Mailbox kündigt sich an |
| C0–C3 | TinyBox-Client (Abschnitt 12) | Grundgerüst, Post-Hinweis, Chat-Broadcast, Offline-Mailbox |

---

## 11. Offene Punkte

1. ~~`third_party`~~ → entschieden: `yes` (Standard).
2. Bulletins nach X Tagen automatisch löschen (Vorschlag: 30)?
3. MQTT: Welcher Broker (lokaler Mosquitto oder extern)? Wofür konkret, also woher kommen die Nachrichten und wer liest die Ausgänge?
4. MQTT-Eingang: Nur Bulletins oder auch Privatnachrichten an einzelne Calls?

---

## 12. TinyBox-Client (Konzept, Entwurf 07.10.2026)

Eigener Client mit Zusatzfunktionen, die es nur mit der TinyBox gibt. Getrennt von brocast.

**Grundsatz:** Der Client ist ein Zusatz, keine Voraussetzung. Alles Wesentliche funktioniert weiterhin mit jedem Terminalprogramm, über Digi und über Node.

### 12.1 Technik

- Python-Dienst mit **lokaler Web-GUI** (127.0.0.1), gleiche Bauart wie der brocastd-Listener.
- Anbindung an Direwolf über **AGW**, nicht KISS. Direwolf erledigt die AX.25-Verbindung (`C`/`D`/`d`). Der Client sendet UI-Frames (`M`/`V`) und liest alle Frames roh mit (`k`).
- Zu prüfen: Wie viele Anwendungen Direwolf gleichzeitig am AGW-Port zulässt (`MAX_NET_CLIENTS`), relevant für PC2 mit TinyBox + brocastd.

### 12.2 Handshake (Vorschlag)

- Der Client sendet nach dem Login `//CLIENT TB1 caps=NOTE,CHAT,SYNC`.
- Die TinyBox antwortet `//OK TB1 caps=…` mit dem gemeinsamen Funktionsumfang.
- Die TinyBox merkt sich je Sitzung, ob ein Client angemeldet ist.
- **UI-Modus nur bei direkter Verbindung:**
  - Hat die Sitzung einen Digi-Pfad (`via`), bleibt sie immer im I-Frame-Modus.
  - Der Client meldet sich nur für den UI-Modus an, wenn er die TinyBox selbst hört. Damit sind Node-Verbindungen abgedeckt.

### 12.3 Funktionen v1 (Reihenfolge = Umsetzungsreihenfolge)

| # | Funktion | Kern |
|---|---|---|
| C0 | Grundgerüst + Handshake | AGW-Anbindung, Verbinden, UI mitlesen, `//CLIENT` |
| C1 | Post-Benachrichtigung | Die TinyBox sendet ein UI-Frame „neue Post für <Call>“. Der Client zeigt einen Hinweis an, ohne verbunden zu sein. |
| C2 | Chat mit UI-Broadcast | Beitrag als I-Frame an die TinyBox, die ihn einmal als UI an `TBCHAT-x` sendet (x = Board 0–15). Client-Sitzungen bekommen die Zeile nicht zusätzlich per I-Frame. |
| C3 | Offline-Mailbox mit Delta-Sync | Neue Nachrichten/Bulletins komprimiert in einem Durchgang holen, offline lesen und schreiben, gesammelt senden, nach Abbruch fortsetzen |

### 12.4 Chat-Frame (Vorschlag)

```
Ziel:   TBCHAT-x        Quelle: <TinyBox-Call>     PID: 0xF0
Info:   [Version][Folgenummer][Typ][Autor-Call][Text UTF-8]
Typ:    Zeile | Betreten | Verlassen | System
```

- Der Client erkennt Lücken an der Folgenummer und fordert über seine Sitzung nach (`//RESEND <Board> <von>-<bis>`). Die Antwort kommt nur an ihn, per I-Frame.
- Teilnehmer mit Terminalprogramm sowie Verbindungen über Digi oder Node bekommen die Zeilen wie bisher einzeln per I-Frame.
- Voraussetzung: Der bestehende Chat-Code (aus einem anderen Chat) muss zuerst ins Repo.

### 12.5 Später

Strukturierter Modus (CBOR statt Menütext), Formulare, kleine Dateien, Sysop-Fernverwaltung mit Challenge-Response (keine Verschlüsselung), Anzeige der Verbindungsqualität, zeitgesteuertes Abholen.

---

## Quellen

- AEA PK-232MBX Operating Manual, Kap. 5 (nur Orientierung): https://www.dl0bn.de/dc7xj/Anleitungen/AEA%20PK-232MBX_Manual.pdf
- Direwolf-Dokumentation (AGW-Interface): https://github.com/wb2osz/direwolf/tree/master/doc
