# TinyBox-Client – Change Requests

Gesammelt beim ersten Test PC1 ↔ PC2 (OE3GAS, OE3TEC) am 09.10.2026, ergänzt laufend.
Stand: 12.10.2026 (CR26–CR29 und CR12 umgesetzt)

## Übersicht

| CR | Inhalt | Status |
|---|---|---|
| 1 | Einzelnes Emoji als Nachricht groß anzeigen (≥ 2×) | ✅ (c376e16) |
| 2 | Emojis: 🤮 💩 ❓ ❗ und Pfeile dazu, 🗼 raus, Auswahl nach Gruppen sortiert | ✅ siehe unten |
| 3 | MOTD pro Board | ✅ siehe unten |
| 4 | Schrift: `_fett_` und Monospace für ASCII-Art | ✅ `_fett_`, `` `mono` `` (c376e16) |
| 5 | URLs erkennen und klickbar | ✅ (c376e16) |
| 6 | „Leave board“ im Chat statt in den Settings | ✅ (c376e16) |
| 7 | Bug: APRS-Symbol-Änderung wirkt erst nach Board-Wechsel – soll sofort wirken (Avatar-Update aller bleibt) | ✅ siehe unten |
| 8 | Eigene Reaktion sofort anzeigen | ✅ blass bis Echo, nach 2 min ohne Echo zurück (c376e16) |
| 9 | Zeilenumbruch mit Shift+Enter | offen – braucht Zeilenumbruch-Kodierung über Funk (Protokoll ist zeilenbasiert) |
| 10 | Mehrzeilige Texte einfügen | offen – wie CR9 |
| 11 | Sticker und Animationen | Sticker ✅ (Animationen offen) – siehe unten |
| 12 | Kleine Bilder im Chat (Verkleinern im Browser, BlurHash-Vorschau, Laden beim Antippen) | ✅ siehe unten |
| 13 | History wählbar beim Einchecken („last n lines?“, Enter = keine) | ✅ siehe unten |
| 14 | Zitatfunktion (Nachricht antippen → Zitieren, gekürzt über der Antwort) | ✅ siehe unten |
| 15 | @CALL hebt Nachricht beim Empfänger farbig hervor | ✅ (c376e16) |
| 16 | Anstupsen: Klick auf Call in Teilnehmerliste → kurze persönliche Nachricht als Pop-up mit Klingelton | offen – über Funk für Mithörer lesbar |
| 17 | „Cry out“: max. 32 Zeichen, sehr große Schrift in einer „Bang!“-Blase | ✅ siehe unten |
| 18 | Versionskontrolle: Client prüft, ob er aktuell ist; User wird informiert und aufgefordert, die neue Version zu holen | ✅ siehe unten |
| 19 | Rubriken sind Sysop-Sache: feste Rubrikenliste, User schreiben Bulletins nur an ALL und diese Rubriken (Auswahl im Composer), Forwarding nimmt nur diese Rubriken an | ✅ siehe unten |
| 20 | Verbindungsqualität: 1–5 Balken neben jeder Station im Board, Meldung bei Verbindungsabbruch, Befehl `STAT` | ✅ siehe unten |
| 21 | Bulletins zwischen Rubriken verschieben und kopieren | Entschieden: nur Sysop, nur Sysop-Konsole und Sysop-Weboberfläche – noch nicht umgesetzt |
| 22 | Sysop-Konsole: Befehl RESTART (Neustart, z. B. nach Änderung in tinybox.conf) | ✅ siehe unten |
| 23 | BUG – Emoji-Picker: Schnellauswahl-Leiste verdeckt die Gesamtauswahl | ✅ siehe unten |
| 24 | BUG – Schnellauswahl-Leiste ragt in der PC-Ansicht rechts aus der Chat-Spalte | ✅ siehe unten |
| 25 | Board antippen: Button einfärben, bis man im Board angekommen ist | ✅ siehe unten |
| 26 | Delta-Abgleich: Mail-/Bulletin-Sync mit minimaler Payload (ein Wechsel, nur Änderungen, kleine Texte gleich mit, Z für Köpfe) | ✅ siehe unten |
| 27 | Persönliche Post an mehrere Empfänger (`OE3TEC,OE1ABC`): Text einmal über Funk, TinyBox legt je Empfänger eine eigene Nachricht an | ✅ siehe unten |
| 28 | Emoticons ↔ Emojis: `;-)` beim Tippen sofort als Emoji, Terminal-Eingabe `;-)` im Client als Emoji, Emojis mit ASCII-Form gehen als `:-)` statt `~0B` über Funk | ✅ siehe unten |
| 29 | Terminal: Ausgaben über 10 Zeilen seitenweise mit „continue/abort“ (`L` und jeder andere Befehl), damit nicht hunderte Titel über die Luft laufen | ✅ siehe unten |
| 30 | Bild-Upload eines Teilnehmers sichtbar machen: „OE1ABC uploading picture“ mit Fortschrittsbalken | ✅ siehe unten |
| 31 | Kommentarbezug eindeutig machen (bisher Rufzeichen + Minute, mehrdeutig) | ✅ siehe unten |

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

- **Entschieden (11.10.2026):** Jeder Sticker hat einen **Kurznamen mit höchstens 4 Zeichen** (Buchstaben/Ziffern, Varianten mit Ziffer: CQ1, CQ2, SWR1, SWR2). Terminal-Teilnehmer sehen **`[STK]CQ`**.
- Vorschlag zur Umsetzung: über Funk geht genau dieser Text `[STK]CQ` als ganzer Beitrag (7–9 Byte). Damit braucht es keine Umsetzung für Terminal-Teilnehmer, und sie können selbst Sticker senden, indem sie `[STK]CQ` tippen.
- Kurznamen (von Gerhard bestätigt 11.10.2026): 01 CQ, 02 73, 03 88, 04 QSL, 05 S9P, 06 QRM, 07 QRT, 08 QRZ, 09 OHM, 10 PILE, 11 SMOK, 12 SWR1, 13 SWR2, 14 DUMY, 15 OPEN, 16 DEAD, 17 DX, 18 COFE, 19 DIPO, 20 ANT. Liste: `tbclient/web/stickers/stickers.json` – Namen ändern nie ihre Bedeutung, neue nur anhängen.

