# TinyBox-Client – Change Requests

Gesammelt beim ersten Test PC1 ↔ PC2 (OE3GAS, OE3TEC) am 09.10.2026, ergänzt laufend.
Stand: 11.10.2026 (Abend)

## Übersicht

| CR | Inhalt | Status |
|---|---|---|
| 1 | Einzelnes Emoji als Nachricht groß anzeigen (≥ 2×) | ✅ (c376e16) |
| 2 | Emojis: 🤮 💩 ❓ ❗ und Pfeile dazu, 🗼 raus, Auswahl nach Gruppen sortiert | ✅ siehe unten |
| 3 | MOTD pro Board | offen – wer setzt sie (Sysop)? |
| 4 | Schrift: `_fett_` und Monospace für ASCII-Art | ✅ `_fett_`, `` `mono` `` (c376e16) |
| 5 | URLs erkennen und klickbar | ✅ (c376e16) |
| 6 | „Leave board“ im Chat statt in den Settings | ✅ (c376e16) |
| 7 | Bug: APRS-Symbol-Änderung wirkt erst nach Board-Wechsel – soll sofort wirken (Avatar-Update aller bleibt) | ✅ siehe unten |
| 8 | Eigene Reaktion sofort anzeigen | ✅ blass bis Echo, nach 2 min ohne Echo zurück (c376e16) |
| 9 | Zeilenumbruch mit Shift+Enter | offen – braucht Zeilenumbruch-Kodierung über Funk (Protokoll ist zeilenbasiert) |
| 10 | Mehrzeilige Texte einfügen | offen – wie CR9 |
| 11 | Sticker und Animationen | Sticker-Set fertig (20 Dateien), Einbau und Animationen offen – siehe unten |
| 12 | Konzept: kleine Bilder anhängen – Umsetzung, Maximalgröße, Binärübertragung (7PLUS?) | Konzept offen |
| 13 | History wählbar beim Einchecken („last n lines?“, Enter = keine) | ✅ siehe unten |
| 14 | Zitatfunktion (Nachricht antippen → Zitieren, gekürzt über der Antwort) | offen |
| 15 | @CALL hebt Nachricht beim Empfänger farbig hervor | ✅ (c376e16) |
| 16 | Anstupsen: Klick auf Call in Teilnehmerliste → kurze persönliche Nachricht als Pop-up mit Klingelton | offen – über Funk für Mithörer lesbar |
| 17 | „Cry out“: max. 32 Zeichen, sehr große Schrift in einer „Bang!“-Blase | ✅ siehe unten |
| 18 | Versionskontrolle: Client prüft, ob er aktuell ist; User wird informiert und aufgefordert, die neue Version zu holen | ✅ siehe unten |
| 19 | Rubriken sind Sysop-Sache: feste Rubrikenliste, User schreiben Bulletins nur an ALL und diese Rubriken (Auswahl im Composer), Forwarding nimmt nur diese Rubriken an | erfasst – noch nicht umgesetzt, siehe unten |
| 20 | Bulletins zwischen Rubriken verschieben und kopieren | Vorschlag – Entscheidungen offen, siehe unten |
| 20 | Verbindungsqualität: 1–5 Balken neben jeder Station im Board, Meldung bei Verbindungsabbruch, Befehl `STAT` | ✅ siehe unten |

## CR2 – Emojis (erledigt 11.10.2026)

- Neu in `emoji.json` (Version 2, angehängt): 🤮 `~1Q`, 💩 `~1R`, ❓ `~1S`, ❗ `~1T`, Pfeile ⬆️ ➡️ ⬇️ ⬅️ ↗️ ↘️ ↙️ ↖️ (`~1U` … `~21`).
- 🗼 (`~10`, der rote Turm) wird nicht mehr angeboten: Eintrag in `"hidden"`. Kommt der Code an, wird er weiter angezeigt – Codes ändern nie ihre Bedeutung.
- Die Auswahl ist nach Gruppen sortiert (`"picker"` in `emoji.json`): Gesichter, Hände & Herz, Zeichen & Pfeile, Funk & Technik, Wetter & Natur, Unterwegs, Essen & Feiern, Tiere & Sonstiges.

