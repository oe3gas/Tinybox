# TinyBox – Planung

Kleine, eigenständige Packet-Radio-Mailbox für Direwolf.
Bedienersprache: **Englisch**. Speicherung komplett am PC.
Forwarding mit anderen Mailboxen als optionales Modul (Abschnitt 13). Vorbereitet für die Anbindung an MQTT-Broker.
Eigener TinyBox-Client mit Sonderfunktionen in Planung (Abschnitt 12).

Stand: 07.10.2026 (Rev. 4) · OE3GAS

**Überblick: zwei Projektteile neben dem Kern**

| Teil | Zweck | Stand | Details |
|---|---|---|---|
| Forwarding (F0–F7) | TinyBox tauscht Post und Bulletins mit anderen Mailboxen (LinBPQ, FBB, openBCM) | F1–F5 fertig: TinyBox empfängt und sendet (ASCII, FBB, B1 komprimiert), ruft Partner selbst an; mit LinBPQ getestet. Als Nächstes F6 (Anschluss ans Netz) | Abschnitt 13 und Konzept-Doc |
| TinyBox-Client (C0–C3) | Eigener Client mit Funktionen, die es nur mit der TinyBox gibt: Post-Hinweis, Chat per UI-Broadcast, Offline-Mailbox | C0, C1, C2 umgesetzt (08.10.2026): Grundgerüst, Handshake, Post-Hinweis, Chat mit UI-Broadcast, Web-GUI im Messenger-Stil (Handy und PC). Offen: C3 | Abschnitt 12 |

**Änderungen gegenüber Rev. 3**

- Planung an den Code angeglichen (Stand Commit 329e67d).
- Forwarding ist jetzt im Umfang, als abschaltbares Modul (Abschnitt 13). Der Kern ist auf Schema 5: hierarchische Adressen, BID, R:-Zeilen.
- Chat-Boards (Befehl `C`) sind fertig und jetzt beschrieben (Abschnitt 2a).
- Client: Web-GUI im LAN/WAN erreichbar, ohne Anmeldung, mobile Oberfläche (Abschnitt 12.1).
- Befehlssatz, Ereignisse, Konfiguration, Datenhaltung, Projektstruktur und Meilensteine nachgezogen. Entwickelt wird auf PC2 in `C:\Tinybox`, PC1 (`E:\Tinybox`) holt per `git pull`.

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
- Chat-Boards für eingeloggte Stationen (Abschnitt 2a).
- Optional: Austausch mit anderen Mailboxen (Forwarding, Abschnitt 13).
- Nachrichten können später auch über MQTT eingespielt und ausgegeben werden.
- Einfacher, gut lesbarer Code (Lernprojekt).

**Nicht im Umfang (v1)**

- BBS-Forwarding gehört nicht zum Kern. Es kommt als eigenes, abschaltbares Modul dazu (Abschnitt 13). Ohne Modul bleibt TinyBox eine Standalone-Mailbox.
- Keine Dateiablage / kein YAPP.
- MQTT: in v1 nur die Schnittstellen vorbereiten, die Umsetzung folgt in einem eigenen Meilenstein.

---

## 2. Befehlssatz

Orientiert sich am klassischen WORLI/MailDrop-Stil, den Packet-Nutzer kennen. Die Einzelheiten legt TinyBox selbst fest.

| Befehl | Funktion |
|---|---|
| `A` | Laufende Ausgabe abbrechen |
| `B` | Abmelden, Verbindung trennen |
| `C` / `C board` | Chat: Boards auflisten / Board betreten (Name oder Nummer), Abschnitt 2a |
| `H` / `?` | Hilfe |
| `J` | Zuletzt verbundene Stationen |
| `K n` | Nachricht n löschen (eigene oder an mich) |
| `KM` | Alle gelesenen Nachrichten an mich löschen |
| `L` | Nachrichten auflisten |
| `LB` / `LP` | Nur Bulletins / nur private Nachrichten |
| `L@ gebiet` | Nachrichten @ Gebiet oder Mailbox, z. B. `L@ WW` |
| `L> call` / `L< call` | Nachrichten an / von `call` |
| `LM` | Nur Nachrichten an mich |
| `R n` | Nachricht n lesen |
| `RM` | Alle ungelesenen Nachrichten an mich lesen |
| `S call` / `SP call` | Private Nachricht an `call` |
| `SP call @ mailbox` | Private Nachricht an einen User einer anderen Mailbox, z. B. `SP OE1ABC @ OE1XAB.#WIE.AUT.EU` (nur mit Forwarding) |
| `SB rubrik [@ gebiet]` | Bulletin, z. B. `SB ALL` oder `SB ALL @ WW`; optional am Ende `$BID` |
| `V` | Version |
| `E n feld wert` | Nachrichtenkopf ändern (nur SYSOP), Felder TO, FROM, TYPE, STATUS, SUBJ, AT |
| `DICT` | brocast-Dictionary als Text ausgeben (für den Import im brocast-Listener) |

**`DICT` (Zusammenarbeit mit brocast):** TinyBox bleibt eine Textmailbox ohne Dateiablage. Das brocast-Dictionary ist reiner Text (YAML) und wird deshalb einfach ausgegeben: zwischen den Zeilen `#BROCAST-DICT BEGIN v<Version> lines=<n> sha256=<Prüfsumme>` und `#BROCAST-DICT END`, ohne Kommentar- und Leerzeilen, rein ASCII (Umlaute in Anführungszeichen als `\uXXXX`). Der Nutzer speichert den Mitschnitt seines Terminals und importiert ihn im brocast-Listener, der Zeilenzahl und SHA-256 prüft. Die Datei liest TinyBox direkt von der Platte (`[brocast] dict_file` in `tinybox.conf`), eine neue Version ist sofort verfügbar.

Eingabe einer Nachricht: zuerst wird der Betreff abgefragt, dann der Text. Ende mit **`/EX`** in eigener Zeile oder **CTRL-Z**.