### Umsetzung Sticker (✅ 11.10.2026)

- **Über Funk** genau `[STK]CQ` als ganzer Beitrag (7–9 Byte), auch mit Zitat davor (`~^OE3TEC 1402 [STK]73`). Terminal-Teilnehmer sehen `[STK]CQ` und können Sticker so auch selbst senden.
- **Client:** Knopf 🏷️ neben dem Emoji-Knopf öffnet die Sticker-Auswahl, Antippen sendet sofort. Anzeige ohne Sprechblase, ca. 128 px; Reaktionen und Zitieren gehen wie bei Text. Unbekannter Name (neuerer Client) → der Text `[STK]XYZ`.
- Client-Version 2026.10.11.9.

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

## CR12 – Kleine Bilder im Chat (Konzept 11.10.2026, ✅ 12.10.2026)

### Entscheidungen (Gerhard, 11.10.2026)

1. **Nur Chat.** Binär-Anhänge in Mails werden später extra betrachtet (dann prüfen, was LinBPQ/FBB heute statt 7PLUS können, z. B. Winlink B2F-Anhänge bei LinBPQ, `#BIN#` bei FBB).
2. **Maximalgröße** mit Standardwert (Vorschlag 8 KB), vom Sysop einstellbar. Der User sieht **vor dem Hochladen**, wie lange Upload und Download dauern, und entscheidet selbst.
3. **Vorschau = BlurHash** (unscharfe Farbvorschau, ca. 20–30 Zeichen).
4. **Upload-Dialog ohne Vorschau:** Bild wählen → Hinweis „Das Bild wird auf kleine Größe reduziert: ca. 5,1 KB, Upload ca. 1 min, Laden für andere ca. 1 min (1200 Bd)“ → **OK** oder **Abbruch**.
5. **Aufbewahrung wie die History des Boards.** Auch beim Laden der History kommt nur der Verweis mit BlurHash; das Bild holt man mit Antippen. Unter dem BlurHash steht die Ladezeit – über Funk geht dafür nur die Größe, die Zeit rechnet der Client selbst aus.

### Grundsätze

- **Kompression = Bildformat, nicht LZHUF.** WebP (bzw. JPEG als Rückfall) ist schon komprimiert, LZHUF bringt darauf nichts. Gespart wird mit Auflösung (z. B. 320 px an der langen Seite) und Qualität. Der Browser macht das selbst (`canvas.toBlob("image/webp", q)`): er verkleinert und senkt die Qualität schrittweise, bis das Bild unter die Maximalgröße passt.
- **Kein 7PLUS** zwischen Client und TinyBox: AX.25 connected ist 8-Bit-transparent und gesichert (CRC + Wiederholung). Übertragen wird binär in Stücken mit Offset wie beim Mail-Abgleich (`//PART`), ein abgebrochener Transfer setzt fort.
- **Über Funk im Chat nur der Verweis**, nie das Bild. Wer es sehen will, holt es per I-Frame bei der TinyBox.
- **TinyBox dekodiert keine Bilder:** sie speichert einen Blob unter seinem Hash, prüft nur Größe und Dateikennung (WebP/JPEG). Gleiches Bild = ein Exemplar.

### Ablauf (Vorschlag, Details bei der Umsetzung)

- **Chat-Beitrag** mit Bild: Escape `~#` + Kennung + Größe + Seitenverhältnis + BlurHash, z. B.
  `~#3fa9c2d1 5120 4x3 LEHV6nWB2yk8pyo0adR*.7kCMdnj` (ca. 45 Byte). Optional danach Text als Bildunterschrift.
- **Hochladen:** Client sendet `//IMGPUT <hash> <größe>` und die Daten in Stücken (z. B. 256 Byte, mit Pausen, damit Chat-Zeilen dazwischen durchkommen); TinyBox antwortet `//IMGOK` bzw. `//ERR img too_large`. Erst dann geht der Chat-Beitrag hinaus.
- **Laden:** Antippen → `//IMG <hash> <offset> <länge>` → Antwort wie `//P` (binär). Der Client merkt sich geladene Bilder.
- **Anzeige:** BlurHash im richtigen Seitenverhältnis mit „🖼 5,1 KB · ca. 1 min · antippen zum Laden“, nach dem Laden das Bild in der Bubble. Die Ladezeit schätzt der Client aus Größe und Link (Baudrate bzw. gemessene Rate beim Abgleich).
- **Terminal-Teilnehmer** sehen z. B. `[Bild 5,1 KB – nur im TinyBox-Client]`.
- **Aufbewahrung:** Ein Bild wird gelöscht, wenn keine Chat-Zeile in der History es mehr verwendet.

### Weitere Entscheidungen (Gerhard, 11.10.2026)

- **Live-Boards** (`live`, z. B. RUNDE): **keine Bilder.**
- **Maximalgröße:** Standard 8 KB, in `tinybox.conf` `[chat]` `image_max = 8k`.
- **Abschaltbar durch den Sysop** pro Board in der `tinybox.conf` (Vorschlag: Zusatz in `[chat_boards]`, z. B. `TECH = 30d  Technical questions  noimg`, oder eigener Schlüssel – bei der Umsetzung festlegen). Der Client zeigt den Bild-Knopf nur in Boards, die Bilder erlauben (kommt mit der Board-Liste).
- **Ladefortschritt** im Chat anzeigen: beim Hochladen in der eigenen Bubble, beim Laden über dem BlurHash (Balken + „2,3 / 5,1 KB“). Möglich, weil in Stücken übertragen wird.