## CR7 – APRS-Symbol sofort (erledigt 11.10.2026)

- Ursache: Das Symbol ging nur beim Betreten eines Boards mit (`+CALL sym`); eine Änderung meldete der Client zwar der TinyBox, aber niemand gab sie an das Board weiter.
- Neu: Der Client sendet `//SYM <symbol>` (`-` = keins). Ist er in einem Board, bekommen alle Clients dort sofort das Ereignis `=CALL <symbol>` (bzw. `=CALL`), per UI-Frame ca. 12 Byte Nutzdaten. Alle Avatare dieser Station wechseln das Symbol. Terminal-Teilnehmer bekommen nichts.
- Außerhalb eines Boards wird das Symbol nur gemerkt und beim nächsten Betreten mitgeschickt. Gleiches Symbol noch einmal: kein Ereignis.
- Client-Version 2026.10.11.2. Tests in `tests/test_clientproto.py` und `tests/test_tbclient.py`; Praxistest mit TinyBox und zwei Clients.

## CR11 – Sticker und Animationen

### Grundsatz

- **Über Funk geht nur ein kurzer Code** (wie bei den Emojis, ca. 3 Byte), nie das Bild.
- **Die Bilder liegen fest im Client** und werden versioniert wie `emoji.json`. Ein neues Paket kommt mit einem neuen Client (Git); später ist auch die Verteilung über das brocast-Dictionary denkbar.
- **Start mit einer festen Auswahl**, dann schauen, wie sie genutzt wird.
- Offen: Format des Codes im Chattext (z. B. eigenes Escape-Zeichen) und wie Terminal-Teilnehmer ihn sehen.

### Quellen (Recherche 10.10.2026)

- Fertige, frei nutzbare **Funk-Sticker gibt es praktisch nicht**. Radioddity „Ramoji“ (6 animierte GIFs: CQCQ, QRL, Morse, Roger, Over, 73) ist „free to use“, aber © Radioddity ohne Lizenz – Weitergabe nur nach Rückfrage.
- Allgemeine Emojis mit offener Lizenz: **Noto Emoji Animation** (CC BY 4.0; Lottie/WebP/GIF), OpenMoji (CC BY-SA 4.0), Microsoft Fluent Emoji (MIT, statisch), Twemoji (CC BY 4.0). Quelle im Client-„About“ nennen.
- Erste Idee: Funk-Sticker selbst als SVG zeichnen. Ersetzt durch das von Gerhard gelieferte Set (siehe unten). Allgemeine Animationen weiter von Noto.

### Sticker-Set (initiales Set, 20 Stück, 11.10.2026)

Von Gerhard geliefert, einzeln freigestellt. Dateien: `tbclient/web/stickers/` (WebP mit Transparenz, je ca. 20–37 KB, zusammen ca. 0,5 MB). Übersicht: `docs/sticker-set.png`. Die gezeichneten SVG-Entwürfe vom 10.10. sind damit ersetzt (in der Git-Historie noch vorhanden).