**Rechte**

- **User**: liest Bulletins und die eigenen Privatnachrichten. Löscht nur Nachrichten, die an ihn gerichtet oder von ihm sind.
- **SYSOP** (lokal): darf alles lesen und löschen, dazu `E n`.
- `third_party = yes` (Standard): jeder darf an jeden schreiben. Mit `no` dürfen Remote-User nur an den Sysop schreiben.

**Typ/Status**: Typ `P` (privat) oder `B` (Bulletin); Status `N` (ungelesen) oder `Y` (gelesen). Ein dritter Buchstabe im Listing zeigt den Forward-Zustand: `$` wartet, `F` weitergeleitet, `H` gehalten (gehaltene Nachrichten sieht nur der Sysop).

## 2a. Chat-Boards (fertig, Commit 33c2259)

- Feste Boards, vom Sysop in `[chat_boards]` festgelegt: `NAME = Aufbewahrung Beschreibung`. Aufbewahrung `live` (nichts wird gespeichert) oder z. B. `12h` / `7d` (max. `365d`). Die Reihenfolge in der Datei ist die Nummer des Boards.
- `C` listet die Boards, `C board` betritt eines. Im Board ist jede Zeile Chattext, Befehle beginnen mit `/`: `/Q`, `/EX` oder CTRL-Z zurück in die Mailbox, `/W` wer ist da, `/L` alle Boards, `/J board` wechseln, `/H` Hilfe.
- Beim Betreten zeigt TinyBox bis zu `history_lines` alte Zeilen (Tabelle `chat_lines`). Zeilenlänge max. `max_line`.
- Der `ChatHub` (`chat.py`) verteilt die Zeilen und meldet `chat.joined`, `chat.left`, `chat.message` an den Event-Bus. Sysop-Konsole und Web-GUI zeigen den Chat an.
- Grenze: Jede Zeile geht per I-Frame einzeln an jeden Teilnehmer (1 Eingabe = n Ausgaben auf der Frequenz). Das soll der Client mit UI-Broadcast lösen (Abschnitt 12, C2).

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
| `message.edited` | Nachricht geändert (`E n`, Eingang mit `Replace:`) |
| `message.expired` | Nachrichten abgelaufen und gelöscht (Aufräumroutine) |
| `chat.joined` / `chat.left` / `chat.message` | Chat-Boards (Abschnitt 2a) |

**Adapter heute (Rev. 4):** AGW (Funk), Telnet (Test), Sysop-Konsole, Sysop-Web-GUI, Eingangsordner (`inbox`), brocast und das Forward-Modul (nur bei `[forward] enabled = yes`). Der Chat läuft über den `ChatHub` neben dem MessageService. MQTT fehlt noch (M5).

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

INI-Format (Python `configparser`, Standardbibliothek). Die vollständige, kommentierte Vorlage ist `tinybox.conf.example` im Repo. `tinybox.conf` selbst ist PC-spezifisch und liegt nicht im Repo.

| Abschnitt | Inhalt |
|---|---|
| `[station]` | Mailbox-Call, Sysop-Call, `sysop_via_radio`; neu `haddress` (z. B. `OE3XTC.#NOE.AUT.EU`) und `qth` für die R:-Zeilen |
| `[direwolf]` | AGW-Host und -Port, Funkkanal, Reconnect, `paclen`, `max_outstanding` |
| `[mailbox]` | Begrüßung, `third_party`, `max_users`, Größen, Idle-Timeout, `bulletin_expire_days` (0 = nie löschen) |
| `[telnet]` | Testport, nur Loopback |
| `[web]` | Sysop-Web-GUI, nur Loopback, Port 8080 |
| `[console]` | Sysop-Konsole und Monitor |
| `[storage]`, `[logging]` | Datenordner; Loglevel, optional Logordner |
| `[brocast]` | Datei für `DICT`, Bulletins an brocastd melden (Abschnitt 6b) |
| `[inbox]` | Eingangsordner für Skripte (Abschnitt 6c) |
| `[chat]`, `[chat_boards]` | Chat ein/aus, Verlauf, Zeilenlänge; die festen Boards (Abschnitt 2a) |
| `[forward]` | Modul ein/aus (Standard `no`), `bid_days`, Aliase, eingehender TCP-Port (Abschnitt 13) |
| `[partner.CALL]` | je Partner-Mailbox: Transport `agw`/`tcp`, Funk-Call, Digis, Login, Passwort, Routen, Gebiete, Protokoll, Timeout; Zeitplan `auto`, `interval_min`, `window`, `retry_min` |
| `[mqtt]` | vorbereitet, Standard `no` (M5) |

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