### Umsetzung (✅ 12.10.2026) – Payload nochmals durchgesehen (Gerhard, 12.10.2026)

Vor dem Codieren wurde jedes Feld, das über die Luft geht, auf Bytes geprüft. Abweichungen vom Ablauf-Vorschlag oben:

- **Verweis:** `~#` + Hash **6 Hex** + Größe **2 Hex in 64-Byte-Schritten** + BlurHash, **ohne Trennzeichen** (Hash und Größe sind fix lang, der BlurHash beschreibt seine Länge selbst) → **26–32 Byte** statt ~48. Beispiel: `~#a1b2c350BjElSA|nsR,x$0n~ Blick vom Berg`.
- **Bildmaße gehen nicht über Funk.** Kein fester Rahmen: Form und Seitenverhältnis bleiben, der Client formt den Platzhalter aus den BlurHash-Komponenten (3×2 quer, 2×3 hoch, 3×3 quadratisch), die Pixel kommen mit dem Bild. Der Browser verkleinert auf höchstens 320 px lange Seite und senkt dann Qualität/Auflösung, bis es unter das Limit passt.
- **BlurHash 16–22 Zeichen** (3×2 / 2×3 / 3×3) statt 28.
- **Kein Stückeln, kein Ack:** AX.25 ist gesichert. Upload `//IMGPUT <hash> <bytes>` → `//IMGGO <hash> <have>` → Bytes am Stück → `//IMGOK`; Download `//IMG <hash> [<offset>]` → `//I <hash> <offset> <total>` + Bytes am Stück. Overhead je ≈ 35–55 Byte statt 8–18 %. Der Client gibt die Bytes stückweise mit Pause an Direwolf (`tbclient.conf [images]`) und wartet, bis das Stück davor gesendet ist (AGW `Y`) – kostet keine Luft. Fortschritt: beim Hochladen aus den übergebenen Stücken, beim Laden aus den eintreffenden Bytes.
- **Erlaubnis** kommt beim Betreten (`//IN … img`, 4 Byte), nicht in der Board-Liste (`//B` ließe sich nicht erweitern, ohne alte Clients zu brechen). Abschalten pro Board: `noimg` direkt nach der Aufbewahrung (`TECH = 30d noimg Technical questions`).
- Terminal-Teilnehmer lesen `[Image 5.0 KB - TinyBox client only]` (auch `/H`-Verlauf und Reaktionsziel). Bilder nur über Funk (AGW) wie Cap Z; Cap `IMG`.
- Dateien: `tinybox/chatimg.py` (Protokoll, Referenz, Prüfung, Purge), `tbclient/images.py` (Transfer, Ablage `data/tbclient/images/`), BlurHash-Encoder/-Decoder in `app.js`. Protokoll ausführlich in `PLANUNG.md` 12.10.

### Fehler beim ersten Funktest und Behebung (✅ 12.10.2026, Client 2026.10.12.9)

Beim ersten Bild über Funk kamen die letzten Bytes nicht an: der Upload meldete „damaged on the way", und der Rest des Bildes stand als Zeichenmüll im Chat (und ging als Chat-Beitrag an alle).

**Ursache:** Der Client gibt die Bildbytes absichtlich in Häppchen mit Pausen an Direwolf. In diesen Pausen konnte jede andere Zeile dazwischenrutschen – getippter Text, eine Reaktion, vor allem das automatische `//RESEND`/`//LOST` der Lückenerkennung. Die TinyBox nimmt nach `//IMGPUT` aber **alles** als Bilddaten, zählte die Zeile mit, war zu früh „fertig" – und las die letzten echten Bildbytes als Chat-Zeile. Der Hash stimmte folglich nicht.

**Behoben in drei Schritten:**
- **Client:** Sendesperre von `//IMGPUT` bis zum letzten Byte (`ClientCore.hold_lines`). Zurückgehaltene Zeilen gehen danach in der getippten Reihenfolge hinaus; bricht die Verbindung ab, werden sie verworfen. Ein laufender Mailbox-Abgleich blockiert den Upload weiterhin (und umgekehrt), nach 10 Minuten Wartezeit mit Fehlermeldung statt Senden.
- **TinyBox:** Zeitlimit für den Rohmodus (`chatimg.RAW_TIMEOUT`, 120 s ohne Byte, geprüft im Idle-Watchdog des AGW-Adapters). Die Sitzung liest wieder Zeilen, meldet `//ERR img timeout <bytes>`, und das bereits Empfangene bleibt erhalten – das nächste `//IMGPUT` setzt dort fort.
- **TinyBox:** Chat-Zeilen mit Steuerzeichen (C0 außer Tab/Ctrl-Z, oder über 20 % C1-Zeichen) werden verworfen und nur geloggt. So geht im Fehlerfall nie wieder Binärmüll über Funk an alle Teilnehmer.
- **Client:** Nach einem fehlgeschlagenen Upload gibt es „Try again" (das verkleinerte Bild liegt noch im Client) neben „Discard".

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
- **News-Bulletins (inkrementell, ab 11.10.2026 abends):** Pro Client-Version eine kurze Datei `tbclient/news/<Version>.txt` (ASCII, ohne Emojis, nur Stichworte – geht über Funk). Die TinyBox legt jede beim Start als eigenes Bulletin „Client <Version>“ an die Rubrik **TBNEWS**; die Clients holen nur die neuen. Es bleiben die letzten 10 Versionen, ältere Dateien kann man löschen. Ändert sich ein Text, bekommt das Bulletin eine neue Nummer. `tbclient/FEATURES.txt` ist nur noch die Übersicht im Repo und wird nicht gesendet (das frühere große Feature-Bulletin wird beim Start gelöscht). **Bei jeder neuen Client-Version eine News-Datei anlegen.**
- **Hinweis im Client:** gelbes Banner „New client version … available (you have …). Get it with git pull and restart the client.“ mit Knopf **„Read about new features“**: abonniert TBNEWS, gleicht die Bulletins ab und öffnet das Feature-Bulletin. Wegklicken gilt bis zur nächsten Version; der Hinweis bleibt auch nach Trennen/Neustart des Clients.
- **Seite veraltet:** Wurde der Client aktualisiert, die Seite im Browser ist aber noch alt, zeigt sie „The client was updated … – reload the page“ mit Knopf „Reload page“.
- **Unbekannte Emoji-Codes** (von einem neueren Client) erscheinen als `[?]` statt als Rohcode.
- Tests: `tests/test_clientnews.py`; Praxistest mit TinyBox, aktuellem und altem Client (PC und Handy).