| Nr. | Datei | Motiv |
|---|---|---|
| 1 | `01-cq.webp` | „CQ CQ CQ“, Mikrofon und Transceiver |
| 2 | `02-73.webp` | „73!“, OM mit Daumen hoch |
| 3 | `03-88.webp` | „88 ❤“, zwei Funker formen ein Herz |
| 4 | `04-qsl.webp` | „QSL? / QSL ✓“ mit QSL-Karten |
| 5 | `05-59plus20.webp` | „5/9+20“, jubelnder OM, Signalbalken |
| 6 | `06-qrm.webp` | „QRM!“, genervter OM |
| 7 | `07-qrt.webp` | „QRT – gute Nacht“, Shack bei Nacht, Katze |
| 8 | `08-qrz.webp` | „QRZ?“, OM mit Kopfhörer im Dunkeln |
| 9 | `09-widerstand.webp` | „Widerstand“, muskulöser Widerstand mit Sonnenbrille |
| 10 | `10-pileup.webp` | „PILEUP“, schreiende Menge |
| 11 | `11-magic-smoke.webp` | „Magic Smoke“, rauchendes Gerät |
| 12 | `12-swr-1-1.webp` | „SWR 1:1“, zufriedenes Messgerät |
| 13 | `13-swr-unendlich.webp` | „SWR ∞“, verzweifelter OM |
| 14 | `14-dummy-load.webp` | „Dummy Load“, cooler Kühlkörper |
| 15 | `15-band-offen.webp` | „Band offen!“, Erdkugel mit Verbindungen |
| 16 | `16-band-tot.webp` | „Band tot“, toter Planet |
| 17 | `17-bin-dxen.webp` | „Bin DXen“, Funken am Strand |
| 18 | `18-kaffee.webp` | „Kaffee im Shack“, Tasse „DX FUEL“ |
| 19 | `19-dipole.webp` | „All you need is a Dipole!“ |
| 20 | `20-antennenbau.webp` | „Bin am Antennenbauen“ |

- Offen: Einbau in den Client (Sticker-Auswahl, Anzeige), Code über Funk (Vorschlag: Escape + Nummer, z. B. `~$01`), Anzeige für Terminal-Teilnehmer (z. B. „[Sticker: CQ CQ CQ]“).

### Animationen (Vorschlag, 10 Stück – noch nicht entschieden)

| Nr. | Animation | Herkunft |
|---|---|---|
| 1 | Antenne strahlt Wellen ab (CQ) | selbst |
| 2 | Morsetaste klopft | selbst |
| 3 | S-Meter-Zeiger schnellt auf 9+ | selbst |
| 4 | Signal hüpft an der Ionosphäre (Skip) | selbst |
| 5 | Blitz schlägt in die Antenne | selbst |
| 6 | Satellit zieht vorbei (Pass) | selbst |
| 7 | 🎉 Konfetti (Erstverbindung, neues DXCC) | Noto |
| 8 | 😂 Lachen | Noto |
| 9 | 🔥 Feuer | Noto |
| 10 | 👋 Winken (Gruß, 73) | Noto |

- Offen: Auswahl bestätigen; Verfügbarkeit 7–10 in der Noto-Liste prüfen; Technik für eigene Animationen (animiertes SVG/CSS vs. Lottie).

## CR12 – Kleine Bilder anhängen (Konzept offen)

Zu klären: Umsetzung in Client und TinyBox, Maximalgröße, Binärübertragung (7PLUS oder andere).

## CR13 – History nur auf Wunsch (erledigt 11.10.2026)

- **Aufbewahrung** wie bisher pro Board in `tinybox.conf` `[chat_boards]` (Beispiel: TREFF 7d, DX 24h, TECH 30d, RUNDE live). `history_lines` (Standard 20) ist jetzt die **Höchstzahl pro Abruf**.
- **Vorher:** Beim Betreten kamen ungefragt die letzten 20 Zeilen (~800 Byte, 6–10 s Kanal bei 1200 Bd), auch wenn man sie schon kannte.
- **Terminal:** Beim Betreten nur noch
  `*** 37 lines stored. Last from 2026-10-09 12:33 UTC` und `*** /H n to read`. `/H n` zeigt die letzten n Zeilen, `/H` allein bleibt die Hilfe.
- **Client:** `//IN … hist=<Anzahl> last=<Zeit> now=<Zeit der TinyBox>`; die History holt er mit `//HIST max=<n> [since=<Zeit>] [before=<Zeit>]`, Antwort `//H …` + `//HEND <n> <ältere>` – nur an ihn, per I-Frame.
  - Einstellung **„Chat history“**: *Only what I missed (max. 20)* (Standard), *None*, *Last 10*, *Last 20*. „Verpasst“ = seit dem letzten Verlassen des Boards; die Zeit wird mit der Uhr der TinyBox gerechnet (`now=`), falsch gehende PC-Uhren stören nicht.
  - **Leiste oben im Chat:** „📜 37 older posts · load 10 · load all“ (all = höchstens `history_lines` pro Klick, die Leiste zeigt den Rest).
  - Zeitgrenzen sind inklusiv, doppelte Zeilen verwirft der Client – keine Zeile geht verloren, die Reihenfolge stimmt auch bei Zeilen aus derselben Sekunde.