`data_dir` (Standard `data\` neben der `tinybox.conf`)

- `tinybox.db` (SQLite, Schema 5, ältere Datenbanken werden beim Start migriert)
  - `messages(id, msgid, type, status, to_call, from_call, subject, body, size, origin, created, read_at, replace_key, expires, brocast, at_addr, bid, bid_kind, rlines, fwd, note)`
    - Schema 5 (Forwarding): `at_addr` (@-Adresse bzw. Verteilgebiet, leer = lokal), `bid` (max. 12 Zeichen, eindeutig), `bid_kind` (B echte BID, M erzeugte MID), `rlines` (R:-Zeilen, getrennt vom Text), `fwd` (leer, `$`, `F`, `H`), `note` (Grund fürs Halten)
  - `bids(bid, first_seen, origin)` – jede je gesehene BID, Aufbewahrung `bid_days`
  - `fwd_queue(msg_id, partner, state, changed)` – nur vom Forward-Modul befüllt; Zustände open, later, done, rejected
  - `chat_lines(id, board, call, text, created)` – nur Boards mit Verlauf
  - `jlog(call, first_seen, last_seen, count)`
  - `users(call, last_login)`
- Log-Datei optional: `[logging] log_dir` (Ordner muss existieren und beschreibbar sein), pro Start eine Datei `Tinybox_log_<JJJJ-MM-TT_hh-mm-ss>.log`, reiner Text

Nachrichtennummern laufen fortlaufend und werden nie wiederverwendet. Für ein Backup genügt es, den Ordner zu kopieren.

---

## 8. Projektstruktur

```
C:\Tinybox\                PC2 (Entwicklung); PC1: E:\Tinybox, per git pull
  PLANUNG.md  README.md  GIT-ANLEITUNG.md
  tinybox.conf              PC-spezifisch, nicht im Repo (Vorlage tinybox.conf.example)
  tinybox.bat  tinybox_dauerbetrieb.bat  start_alles.bat  runtests.bat
  tinybox\
    __main__.py             Start, Konfiguration laden, Adapter starten
    app.py                  verbindet die Bausteine
    config.py               tinybox.conf lesen und prüfen
    events.py               Event-Bus
    service.py              MessageService (Regeln, Rechte, BID-Prüfung)
    store.py                SQLite, Schema 5 mit Migration
    addressing.py           hierarchische Adressen, BID, R:-Zeilen
    session.py              Sitzungs-Zustandsautomat
    commands.py             Befehle
    chat.py  chatcmd.py     Chat-Boards (ChatHub, Befehl C, /-Kommandos, TBCHAT-Ereignisse)
    clientproto.py          Client-Protokoll TB1 (//CLIENT, //BOARDS, //RESEND)
    dictfile.py             Befehl DICT
    texts.py                englische Ausgabetexte
    adapters\
      agw.py                Direwolf/AGW (annehmen und anrufen)
      telnet.py             Testport
      sysop.py              lokale Konsole
      web.py                Sysop-Web-GUI (Dateien in tinybox\web\)
      inbox.py              Eingangsordner
      brocast.py            Bulletins an brocastd
      forward.py            Forward-Modul (nur bei [forward] enabled)
      mqtt.py               (später, M5)
    fwd\                    Forwarding: protocol, link (AGW/TCP), router, session
    web\                    HTML/CSS/JS der Sysop-Web-GUI
  tbclient\                 TinyBox-Client (Abschnitt 12): Start tbclient.bat, Vorlage tbclient.conf.example
    core.py  proto.py       Client-Logik, Ereignis-Parser
    links.py  radio.py      AGW (Funk, mit Rohframes) bzw. Telnet; AX.25/APRS-Symbole
    web.py  web\            Web-GUI (Messenger-Chat), emoji.json, aprs\ (Symbole OH7LZB)
  fwdsim\                   Forward-Testpartner, eigenständig (Abschnitt 13)
  brocast\                  brocast (eigenes Projekt, siehe brocast\README.md)
  geosphere_*.py            Wetter- und Warnungs-Skripte für den Eingangsordner
  tests\
  docs\                     W0RLI-Spezifikation, Fachartikel
  data\  logs\  eingang\     Betriebsdaten, nicht im Repo
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
| M3g ✅ | Chat-Boards mit Aufbewahrung, Befehl `C`, /-Kommandos, Anzeige in Konsole und Web (Abschnitt 2a) | Fertig 04.10.2026 |
| M4 | Limits, Timeouts, Logging, Tests | Dauerbetrieb |
| P1 ❗ | **Major Fix** brocastd: kein Datenbank-Schreiben pro Funk-Frame, Sendeprotokoll abschaltbar (offener Punkt 9) | Voraussetzung für Dauerbetrieb auf dem NanoPi (eMMC) |
| M5 | MQTT-Adapter (Ein-/Ausgang) | Anbindung an Broker |
| M6 (opt.) | Beacon (UI-Frame) | Mailbox kündigt sich an |
| F0–F7 | Forwarding-Modul (Abschnitt 13) | F1–F5 fertig (06.–08.10.2026), mit LinBPQ getestet; F0 teilweise. Als Nächstes F6 |
| C0–C3 | TinyBox-Client (Abschnitt 12) | Grundgerüst, Post-Hinweis, Chat-Broadcast, Offline-Mailbox. Konzept fertig, noch kein Code |

---

## 11. Offene Punkte

1. ~~`third_party`~~ → entschieden: `yes` (Standard).
2. ~~Bulletins nach X Tagen automatisch löschen~~ → umgesetzt: `bulletin_expire_days = 30` (0 = nie).
3. MQTT: Welcher Broker (lokaler Mosquitto oder extern)? Wofür konkret, also woher kommen die Nachrichten und wer liest die Ausgänge?
4. MQTT-Eingang: Nur Bulletins oder auch Privatnachrichten an einzelne Calls?
5. Client-Web-GUI im WAN ohne Anmeldung (Abschnitt 12.1): Wer die Adresse kennt, kann unter dem Rufzeichen des Client-Betreibers senden (Chat, Post). Zu klären, wie das abgesichert wird, z. B. nur über VPN/HAMNET erreichbar oder ein einfaches Zugangstoken.
6. Direwolf: Wie viele Programme gleichzeitig am AGW-Port (`MAX_NET_CLIENTS`)? Relevant für PC2 mit TinyBox, brocastd und ggf. Client.
7. Forwarding über Funk ohne Aufsicht ist vermutlich eine Relaisfunkstelle mit Clubrufzeichen: mit Fernmeldebüro oder ÖVSV klären (F0). Bis dahin Forwarding nur über TCP/HAMNET.
8. Forwarding: OE-Hub-Partner finden, eigene Region für `haddress` mit dem Hub-Sysop abstimmen (F0/F6).
9. **MAJOR FIX (vor Dauerbetrieb auf dem NanoPi, eMMC 8 GB):** brocastd schreibt bei **jedem Funk-Frame** mehrfach in die SQLite-Datenbank, jeweils als eigener Commit ohne PRAGMAs (Rollback-Journal, `synchronous=FULL`, also mehrere fsync pro Commit). Das ist verschwenderisch und verschleißt den eMMC. Gefunden am 07.10.2026 bei der Produktionsversion (`PRODUCTION.md`).
   - Jeder gesendete Frame wird über `_send` → `_receive(own=True)` (`brocast/brocast/daemon.py:79-84`) als eigener Empfang verbucht. Das sind die Commits `heard()` (`store.py:326`), `save_received`, `update_lpage` (`listener.py:191-258`) und `add_rxlog` (`store.py:347`). Pro Seite kommt noch `mark_sent` dazu (`carousel.py:225`).
   - Jeder empfangene Frame, auch fremde wie APRS, schreibt `add_rxlog` (`daemon.py:95-100`). Brocast-Frames schreiben zusätzlich `heard()` und die lpage-Commits.
   - Das Sendeprotokoll schreibt eine Zeile pro Frame (`txlog.py:46-59`). Es lässt sich nicht abschalten: Ein leeres `txlog_dir` wird zu `logs` (`config.py:138`), deshalb ist die Prüfung `is not None` in `daemon.py:65` toter Code.

   Vorschlag:
   - Pro Verbindung `PRAGMA journal_mode=WAL` und `synchronous=NORMAL`.
   - Flüchtige Daten nur im RAM halten: rxlog, „stations heard“, das Echo eigener Frames und `last_seen`, wenn eine Seite nur wiederholt wird. Höchstens gebündelt speichern, z. B. alle 10 min und beim Beenden.
   - Den Sendezeitplan (`mark_sent`) im RAM führen und nur gebündelt oder beim Beenden speichern.
   - Leeres `txlog_dir` = Sendeprotokoll aus.
   - Ziel: Die Datenbank wird nur bei echten Änderungen geschrieben, also bei neuen oder geänderten Seiten, Einstellungen und Bedienung.
   - Danach dieselben PRAGMAs für die TinyBox-Datenbank prüfen, die nur bei Login, Nachrichten und Chat schreibt (niedrige Priorität).

   Bis zum Fix bleibt die brocastd-Datenbank auf dem eMMC. Das Sendeprotokoll legt die Produktionsversion in den RAM (`/run/tinybox`).

---

## 12. TinyBox-Client (Konzept, Stand 07.10.2026)

Eigener Client mit Zusatzfunktionen, die es nur mit der TinyBox gibt. Getrennt von brocast.

**Grundsatz:** Der Client ist ein Zusatz, keine Voraussetzung. Alles Wesentliche funktioniert weiterhin mit jedem Terminalprogramm, über Digi und über Node.

### 12.1 Technik

- Python-Dienst mit **Web-GUI**, gleiche Bauart wie der brocastd-Listener.
- Die Web-GUI ist im **LAN und WAN** erreichbar (vor allem für den Chat am Handy), **ohne Anmeldung**, mit **mobiler Oberfläche**. Absicherung: offener Punkt 5. Die Sysop-Web-GUI der TinyBox bleibt davon unberührt auf 127.0.0.1.
- Anbindung an Direwolf über **AGW**, nicht KISS. Direwolf erledigt die AX.25-Verbindung (`C`/`D`/`d`). Der Client sendet UI-Frames (`M`/`V`) und liest alle Frames roh mit (`k`).
- Zu prüfen: Wie viele Anwendungen Direwolf gleichzeitig am AGW-Port zulässt (`MAX_NET_CLIENTS`), relevant für PC2 mit TinyBox + brocastd.

### 12.2 Handshake (umgesetzt für CHAT und UI)

- Der Client sendet nach dem Login `//CLIENT TB1 caps=CHAT,UI sym=/-` (später auch `NOTE`, `SYNC`).
- Die TinyBox antwortet `//OK TB1 caps=…` mit dem gemeinsamen Funktionsumfang.
- Die TinyBox merkt sich je Sitzung, ob ein Client angemeldet ist.
- **UI-Modus nur bei direkter Verbindung:**
  - Hat die Sitzung einen Digi-Pfad (`via`), bleibt sie immer im I-Frame-Modus.
  - Der Client meldet sich nur für den UI-Modus an, wenn er die TinyBox selbst hört. Damit sind Node-Verbindungen abgedeckt.

### 12.3 Funktionen v1 (Reihenfolge = Umsetzungsreihenfolge)

| # | Funktion | Kern |
|---|---|---|
| C0 | Grundgerüst + Handshake | AGW-Anbindung, Verbinden, UI mitlesen, `//CLIENT` |
| C1 | Post-Benachrichtigung | Die TinyBox sendet ein UI-Frame „neue Post für <Call>“. Der Client zeigt einen Hinweis an, ohne verbunden zu sein. **Umgesetzt:** UI an `TBMAIL`, Text `OE3ABC 2 new` (Rufzeichen ohne SSID, Zahl ungelesener Privatnachrichten). Nur lokale Post (nicht zum Weiterleiten oder angehalten), höchstens ein Frame pro Rufzeichen und Minute; mehr Post in dieser Minute wird am Ende einmal mit neuer Zahl gemeldet. Abschaltbar: `[client] mail_notify = no`. Der Client wertet zusätzlich die Login-Zeile „You have n new message(s)“ aus. |
| C2 | Chat mit UI-Broadcast | Beitrag als I-Frame an die TinyBox, die ihn einmal als UI an `TBCHAT-x` sendet (x = Nummer des Boards in `[chat_boards]`, 1–15 = SSID). Client-Sitzungen im UI-Modus bekommen die Zeile nicht zusätzlich per I-Frame. Ab Board 16 gehen die Ereignisse per I-Frame. **Umgesetzt.** |
| C3 | Offline-Mailbox mit Delta-Sync | Neue Nachrichten/Bulletins komprimiert in einem Durchgang holen, offline lesen und schreiben, gesammelt senden, nach Abbruch fortsetzen |

### 12.4 Chat-Frame (entschieden 08.10.2026: lesbarer Text)

```
Ziel:   TBCHAT-x        Quelle: <TinyBox-Call>     PID: 0xF0
Info:   lesbarer Text, Folgenummer hexadezimal (1–2 Zeichen)
```

| Typ | Info-Feld | Beispiel |
|---|---|---|
| Beitrag | `#<nr> <Call>: <Text>` | `#4F OE3GAS: Servus, Wetter passt :+1` |
| Betreten | `#<nr> +<Call> [<APRS-Symbol>]` | `#50 +OE3GAS /-` |
| Verlassen | `#<nr> -<Call>` | `#51 -OE3GAS` |
| Reaktion | `#<nr> <Call> *<Bezug-nr> <Emoji>` | `#52 OE3TEC *4F :+1` |
| System | `#<nr> !<Text>` | `#53 !Board schließt um 22:00` |

- Keine Steuerbytes: Mithörer mit Terminalprogramm oder Direwolf lesen den Chat ohne Client mit.
- Keine Version im Frame; Client und TinyBox tauschen sie beim `//CLIENT`-Handshake aus (12.2).
- Emojis und Avatare: siehe 12.6.

- Der Client erkennt Lücken an der Folgenummer und fordert über seine Sitzung nach (`//RESEND <Board> <von>-<bis>`). Die Antwort kommt nur an ihn, per I-Frame.
- Teilnehmer mit Terminalprogramm sowie Verbindungen über Digi oder Node bekommen die Zeilen wie bisher einzeln per I-Frame.
- Voraussetzung erfüllt: Der Chat-Code ist seit Commit 33c2259 im Repo (Abschnitt 2a).
- Gelöst: Die TinyBox hält je Board die letzten 256 Ereignisse im Speicher, `//RESEND` (höchstens 64 auf einmal) bedient sich dort – auch bei Live-Boards.

**Umgesetztes Client-Protokoll (TB1)** – Steuerzeilen per I-Frame, nur für Client-Sitzungen (ohne Prompt):

| Richtung | Zeile | Bedeutung |
|---|---|---|
| C → T | `//CLIENT TB1 caps=CHAT,UI sym=/-` | Anmeldung; UI nur bei Funk-Sitzung, `sym` nur wenn im Client gewählt |
| T → C | `//OK TB1 caps=…` | gemeinsamer Funktionsumfang |
| C → T | `//BOARDS` | → `//B <n> <Board> <keep> <User> <Beschreibung>` … `//BEND` |
| C → T | `C <n>` bzw. `/J <n>` | Board betreten bzw. wechseln |
| T → C | `//IN <n> <Board> <keep> <letzte Nr.>` | Board betreten |
| T → C | `//H <Unixzeit> <Call>: <Text>` | Verlaufszeile |
| T → C | `//WHO <Call>[=<Symbol>] …` | wer schon da ist |
| C → T | `/R <Nr.> <Emoji-Code>` | Reaktion (geht auch vom Terminal) |
| C → T | `//RESEND <a>-<b>` | fehlende Ereignisse nachfordern |
| C → T / T → C | `/Q` / `//OUT <Board>` | Board verlassen |

- **Reihenfolge:** Ein UI-Frame geht sofort hinaus, I-Frames warten in der Sendewarteschlange. Das UI-Frame des eigenen Betretens kann deshalb vor `//IN` ankommen; der Client hält solche Ereignisse bis `//IN` zurück.
- **APRS-Symbol eines Teilnehmers:** Symbol aus der Betreten-Meldung (seine eigene Wahl) vor gehörter APRS-Bake. Ohne gewähltes Symbol sendet der Client keins (0 Byte), dann zählt die Bake.

### 12.5 Bezug zum Forwarding

- Client und Forward-Modul sind getrennt. Ein Client ist ein User und meldet sich mit `//CLIENT` an, eine Partner-Mailbox mit ihrer SID. Die Partnerliste (`[partner.CALL]`) entscheidet, wer Forward-Sitzungen bekommt.
- Wiederverwendbar aus F2: ausgehender AGW-Connect (`AgwAdapter.connect`) und die Link-Abstraktion (`tinybox/fwd/link.py`).
- C3 (Delta-Sync) braucht eindeutige Kennungen je Nachricht. Dafür eignen sich `msgid` bzw. die BID aus Schema 5.

### 12.6 Chat-Oberfläche im Messenger-Stil (Stand 08.10.2026)

Der Chat im Client sieht aus wie ein heutiger Messenger: Avatare, Sprechblasen, Emojis. **Grundsatz: Alles Optische entsteht lokal im Client, über Funk geht nur das Nötigste.** Bei 1200 Bd zählt vor allem die Zahl der Frames (jeder UI-Frame hat ≥ 16 Byte Kopf plus TXDelay), erst danach die Bytes.

**Was über Funk geht – und was nicht**

| Element | Über Funk | Umsetzung |
|---|---|---|
| Avatar | nein | Lokal aus dem Rufzeichen erzeugt (siehe unten) |
| Autor | ja, als Text | Im TBCHAT-Frame sendet die TinyBox, also muss der Autor in die Nutzdaten |
| Zeitstempel | nein | Empfangszeit; beim Verlauf aus der BBS liefert die TinyBox die Zeit (connected) |
| Sprechblasen links/rechts | nein | Eigene Beiträge rechts, fremde links |
| „Tippt gerade …“, Gelesen-Häkchen | **bewusst nicht** | Wären je ein Frame pro Teilnehmer |
| Bilder, Sticker, GIFs | nein | Nicht vorgesehen |
| Folgenummer | ja, 1–2 Zeichen | Lückenerkennung, `//RESEND`, Bezug für Reaktionen |

**Nutzdaten als lesbarer Text** (Frame-Schema in 12.4): Terminal-User und Mithörer verstehen den Chat weiterhin. CBOR würde nur 3–5 Byte pro Frame sparen, Kompression bringt unter ~80 Byte nichts.

```
UI an TBCHAT-1:   #4F OE3GAS: Servus, Wetter passt :+1 ~1K
```

**Emojis – nie als Unicode über Funk** (👍 = 4 Byte, mit Hautton 8, Familien-Sequenzen bis 18 Byte):

- **Stufe 1, klassische Emoticons (2–3 Byte):** `:)` `:(` `;)` `:D` `:P` `:O` `<3` `:+1` `:-1` … Der Client zeigt 😊 🙁 😉 😄 😛 😮 ❤️ 👍 👎. Terminal-User verstehen sie ohne Client.
- **Stufe 2, Code-Tabelle (3 Byte):** Escape-Zeichen + 2 Zeichen Base36, z. B. `~1K` = 📻; 1296 Plätze; `~~` = echte Tilde. Die Tabelle wird wie das brocast-Dictionary versioniert mit dem Client ausgeliefert. Grundstock funkerspezifisch (📻 📡 🔋 ⚡ ☕ 🍺 🌧 ☀️ 👋 …).
- Der Emoji-Picker bietet **nur** Emojis aus Stufe 1 und 2 an; jedes Emoji kostet damit höchstens 3 Byte. Ein eingefügtes unbekanntes Emoji wird nicht gesendet, der Client zeigt einen Hinweis.
- **Reaktionen** (👍 auf einen Beitrag, ab v1): eigener Typ mit Folgenummer + Emoji-Code, ca. 5 Byte Nutzdaten.

**Avatar – aus dem Rufzeichen, 0 Byte über Funk**

- Kreis mit **Präfix klein oben, Suffix groß darunter** (z. B. `OE3` / `GAS`). Im lokalen Chat haben fast alle dasselbe Präfix, unterscheidbar macht das Suffix.
- **Füllfarbe** aus einem Hash (FNV-1a) des Rufzeichens **ohne SSID und ohne /-Zusatz**, feste Palette mit 8 Farben, Schrift in der dunklen Stufe derselben Farbe. Jeder Client zeigt für jedes Rufzeichen dasselbe Bild. Kein Farbring.
- **APRS-Symbol als Plakette links oben** (frei wählbar): Über Funk geht wie bei APRS nur der 2-Zeichen-Code (z. B. `/-` Haus, `/>` Auto, `/y` Yagi, `/#` Digi). Herkunft in dieser Reihenfolge: eigene Wahl im Client → APRS-Bake, die der Client von diesem Rufzeichen gehört hat (0 Byte) → Code aus der Betreten-Meldung (2 Byte).
- Mit Plakette rückt das Präfix ca. 5 px nach rechts, **ohne Plakette steht es mittig**.
- Die SSID wird dadurch nützlich: OE3GAS (Haus) und OE3GAS-9 (Auto) haben dieselbe Farbe, aber verschiedene Symbole.
- Grafiken: aprs.fi-Symbolsatz von OH7LZB (github.com/hessu/aprs-symbols, PNG-Sprites 24/48/64/128 px), lokal im Client; Quellenhinweis auf der „Über“-Seite. Namen für die Auswahlliste aus dessen Symbol-Index (JSON).

**Entschieden (08.10.2026):** Escape-Zeichen für Stufe 2 ist `~`. Reaktionen kommen schon in v1.

### 12.6a Oberfläche am PC und Mailbox-Ansicht (entschieden 08.10.2026)

- **Eine Oberfläche, die nach Fensterbreite umschaltet:** ab ca. 1000 px drei Spalten, 700–1000 px zwei, darunter die Handy-Ansicht.
- **Links Navigation:** Chat-Boards mit Teilnehmerzahl, Post (Eingang, Ausgang, Gesendet), Bulletins nach Rubrik mit Zähler, Monitor, Einstellungen.
- **Chat am PC:** Mitte wie am Handy. Rechts die Teilnehmer im Board und die Stationen, deren APRS-Baken gehört wurden (mit „vor n min“).
- **Mailbox am PC:** Liste in der Mitte, Lesebereich rechts (Kopf mit Avatar, Von/An/Datum/Nummer, BID bei Bulletins; Text in Festbreitenschrift). Am Handy nacheinander: Ordner → Liste → Nachricht.
- **Offline (C3):** Knopf „Abgleichen“ mit Zeitpunkt des letzten Abgleichs; Gelesenes liegt lokal. Neue Nachrichten kommen in den **Ausgang** und gehen beim nächsten Abgleich hinaus, bis dahin bearbeitbar oder verwerfbar.
- **Abgleich:** Post immer vollständig; Bulletins nur aus abonnierten Rubriken (sonst dauert der Abgleich bei 1200 Bd zu lange).
- **Löschen:** eigene Post wird beim nächsten Abgleich auch in der TinyBox gelöscht; Bulletins nur lokal (sie gehören allen).

### 12.7 Später

Strukturierter Modus (CBOR statt Menütext), Formulare, kleine Dateien, Sysop-Fernverwaltung mit Challenge-Response (keine Verschlüsselung), Anzeige der Verbindungsqualität, zeitgesteuertes Abholen.

---

## 13. Forwarding-Modul (optional)

Ausführliches Konzept mit Protokollen, Routing, Testfällen und Quellen: Claude-Doc „Tinybox als Packet-Radio-BBS: Forwarding-Konzept“ (https://claude.ai/code/artifact/ed861fd0-7519-4796-8f4b-8de6ab3fbd2a). Hier nur der Überblick.

**Grundsatz:** Das Nachrichtenmodell (Adresse, BID, R:-Zeilen) gehört zum Kern, der Austausch ist ein abschaltbares Modul (`[forward] enabled`). Ohne Modul bleibt TinyBox eine Standalone-Mailbox, `@`-Adressen gibt es dann nur für Bulletins.

**Zielbild in drei Stufen:** Standalone → Empfänger (Leaf an einem Hub, Standardroute WW) → Forwarder (mehrere Partner).

- **Protokolle:** SID-Austausch, FBB-ASCII-Batch (`FB`, `F>`, `FS +-=`, `FF`/`FQ`) als Hauptprotokoll, MBL/RLI-ASCII nach der W0RLI-Spezifikation (12.10.1998, `docs/w0rli/`) als Rückfall, später FBB B1 (LZHUF). TinyBox kündigt `FH$` an, ohne `M`.
- **Transport:** AX.25 über Direwolf/AGW (annehmen und anrufen, auch über Digis) und transparentes TCP (z. B. LinBPQ FBBPORT). Eingehender TCP-Port mit `Callsign:`/`Password:`-Login, standardmäßig aus.
- **Routing (BPQ-Modell):** Persönliche Post an den Partner mit dem besten Treffer von rechts, Bulletins an alle Partner mit passendem Verteilgebiet (erstes Element des @-Feldes). Nie zurück an einen Partner aus den R:-Zeilen. Ohne Treffer Status `H`.
- **Duplikate:** Tabelle `bids` mit Aufbewahrung `bid_days`. Umgang mit bekannter BID/MID je nach SID der Gegenseite (Entscheidung 06.10.2026, siehe Konzept-Doc).
- **brocast:** Fremd-Bulletins gehen nur ins Karussell, wenn `[forward] publish_to_brocast = yes` (Standard `no`).
- **Sysop:** `FWD` (Partner anzeigen), `FWD call` (Forward anstoßen), `FWQ` (Warteschlange), `HOLD n` / `REL n` (Nachricht halten / freigeben). Die Web-GUI zeigt im Kopf „Forward: n queued · n held“, mit den Partnern als Tooltip.

**Stand der Meilensteine**

| # | Inhalt | Stand |
|---|---|---|
| F0 | Vorbereitung: PLANUNG Rev. 4, LinBPQ als Testpartner, Mitschnitte echter Sitzungen, Hub-Suche, Rechtsfrage, Test-Tool fwdsim | teilweise: fwdsim fertig, PLANUNG Rev. 4 erledigt (07.10.2026). Offen: LinBPQ, Mitschnitte, Hub, Rechtsfrage |
| F1 ✅ | Kern: Schema 5, `addressing.py`, `SP/SB … @ … $BID`, `LB`/`LP`/`L@`/`L>`/`L<`, Lesekopf mit BID und R:-Zeilen, `E n AT`, Halten bei Schleife oder zu alter Nachricht | Fertig 06.10.2026 |
| F2 ✅ | Modul-Gerüst: `tinybox/fwd/`, `adapters/forward.py`, `[partner.CALL]`, AGW- und TCP-Verbindungen in beide Richtungen, SID-Aushandlung, Warteschlange, `FWD`/`FWQ` | Fertig 06.10.2026, 144 Tests grün. Angebotenes wird noch zurückgestellt (`=` bzw. Trennen), damit nichts verloren geht |
| F3 ✅ | Empfänger: ASCII- und FBB-Empfang, R:-Zeilen, Loop-Erkennung, BID/MID-Regel, Partner-Whitelist, Grenzen, `publish_to_brocast` | Fertig 07.10.2026, 168 Tests grün |
| F4 ✅ | Forwarder: Senden, Reverse Forward, Routing-Feinschliff, Scheduler, Prompt-Skip je Partner, `HOLD`/`REL`, Web-Anzeige | Fertig 07.10.2026, 191 Tests grün |
| F5 ✅ | B1 komprimiert (LZHUF, Resume) | Fertig 08.10.2026, 204 Tests; B1 mit LinBPQ in beide Richtungen bestätigt |
| F6 | Anschluss ans Netz: Leaf an einem OE-Hub über TCP/HAMNET, Probebetrieb | **als Nächstes** (Hub-Partner nötig) |
| F7 (opt.) | Mehrere Partner, White Pages, MQTT und Forwarding gemeinsam, Doku für Partner-Sysops | offen |

**F3 im Detail (07.10.2026)**

- Neues Modul `tinybox/fwd/receive.py`: entscheidet je Angebot (`+`/`-` bzw. `OK`/`NO`) und speichert über den MessageService (Origin `forward`, eigene R:-Zeile oben, Schleife oder zu alt → `H`).
- Abgelehnt werden: Typ T (NTS) und unbekannte Typen, ungültige Calls oder Adressen, zu große Nachrichten (Größe aus dem Vorschlag), dieselbe BID zweimal im Block, bekannte BIDs. Ausnahme nach W0RLI: Eine bekannte MID persönlicher Post von einer ASCII-Gegenseite ohne `M` wird angenommen und für den Sysop gehalten.
- Gespeichert wird erst nach vollständigem Empfang (Ctrl-Z oder `/EX`); ein Abbruch mitten in der Nachricht hinterlässt nichts. `'/EX'` im Text wird wieder zu `/EX`.
- Ruft TinyBox selbst an, holt sie die Post des Partners in derselben Sitzung ab (FBB: eigenes `FF`, ASCII: `F>`).
- Ein empfangenes Bulletin, das kein weiterer Partner braucht, ist einfach lokal (nicht gehalten).
- Korrektur in AGW-Adapter und TCP-Link: Das CR nach Ctrl-Z erzeugt keine leere Zeile mehr (sonst wurde die leere Zeile als Betreff der nächsten Nachricht gelesen).
- Grenzen je Sitzung: höchstens 500 Nachrichten, Text höchstens doppelte `max_msg_bytes` plus 8 kB, sonst Trennen.

**F4 im Detail (07.10.2026)**

- Neues Modul `tinybox/fwd/send.py`: Warteschlange je Partner, FBB-Vorschläge (`FB`, max. 5 je Block, max. 10 kB), W0RLI-S-Befehle (`$BID` nur bei echten BIDs), Nachricht mit Betreff (max. 79 Zeichen), R:-Zeilen, Leerzeile, Text, Ctrl-Z; eine Textzeile `/EX` geht als `'/EX'`.
- Antworten: `+`/`Y`/`H` → `done`, `-`/`N`/`R`/`E` → `rejected` (Partner hat sie schon), `=`/`L` → `later`. Ist für eine Nachricht kein Partner mehr offen, bekommt sie `F`.
- Beide Richtungen in einer Sitzung: FBB abwechselnd blockweise; ASCII: der Anrufer sendet seine S-Befehle und holt dann mit `F>` ab, der Angerufene bedient `F>` mit seinen S-Befehlen.
- Routing: Bulletins für ein fremdes Gebiet (z. B. `@FRA.EU`) gehen gerichtet wie persönliche Post zum besten Partner, `WW` und die eigenen Gebiete werden geflutet.
- Zeitplan je Partner: `auto` (ruft an, wenn Post wartet; Standard bei TCP `yes`, bei Funk `no` wegen offener Punkt 7), `interval_min` (zusätzlich regelmäßig abholen), `window` (z. B. `22:00-06:00`), `retry_min` (Pause nach Fehler und für „later“). Der Planer schaut alle 30 s und 2 s nach neuer Post.
- Prompt-Falle (T20): TinyBox wartet nach dem Connect zuerst auf die SID, Knoten-Texte davor mit `>` stören nicht. Eine eigene Skip-Option je Partner war deshalb nicht nötig.
- Korrektur in fwdsim: auch dort erzeugte das CR nach Ctrl-Z eine leere Zeile (Betreff der zweiten Nachricht ging verloren).

**Gegentest mit LinBPQ 6.0.25.41 (08.10.2026)** – LinBPQ in WSL auf PC2, Test-TinyBox `test\bpq\`, Mitschnitte in `tests/fixtures/`

- ASCII nach W0RLI funktioniert in beide Richtungen (TinyBox sendet, TinyBox holt mit `F>` ab).
- LinBPQ sendet `F` in der SID nur mit „Allow Binary“ und überträgt dann **immer komprimiert**, auch wenn die Gegenseite kein `B` ankündigt. Unkomprimiertes FBB gibt es mit LinBPQ also nicht: Partner-Einstellung `protocol = b1` oder `ascii`.
- Eine Nachricht mit kaputter @-Adresse wird jetzt angenommen und gehalten statt abgelehnt (ein `-` hieße für den Absender „schon da“).
- **B1 (nach F5):** TinyBox ↔ LinBPQ komprimiert in beide Richtungen, sowohl wenn TinyBox anruft (FBBPORT 8011) als auch wenn LinBPQ anruft (Login am Forward-Port 6411). Titel und Text mit Umlauten kommen unverändert an. Damit sind die Tore von F3 und F4 über TCP erreicht; Funk (AGW zwischen PC1 und PC2) steht noch aus.

**F5 im Detail (08.10.2026)**

- `tinybox/fwd/lzhuf.py`: LZHUF in Python (FBB-Variante: 2-kB-Fenster, 60 Byte Vorschau), byte-identisch mit LinBPQs `lzhuf32.c` – geprüft gegen Testvektoren aus dem kompilierten C-Original (`tests/fixtures/lzhuf_vectors.json`). B1 = CRC-16 + Länge + Daten.
- `tinybox/fwd/b1.py`: Rahmen wie LinBPQ (SOH-Kopf mit Titel und Offset, STX-Blöcke à 250 Byte, EOT mit Prüfsumme); Text innen mit CR LF, R:-Zeilen vor dem Text.
- Link: ein Bytestrom, aus dem zeilenweise oder roh gelesen wird – kein Datenverlust beim Umschalten. AGW reicht Forward-Verbindungen die Rohbytes durch.
- Restart (B1): bricht eine Übertragung ab, hebt TinyBox das Empfangene auf (Tabelle `fwd_partial`, Schema 6, 2 Tage) und antwortet beim nächsten Angebot `!offset`; als Sender setzt TinyBox an diesem Offset fort. Nach 10 Versuchen wieder von vorn.
- SID mit `protocol = b1`: `[TINYBOX-…-B1FH$]`. B0 (Gegenseite nur `B`) ist eingebaut, aber ungetestet.
- Getestet: LZHUF gegen LinBPQ-C-Code, Rahmen, und Sitzungen TinyBox ↔ TinyBox in beide Richtungen inklusive Abbruch und Restart. fwdsim kann kein B1.

**Test-Tool fwdsim** (`fwdsim\`, Start mit `fwdsim.bat`, Bedienung in `fwdsim/README.md`): spielt die Partner OE3GAS (`#OOE`, Endstation und Hop) und DL0XTC (`#BAY`, nur über OE3GAS erreichbar, sendet nie auf Funk). TinyBox läuft im Test als OE3XTC (`#NOE`). Testfälle T01–T28 über TCP oder Direwolf, mit Fehlerinjektion. Gegen einen fwdsim-Stellvertreter laufen alle automatischen Fälle grün. Gegen die echte TinyBox (TCP) laufen seit F4 alle 24 automatischen Fälle grün (T01–T16, T18–T20, T24–T28); T21 (Neustart) ist als Unit-Test abgedeckt. Manuell offen: T17, T22, T23. Noch offen: fwdsim nimmt TCP-Anrufe ohne Login an.

---

## Quellen

- Forwarding-Konzept (Claude-Doc): https://claude.ai/code/artifact/ed861fd0-7519-4796-8f4b-8de6ab3fbd2a
- W0RLI-BBS-Spezifikation vom 12.10.1998: `docs/w0rli/w0rli-bbs-spec-12oct1998.pdf`
- AEA PK-232MBX Operating Manual, Kap. 5 (nur Orientierung): https://www.dl0bn.de/dc7xj/Anleitungen/AEA%20PK-232MBX_Manual.pdf
- Direwolf-Dokumentation (AGW-Interface): https://github.com/wb2osz/direwolf/tree/master/doc