## CR19 – Rubriken sind Sysop-Sache (erledigt 11.10.2026)

### Umsetzung (11.10.2026)

- **Ohne `[rubrics]`** (kein Eintrag) bleibt alles wie bisher: jede Rubrik ist frei. Nur **TBNEWS** ist immer gesperrt.
- **User** (Terminal, Client): Bulletins nur an ALL und angenommene Rubriken. Terminal: `SB FUCHS` → `Rubric FUCHS is not open for bulletins here. Rubrics: ALL WX …` (vor der Texteingabe). Client: `//ERR send bad_rubric FUCHS`.
- **Skripte (Eingangsordner) und MQTT:** nur Rubriken aus der Liste, sonst landet die Datei mit `.err` („Rubrik nicht in [rubrics] der tinybox.conf“) zurück. **Sysop** (Konsole, Sysop-Web) ist frei.
- **Forwarding** (`tinybox/fwd/receive.py`):
  - angenommen → `+`; abgelehnt oder TBNEWS → `-`.
  - **unbekannt, erstes Angebot** → `+`. **Abweichung vom Vorschlag:** das Bulletin wird nicht verworfen, sondern **gehalten (H) gespeichert** (User sehen es nicht, brocast auch nicht), dazu geht die **Mail an den Sysop** („New rubric FUCHS offered by OE3GAS“, mit Kopf, Text und Anleitung). So ist das erste Bulletin nach dem Annehmen auch in der Rubrik.
  - **unbekannt, Sysop hat noch nicht entschieden** → FBB/B1: `=` (später), Partner bietet es wieder an. **ASCII (W0RLI)** kennt kein „später“ → angenommen und gehalten, ohne weitere Mail.
  - Woran „noch nicht entschieden“ erkannt wird: es gibt ein gehaltenes Bulletin dieser Rubrik mit dem Vermerk „new rubric …“. Löscht der Sysop es ohne Entscheidung, beginnt es beim nächsten Angebot von vorn (neue Mail).
- **Nach dem Eintrag in `[rubrics]` und RESTART:** angenommen → gehaltene Bulletins werden freigegeben (wie `REL`), abgelehnt → gelöscht; zurückgestellte kommen beim nächsten Forward-Lauf bzw. werden abgelehnt.
- **Client** (Version 2026.10.11.5): `//RUBRICS` liefert zusätzlich die angenommenen Rubriken ohne Bulletins (`//RU WX 0 0`), die Beschreibungen (`//RU WX : Weather and warnings`) und die Liste zum Schreiben (`//RU + ALL WX CONTEST`, Reihenfolge wie in `[rubrics]`). Alte Clients überlesen diese Zeilen. Composer: beim Typ *Bulletin* Auswahlliste „WX – Weather and warnings“, daneben das Feld für das Verteilgebiet (`@WW`, optional). Ohne Liste (alte TinyBox, noch kein Bulletin-Abgleich) bleibt das freie Feld. Die Rubrikenliste zum Abonnieren zeigt die Beschreibungen.
- Tests: `tests/test_rubrics.py` (Regeln, Terminal, `//RUBRICS`, Forwarding inkl. fwdsim-Lauf FBB).
- **Hinweis zur eigenen `tinybox.conf`:** `BROCAST` hat 7 Zeichen und wird ignoriert (Warnung im Log) – Rubriknamen höchstens 6 Zeichen, z. B. `BROCST`.

### Ursprüngliche Erfassung

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

## CR21 – Bulletins verschieben und kopieren (Vorschlag 11.10.2026, noch nicht umgesetzt)

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
2. Wo: **nur in der Sysop-Konsole (Terminal am TinyBox-PC) und in der Sysop-Weboberfläche** – **keine Sysop-Rechte über Funk und keine im Client** (Entscheidung Gerhard, 11.10.2026).
3. Eine Kopie übernimmt die Ablaufzeit des Originals.

**Sysop-Rechte im Client – verworfen (11.10.2026):** Es gibt keine Sysop-Rechte über Funk und keine im Client. Der folgende Vorschlag bleibt nur zur Dokumentation stehen:
- **Lokal (Client auf dem TinyBox-PC, `link = telnet`):** schon heute bekommt eine Telnet-Sitzung mit dem Sysop-Rufzeichen Sysop-Rechte (der Testport hört nur auf 127.0.0.1). Die TinyBox meldet das im Handshake (`//OK … sysop=1`), der Client zeigt dann die Sysop-Knöpfe.
- **Über Funk:** Rufzeichen sind nicht authentisch (`sysop_via_radio = no`). Neu: Anmeldung mit **Challenge-Response** wie Winlink „Secure Login“: Die TinyBox schickt eine Zufallszahl, der Client antwortet mit einem daraus und einem geheimen Sysop-Passwort berechneten Code (HMAC). Das Passwort geht nie über Funk, ein mitgehörter Code nützt beim nächsten Mal nichts. Der Inhalt bleibt Klartext – es wird nur angemeldet, nichts verschlüsselt.
  - `tinybox.conf`: `sysop_via_radio = auth`, `sysop_secret = …`; `tbclient.conf` bzw. Client-Einstellung: dasselbe Passwort, nur lokal gespeichert.
  - Befehle: `//SYSOP` → `//CHAL <zufall>` → `//SYSOP <code>` → `//OK sysop=1` bzw. `//ERR sysop`.