- **Ältere Clients** (vor 2026.10.11.3) bekommen die History wie bisher beim Betreten.
- Client-Version 2026.10.11.3. Tests in `tests/test_chat.py`, `tests/test_clientproto.py`, `tests/test_tbclient.py`; Praxistest mit 25 Zeilen (Client und Terminal).

## CR17 – „Cry out“ (erledigt 11.10.2026)

- Ein Beitrag mit höchstens **32 Zeichen** wird in **sehr großer Schrift** (Großbuchstaben, Comic-Stil) in einer gelb-roten **„Bang!“-Blase** angezeigt, leicht schräg.
- **Über Funk:** nur zwei Zeichen `~!` vor dem Text, z. B. `~!PILEUP!` (9 Byte). `~!` ist frei, weil eine echte Tilde als `~~` gesendet wird. Terminal-Teilnehmer sehen `~!PILEUP!`.
- **Eingabe:** Knopf 💥 neben dem Emoji-Knopf schaltet den Cry-out-Modus ein (Feld auf 32 Zeichen begrenzt, Zähler im Hinweis), nach dem Senden wieder aus.
- **Schriftgröße** passt sich an: kurze Texte 36 px, längere 28 bzw. 23 px; Wörter werden nicht mitten drin getrennt.
- Status: von Gerhard freigegeben und eingebaut; getestet mit TinyBox + zwei Clients (PC- und Handy-Ansicht).

## CR18 – Versionskontrolle (erledigt 11.10.2026)

Entscheidungen: Version automatisch aus dem Repo, Feature-Beschreibung als festes Bulletin, Versionsnummer = Datum.

- **Version = Datum:** `tbclient/__init__.py` `VERSION = "2026.10.11"`. **Regel: bei jeder Änderung am Client erhöhen** (gleicher Tag noch einmal: `2026.10.11.2`).
- **Handshake:** Client sendet `//CLIENT TB1 v=2026.10.11 caps=…`. Die TinyBox liest die aktuelle Version selbst aus `tbclient/__init__.py` (gleiches Repo: nach `git pull` sofort aktuell, auch ohne Neustart). Ist der Client älter (oder ohne `v=`), antwortet sie `//OK TB1 caps=… cur=2026.10.11 news=<Nr.>`.
- **Feature-Bulletin:** Text in `tbclient/FEATURES.txt` (ASCII, ohne Emojis, damit ihn auch Terminal-Teilnehmer lesen). Die TinyBox legt ihn beim Start als Bulletin an die Rubrik **TBNEWS** („TinyBox News“) an. Feste Bulletins (`fixed:…`) laufen nie nach Alter ab. Ändert sich der Text, bekommt das Bulletin eine neue Nummer, damit die Clients es neu holen. **Bei neuen Funktionen auch FEATURES.txt ergänzen.**
- **Hinweis im Client:** gelbes Banner „New client version … available (you have …). Get it with git pull and restart the client.“ mit Knopf **„Read about new features“**: abonniert TBNEWS, gleicht die Bulletins ab und öffnet das Feature-Bulletin. Wegklicken gilt bis zur nächsten Version; der Hinweis bleibt auch nach Trennen/Neustart des Clients.
- **Seite veraltet:** Wurde der Client aktualisiert, die Seite im Browser ist aber noch alt, zeigt sie „The client was updated … – reload the page“ mit Knopf „Reload page“.
- **Unbekannte Emoji-Codes** (von einem neueren Client) erscheinen als `[?]` statt als Rohcode.
- Tests: `tests/test_clientnews.py`; Praxistest mit TinyBox, aktuellem und altem Client (PC und Handy).

## CR19 – Rubriken sind Sysop-Sache (erfasst 11.10.2026, noch nicht umgesetzt)