- **Sysop-Weboberfläche der TinyBox** (Port 8080, mit Login-Link) bleibt der Weg für die Verwaltung am TinyBox-PC.

## CR22 – RESTART in der Sysop-Konsole (erledigt 11.10.2026)

- `RESTART [s]` startet die TinyBox neu, z. B. nach einer Änderung in `tinybox.conf` oder nach einem `git pull`. Ablauf wie `SHUTDOWN`: verbundene Stationen werden gewarnt („OE3GAS-1 restarts in 60 seconds and is back shortly …“, Erinnerung bei 30 und 10 s), Standard 60 s, `RESTART NOW` sofort, `RESTART CANCEL` sagt ab. Ist niemand verbunden, sofort.
- **Vorher wird `tinybox.conf` geprüft.** Hat sie einen Fehler, startet die TinyBox **nicht** neu und zeigt den Fehler – sie läuft mit der alten Konfiguration weiter.
- **Neustart im selben Fenster:** `tinybox.bat` und `tinybox_dauerbetrieb.bat` starten die TinyBox sofort wieder (Exit-Code 3); ohne Batch-Datei (Linux, systemd) ersetzt sich der Prozess selbst. Neue Konfiguration und neuer Code werden dabei geladen.
- Tests in `tests/test_shutdown.py`; README und PRODUCTION ergänzt.
- Hinweis: Die neuen Batch-Dateien wirken erst, wenn TinyBox einmal mit ihnen gestartet wurde.

## CR23 – BUG Emoji-Picker: Schnellauswahl-Leiste verdeckt die Gesamtauswahl (gemeldet und ✅ 11.10.2026)

**Fehler:** Wenn man die Emoji-Gesamtauswahl öffnet (über den ➕-Button in der Reaktions-/Schnellauswahl-Leiste mit 👍 ❤️ 😂 😮 😞 📻 ➕), bleibt diese Leiste als schwebendes Overlay über dem großen Emoji-Panel stehen und verdeckt Einträge (z. B. die Zeile „RADIO & TECH“).

**Erwartet:** Sobald die Gesamtauswahl geöffnet wird, wird die Schnellauswahl-Leiste ausgeblendet/geschlossen.

**Fix (b5714a8):** In `openReactBar()` schließt der ➕-Button zuerst die Leiste und öffnet dann die Gesamtauswahl für die gemerkte Nachricht. Wird eine andere Nachricht angetippt, während die Gesamtauswahl im Reaktionsmodus offen ist, schließt sie sich.

**Test auf PC1 (11.10.2026), PC- und mobile Ansicht:**
- a) Nachricht antippen → Leiste erscheint: ok
- b) ➕ → Leiste weg, Gesamtauswahl frei („RADIO & TECH“ sichtbar): ok
- c) Emoji aus der Gesamtauswahl → Reaktion an der angetippten Nachricht, Gesamtauswahl zu: ok
- d) ➕ bei Nachricht A offen, dann B antippen: **Fehler** – die Gesamtauswahl schließt sich, die Leiste für B erscheint aber nicht (erst beim zweiten Antippen). Die Reaktion landet dann richtig bei B.
- e) Emoji-Button im Eingabefeld fügt Emojis weiter in den Text ein: ok

**Ursache von d:** Schließt sich die Gesamtauswahl, wird `#chat` höher und der Browser verschiebt die Scroll-Position von selbst. Das `scroll`-Ereignis von `#chat` ruft `closeReactBar()` auf und schließt die gerade geöffnete Leiste sofort wieder.

**Nachbesserung (08a5993):** `openReactBar()` merkt sich beim Schließen der Gesamtauswahl einen Zeitpunkt (`ignoreChatScrollUntil`, 150 ms). Scroll-Ereignisse von `#chat` innerhalb dieser Zeit schließen die Leiste nicht. Echtes Scrollen durch den User schließt sie weiterhin.

**Nachtest auf PC1 (11.10.2026, 22:02):** d in PC- und mobiler Ansicht ok – die Leiste für die zweite Nachricht bleibt stehen, die Reaktion landet dort. Echtes Scrollen schließt die Leiste weiterhin.

## CR24 – BUG Schnellauswahl-Leiste ragt in der PC-Ansicht rechts aus der Chat-Spalte (gemeldet und ✅ 11.10.2026)

**Fehler:** In der PC-Ansicht (3 Spalten) ragt die Schnellauswahl-Leiste bei eigenen (rechtsbündigen) Nachrichten über den rechten Rand der Chat-Spalte hinaus in die rechte Spalte („IN THIS BOARD“).

**Ursache:** `openReactBar()` begrenzt die Position auf `window.innerWidth`, nicht auf die Breite der Chat-Spalte.

**Erwartet:** Die Leiste bleibt innerhalb der Chat-Spalte.

**Fix (4c080ac):** `openReactBar()` begrenzt die Position der Leiste jetzt auf die Chat-Spalte (`#chat`), links und rechts mit 8 px Abstand. Ist die Leiste breiter als die Spalte, beginnt sie am linken Rand der Spalte.

**Test auf PC1 (11.10.2026):** PC-Ansicht ok – die Leiste endet innerhalb der Chat-Spalte (8 px vor dem Rand). Mobile Ansicht unverändert.

## CR25 – Board antippen: Bestätigung (✅ 11.10.2026)

- Das angetippte Board (Chip oben bzw. Eintrag in der linken Spalte) wird **orange und pulsiert leicht**, bis die TinyBox meldet, dass man im Board ist; dann wird es wie gewohnt blau (aktiv).
- Kommt keine Bestätigung (z. B. Verbindung weg), endet die Markierung nach spätestens 2 Minuten. Bei „Bewegung reduzieren“ im System pulsiert nichts.
- Client-Version 2026.10.11.6. Nur Oberfläche (`app.js`, `app.css`).

## CR3 – MOTD pro Board (✅ 11.10.2026)

- Der **Sysop** setzt sie in `tinybox.conf`, eigener Abschnitt `[chat_motd]`, eine Zeile pro Board, höchstens 120 Zeichen (kein `#` oder `;` im Text – die beginnen einen Kommentar). Ändern: Datei bearbeiten, `RESTART`.
  ```
  [chat_motd]
  TREFF = Willkommen! Runde jeden Sonntag 19:00 auf dieser QRG.
  ```
- **Terminal:** beim Betreten eine Zeile `*** <Text>` unter der Board-Überschrift.
- **Client:** über Funk geht beim Betreten nur eine Prüfsumme (`//IN … motd=ab12`, 10 Byte). Den Text holt der Client nur, wenn er neu ist (`//MOTD` → `//MOTD ab12 <Text>`) und merkt ihn sich. Anzeige oben im Chat als gelbe Notiz mit 📌.
- Client-Version 2026.10.11.7. Tests in `tests/test_motd.py`.

## CR14 – Zitieren (✅ 11.10.2026, Variante B)

- **Bedienung:** Beitrag antippen → in der Leiste ganz links **↩** → über dem Eingabefeld steht „You are adding a comment on **OE3TEC:** Wer ist heute…“ (✕ = kein Kommentar), das Eingabefeld zeigt „Your comment on OE3TEC's message“ → Text schreiben, senden.
- **Nur im laufenden Chat** (Fix 12.10.2026): Kommentieren und Reagieren geht nur bei Beiträgen, die eingetroffen sind, während man im Board ist. Beiträge aus der History (gestrichelter Rand) sind nur lesbar – kein ↩, keine Reaktionen, kein nachträgliches Kommentieren.
- **Über Funk nur ein Verweis** vor dem Text: `~^OE3TEC 1402 Ich bin QRV` – Rufzeichen und Minute (UTC, Uhr der TinyBox) des zitierten Beitrags, ca. 13 Byte.
- **Anzeige:** Der Client sucht den Beitrag im eigenen Chat (±1 Minute, bei mehreren der letzte) und zeigt über der Antwort einen Zitatblock „↩ OE3TEC 14:02“ mit Auszug; Antippen springt zum Original. Ohne Original (später gekommen, History nicht geladen) nur „↩ OE3TEC 14:02“.
- Wer zitiert wird, sieht die Antwort hervorgehoben wie bei @CALL (CR15).
- **Terminal-Teilnehmer** sehen `~^OE3TEC 1402 Ich bin QRV`.
- Kein Zitat im Cry-out-Modus. Client-Version 2026.10.11.8, nur Client (`app.js`, `app.css`, `index.html`); Fix History/Kommentarleiste: 2026.10.12.

## CR26 – Delta-Abgleich mit minimaler Payload (✅ 12.10.2026)

**Problem:** Der Mail-Sync holte immer alle Köpfe der eigenen Post von vorn (30 Mails ≈ 2,7 kB in 3 Wechseln, auch ohne Neues), der Bulletin-Sync jedes Mal die ganze Rubrikenliste. Eine neue kurze Mail = 4 Wechsel. Über Funk zählt jeder Wechsel (TXDelay, ACK, Pause) mehr als die Bytes.

**Lösung** (Konzept und Protokoll: PLANUNG.md 12.9):
- **TinyBox:** Änderungszähler `seq`/`cseq` je Nachricht und Tombstones gelöschter Nachrichten (SQLite-Trigger, Schema 7). Neue Befehle `//SYNC` (Löschen + Gelesen + Delta der Köpfe + kleine Texte in **einem** Wechsel) und `//BSYNC` (Rubrikenliste nur bei Änderung per Hash, neue/gelöschte Bulletins, kleine Texte). Cap `SYNC2`. Mit `Z` über Funk kommt die Antwort ab 200 Byte als ein LZHUF-Block (`//ZSYNC`). Alte Befehle bleiben für alte Clients.
- **Client:** nutzt `SYNC2`, wenn die TinyBox es anbietet, sonst alter Ablauf. Merkt sich `seq` je Abgleich; in der TinyBox gelöschte Post verschwindet jetzt auch hier (`//D`). Vollabgleich bei `//ERR seq` (TinyBox-DB neu).
- **Ergebnis:** „nichts Neues“ = 1 Wechsel, ~45 Byte statt ~2,7 kB; 1 neue Mail = 1 Wechsel statt 4.
- Client-Version 2026.10.12.3. Tests: `tests/test_mailsync.py` (`DeltaSyncTests`).

## CR27 – Persönliche Post an mehrere Empfänger (✅ 12.10.2026)

**Entscheidung:** nur Variante „mehrere Rufzeichen in einer Mail". Eine Verteilerliste (eine Nachricht, viele Leser, Lesestatus je Leser) gibt es nicht – dafür sind die Rubriken da (Bulletins).