**Heute:** Es gibt keine Rubrikenliste. Eine Rubrik entsteht mit dem ersten Bulletin an sie (Empfängerfeld, 1–6 Zeichen) – von Usern, per Forwarding, Skript oder Sysop – und verschwindet mit dem letzten. Tippfehler erzeugen eigene Rubriken, Beschreibungen gibt es nicht.

**Gewünscht (Gerhard):**
- Rubriken legt **nur der Sysop** fest.
- **Forwarding:** Bulletins von Partner-Mailboxen kommen **nur in den freigegebenen Rubriken** in die Box, alles andere nicht automatisch.
- **User** schreiben Bulletins **nur an ALL und die freigegebenen Rubriken**.
- **Bulletin-Composer im Client:** Auswahl der Rubrik (statt freiem Feld).

**Entscheidungen (11.10.2026):**
- Skripte (Eingangsordner, z. B. GeoSphere) und MQTT schreiben nur an Rubriken aus der Liste; der Sysop ist frei.
- **Neue Rubriken aus dem Forwarding** werden nicht angelegt, sondern kommen als **Mail an den Sysop**; er entscheidet und trägt sie in `tinybox.conf` ein – als angenommen oder als abgelehnt.
- Die Liste gilt vorerst **nur für den Rubriknamen**, nicht für das Verteilgebiet (`@WW`, `@OE` …) – Forwarding über Funk gibt es in OE/DL derzeit kaum.

**Syntax in `tinybox.conf` (Vorschlag):**

```
[rubrics]
# Bulletin rubrics, set by the sysop. One line per rubric:
#   NAME = description      accepted: users may write, forwarding is taken
#   NAME = - [note]         refused: forwarding is declined, no sysop mail
# NAME: 1-6 letters/digits. ALL is always accepted. Order = order in the client.
ALL    = To everybody
WX     = Weather and warnings
AMSAT  = Amateur radio satellites
KEPLER = Satellite orbit data
CONTEST= Contests, results
FLOHMA = Buy, sell, swap
HUMOR  = -  not wanted here
```

**Ablauf beim Forwarding:**
- Rubrik **angenommen** → Bulletin wird angenommen (FBB „+“) und gespeichert.
- Rubrik **abgelehnt** → Vorschlag wird abgelehnt (FBB „-“), der Partner bietet ihn nicht mehr an.
- Rubrik **unbekannt** → das **erste** Bulletin wird angenommen, aber **nicht als Bulletin** gespeichert, sondern als **persönliche Mail an den Sysop**: „Neue Rubrik XYZ, angeboten von PARTNER“ mit Betreff und Text des Bulletins und dem Hinweis, wie man sie in `[rubrics]` annimmt oder ablehnt. Weitere Bulletins derselben Rubrik werden zurückgestellt (FBB „=“ = später), bis der Sysop entschieden hat – so geht nichts verloren und es kommt nur eine Mail pro Rubrik.
- Nach dem Eintrag in `tinybox.conf` (und Neustart) gilt die Entscheidung; zurückgestellte Bulletins kommen beim nächsten Forward-Lauf herein bzw. werden abgelehnt.

**Weitere Umsetzung:**
- **Terminal:** Bulletin an eine nicht angenommene Rubrik → Fehlermeldung mit der Liste der erlaubten Rubriken.
- **Client:** `//RUBRICS` liefert auch die angenommenen Rubriken ohne Bulletins und ihre Beschreibung (z. B. `//RU WX 0 0 Weather and warnings`). Der Composer zeigt beim Typ *Bulletin* eine Auswahlliste („ALL – To everybody“, „WX – Weather …“); die Rubrikenliste zum Abonnieren zeigt die Beschreibungen.
- **Bestehende Bulletins** in nicht angenommenen Rubriken bleiben bis zum Ablauf.
- **TBNEWS** („TinyBox News“, Feature-Bulletin aus CR18) ist eine System-Rubrik: immer vorhanden, muss nicht in `[rubrics]` stehen, User können dort nicht schreiben, Forwarding nimmt sie nicht an.