**Verhalten:**
- Empfängerfeld mit Komma: `OE3TEC,OE1ABC[@ADRESSE]`. Terminal `SP OE3TEC,OE1ABC`, Client-Composer (Feld „To"), `//SEND P OE3TEC,OE1ABC <n> mid=…`. Eine `@`-Adresse gilt für alle; braucht ein Empfänger eine andere, zwei Mails schreiben. Höchstens 10 Empfänger, doppelte werden zusammengefasst, jeder wie bisher geprüft (`check_send`).
- Die TinyBox legt **je Empfänger eine eigene Nachricht** an: gleicher Text und Betreff, eigene Nummer, eigener Status, eigene MID (fürs Forwarding, jede Kopie geht ihren eigenen Weg). Ist einer der Empfänger ungültig, wird gar nichts gespeichert (`//ERR send …` bzw. Fehlertext am Terminal) – keine halben Sendungen.
- Über Funk geht der Text **einmal**: der Client schickt eine `//SEND`-Zeile mit der Empfängerliste; Antwort `//SENT <Nr.> <Nr.> …` (eine Zeile, alle Nummern). `mid=` bleibt eine Kennung für die ganze Sendung: kommt sie noch einmal, antwortet die TinyBox mit den vorhandenen Nummern (Zuordnung Kennung → Nummern über `msgid = tbc-<Kennung>-<Empfänger>`).
- Terminal-Antwort: `Message 12, 13 saved` (wie bisher, nur mit allen Nummern).
- Client: im Ordner „Sent" erscheint je Empfänger ein Eintrag (jede Kopie hat ihre Nummer, kann einzeln gelöscht werden); der Ausgang zeigt die Sendung bis zum `//SENT` als einen Eintrag. Der Delta-Abgleich braucht nichts Neues.
- Alte Clients: schicken nie ein Komma, nichts ändert sich.

**Umgesetzt 12.10.2026:** `MessageService.check_send_list()` (Liste prüfen, Doppelte falten, max. 10; Bulletins und `$BID` nur ein Ziel), Terminal `S OE3TEC,OE1ABC` → `Msg 12, 13 saved.`, `//SEND` → `//SENT 12 13` (msgid `tbc-<mid>-<Call>`, ein Empfänger wie bisher `tbc-<mid>`), Client legt je Nummer einen „Sent"-Eintrag an, Composer nimmt `OE3ABC,OE3XYZ[@…]`. Jede Kopie beginnt mit der Zeile `To: OE3TEC, OE1ABC`, damit jeder Leser sieht, wer sie noch bekommen hat (Ergänzung 12.10.2026 abends; auch im Sent-Ordner des Clients). Client-Version 2026.10.12.4, To-Zeile 2026.10.12.5. Tests: `test_mailsync.py` (`MultiRecipientTests`).

## CR28 – Emoticons und Emojis in beide Richtungen (✅ 12.10.2026)

**Beobachtet (Funktest 12.10.2026):** Vom Terminal kam `das funktioniert ;-)` – der Client zeigte `;-)` als Text, weil nur die nasenlosen Formen (`;)`) bekannt sind. Vom Client ging `sehr nett!~0B` – 🙂 aus dem Picker hat keine Emoticon-Form, also der Code; dazu klebte er am `!`. Am Terminal liest sich das als `~0B`.

**Heute:** Stufe 1 (PLANUNG 12.4) kennt neun Emoticons ohne Nase (`:)` `:(` `;)` `:D` `:P` `:O` `<3` `:+1` `:-1`), umgewandelt erst beim Senden bzw. beim Anzeigen, nur als eigenes Wort (Leerzeichen davor).

**Gewünscht:**
1. **Eingabe im Client:** Ein Emoticon wird **sofort beim Tippen** zum Emoji (sobald Leerzeichen, Satzzeichen oder Enter folgt), wie in Messengern. Die Tabelle kennt die Formen mit und ohne Nase: `:-)` `:)` `;-)` `;)` `:-D` `:D` `:-(` `:(` `:-P` `:P` `:-O` `:O` `:-/` `:-|` `<3` `:+1` `:-1` … Der Picker bleibt für den Rest.
2. **Senden:** Jedes Emoji, das eine Emoticon-Form hat, geht **als Emoticon** über Funk, nie als `~XY` – auch Varianten, die nur im Aussehen abweichen (🙂 😊 😀 → `:-)`, 😄 😃 😁 → `:-D`, 😉 → `;-)`, 🙁 😢 → `:-(`). Gesendet wird die Form **mit Nase** (`:-)`, wie am Terminal üblich; 1 Byte mehr, dafür für Terminal-User eindeutig). Fehlt vor dem Emoticon ein Leerzeichen (`nett!:-)`), fügt der Client es ein. `~XY` nur noch für Emojis ohne ASCII-Form.
3. **Anzeige im Client:** Emoticons aus jeder Quelle (Terminal, alter Client, History `//H`) werden zum **kanonischen Emoji** der Tabelle (`:-)` und `:)` → 🙂; `:-D` → 😄 …), auch direkt nach Satzzeichen (`Hallo!:-)`), nicht aber mitten im Wort (`QTH:Pinkafeld`, `http://`).
4. **Terminal:** nichts zu tun – die TinyBox reicht Text durch; wer `;-)` tippt, erscheint im Client als 😉. Reaktionen (`~XY` als Reaktionscode) bleiben, wie sie sind.

**Umgesetzt 12.10.2026 (nur Client):** `emoji.json` Version 3 – 16 Emoticons `{wire, aliases, emoji, also}`: `:-)` `;-)` `:-D` `:-(` `:'(` `:-P` `:-O` `:-/` `:-|` `:-*` `8-)` `>:-(` `xD` `<3` `:+1` `:-1`, jeweils mit nasenloser Form; 😊 😀 ☺️ gehen als `:-)`, 😃 😁 😆 als `:-D`, 😎 als `8-)`, 😢 als `:'(`, 😡 als `>:-(`, 😂 als `xD` (die alten Codes `~0A` `~0D` `~14` `~15` werden weiter verstanden). `app.js`: Live-Ersetzung beim Tippen (`liveEmoticon`, nach Leerzeichen oder Satzzeichen, Cursor bleibt), Erkennung auch nach Satzzeichen (`Hallo!:-)`), nicht im Wort (`QTH:Pinkafeld`, `http://`); Picker mit neuer erster Gruppe „Smileys (ASCII, cheapest)“, die anderen Gruppen ohne diese Doppelten. Client-Version 2026.10.12.4. Tests: `test_tbclient.py` (`EmoticonTests`, laufen mit node, sonst übersprungen).

## CR29 – Terminal: lange Ausgaben seitenweise (✅ 12.10.2026)

**Problem:** `L` listet alle Nachrichten; mit wachsender Box laufen irgendwann hunderte Titel ungefragt über Funk. Gleiches gilt für `LB`, `H`, `J` und lange Texte bei `R`.

**Lösung (nur TinyBox, `session.py`):** Jede Antwort auf einen Terminal-Befehl, die länger als 10 Zeilen ist, kommt in Seiten zu 10 Zeilen mit der Zeile `--More (10/37)-- Enter = continue, A = abort: `. Enter (oder jede andere Eingabe) holt die nächste Seite, `A` / `Q` / `/AB` verwirft den Rest (`*** rest skipped`). Gilt für alle Terminal-Befehle; nicht für Clients, den Chat, `DICT` und Befehle, die in einen anderen Zustand wechseln (`S`, `C`). Nach `B` kommt das „73, bye“ noch vor dem Trennen. `PAGE_LINES = 10` in `session.py`, Texte in `texts.py`. Tests: `test_tinybox.py` (`PagingTests`), `test_agw.py` angepasst. Als TBNEWS-Feature in Client-News 2026.10.12.8 (nur Textänderung, der Client selbst ist unverändert).

## CR30 – Bild-Upload sichtbar machen (✅ 12.10.2026)

**Problem:** Lädt jemand ein Bild hoch, ist der Kanal ein bis zwei Minuten belegt, ohne dass die anderen wissen warum.

**Entscheidung:** Ein einziges Ereignis beim Start, kein laufender Fortschritt über Funk.

- Die TinyBox sendet, sobald sie den Upload mit `//IMGGO` freigibt, das Chat-Ereignis `^<Call> <Größe>` (Größe wie in der Bildreferenz: 2 Hex in 64-Byte-Schritten), z. B. `#5A ^OE1ABC 50` – rund 14 Byte, einmal pro Bild. Nicht in der History gespeichert (wie das Qualitäts-Ereignis `%`).
- **Client:** Zeile im Chat „OE1ABC uploading picture · 2.1 / 5.0 KB“ mit Fortschrittsbalken. Der Fortschritt ist **echt gemessen**: der Client hört den Kanal ohnehin mit und zählt die Nutzbytes der I-Frames, die von dieser Station zur TinyBox gehen – null zusätzliche Payload. Wer die Station nicht direkt hört (Digi, zu schwach), zählt nichts; dort läuft der Balken über die geschätzte Dauer. Wiederholte Frames würden doppelt zählen, darum ist bei 100 % Schluss. Mit der eintreffenden Bildzeile verschwindet die Anzeige; bleibt sie aus (abgebrochener Upload), blendet der Client sie nach der doppelten geschätzten Dauer aus.
- **Terminal-Teilnehmer** lesen `*** OE1ABC is sending a picture (5.0 KB)` – auch dort weiß damit jeder, warum die Frequenz belegt ist.
- Der Uploader selbst sieht weiterhin nur seine eigene Bubble mit „sending …“.

## CR31 – Kommentarbezug eindeutig (✅ 12.10.2026)

**Problem (Funktest 12.10.2026):** Der Kommentar bezog sich über Rufzeichen + Minute (`~^OE3TEC 1402`) auf einen Beitrag. Hat dieselbe Station in derselben Minute mehrmals geschrieben, nahm der Client den letzten – inhaltlich falsch.

**Entscheidung:** Bezug über die **Folgenummer des Ereignisses**, die es ohnehin in jedem Frame gibt und die die Reaktionen schon so nutzen (`#52 OE3TEC *4F :+1`). Ein eigener Hash wäre größer und bräuchte neue Vergabe- und Abgleichlogik auf beiden Seiten.

- **Über Funk:** `~^4F Ich bin QRV` statt `~^OE3TEC 1402 Ich bin QRV` – **5 statt 14 Byte**, eindeutig über die letzten 256 Ereignisse des Boards (genau das Fenster, in dem Kommentieren erlaubt ist).
- **Client:** sendet nur noch das neue Format, liest beide (alte Zeilen stehen in der History). Kennt er den Bezug nicht (später eingecheckt), zeigt er „↩ message #4F“ – **kein Nachfordern über Funk**: echte Lücken holt die Lückenerkennung ohnehin selbst, und ein `//RESEND` für Ereignisse von vor dem Einchecken würde die Empfangsquote (14.3) verfälschen.
- **Terminal-Teilnehmer:** Die TinyBox löst den Verweis auf und schreibt `[re OE3TEC: "Servus, Wetter passt"] Ich bin QRV` – vorher stand dort der rohe Verweis. Enthält der zitierte Beitrag ein Bild, steht im Auszug kurz `[Image]` (sonst bliebe vom Auszug nichts übrig). Im Verlauf (`/H`), wo das Ereignisfenster nicht mehr gilt, steht `[re #4F]`.
- Kommentieren bleibt auf Beiträge beschränkt, die im laufenden Chat eintreffen (Entscheidung 12.10.2026) – History-Zeilen haben keine Folgenummer.