**Übliche PR-Rubriken (Recherche 11.10.2026)** – neben ALL und DX. Englische Bezeichnungen aus US-/internationalen Boxen (FBB, BPQ) sind belegt; die deutschsprachigen Namen stammen aus der Praxis der DL/OE-Boxen (OpenBCM/FBB) und sind nicht online belegt, bitte gegen die Rubriken der Partnerboxen prüfen:

| Rubrik | Inhalt | Herkunft |
|---|---|---|
| AMSAT | Amateurfunk-Satelliten, AMSAT-Nachrichten | international (belegt) |
| KEPS / KEPLER | Bahndaten (Keplerelemente) der Satelliten | international / DL |
| PACKET | Packet Radio, Netz, Software | international (belegt) |
| SWOP / SALE / FLOHMA | Verkauf, Tausch, Suche („Flohmarkt“) | US (belegt) / DL |
| QST | Nachrichten an alle Funkamateure, Verbände (ARRL) | US (belegt) |
| ARES / NOTFUNK | Notfunk | US (belegt) / OE |
| WX / WETTER | Wetter und Wetterwarnungen | international / DL |
| PROPAG | Ausbreitung, Sonnenaktivität | international |
| CONTEST | Contest-Ankündigungen und -Ergebnisse | international |
| DXNEWS | DX-Meldungen, DXpeditionen (oft neben DX) | DL |
| APRS | APRS | international |
| ATV | Amateurfunk-Fernsehen | DL |
| TECHNIK / ANTENNE | Technik, Selbstbau, Antennen | DL |
| LINUX | Linux im Amateurfunk | DL |
| HUMOR | Witze, Funkerhumor | DL |
| QSL | QSL-Karten, -Büro | DL |
| RUNDSP | Rundsprüche (DARC/ÖVSV) | DL/OE |
| (Verband/Region) | z. B. Landesverband, Ortsstelle | OE |

Quellen: [Introduction to Packet Radio (ZL1RAH)](https://www.qsl.net/zl1rah/about_packet.htm) (ALL, QST, ARES, USERS, SWOP, AMSAT, PACKET, Verteilgebiete), [Packet Radio FAQ](https://papperlan.duckdns.org/textfiles.com/internet/FAQ/faq-pktr.txt) (ARRL-, AMSAT- und Ausbreitungs-Bulletins), [FBB (Wikipedia)](https://en.wikipedia.org/wiki/FBB_(software)).

## CR20 – Verbindungsqualität (erledigt 11.10.2026)

Konzept und Entscheidungen: PLANUNG.md Abschnitt 14. Commits 6b379e8 (Abfrage, Balken, `STAT`) und 1f3312c (Client, Empfangsquote, Abbruch).

- Eigener Direwolf-Fork `oe3gas/direwolf-tinybox` (Zweig `tinybox`) zählt pro Verbindung Wiederholungen, REJ, T1-Abläufe usw.; TinyBox fragt sie alle 30 s über die neue AGW-Abfrage `Q` ab.
- Bewertung: letzte 50 Frames pro Richtung, höchstens 30 Minuten; die schlechtere Richtung gibt die Balken, jeder T1-Ablauf kostet einen Balken; unter 20 Frames grau.
- Für Clients im UI-Modus zählt zusätzlich die Empfangsquote der TBCHAT-Frames (aus `//RESEND` und neuem `//LOST`) – damit gibt es Balken auch ohne Fork-Direwolf.
- Client: Balken rechts in der Teilnehmerliste (grün 4–5, gelb 3, rot 1–2, grau = noch keine Daten), über das Chat-Ereignis `%`; bei Abbruch die Zeile „Connection to … lost“.
- Terminal: `STAT` (eigene Verbindung) und `STAT ALL` (alle) als Text.
- Client-Version 2026.10.11.4.

## CR20 – Bulletins verschieben und kopieren (Vorschlag 11.10.2026, noch nicht umgesetzt)

**Heute:** Der Sysop kann mit `E <Nr> TO <Rubrik>` (Terminal) bzw. „edit“ in der Sysop-Weboberfläche den Empfänger eines Bulletins ändern – das ist ein Verschieben, aber: die Nummer bleibt gleich, deshalb merken die Clients nichts davon (ihr Abgleich holt nur Nummern, die größer sind als die höchste bekannte der Rubrik). Kopieren gibt es nicht.

**Vorschlag:**
- **Wer:** nur der Sysop (Rubriken sind Sysop-Sache, CR19). Ziel muss eine angenommene Rubrik aus `[rubrics]` sein.
- **Terminal (Sysop):**
  - `MOVE <Nr>[,<Nr>…] <Rubrik>` – verschiebt, z. B. `MOVE 12,15 WX`
  - `COPY <Nr>[,<Nr>…] <Rubrik>` – legt eine Kopie in der Ziel-Rubrik an
- **Sysop-Weboberfläche der TinyBox:** in der Nachrichtenliste Mehrfachauswahl + Knöpfe „Move to…“ / „Copy to…“ mit Auswahlliste der Rubriken.
- **Client:** dieselben Knöpfe im Bulletin-Leser, aber nur, wenn die TinyBox der Sitzung Sysop-Rechte gibt (lokal, `sysop_via_radio = no` bleibt).
- **Verschieben:** Das Bulletin behält Text, Absender, Datum und BID und bekommt die neue Rubrik. Damit die Clients es mitbekommen, führt die TinyBox ein kleines Verschiebe-Protokoll (alte Nr. → neue Rubrik, Zeit). Beim nächsten Bulletin-Abgleich bekommt der Client eine Zeile `//MV <Nr> <Rubrik>` und hängt sein lokales Exemplar um – **der Text wird nicht noch einmal übertragen** (kanalschonend). Clients, die die neue Rubrik nicht abonniert haben, entfernen es.
- **Kopieren:** neues Bulletin mit neuer Nummer und eigener BID in der Ziel-Rubrik, Text/Absender/Datum wie das Original, Vermerk „copied from <Rubrik> #<Nr>“ in der ersten Zeile. Wer die Ziel-Rubrik abonniert hat, bekommt es beim nächsten Abgleich wie ein neues Bulletin.
- **Forwarding:** Verschieben und Kopieren wirken **nur lokal**; nichts wird erneut an Partner-Mailboxen geschickt (die Kopie bekommt keinen Forward-Status).
- **Protokoll:** jede Aktion im Log („sysop moved #12 ALL -> WX“).

**Entscheidungen (11.10.2026):**
1. Nur der Sysop, nicht der Autor.
2. Wo: offen, bis geklärt ist, wie Sysop-Rechte im Client funktionieren (siehe unten).
3. Eine Kopie übernimmt die Ablaufzeit des Originals.

**Sysop-Rechte im Client (Vorschlag):**
- **Lokal (Client auf dem TinyBox-PC, `link = telnet`):** schon heute bekommt eine Telnet-Sitzung mit dem Sysop-Rufzeichen Sysop-Rechte (der Testport hört nur auf 127.0.0.1). Die TinyBox meldet das im Handshake (`//OK … sysop=1`), der Client zeigt dann die Sysop-Knöpfe.
- **Über Funk:** Rufzeichen sind nicht authentisch (`sysop_via_radio = no`). Neu: Anmeldung mit **Challenge-Response** wie Winlink „Secure Login“: Die TinyBox schickt eine Zufallszahl, der Client antwortet mit einem daraus und einem geheimen Sysop-Passwort berechneten Code (HMAC). Das Passwort geht nie über Funk, ein mitgehörter Code nützt beim nächsten Mal nichts. Der Inhalt bleibt Klartext – es wird nur angemeldet, nichts verschlüsselt.
  - `tinybox.conf`: `sysop_via_radio = auth`, `sysop_secret = …`; `tbclient.conf` bzw. Client-Einstellung: dasselbe Passwort, nur lokal gespeichert.
  - Befehle: `//SYSOP` → `//CHAL <zufall>` → `//SYSOP <code>` → `//OK sysop=1` bzw. `//ERR sysop`.
- **Sysop-Weboberfläche der TinyBox** (Port 8080, mit Login-Link) bleibt der Weg für die Verwaltung am TinyBox-PC.

