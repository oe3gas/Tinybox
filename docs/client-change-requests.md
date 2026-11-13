# TinyBox-Client – Change Requests

Gesammelt beim ersten Test PC1 ↔ PC2 (OE3GAS, OE3TEC) am 09.10.2026, ergänzt laufend.
Stand: 13.11.2026 (CR128; CR127; CR126; CR124; CR123; CR122; CR87–CR100 aus dem Security-Audit erfasst, PLANUNG 29; CR103 PLANUNG 30; CR104, CR105, CR106; CR110)

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
| 16 | Anstupsen: Klick auf Call in Teilnehmerliste → kurze persönliche Nachricht als Pop-up mit Klingelton | ✅ mit CR85 (Erwähnungs-Alarm bei `@CALL`: Popup und „BK“ in CW), 08.11.2026 |
| 17 | „Cry out“: max. 32 Zeichen, sehr große Schrift in einer „Bang!“-Blase | ✅ siehe unten |
| 18 | Versionskontrolle: Client prüft, ob er aktuell ist; User wird informiert und aufgefordert, die neue Version zu holen | ✅ siehe unten |
| 19 | Rubriken sind Sysop-Sache: feste Rubrikenliste, User schreiben Bulletins nur an ALL und diese Rubriken (Auswahl im Composer), Forwarding nimmt nur diese Rubriken an | ✅ siehe unten |
| 20 | Verbindungsqualität: 1–5 Balken neben jeder Station im Board, Meldung bei Verbindungsabbruch, Befehl `STAT` | ✅ siehe unten |
| 21 | Bulletins zwischen Rubriken verschieben und kopieren | ✅ 10.11.2026 (Konsole, Sysop-Web-GUI, Client des Sysops über CR94) |
| 22 | Sysop-Konsole: Befehl RESTART (Neustart, z. B. nach Änderung in tinybox.conf) | ✅ siehe unten |
| 23 | BUG – Emoji-Picker: Schnellauswahl-Leiste verdeckt die Gesamtauswahl | ✅ siehe unten |
| 24 | BUG – Schnellauswahl-Leiste ragt in der PC-Ansicht rechts aus der Chat-Spalte | ✅ siehe unten |
| 25 | Board antippen: Button einfärben, bis man im Board angekommen ist | ✅ siehe unten |
| 26 | Delta-Abgleich: Mail-/Bulletin-Sync mit minimaler Payload (ein Wechsel, nur Änderungen, kleine Texte gleich mit, Z für Köpfe) | ✅ siehe unten |
| 27 | Persönliche Post an mehrere Empfänger (`OE3TEC,OE1ABC`): Text einmal über Funk, TinyBox legt je Empfänger eine eigene Nachricht an | ✅ siehe unten |
| 28 | Emoticons ↔ Emojis: `;-)` beim Tippen sofort als Emoji, Terminal-Eingabe `;-)` im Client als Emoji, Emojis mit ASCII-Form gehen als `:-)` statt `~0B` über Funk | ✅ siehe unten |
| 29 | Terminal: Ausgaben über 10 Zeilen seitenweise mit „continue/abort“ (`L` und jeder andere Befehl), damit nicht hunderte Titel über die Luft laufen | ✅ – seit CR40 ersetzt durch Hinweis + Abort |
| 30 | Bild-Upload eines Teilnehmers sichtbar machen: „OE1ABC uploading picture“ mit Fortschrittsbalken | ✅ siehe unten |
| 31 | Kommentarbezug eindeutig machen (bisher Rufzeichen + Minute, mehrdeutig) | ✅ siehe unten |
| 32 | Logfile zum Debuggen mit Claude: eine Datei pro Tag, feste Spalten, Session-Nummer, Startblock, `LOG`-Befehl | ✅ siehe unten |
| 33 | Teilnehmernummern und Verbindungsdetails im Client (Detailansicht je Station) | ✅ siehe unten |
| 34 | Bildübertragung schneller (256-Byte-Frames, Bild am Stück an Direwolf) | ✅ siehe unten |
| 35 | Bug: Bekanntes Bild ließ sich nicht erneut in den Chat stellen – Upload brach stumm ab | ✅ siehe unten |
| 36 | Bildgröße im Chat sichtbar (klein bleibt klein), Größenwahl mit Zahlen in den Knöpfen | ✅ siehe unten |
| 37 | brocast-Listener: Ansicht „Mit Trennlinien“ raus, Teile-Knöpfe nur im Teletext, Teletext in echter Teletext-Optik (Pixelschrift, großer Zeilenabstand) | ✅ siehe unten |
| 38 | Teletext: Zeilenabstand auf Zeichenhöhe, brocast-Schriftzug nach der Teletext-Titelseite über jeder Seite; Bildkonverter (Bilder als Mosaik-Bulletins, nur station) | ✅ siehe unten |
| 39 | TinyBox-Web-GUI: „Rubrics“ aufklappbar in der Seitenleiste, Klick zeigt die Bulletins dieser Rubrik | ✅ siehe unten |
| 40 | Sync beim Anmelden: alle Köpfe (eigene Mails + abonnierte Rubriken), persönliche Mails ≤ 256 Byte gleich mit, sonst Text erst beim Anklicken; geordneter Abort mit Restanzeige und Zeitschätzung; Terminal: Abort statt 10-Zeilen-Seiten (CR29); Frist je Rubrik | ✅ siehe unten |
| 41 | KISS-Mode: Kanal- und kisshub-Werte in der Sysop-Web-GUI (Kanalauslastung, gehörte Stationen, TNC-Zustand, Wartezeit im Hub) für das Qualitäts-Monitoring | ✅ siehe unten |
| 42 | Freier Connect: „Connect to:“ in der Titelleiste statt fest verdrahtetem OE3GAS-1, Verlauf der letzten Ziele, Titelleiste einzeilig mit Zustands-Icons (connecting mit Zähler, connected, disconnecting, no answer / disconnected by) | ✅ siehe unten |
| 43 | Terminalmodus: Gegenstelle ist keine TinyBox → Terminal statt Chat, kein `//CLIENT`; bei einer TinyBox per Menü | ✅ siehe unten |
| 44 | Verbindungslogbuch in TinyBox und Client: Gegenstation, Connect, Disconnect, Dauer, Bytes; unbegrenzt, Export CSV und ADIF; jeder User sieht seine Connects (`QSO`) | ✅ siehe unten |
| 45 | Multi-Connect im Client: bis 5 Verbindungen, umschaltbar (Kanäle), Monitor-Kanal | ✅ siehe unten |
| 46 | Client über kisshub (`link = kiss`) mit eigenem AX.25 – vollwertiges PR-Programm ohne Direwolf und ohne TinyBox; eingehende Connects | ✅ siehe unten |
| 47 | Mail in der Outbox sofort aussenden, nicht erst beim nächsten Sync | ✅ siehe unten |
| 48 | TinyBox-Bake: Text und Intervall in `[beacon]`, neue Post als „Mail for:“-Liste in der Bake | ✅ siehe unten |
| 49 | Suche in Mails und Bulletins: Client (Suchfeld), TinyBox (Befehl `F`), Sysop-Weboberfläche | ✅ siehe unten |
| 50 | Monitor: alter Monitor aus den Settings raus, ohne „fm“, Rufzeichen farbig, Filter nach Text und nach TinyBox-Sonderframes, Clear | ✅ siehe unten |
| 53 | TinyBox-Web-GUI: Monitor auf schwarzem Hintergrund (wie im Client) | ✅ siehe unten |
| 73 | Benutzerprofil: Name, Locator, Home-BBS in TinyBox und Client (Terminal-Fragen, Formular im Client, `//PROF`, `//WHOIS`) | ✅ siehe unten (Funktest offen) |
| 79 | APRS-Statistik: Netzgraph (Bubbles, Knoten, Wege) mit Filter nach Paketart, Geräte-Torte | ✅ Stufe 1 und 2 siehe unten |
| 82 | TinyBox: Sysop-Befehl `RELOAD` – `tinybox.conf` neu einlesen, ohne die User zu trennen | ✅ siehe unten |
| 83 | TinyBox-Web-GUI: Frame-Monitor auch im AGW-Mode – gehörte Frames (Stufe 1) und eigene gesendete Frames über den Direwolf-Fork (Stufe 2) | ✅ siehe unten (Funktest offen) |
| 84 | Kommentar auf eine Nachricht aus der History: Text statt „message #n“ | ✅ siehe unten (Funktest offen) |
| 85 | Erwähnungs-Alarm: Popup des Betriebssystems und „BK“ in CW bei @CALL | ✅ siehe unten (Funktest offen) |
| 86 | Dateien im Board-Chat (LZHUF), wie Bilder (CR12) und Dateien im TBClient-Chat (CR78 Stufe 7) | ✅ 10.11.2026 (mit 16-Hex-Hash aus CR96), siehe unten |
| 87 | brocastd: Absturz durch ungültiges `exp` (TB-01) | ✅ siehe unten |
| 88 | Parser-Robustheit: Zahlen, Ausnahmen, Endlosschleifen (TB-09, TB-20c, TB-23) | ✅ siehe unten (Fuzz-Lauf mit CR98 ✅) |
| 89 | Forwarding-Robustheit: BID, Restart, Sitzungsdauer, Ctrl-Z (TB-10, TB-11, TB-20a/b) | ✅ siehe unten |
| 90 | Interlink-Authentisierung (TB-02): Stufe 1 Doppel-Rufzeichen erkennen ✅, Stufe 2 HMAC offen | Stufe 1 ✅, siehe unten |
| 91 | Dictionary-Integrität: voller Vergleich, keine automatische Weiterverbreitung (TB-04) | ✅ siehe unten (Signatur mit CR94) |
| 92 | Rollen und Rechte: Sysop-Inhalte, Rubrik-Rechte, nicht authentifizierte User (TB-08, 14, 15, 21) | ✅ 10.11.2026, siehe unten |
| 93 | User-Authentisierung tbclient ↔ Heimat-BBS (Schlüsselpaar, Vertrauenskette) | Stufe 1–3 ✅, Sysop-Web-GUI ✅, siehe unten |
| 94 | Admin-Protokoll mit Signatur (Funk), Standards übers Internet | Sysop über Funk nur mit Client ✅ (Variante B), kein Notzugang; offen: signierte brocast-Seiten, Widerruf über brocast, gemeinsamer Herausgeber – siehe unten |
| 95 | Zeichensatz-Policy und Ausgabe-Maskierung `prcore/text.py` (TB-11, 12, 22) | ✅ siehe unten (Abstufung nach Rolle mit CR92) |
| 96 | Datei- und Bildempfang absichern: Hash, Typprüfung, Abbruch (TB-05, TB-16) | ✅ Stufe 1, siehe unten (längerer Hash mit CR86) |
| 97 | Ratenbegrenzung und Obergrenzen (TB-03, 13, 17, 18, 19) | ✅ siehe unten |
| 98 | Client-Audit: Zugriff auf PC-Daten und In-Band-Befehle | ✅ siehe unten, Bericht `docs/audit-client-cr98.md` |
| 99 | Chatverlauf und Peer-Identität (TB-06, TB-07) | ✅ 10.11.2026 (TB-06; TB-07 Zeilen bleiben unsigniert), siehe unten |
| 100 | Client-Web-GUI: nur eigenes Netz, Schutz gegen DNS-Rebinding und fremde Origins | ✅ siehe unten |
| 101 | TinyBox-Web-GUI: Live-Monitor im Dashboard nur mit Filter, Knopf „Switch to monitor screen“ | ✅ siehe unten |
| 102 | APRS-Netzgraph: keine Linien zur eigenen Station, Auswahl nach Rolle, direkt gehört voll gefärbt, km an der Karte | ✅ siehe unten |
| 103 | APRS-Statistik bei viel Verkehr: fest 250.000 Frames, „All“ zeigt den Zeitraum, Auswertung im Thread | ✅ siehe unten, PLANUNG 30 |
| 104 | Settings-Seite: Karten, zweispaltig, „Connection Status“ mit Mailbox und Auth-Hinweis, „In/Out bytes“, „2h 41m“, Log nach Connect-Zeit sortiert, CW-Tempo für Erwähnungs-Alarm, „by OE3GAS“ | ✅ siehe unten |
| 105 | Eigenes Profilfoto (optional, rund), im Chatboard und bei Verbindung mit anderem Client links neben dem Call-Icon | offen, siehe unten |
| 107 | Gleiche Funktionen Client↔Client und im Chatboard (Shoutout, Kommentar, Reaktion, Sticker, Links, Alarm – und umgekehrt Dateien, Karte, Haken …) | ✅ 10.11.2026 (Teil 1 Client↔Client, Teil 2 Chatboard mit CR86) – siehe unten |
| 110 | Statusleiste: Phasen und Verkehr Client↔Box und Client↔Client in Echtzeit als Chips, Modem/TX/RX in der Kopfzeile, ein-/ausblendbar | ✅ 11.11.2026 – siehe unten |
| 115 | TinyBox: Station sperren (BAN/UNBAN) und entfernen (PURGE = löschen + sperren) | ✅ 11.11.2026 – siehe unten |
| 113 | LoTW als Vertrauensanker: eigenen Schlüssel mit dem LoTW-Zertifikat bestätigen (höchstes Vertrauen) | Stufe 1 (Client signiert) ✅, Stufe 2 (Prüfung in der Box) ✅ 11.11.2026; Stufe 3 Anzeige und „Gerät bürgt für Gerät“ offen – siehe unten |
| 112 | Direwolf-Fork überarbeitet für die Statusleiste: SABM-Versuche, Retry, echtes TX/RX (PTT/DCD), Kanalauslastung, Pegel je Frame, AX.25-Parameter, Feature-Abfrage; Abbruchgrund, eigene Frames im Client-Monitor | ✅ 11.11.2026 (Fork 2026.11.11, Funktest offen) – siehe unten |
| 117 | Bild-Upload: Fortschrittsbalken und TX-Chip in der Kopfzeile passen nicht zum Senden (Balken steht, TX dunkel) | ✅ 11.11.2026 (Client 2026.11.11.12, Nachtrag .13: TX nur PTT, Queue-Chip; .14: Queue in Echtzeit; Funktest offen) – siehe unten |
| 118 | TinyBox-Begrüßungsdialog: Gruß nach dem Namen (zufällig aus 8), Home-BBS mit Rufzeichen-Plausibilität, „S SYSOP“ mitten in den Fragen; Nachtrag: dieselbe Prüfung für Empfänger und @-Mailbox bei S | ✅ 11.11.2026 (Client 2026.11.11.15) – siehe unten |
| 119 | TinyBox-Terminal: `SB` nicht mehr in der Hilfe für nicht authentifizierte User | ✅ 11.11.2026 – siehe unten |
| 120 | Chatboard: Terminal-User in der User-Ansicht kennzeichnen (Pille „terminal“) und beim Betreten eine Systemmeldung an alle | offen – entschieden (Variante A + Systemmeldung), Umsetzung ab 12.11.2026 – siehe unten |
| 121 | TinyBox: eine Verbindung je Rufzeichen – neuer Connect auf laufende Verbindung bekommt DM, N(R)-Fehler beendet mit DISC (gleiches Call doppelt auf der Frequenz) | ✅ 11.11.2026 (KISS/AXUDP; Funktest offen) – siehe unten |
| 122 | CQ contest – Schiffe versenken mit Amateurfunk-Touch: 8 × 8 Großfelder um die Box bzw. den Einladenden, 5 Conteststationen je Spieler, „CQ <Großfeld>“; gegen einen TBClient oder gegen die TinyBox | ✅ 12.11.2026 (Client 2026.11.12, Nachtrag .2: Einladung, Log, Blinken; .3: Pause, hochklappen; .4: über die Box gegen andere Clients; .5: Hinweis-Fix; 2026.11.13.2: Ansicht; Funktest Box ✓, Client↔Client offen) – siehe unten |
| 123 | Prefix raten im Chatboard: die Box nennt ein Rufzeichen, Spieler tippen die DXCC-Entität (A/B/C); Stufen, IARU-Regionen, Anzahl Calls, Anmeldung, Zuschauer, 30-s-Timer, einklappbar | ✅ 12.11.2026 (Client 2026.11.12.5, Funktest offen) – siehe unten |
| 124 | Prefix raten: Oberfläche auf Deutsch, Kreis-Timer (schrumpfende Fläche, Sekunden mittig) für Anmeldung und Tipp, Starter kann die Anmeldung vorzeitig beenden, attraktivere Einladung, gewählter Tipp farbig, Weltkarte als Hintergrund | ✅ 13.11.2026 (Client 2026.11.13, Funktest offen) – siehe unten |
| 125 | TinyBox: bis zu 5 gleichberechtigte Sysops – `sysop_call` in `tinybox.conf` nimmt eine Liste, Post an den Sysop geht an `SYSOP` (alle) | offen – siehe unten |
| 126 | Prefix raten: Antwortzeit 5–30 s einstellbar, Ergebnis nach jedem Call, Übersicht am Spielende, Spielerliste auf der Box (Spiele, richtige/alle Tipps), Sysop löscht Scores – für alle Spiele | ✅ 13.11.2026 (Client 2026.11.13.3, Funktest offen) – siehe unten |
| 127 | Spielergebnisse (Schach, CQ Contest) vom Client signiert an die Box melden – zählt nur, wenn beide Spieler dasselbe Ergebnis signiert melden | ✅ 13.11.2026 (Client 2026.11.13.5, Funktest offen) – siehe unten |
| 128 | Spiele: keine Terminal-User; Zuschauer sehen nur, dass ein Spiel läuft (Prefix raten, Elmer Quiz) | offen – siehe unten |

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

## CR21 – Bulletins verschieben und kopieren (✅ 10.11.2026)

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

**Umsetzung (10.11.2026) ✅:**
- `service.move_bulletin` / `copy_bulletin`; Konsole `MOVE n[,n] RUBRIK`, `COPY n[,n] RUBRIK`, dazu
  `KILL n[,n]`; Sysop-Web-GUI: „Move / copy“ im Leser (`POST /api/messages/<n>/move|copy`); Client
  des Sysops: „Sysop ▾“ im Leser (signierte `//ADM`-Befehle, CR94), danach Abgleich.
- **Abweichung vom Vorschlag:** Verschieben gibt eine **neue Nummer** statt eines eigenen
  `//MV`-Protokolls. Das alte Exemplar wird gelöscht (Clients bekommen `//D`), das neue erscheint
  in der Ziel-Rubrik wie ein neues Bulletin (nur der Kopf, Text bei Bedarf, CR40). So verstehen es
  auch ältere Clients, und der Text geht nicht noch einmal über Funk. Text, Absender, Datum, BID
  und Ablauf bleiben.
- Kopie: eigene Nummer und BID, erste Zeile „(copied from <Rubrik> #<Nr>)“. Beides ohne
  Forward-Status. Ziel: eine angenommene Rubrik, nicht TBNEWS, nicht dieselbe. Log „… moved
  bulletin #12 ALL -> WX (now #57)“. Tests `tests/test_cr94.py` (`MoveCopy`).

**Geändert 10.11.2026 (OE3GAS, CR94):** Sysop über Funk gibt es jetzt – nur mit dem Client, Login
mit dem Schlüssel des Sysops und jeder Konsolenbefehl einzeln signiert. Verschieben/Kopieren
(MOVE/COPY) gehört, wenn es kommt, in diese Befehlsliste.

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


**Korrektur 15.10.2026:** Die Eingabeprüfung im Composer ließ nur ein Rufzeichen zu – Listen
wurden mit „Please enter a call“ abgelehnt, Leerzeichen einfach entfernt. Jetzt trennen
Leerzeichen, Komma oder Strichpunkt (bis 10 Empfänger, z. B. `OE3TEC OE3NDC`); der Client
schickt sie als `OE3TEC,OE3NDC`. Client 2026.10.15.7.
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

## CR32 – Logfile zum Debuggen mit Claude (✅ 13.10.2026)

**Umgesetzt 13.10.2026, alle Punkte 32.1 bis 32.11** – auch die beiden zunächst
als „nice to have“ zurückgestellten, Laufzeiten (32.8) und Übergabepaket (32.10).
Reines TinyBox-Thema, der Client bleibt unberührt: keine neue Client-Version,
keine News-Datei. Neu `tinybox/logsetup.py`; geändert `__main__.py`, `config.py`,
`session.py`, `app.py`, `texts.py`, `adapters/agw.py`, `adapters/telnet.py`,
`adapters/sysop.py`, `clientsync.py`, `fwd/session.py`, `fwd/send.py` und
`tinybox.conf.example`. Tests in `tests/test_logging.py` (44 Tests).

**Problem (vorher):** Beim Debuggen mit Claude war das Log nur eingeschränkt brauchbar.
Jeder Start legte eine neue Datei `Tinybox_log_<Datum>_<Zeit>.log` an – nach einigen
Neustarts lagen dort ein Dutzend Dateien und es musste erst geklärt werden, welche
gemeint ist. Die Zeilen trugen keine Session-Nummer, zwei gleichzeitige Verbindungen
derselben Station (Funk und Telnet) waren nicht auseinanderzuhalten. Es stand nicht
drin, welche Version und welche Adapter überhaupt laufen, und `level = DEBUG` ließ
sich nur global schalten, was die Datei mit Monitor-Verkehr zuschüttete.

**Ziel:** Eine Datei, aus der sich der Ablauf ohne Rückfragen rekonstruieren lässt –
auch von Claude, der den Rechner nicht sieht.

### 32.1 Eine Datei pro Tag (entschieden 13.10.2026)

**Nicht je Neustart** (so ist es heute) und keine feste Einzeldatei mit Rotation,
sondern **eine Datei pro Kalendertag**: `tinybox-2026-10-13.log` im `log_dir`.

- Grund gegen „je Neustart“: nach `git pull` + `RESTART` liegt die Ursache
  (Startblock, geänderte Konfiguration) in einer anderen Datei als die Wirkung,
  und im Dauerbetrieb entstehen an einem Abend mehrere Dateien.
- Grund für den Tag: Probleme werden zeitlich beschrieben („gestern Abend beim
  Funktest“). `tinybox-2026-10-12.log` ist damit direkt adressierbar, ohne Raten
  zwischen `.1`, `.2`, `.3`.
- **Neustarts bleiben sichtbar**, als Block innerhalb des Tages:

  ```
  2026-10-13 19:42:01.004 I core  #0 - ----- TinyBox 2026.10.12 (a1b2c3d) start -----
  ...
  2026-10-13 21:15:33.210 I core  #0 - ----- stop: RESTART, 1h33m, 7 sessions, 0 errors -----
  2026-10-13 21:15:41.882 I core  #0 - ----- TinyBox 2026.10.12 (f4e5d6c) start -----
  ```

  Damit ist sofort zu sehen, ob zwischen zwei Beobachtungen ein Neustart lag.

**Umsetzung:** nicht mit `TimedRotatingFileHandler` – der benennt die laufende
Datei beim Rollover um, und Windows kann eine offene Datei nicht umbenennen; im
Dauerbetrieb über Mitternacht gibt das Fehler, die man dann gerade im Log nicht
findet. Stattdessen ein kleiner eigener Handler:

- Dateiname aus dem Datum, immer im **Append**-Modus geöffnet. Kein Umbenennen,
  keine Sperrprobleme; mehrere Starts an einem Tag hängen hinten an.
- Vor dem Schreiben ein Datumsvergleich; hat der Tag gewechselt, wird geschlossen
  und die neue Datei geöffnet. Kostet einen Integer-Vergleich pro Zeile.
- `keep_days = 14` in `[logging]`: beim Start und beim Tageswechsel werden ältere
  Dateien gelöscht. Logs liegen ohnehin nie im Repo.
- Notbremse gegen Größe: über 20 MB an einem Tag (DEBUG auf `agw` bei viel
  Verkehr) geht es auf `tinybox-2026-10-13.2.log` weiter.
- Der Pfad steht im Startblock und im `LOG`-Befehl, damit er nicht gesucht
  werden muss.

### 32.1a Format

- **Feste Spalten**, eine Zeile = ein Ereignis:

  ```
  2026-10-13 19:42:08.233 I session  #7 OE3TEC  < LIST
  ```

  Zeit mit Millisekunden | Level als ein Buchstabe (`D I W E`) | Komponente
  (feste Breite) | Kontext (Session-Nummer + Rufzeichen) | Meldung.
  Millisekunden, weil über Funk fast jeder Fehler ein Zeitproblem ist (T1, Retries).
- **Dreizeilige Legende als Kopf der Datei**, damit die Leseregeln mitkommen,
  wenn die Datei in einen Chat gelegt wird.

### 32.2 Session-Nummer

Jede Verbindung bekommt eine laufende Nummer (`#7`), die in **jeder** Zeile dieser
Verbindung steht – auch in denen von `store`, `chat` und `sync`. `grep "#7"` liefert
dann die Verbindung von `connected` bis `disconnected`, auch wenn drei Stationen
gleichzeitig arbeiten. Zeilen ohne Verbindung tragen `#0 -`.

Technisch über `contextvars`: der Kontext wird beim Behandeln einer Zeile gesetzt,
und eine dabei gestartete Task erbt ihn – spätere Zeilen derselben Arbeit behalten
also die Nummer. Weil ein Neustart an dieselbe Tagesdatei anhängt, liest die
TinyBox beim Start die höchste Nummer aus der Datei und zählt darüber weiter:
`#7` bleibt damit **innerhalb der ganzen Tagesdatei** eine Verbindung, nicht nur
innerhalb eines Laufs.

### 32.3 Richtungszeichen in zwei Ebenen

- `<` Eingabe der Station, `>` Ausgabe der TinyBox (wie heute im Monitor).
- `<<` / `>>` für AGW-Frames mit Frametyp und Bytezahl.

So ist auf einen Blick zu sehen, ob eine Zeile auf Text- oder auf Frameebene fehlt –
genau die Unterscheidung, die bei Abbrüchen zählt.

### 32.4 Startblock und Schlusszeile

Erste Zeilen jedes Laufs, immer, auch auf `INFO`: TinyBox-Version und Git-Commit,
Python- und OS-Version, Pfad der `tinybox.conf`, Datenverzeichnis, Mailbox- und
Sysop-Rufzeichen, angebotene Client-Version, AGW-Host/Port und die Adapterliste
(`telnet=on web=on brocast=on inbox=on forward=off mqtt=off`). **Keine Token und
keine Login-URL**, nur `token=set` / `token=unset`.

Schlusszeile: Grund des Endes (normal, Ctrl+C, RESTART, Ausnahme), Laufzeit und
Zähler (Sessions, Frames rein/raus, Bulletins weitergeleitet, Fehler). Damit ist
ein Lauf als sauber oder unsauber erkennbar, ohne die Datei zu lesen.

### 32.5 Ausnahmen mit Kontext

Unerwartete Ausnahmen in allen Adapter-Tasks laufen über einen gemeinsamen Helfer
und kommen mit Traceback, Session-Kontext **und der auslösenden Eingabezeile** ins
Log. Die Eingabezeile ist der Teil, der einen Fehler reproduzierbar macht.

### 32.6 DEBUG je Komponente statt global

In `[logging]` zusätzlich `debug = agw,fwd`: nur diese Komponenten gehen auf
DEBUG, der Rest bleibt auf `level`. Ein unbekannter Name ist ein Konfigurationsfehler
und nennt die Liste. Komponenten: `agw`, `brocast`, `bus`, `chat`, `cmd`, `core`,
`fwd`, `inbox`, `linkq`, `news`, `notify`, `session`, `store`, `svc`, `sync`,
`sysop`, `telnet`, `web` – oder `all`.

Dazu `keep_days` (siehe 32.1). Beides gilt für Datei **und** Konsole, damit man
Eingeschaltetes auch live mitlesen kann.

### 32.7 Sysop-Befehl `LOG`

- `LOG` – zeigt Level, aktive Debug-Komponenten, Dateipfad und Dateigröße.
- `LOG DEBUG agw` / `LOG OFF agw` – schaltet im Betrieb, ohne Neustart.
- `LOG MARK <Text>` – schreibt `===== MARK: <Text> =====` in die Datei.
  Marke setzen, Fehler auslösen, danach „ab der Marke“ sagen: spart beim Debuggen
  die meiste Zeit.

### 32.8 Laufzeiten

Dauer in Millisekunden am Zeilenende in Klammern, dort wo sie etwas aussagt:
Session gesamt, Befehlsausführung, Sync-Lauf, Forward-Session, Schreibzugriff über
50 ms, AGW-Connect.

### 32.9 Datensparsam

Der **Text einer Mail** (Betreff und Rumpf, also die Zeilen im Sendemodus) steht
nur als Länge plus die ersten 40 Zeichen im Log: `< 12c 'Test subject'`. Vollständig
erst mit `LOG DEBUG session`. Die Datei wird in Chats gelegt – fremde persönliche
Post soll nicht mitfahren, und die Datei bleibt klein.

Befehle und Antworten bleiben unverkürzt, sonst wäre das Protokoll nicht mehr zu
lesen; Chat-Zeilen ebenso, die hören die Mitlauscher auf der Frequenz ohnehin.
Wer gar keinen Verkehr im Log will, setzt wie bisher `monitor = no`.

### 32.10 Übergabepaket

`LOG BUNDLE` (bzw. `python -m tinybox --debugbundle`) schreibt
`tinybox_debug_<Datum>.txt`: Startblock, die letzten n Zeilen des Logs, Version,
`tinybox.conf` ohne Token, Verzeichnisübersicht von `data`. Eine Datei, die
unverändert in den Chat gelegt werden kann.

### 32.11 Lesehilfe

Ein echter Auszug (Funktest 13.10.2026, zwei Telnet-Sitzungen):

```
2026-10-13 20:08:28.844 I core     #0 -         ----- TinyBox 0.1.0 (f3bee5c) start -----
2026-10-13 20:08:28.844 I core     #0 -         adapters: telnet=on web=on brocast=on inbox=on forward=off mqtt=off console=on
2026-10-13 20:08:28.844 I core     #0 -         brocast token unset, level INFO, debug agw, keep_days 14
2026-10-13 20:08:28.938 W agw      #0 -         Direwolf AGW 127.0.0.1:8000 not reachable (...), retrying every 5s
2026-10-13 20:08:29.937 I telnet   #1 OE3TEC    telnet connect from ('127.0.0.1', 48146)
2026-10-13 20:08:29.944 I session  #1 OE3TEC    < L
2026-10-13 20:08:29.945 I session  #1 OE3TEC    >  MSG# TS   SIZE TO        @BBS    FROM      DATE   UTC   SUBJECT
2026-10-13 20:08:29.946 I session  #1 OE3TEC    < S OE1ABC
2026-10-13 20:08:29.947 I session  #1 OE3TEC    < 12c 'Test subject'
2026-10-13 20:08:29.949 I session  #1 OE3TEC    session end via telnet after (11ms)
2026-10-13 20:08:30.537 I telnet   #2 OE1ABC    telnet connect from ('127.0.0.1', 42782)
2026-10-13 20:08:31.000 I core     #0 -         ===== MARK: Funktest CR32 =====
2026-10-13 20:08:31.648 I core     #0 -         ----- stop: SHUTDOWN, 2s, 2 sessions, 0/0 frames in/out, 0 fwd, 2 warnings, 0 errors -----
```

Leseregeln:

- `-----` trennt die Läufe; `start` und `stop` stehen direkt untereinander, man
  sieht also sofort, ob zwischen zwei Beobachtungen ein Neustart lag.
- ` E ` sind die Fehler, ` W ` die Warnungen – beides zuerst durchsehen. Die
  Schlusszeile sagt, ob es überhaupt welche gab.
- `#7` greppen gibt eine Verbindung vollständig, quer über alle Komponenten und
  über Neustarts hinweg eindeutig.
- `MARK:` zeigt, worauf gezeigt wurde.
- Ein `>` ohne folgendes `<` innerhalb von Sekunden: die Station ist weg.
- Zahl in Klammern: dort ist die Zeit geblieben.
- `12c '...'` ist gekürzter Mail-Text (32.9), kein abgeschnittener Befehl.

Dieselben drei Zeilen stehen als Kommentarkopf in jeder Logdatei, damit sie
mitkommen, wenn die Datei in einen Chat gelegt wird.

## CR33 – Teilnehmernummern und Verbindungsdetails im Client (✅ 13.10.2026)

**Anlass:** Die Sysop-Web-GUI zeigt seit 13.10. je User die Zahlen hinter den Balken (Richtungen, Verluste, Schwellenleiter, Zähler). Dasselbe soll der TBClient+ zeigen – ohne nennenswert mehr Funkverkehr.

**Payload-Abschätzung (13.10.2026, 5 Stationen, 1200 Bd):** volle Auskunft mit Rufzeichen und Klartext ≈ 230 Byte; mit Teilnehmernummern, kompaktem Klartext (Bytes in 100er-Schritten, SRT in 0,1 s) ≈ 165 Byte ≈ 1,5 s inkl. TXDelay; Binär brächte nur ≈ 0,3 s mehr, wäre aber im Monitor unlesbar und müsste am Binärfilter (CR12) vorbei. Entschieden: Nummern + kompakter Klartext, nur bei Änderung, höchstens alle 2 Minuten (< 1,5 % Kanal).

**Lösung** (Protokoll: PLANUNG.md 12.4 und 14.6):
- **Teilnehmernummern:** Jede Station bekommt beim Betreten eines Boards die kleinste freie Nummer 1…n; sie bleibt, solange die Station im Board ist, und wird danach wieder frei. Neue Cap `NUM` beim `//CLIENT`-Handshake. Für NUM-Clients: `//WHO 1 OE3GAS=/- 3 OE3TEC-1`, Ereignisse `+2 OE3TEC-1 /-`, `-2`, `=2 /k`, `%2 4 3 ?`. `//OK` nennt zusätzlich `q=50/30/20/5,10,20,35,50` (Fenster, Minuten, Mindest-Frames, Balkenschwellen).
- **Alte Clients ohne `NUM`:** bekommen weiterhin die Rufzeichenform – der UI-Frame trägt die Nummernform, alte UI-Clients erhalten die alte Zeile zusätzlich als I-Frame (gleiche Folgenummer, der Client dedupliziert). `//RESEND` liefert ihnen ebenfalls die alte Form.
- **Statusframe `%Q`:** `%Q <n> <Balken> <out Frames> <out Wdh> <in Frames> <REJ tx> <Wdh rx> <REJ rx> <T1> <Netto/100> <Wdh/100> <RX gesendet> <RX verpasst> <SRT·10>;…` – alle Teilnehmer mit Daten, Fensterwerte wie in der Sysop-GUI. **Ohne Folgenummer**, wird nie nachgefordert (der nächste bringt frischere Werte), zählt nicht für die Empfangsquote. Nur an NUM-Clients: einmal als UI-Frame, per I-Frame an Clients ohne UI.
- **Client:** Teilnehmer in der Liste antippen öffnet die Detailansicht: große Balken, drei Richtungskacheln (outgoing, incoming, rx quote) mit Frames, Verlusten und Formel, Schwellenleiter mit Rechnung inkl. T1-Abzug, Zähler (REJ rx, T1, Netto/Wdh, SRT), Alter der Daten. Rechnung im Client nach denselben Regeln wie `linkq.py`, Schwellen aus `q=`.
- Client-Version 2026.10.13.2. Tests: `test_clientproto.py` (`test_member_numbers`), `test_linkq.py` (`test_qstat_line_for_num_clients`, `ClientQualityTests`), `test_tbclient.py`.

## CR34 – Bildübertragung schneller (✅ 13.10.2026)

**Problem:** Ein Bild (8 kB) brauchte ≈ 3 Minuten. Der Client gab die Bytes in 256-Byte-Stücken mit 2 s Pause an Direwolf und wartete je Stück auf die Bestätigung; dazu 128-Byte-Frames fest im Client (`links.py`) und in der TinyBox (`paclen`). Das AX.25-Fenster war nie gefüllt, jede Sendung ein eigener Durchlauf (TXDelay, ACK, Pause): ≈ 45 B/s. Analyse und Rechnung: PLANUNG.md 12.10a.

**Lösung:**
- Frames 256 Byte (Client fest, TinyBox `paclen = 256`, `max_outstanding = 6`).
- Upload am Stück an Direwolf; die Chat-Zeile mit dem Verweis geht gleich hinter den Bytes raus (ein Wechsel weniger). Fortschrittsbalken aus AGW `Y`; Stillstand erst nach 120 s ohne Bewegung ein Fehler.
- `direwolf.conf` beide PCs: `PACLEN 256`, `MAXFRAME 4`, `EMAXFRAME 6` (sonst ginge mit v2.2 das ganze Bild als eine 60-s-Sendung raus).
- Dialog: Größenwahl **klein / normal / groß** (2 / 4 kB / Board-Limit, 192 / 256 / 320 px), Wahl bleibt im Browser; `[images] target_bytes` (4096) und `bytes_per_sec` (100) im Client, `piece_bytes`/`pause_sec` entfallen.
- Erwartung: ≈ 115 B/s, 4-kB-Bild in ≈ 35 s, 8 kB in ≈ 70 s. Nach den ersten Funkmessungen `bytes_per_sec` nachziehen.
- Client-Version 2026.10.13.4. Tests: `test_tbclient.py` (`ImageTests`, `ImageHoldTests`).

## CR35 – Bekanntes Bild nochmal senden (✅ 13.10.2026)

**Problem:** Ein Bild, das schon einmal übertragen wurde, ließ sich nicht erneut in den Chat stellen – der Upload „verschwand“ kommentarlos. Log 13.10., 22:50: `//IMGPUT 22cec8 8008` → sofort `//IMGOK 22cec8`, danach nichts mehr. Die TinyBox erkennt am Hash, dass sie das Bild hat, und verlangt die Bytes nicht nochmal (`//IMGOK` statt `//IMGGO`) – gewollt, spart Airtime. Der Client wertete das aber als „fertig“ und schickte die Chat-Zeile mit dem Verweis nie; die geht sonst erst hinter den Bytes raus (`_send_all`).

**Lösung:** Kommt `//IMGOK` ohne vorheriges `//IMGGO`, sendet der Client nur die Chat-Zeile (`~#<hash>…` + Bildtext). Das Bild erscheint wieder im Chat, die anderen Stationen holen es wie sonst von der TinyBox bzw. haben es schon. Upload-Status trägt `known=True`. TinyBox unverändert.

- Client-Version 2026.10.13.5. Test: `test_tbclient.py` (`ImageHoldTests.test_known_picture_sends_only_the_chat_line`).

## CR36 – Bildgröße im Chat und Größenwahl im Dialog (✅ 14.10.2026)

**Problem:** Ein „small“-Bild (gröbere Auflösung) wurde im Chat genauso groß angezeigt wie ein „large“-Bild – die Bubble streckte jedes Bild auf 240 px. Die Wahl im Dialog bestimmte nur die Bytes, auf dem Schirm war kein Unterschied. Außerdem standen die Zahlen (Pixel, Bytes, Dauer) nur als Hinweistext unter den drei Größenknöpfen.

**Lösung:**
- Größenstufen jetzt **108 / 192 / 320 px** lange Seite (vorher 192 / 256 / 320) bei unverändert 2 kB / 4 kB / Board-Limit.
- **Anzeige in eigener Pixelgröße:** die Bild-Box folgt dem Bild (`fit-content`, höchstens 320 px bzw. 70 % der Fensterbreite). Der unscharfe Platzhalter vor dem Laden bekommt seine Breite aus den Bytes (die Pixel gehen nicht über Funk): bis ≈ 3 kB → 108 px, bis ≈ 6 kB → 192 px, sonst 320 px.
- **Dialog:** „Select size“ mit drei Knöpfen untereinander, jeder trägt seine Zahlen, z. B. `small (108×81), ~2.0 KB, ~30 s` – Pixel aus dem Seitenverhältnis des gewählten Bildes, Dauer aus `bytes_per_sec`. Rechts daneben nur die Bildunterschrift; die früheren Erklärtexte (Ergebniszeile, Hinweis über „Send“) sind weg, die Zahlen stehen ja in den Knöpfen. Die Zeile rechts bleibt für „Shrinking…“ und Fehlermeldungen. Unter 700 px Breite rutscht die Unterschrift unter die Knöpfe.
- Client-Version 2026.10.14.2 (Kosmetik nachgezogen). Nur Web-GUI (`index.html`, `app.js`, `app.css`), kein Protokoll berührt.

## CR37 – Ansichten im brocast-Listener (✅ 14.10.2026)

**Problem:** Drei Ansichten für eine Seite waren zwei zu viel. „Mit Trennlinien“ brachte gegenüber dem
Fließtext nur eine gestrichelte Linie je Unterseite. Im Fließtext standen die Teile-Knöpfe (`1/8`, `2/8`, …),
obwohl dort ohnehin alle Teile untereinander stehen – sie sprangen nur zum Anfang eines Teils. Und die
Teletext-Ansicht hieß zwar so, sah aber aus wie der Fließtext mit weniger Inhalt.

**Lösung:**

1. **„Mit Trennlinien“ entfällt.** Es bleiben **Fließtext** und **Teletext**; ein im Browser gemerktes
   `parts` fällt auf Fließtext zurück. Die Umschaltung steht jetzt bei *jeder* Seite (vorher erst ab zwei
   Teilen), damit auch eine einteilige Seite als Teletext gelesen werden kann.
2. **Fließtext ohne Teile-Knöpfe.** Dort steht nur noch rechts die Umschaltung „Ansicht“. Die Knöpfe
   (mit ◀ ▶) gibt es im Teletext, wo sie wirklich blättern.
3. **Teletext-Optik.** Die Seite wird als schwarzer Bildschirm gezeichnet: eigene Pixelschrift, 40 Zeichen
   je Zeile, Zeilenabstand 1,65 (bewusst luftiger als das enge Original-Raster – das war am Bildschirm zu
   gedrängt). Kopfzeile wie beim Teletext: Rubrik links im roten Feld, Station und Seitennummer rechts,
   darunter der Titel in Gelb. Farben nach Bedeutung: Überschriften gelb, Hinweise/Tabellenköpfe cyan,
   Warnungen gelb, Alarme rot, fehlende Teile magenta.
   - Die Schrift (`brocast/brocast/web/teletext.woff`, 5,8 kB, 228 Zeichen) entsteht aus einem
     7 × 13-Pixel-Raster: `brocast/tools/build_teletext_font.py` rastert DejaVu Sans Mono **Bold** bei 10 px
     in reinem Schwarz-Weiß und macht aus jedem Pixel ein Quadrat im Umriss. Die fette Schnittlage liefert
     2 Pixel breite Striche – das ist der grobe Teletext-Eindruck. Bei `font-size: 32px` ist ein Schriftpixel
     genau zwei Bildschirmpixel (am Handy 24 px), daher die harten Kanten.
   - Ausgeliefert wird sie vom Listener selbst (`/teletext.woff`, CSP `default-src 'self'` – kein
     Internet, keine Google Fonts).
   - **Der Teletext-Bildschirm ist immer Text:** Wetterkacheln und das Wetterraster (CR-Vorgänger,
     PLANUNG 6g) erscheinen dort als Werteliste bzw. als einfache Tabelle, und der Knopf
     „Grafisch/Text“ wird in dieser Ansicht ausgeblendet. Er gilt für den Fließtext.

Vorschau ohne laufenden brocastd: `brocast/mockup/teletext-vorschau.html`.
Betrifft nur den Listener (`app.js`, `app.css`, `webserver.py`, `listener_api.py`) – kein Protokoll, keine
Änderung an dem, was über Funk geht.

## CR38 – Teletext-Kopf, Zeilenabstand und Bildkonverter (✅ 14.10.2026)

**1. Zeilenabstand auf Zeichenhöhe.** 1,65 war gut zwei Zeichenhöhen Luft zwischen den Zeilen – zu viel.
Jetzt 1,125 (18 von 16 Schriftpixeln): zwischen zwei Zeilen bleibt genau eine Zeichenhöhe. Die Zahl ist so
gewählt, dass der Zeilenabstand bei `font-size: 32px` volle 36 Bildschirmpixel sind; bei krummen Werten
säße jede zweite Grundlinie auf einem halben Pixel und die Schrift würde verwischen.

**2. brocast-Schriftzug über jeder Teletext-Seite.** Vorbild ist die ORF-Teletext-Titelseite (Vorlage von
OE3GAS): ein Feld aus lauter hellen Quadraten mit schwarzen Fugen, der Schriftzug steht als ausgesparte,
schwarze Fläche darin, darunter die rote Linie.

- Erzeugt von `brocast/tools/build_logo.py` nach `brocast/brocast/web/brocast-logo.svg` (5,7 kB):
  Raster 6 Einheiten je Zelle (davon 5 das helle Quadrat), Buchstaben aus Liberation Sans Bold
  (Arial-Nachbau wie auf der Vorlage), schwarz-weiß gerastert; die Schriftgröße wird automatisch so
  gewählt, dass der Schriftzug in die Feldbreite passt (91 × 20 Zellen).
- SVG mit `shape-rendering="crispEdges"`, Breite 100 % des Bildschirms – bei 40 Zeichen × 14 px sind
  das genau 560 px, also 1 SVG-Einheit = 1 Bildschirmpunkt.
- Ausgeliefert vom Listener selbst (`/brocast-logo.svg`, CSP `img-src 'self'`).

**3. Bildkonverter (neu).** `py -3 -m brocast bild <datei>` macht aus einem Bild eine Teletext-Bildseite –
ASCII-Art-Prinzip, nur sechsmal feiner.

- **Nur im station-Betrieb:** der Befehl liest `brocastd.conf` und bricht bei `mode = listener` ab.
- **Darstellung:** ein Zeichen trägt 2 × 3 Felder (Sextanten `U+1FB00…U+1FB3B` plus Leer-, Halb- und
  Vollblock, `brocast/mosaic.py`). Ein Bild ist damit ganz normaler Text in `pre`-Blöcken – **keine neue
  Blockart, kein neues Dictionary** (bleibt v2). Der Listener erkennt ein Bild daran, dass der Block nur
  aus Mosaikzeichen besteht, und zeichnet es mit Zeilenhöhe 0,75 em lückenlos; die Zeichen dafür sind in
  der Pixelschrift gezeichnet statt gerastert, damit die Felder exakt aneinanderstoßen.
- **Bytes:** je Zeichen vier Bytes UTF-8, davon sind aber drei bei allen gleich – mit dem
  Preset-Wörterbuch (PLANUNG 6e) bleiben rund 0,9 Byte je Zeichen. Gemessen: 40 × 16 Zeichen
  (80 × 48 Punkte) = 2 096 Byte roh → **514 Byte gepackt, 3–4 Frames**. Eine eigene 1-Byte-Kodierung
  käme auf 370 Byte – die 40 % mehr sind es wert, dafür bleibt die Seite reiner Text.
- **Aufruf:** ohne weitere Angabe nur Vorschau im Fenster samt Byte- und Frame-Zahl; `--senden` gibt die
  Seite an das laufende brocastd (Ingest-API, Lieferant `bild`, Schlüssel = Dateiname → neue Revision
  statt neuer Seite), `--tinybox ORDNER` legt sie als **Bulletin** in den TinyBox-Eingang (Kopfzeile
  `Brocast:` wie bei den GeoSphere-Skripten, Text in der Mailbox ist dasselbe Mosaik).
  Dazu `--spalten` (Breite in Zeichen, max. 40), `--invert`, `--hart` (harte Schwelle für Zeichnungen
  statt Fehlerstreuung), `--titel`, `--text`, `--rubrik`, `--gueltig`.
- **Pillow** wird nur für diesen Befehl gebraucht; fehlt es, sagt der Befehl das und bricht ab.

Tests: `brocast/tests/test_mosaic.py` (Zeichentabelle gegen die Unicode-Namen, Raster, Seitenverhältnis,
Blockgrößen, Frames, und ob die Pixelschrift jedes Mosaikzeichen kennt).
Vorschau: `brocast/mockup/teletext-vorschau.html` (Textseite und Bildseite).

## CR39 – Rubriken in der Seitenleiste der Web-GUI (✅ 14.10.2026)

**Problem:** Die Rubriken standen nur in der Karte „Rubrics" auf dem Dashboard. Wer in den Messages
arbeitete, musste erst aufs Dashboard zurück, um auf eine Rubrik zu filtern.

**Lösung:** In der Seitenleiste unter *Messages* der aufklappbare Punkt **Rubrics** (Pfeil ▾/▸, daneben die
Zahl der Rubriken).

- Darunter je Rubrik eine Zeile mit Name und `Bulletins (ungelesen)`; ein Klick öffnet die Messages,
  gefiltert auf diese Rubrik (wie bisher die Dashboard-Karte, inklusive Chip „Rubric XY ✕" zum Aufheben).
  Die gewählte Rubrik ist in der Seitenleiste markiert.
- Reihenfolge wie in `[rubrics]` der `tinybox.conf`, danach `TBNEWS` und die Rubriken, die nur durch
  Bulletins existieren. Eine abgelehnte Rubrik (`NAME = -`) steht durchgestrichen und grau da,
  der Tooltip nennt den Grund („refused" / „not in [rubrics] of tinybox.conf").
- Auf- und zugeklappt bleibt im Browser gemerkt (`localStorage tinybox.rubrics`), Standard aufgeklappt.
- Die Liste kommt aus `GET /api/rubrics` – dieselbe Quelle wie die Dashboard-Karte, die jetzt denselben
  Zwischenspeicher nutzt (ein Abruf je Aktualisierung statt zwei). Keine Änderung am Server.

Nur Sysop-Oberfläche, daher keine neue Client-Version und keine TBNEWS.

## CR40 – Sync beim Anmelden: nur Köpfe, Text auf Abruf (✅ 15.10.2026)

### Umsetzung (15.10.2026)

Client-Version **2026.10.15**. TinyBox und Client müssen beide aktualisiert werden (neue Cap `SHORT`);
ein alter Client an einer neuen TinyBox und umgekehrt funktionieren weiter (dann ohne `short=`).

- **TinyBox – Frist je Rubrik:** `[rubrics] NAME = Beschreibung | Tage` (auch `7d`), `0` = nie löschen,
  ohne Angabe gilt `[mailbox] bulletin_expire_days`. `purge_expired()` löscht je Rubrik; die Web-GUI zeigt
  „kept 7 d" in der Rubrik-Karte und im Tooltip der Seitenleiste (`/api/rubrics` liefert `expire_days`).
- **TinyBox – `//SYNC … short=<n>`** (Cap `SHORT`): nur Texte persönlicher Mails bis `n` Byte gehen mit.
- **TinyBox – Terminal:** Ausgaben über 10 Zeilen beginnen mit `*** 37 lines follow - send A to abort` und
  laufen dann komplett durch; `A` verwirft, was noch in der Warteschlange liegt (was Direwolf schon hat,
  höchstens `max_outstanding` Frames, geht noch hinaus). Über Telnet wirkt `A` nicht (wird sofort geschrieben).
  Die Seitenteilung von CR29 (`--More--`) ist weg.
- **Client – Abgleich nach jeder Anmeldung:** 1,5 s nach `//OK` startet der Scope `login` (Postausgang,
  Mail-Köpfe, dann Köpfe der abonnierten Rubriken). Abschaltbar mit `[sync] on_login = no`.
  Auch der Knopf „Sync“ holt nur noch Köpfe.
- **Client – kurz:** `[sync] short_bytes` (Vorgabe 256, 0 = nie); steht ein Eintrag in der conf, gilt dieser.
  Ohne Cap `SHORT` (alte TinyBox) holt der Client die kurzen Texte mit einem `//GET`.
- **Client – Text beim Anklicken:** `POST /api/mail/fetch {"id": n}`. Der Reader zeigt „Loading the text
  (1.2 KB) – text #12 (1.2 kB, approx. 15 s)… [Abort]“ und dann den Text. Ohne Verbindung:
  „Not connected – the text cannot be fetched now.“, nichts wird vorgemerkt. Ein Klick während eines
  Abgleichs geht zwischen zwei Wechseln hinaus. In der Liste steht bei fehlenden Texten „not loaded · 1.2 KB“.
- **Client – Abort:** Knopf „✕ Abort“ in den Köpfen *Mail*/*Bulletins* (ersetzt „Cancel“), im Reader beim
  Laden eines Textes. `POST /api/mail/abort` (`/api/mail/cancel` geht weiter). Nach 30 s ohne Antwort
  harter Abbruch.
- **Client – Meldungen** (oben in der Ordnerliste, wegklickbar, und in der Konsole), z. B.
  `Mail: 27 mail header(s) (approx. 55 s) to fetch. Press Abort to stop at any time.`, dann
  `Bulletins: 40 bulletin header(s) (WX 30, DX 10) (approx. 1 min 10 s) to fetch. …` – nach einem
  vollständigen Abgleich verschwindet die Meldung wieder. Beim Abort:
  `Sync aborted. Still pending: 23 mail header(s), … It goes on from here at the next login or with Sync.`
- Tests: `test_rubrics.py` (`RubricValidity`), `test_mailsync.py` (`ShortTextTests`, `LoginSyncAbortTests`,
  `EstimateTests`, angepasst), `test_tinybox.py` (`PagingTests`), `test_agw.py`.

### Erfassung

**Wunsch (OE3GAS):** Meldet sich ein Client bei der TinyBox an, dann soll er

1. die **Köpfe aller Mails** bekommen – die eigene persönliche Post und die Bulletins der Rubriken,
   die er abonniert hat;
2. erst wenn er auf einen Kopf **klickt**, wird diese Mail bzw. dieses Bulletin (der Text) abgerufen.

**Heute:** Der Abgleich startet nur per Knopf, getrennt für *mail* und *bulletins*
(`POST /api/mail/sync`). Er holt die Köpfe (`//SYNC` / `//BSYNC`, CR26) und danach **alle fehlenden
Texte** (`_texts()` in `tbclient/sync.py`); kurze Texte hängt die TinyBox schon an die Delta-Antwort
(`want=`, PLANUNG 12.9 Stufe 2). Bei vielen Bulletins laufen so Texte über Funk, die nie jemand liest.
„Cancel“ (`/api/mail/cancel`) bricht heute hart ab (`task.cancel()` mitten im Wechsel).

### Entscheidungen (OE3GAS, 15.10.2026)

| # | Frage | Entscheidung |
|---|---|---|
| E1 | Kurze persönliche Mails gleich mitnehmen? | **Ja.** Bulletins nie – nur Köpfe. |
| E2 | Wann abgleichen? | **Bei jeder Anmeldung** automatisch (Mail + abonnierte Rubriken). Knopf „Sync“ bleibt für zwischendurch. |
| E3 | Erstes Anmelden (leere Mailbox) | 1) **alle Köpfe der persönlichen Mails**, 2) **alle Köpfe der abonnierten Rubriken** – **kein Limit**, keine „Weiter“-Abfrage. Der User entscheidet selbst mit „Abort“ (E4), wann Schluss ist. Die Menge ist ohnehin durch die Ablauffrist der Bulletins begrenzt. |
| E4 | Abbruch | **Abort-Knopf** für einen **geordneten** Abbruch (siehe unten). |
| E5 | Restanzeige | Beim **Start** des Transfers (nach dem Anmelden) und beim **Abort** eine Meldung: was ist noch ausständig + **geschätzte Zeit**. |
| E6 | Klick auf einen Kopf ohne Verbindung (kein Connect) | Meldung **„not connected“**, Anforderung **verwerfen** – nicht für das nächste Mal vormerken. |
| E7 | Was ist „kurz“? | **`short_bytes` = 256 Byte** als Vorgabe; steht ein Eintrag in `[sync]` der `tbclient.conf`, gilt dieser. Richtwert: „kurz“ ≈ **2 s** Sendezeit. |
| E8 | Hinweis auf Abort | **Zu Beginn** des Downloads wird der User auf die Abort-Möglichkeit hingewiesen, danach laufen **alle** Köpfe komplett durch. |
| E9 | Terminal (CR29) | Abort auch im Terminalbetrieb; damit **entfällt** die Seitenteilung zu 10 Zeilen mit „continue/abort“ (siehe unten). |

### „Kurz“ = 256 Byte (E7)

- Neue Einstellung `[sync] short_bytes` in der `tbclient.conf` (und `tbclient.conf.example`),
  **Vorgabe 256**, 0 = nie Texte mitnehmen. Steht der Eintrag in der conf, gilt dieser.
- 256 Byte = **1 Frame** (PACLEN 256), ca. 3–4 Zeilen Text. Bei 1200 Bd (~100–120 Byte/s netto)
  rund **2 s** Sendezeit – das ist Gerhards Maßstab für „kurz“.
- Passt mit den Köpfen in denselben Wechsel (`chunk_bytes` 1024, `want=`).
- Umsetzung: neuer Parameter `short=<n>` im `//SYNC`, die TinyBox hängt nur Texte persönlicher Mails
  ≤ `short` an; bei `//BSYNC` immer `want=0`. Alte TinyBox ohne `short=` → Client schickt `want=0`
  (nur Köpfe, Texte auf Klick).
- Längere persönliche Mails und alle Bulletins: nur Kopf, Text beim Anklicken.

### Ablauf beim Anmelden

1. Verbindung steht → Client startet von sich aus den Abgleich: zuerst persönliche Post (`//SYNC`),
   dann abonnierte Rubriken (`//BSYNC`), nur Köpfe (+ kurze persönliche Texte, siehe oben).
2. **Hinweis auf Abort** (E8) gleich beim Start, z. B. „Downloading headers – press Abort to stop at any time“.
   Danach laufen **alle** Köpfe ohne Limit und ohne Rückfrage durch (persönliche Post, dann jede abonnierte Rubrik).
3. **Startmeldung** (E5), sobald die erste Antwort da ist – erst dann ist der Umfang bekannt
  (`//SYNCEND <more>` liefert die Zahl der noch ausstehenden Köpfe), z. B.:
   > Sync started: 37 mail headers + 4 short texts, bulletins (3 rubrics) pending – approx. 1 min 40 s
4. Fortschritt in der Statuszeile wie heute (Schritt, n von m).
5. Liste zeigt die Köpfe sofort; Einträge ohne Text erkennbar (Symbol „nicht geladen“ + Größe in Byte).

### Geordneter Abort (E4)

- Knopf **„Abort“** sichtbar, solange ein Abgleich oder Textabruf läuft (ersetzt das bisherige harte Cancel).
- Geordnet heißt: der **laufende Wechsel wird noch fertig empfangen und gespeichert**, dann keine neue
  Anfrage mehr. Kein Abbruch mitten in einem Frame/Text, `seq` bleibt konsistent → der nächste Abgleich
  macht genau dort weiter.
- Wird der Abort gedrückt, während auf die Antwort gewartet wird, und kommt sie nicht binnen einer
  Frist (z. B. 2 × T1-Schätzung bzw. 30 s), dann doch harter Abbruch mit Hinweis.
- Die Verbindung zur TinyBox bleibt bestehen (Chat geht weiter); nur eine vom Sync selbst aufgebaute
  Verbindung (`own_connect`) wird getrennt.
- **Abort-Meldung** (E5), z. B.:
  > Sync aborted. Still pending: 21 mail headers, bulletins of 3 rubrics – approx. 1 min 05 s. Will continue at next login or with „Sync“.

### Zeitschätzung (Vorschlag)

- Restbytes ≈ ausstehende Köpfe × 90 Byte (`HEADER_BYTES`) + Größe der ausstehenden kurzen Texte;
  Bulletins: Zahl der Köpfe je Rubrik aus der Rubrikenliste (`max` gegen lokal höchste Nummer),
  sonst „unbekannt“.
- Zeit = Restbytes ÷ **gemessener** Durchsatz der laufenden Verbindung (Bytes/s der bisherigen Wechsel)
  + Anzahl Wechsel × `pause_sec`. Vor dem ersten Wechsel Annahme 1200 Bd ≈ 100 Byte/s netto.
- Anzeige gerundet („approx. 2 min“), keine Scheingenauigkeit.

### Text auf Klick

- Klick auf einen Kopf → Client holt genau diesen Text (`//GET <id>`, lange Texte über Funk mit
  `//PART`), zeigt „loading … (x Byte, approx. y s)“ und dann den Text; auch hier Abort möglich.
  Einmal geholte Texte bleiben lokal, ein zweiter Klick geht nicht über Funk.
- Neue Web-API, z. B. `POST /api/mail/fetch {"id": n}`, über denselben Syncer (nie zwei Abrufe
  gleichzeitig auf dem Kanal). Läuft gerade der Anmelde-Abgleich, wird der Klick danach bzw. zwischen
  zwei Wechseln bedient.
- **Keine Verbindung** → „not connected“, Anforderung verworfen (E6). Kein eigener Connect nur für den Klick.
- Gelesen-Meldung (`r=` im nächsten `//SYNC`) erst, wenn der Text wirklich angezeigt wurde.

### Ablauffrist der Bulletins

- Bulletins werden nach einer Frist gelöscht; das begrenzt, wie viele Köpfe ein neuer Client überhaupt
  bekommen kann – deshalb ist kein Limit nötig.
- **Heute** gibt es dafür nur **eine** Frist für alle Rubriken: `bulletin_expire_days` (Vorgabe 30) in
  `[mailbox]` der `tinybox.conf`; `purge_expired()` löscht, der Client sieht es über die Tombstones (`//D`).

### Terminal: Abort statt Seitenteilung (E9, ersetzt CR29)

- Heute (CR29): Ausgaben über 10 Zeilen kommen seitenweise (`PAGE_LINES = 10` in `session.py`) mit
  `--More (10/37)-- Enter = continue, A = abort:`.
- Neu: **zu Beginn** einer langen Ausgabe (> 10 Zeilen) ein Hinweis, z. B.
  `37 lines follow - send A to abort`, dann läuft die Ausgabe **komplett** durch, ohne Rückfrage.
- Abort: Eingabe `A` / `Q` / `/AB` während der Ausgabe → die TinyBox schickt nichts mehr nach, Abschluss
  `*** aborted, 21 lines skipped`.
- Technische Grenze: Was schon an Direwolf/AGW übergeben ist, geht noch hinaus. Damit der Abort greift,
  gibt die TinyBox die Ausgabe **portionsweise** an Direwolf (z. B. ~2 Frames vorgehalten, Rest erst wenn
  diese bestätigt sind – AGW `y`/Outstanding-Frames) und prüft dazwischen auf Eingaben.
- Ergibt einen TBNEWS-Hinweis (Bedienung im Terminal ändert sich).

### Entschieden zuletzt

- Ablauffrist: **jede Rubrik bekommt vom Sysop eine eigene Dauer** (Gerhard, 15.10.2026).

## CR41 – KISS-Mode: Kanal- und kisshub-Werte in der Web-GUI (✅ 15.10.2026)

**Problem:** Im KISS-Mode kennt die TinyBox nur ihre eigenen AX.25-Verbindungen. Ob der Kanal voll
ist, ob der TNC hinter kisshub überhaupt arbeitet oder ob Frames im Hub warten, ist nicht sichtbar.
Das führt zu Fehldeutungen beim Qualitäts-Monitoring (T1-Abläufe durch Kollisionen, hängenden TNC
oder volle Hub-Warteschlange sehen aus wie eine schlechte Funkstrecke). Außerdem zeigt die
Kopfzeile grün „connected", solange kisshub läuft – auch wenn der TNC tot ist.

KISS kann grundsätzlich nicht liefern: Trägererkennung (DCD), Signalstärke, verworfene Frames mit
Prüfsummenfehler, tatsächlicher Sendezeitpunkt. Gemessen wird nur, was als gültiger Frame ankommt
oder hinausgeht.

**Weg 1 – Kanal (TinyBox rechnet selbst, aus dem KISS-Datenstrom):** kisshub reicht jeden
empfangenen Frame und die Aussendungen der anderen Clients (brocastd) an die TinyBox weiter.

- Kanalauslastung in % (letzte Minute, letzte 10 Minuten), geschätzt aus Framelänge, Funk-Baudrate
  und TXDELAY; Anteil eigene Aussendungen / andere.
- Frames pro Minute der letzten 60 Minuten.
- Gehörte Stationen (MHEARD): Rufzeichen, Frames, Sendezeit, zuletzt gehört.

**Weg 2 – kisshub (Status-Abfrage `GET http://127.0.0.1:8102/status`, JSON, nur lokal):**

- TNC: Profil, Zustand (down / init / kiss) seit wann, Anzahl Initialisierungen und Portverluste,
  letzter Fehler, die letzten Init-Zeilen mit Antwort.
- Sendewarteschlange: Länge je Priorität, Wartezeit im Hub (Mittel/Maximum der letzten 10 min,
  getrennt für Steuer-Frames und I-Frames), verworfene Frames.
- Clients: Adresse, verbunden seit, Frames in/out, Sendezeit, Absender-Rufzeichen (daran erkennt
  man TinyBox und brocastd).
- Die TinyBox fragt im Takt von `quality_poll_sec` (30 s) ab. `[kiss] status_port` (Standard 8102,
  0 = aus), in kisshub `[server] status_port`.

**Anzeige (nur Sysop-Web-GUI):**

- Kopfzeile im KISS-Mode: statt „Direwolf connected via KISS" der TNC und sein Zustand, z. B.
  „PK-232 ready via KISS"; rot bei TNC nicht bereit oder kisshub nicht erreichbar.
- Dashboard: Karte **Channel** mit Auslastung, Frames/min als Mini-Verlauf, gehörte Stationen,
  TNC-Zustand und Wartezeit im Hub.
- Detailansicht eines Users: Kanalauslastung der letzten 10 min neben den Balken.
- Sysop-Konsole `STATUS`: TNC-Zustand in der Radio-Zeile.

Die Kanalauslastung fließt **nicht** in die Balken ein, sie steht daneben.

Nur TinyBox, kisshub und Sysop-Oberfläche, daher keine neue Client-Version und keine TBNEWS.

**Umgesetzt (15.10.2026):**

- `tinybox/chanmon.py` – Kanalmonitor: jeder Frame aus dem KISS-Strom und jeder eigene;
  Auslastung 1/10 min (TinyBox / andere), Frames und Belegung je Minute (60 min), gehörte Stationen
  mit Pfad. Nur im Speicher.
- kisshub: `GET http://127.0.0.1:8102/status` (`[server] status_port`, 0 = aus) mit TNC-Zustand,
  Init-/Weck-Dialog (letzte 20 Zeilen mit Antwort, ok/nicht ok), Initialisierungen, Portverlusten,
  letztem Fehler, Warteschlange je Priorität, Wartezeit im Hub (Mittel/Maximum, 10 min), verworfenen
  Frames, Clients mit Absender-Rufzeichen und Sendezeit. Neu: Frames, die länger als 30 s warten
  (TNC nicht bereit), werden verworfen statt verspätet gesendet.
- TinyBox: `[kiss] status_port` (Standard 8102), Abfrage alle `quality_poll_sec`;
  `GET /api/channel`; `/api/status` und `/api/sessions/<call>/linkq` um `radio` bzw.
  `channel_load` ergänzt.
- Web-GUI: Kopfzeile „PK-232 ready via KISS" (rot: „kisshub not connected", „PK-232 down",
  „initialising"; Tooltip mit dem Fehler), Dashboard-Karte **Channel** (Kacheln Busy 1 min /
  10 min / Wartezeit im Hub, Verlauf je Minute TinyBox/andere mit Tooltip, kisshub-Werte,
  aufklappbarer TNC-Dialog, Heard-Liste), Kanalauslastung in der Detailansicht unter den Balken.
- `STATUS` in der Sysop-Konsole: „connected (KISS …), TNC PK-232 kiss".
- 13 neue Tests (`tests/test_chanmon.py`).

## CR42 – Freier Connect (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Bisher war das Ziel fest `[tinybox] call` (OE3GAS-1). Der Client soll jede Station
connecten können; die Eingabe des Rufzeichens erfolgt in der Titelleiste („Connect to:“).
Icons: von OE3GAS beigestellt (Connect, Connecting, Connected, Disconnect, Disconnected,
Connect failed).

### Entscheidungen (OE3GAS, 15.10.2026, nach Entwurf)

1. Titelleiste immer **einzeilig**.
2. Links das eigene Rufzeichen.
3. Ganz rechts Disconnect (solange eine Verbindung besteht oder aufgebaut wird),
   Kuvert bzw. Sprechblase (Mail/Chat) und das Menü.
4. Nicht verbunden: Eingabefeld, nicht zu breit (9 Zeichen).
5. Der Connect-Knopf gleich rechts neben dem Eingabefeld.
6. connecting mit Zähler; die Statusanzeige immer rechts neben dem Rufzeichenpaar.
7. connected mit I-Frames bzw. UI.
8. disconnecting nur als Status, bis die Verbindung weg ist; dann wieder das Eingabefeld.
9. Das Feld merkt sich die letzten Eingaben.

### Umsetzung

- **Ziel:** `ClientCore.target` statt `cfg.tinybox_call`; `POST /api/connect
  {"target": "OE3XBS-8"}` (ohne `target`: das zuletzt verwendete). Prüfung wie in der
  Config (Rufzeichen, SSID 0–15), nicht das eigene. Telnet-Link: immer die eigene TinyBox.
- **Verlauf:** die letzten 10 Ziele, neueste zuerst, in `settings.json` des Clients
  (`recent`, `target`) – damit am Handy dieselbe Liste wie am PC. Im Feld als Auswahlliste;
  leeres Feld + Enter = das zuletzt verwendete Ziel (steht als Platzhalter im Feld).
- **Heim-TinyBox:** `[tinybox] call` bleibt die eigene TinyBox. Die Mailbox gehört zu ihr:
  Abgleich beim Anmelden, Sync-Knopf und Text auf Klick nur, wenn man mit ihr verbunden ist
  (oder offline – dann connectet der Sync wie bisher selbst, immer zu ihr). Der Hinweis auf
  neue Post (UI an TBMAIL) zählt nur von ihr. `auto_connect` geht zu ihr.
- **Einstellungen je TinyBox:** letztes Board, „gesehen bis“ (History) und MOTD gelten je
  Ziel (`settings.json` → `targets`); die Heim-TinyBox behält sie wie bisher oben.
- **Zustände:** neu `disconnecting` (Direwolf meldet sich mit `d`, wenn die Verbindung weg
  ist; ohne Antwort nach 90 s trotzdem offline). Wie die letzte Verbindung endete, steht in
  `ended`: `user` (selbst getrennt), `failed` (kam nicht zustande: „no answer from …“),
  `remote` (von der Gegenstelle oder Direwolf-Verlust: „disconnected by … · hh:mm“).
- **connecting-Zähler:** Sekunden seit dem Connect. Die SABM-Versuche selbst meldet
  Direwolf über AGW nicht, daher keine „Versuch n/10“-Anzeige.
- **Titelleiste:** Logo, Avatar, eigenes Call, Zustands-Icon, dann entweder
  „Connect to:“ + Feld + Connect-Knopf oder das Ziel-Call, Punkt und Statustext; rechts
  Disconnect, Mail/Chat, Menü. Am Handy (≤ 520 px) ohne Logo und ohne „Connect to:“-Text,
  ≤ 400 px auch ohne Avatar. Icons: `tbclient/web/conn/*.png` (aus der Vorlage
  ausgeschnitten, das Grau für die dunkle Leiste hell gemacht).
- Tests: `FreeConnectTests` in `tests/test_tbclient.py` (Fehl-Connect, fremde BBS,
  disconnecting, Verlauf über Neustart, Einstellungen je Ziel, Disconnect ohne Antwort).

## CR43 – Terminalmodus (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Frage: Wie sieht das aus, wenn man mit dem Client eine andere BBS connectet, die kein
TinyBox-System ist? Können wir eine Art Terminalmodus bieten?

### Befund vorher

Der Client wartete auf „Welcome to TinyBox“ und schickte nach 6 s **trotzdem**
`//CLIENT TB1 …`. Bei einer BPQ- oder FBB-Box landete diese Zeile als Befehl in deren
Prompt, die Oberfläche zeigte leere Boards.

### Umsetzung

- **Erkennung:** Nach dem Connect gilt die Gegenstelle als TinyBox, wenn „Welcome to
  TinyBox“ kommt. Bleibt das 6 s aus, bekommt nur eine **bekannte** TinyBox den Handshake
  trotzdem (die Heim-TinyBox, der Telnet-Testport und jede, die schon einmal mit `//OK`
  geantwortet hat – `settings.json` → `tinyboxes`). Jede andere Station wird nicht mit
  `//CLIENT` behelligt: der Client geht in den Modus `terminal`.
- **Terminal:** Solange nicht feststeht, dass es eine TinyBox ist, wird jede empfangene
  Zeile unverändert ins Terminal gelegt; im Modus `terminal` wird nichts mehr als
  Steuerzeile (`//`) oder Chat-Ereignis (`#`) gedeutet. Eigene Zeilen gehen mit
  `POST /api/term {"text": "…"}` roh hinaus (CR, auch eine leere Zeile). Puffer: 500 Zeilen,
  die Oberfläche bekommt die letzten 300.
- **Ansicht:** Wird die Station als Terminal erkannt, schaltet die Oberfläche von selbst
  auf die Terminal-Ansicht (Monospace, eigene Zeilen blau, Zustandszeilen grau, unten
  Eingabezeile mit Pfeil hoch/runter für die letzten 50 Eingaben). Statustext
  „connected · terminal“; das Mail-Kuvert führt zur (lokalen) Mailbox, von dort `>_`
  zurück ins Terminal.
- **Von Hand:** Menü → „Terminal“ (am PC auch in der linken Spalte) öffnet die Ansicht auch
  bei einer TinyBox; getippte Zeilen gehen dann direkt an sie.
- **Zeichensatz:** UTF-8, sonst Latin-1 (wie bisher in `LineSplitter`).
- **Grenzen:** kein Binärtransfer (YAPP, 7plus), keine Bilder, keine Mailbox der fremden BBS.

## CR44 – Verbindungslogbuch (✅ 15.10.2026)

### Erfassung und Entscheidungen (OE3GAS, 15.10.2026)

Logbuch der Verbindungen in Client und TinyBox – keine Inhalte, nur Gegenstation,
Connect-Zeit, Disconnect-Zeit, Gesamtdauer und, wenn möglich, die Bytes hin und zurück.

1. Aufbewahrung **unbegrenzt**, Export als **CSV** und **ADIF**.
2. In der TinyBox sieht **jeder User seine eigenen Connects**.
3. Fehlversuche (SABM ohne Login) kommen in der TinyBox **nicht** hinein.
4. Frequenz (für ADIF) im Client: **beim Start des Clients einmal abfragen**, gilt für die
   ganze Sitzung; die zuletzt erfasste wird angeboten und kann übernommen oder
   überschrieben werden.

### TinyBox

- Tabelle `connlog` in der Datenbank: `call`, `via` (radio/telnet), `t_on`, `t_off`, `secs`,
  `rx`/`tx` (Nutzdaten-Bytes, gezählt im AGW-, KISS- und Telnet-Adapter),
  `air_tx`/`air_rx` (Bytes über die Luft inkl. Wiederholungen aus der letzten
  `Q`-Abfrage des Direwolf-Forks, sonst leer), `ended` (`bye` = von der TinyBox beendet,
  `disc` = von der Station, `lost` = Verbindung verloren). Geschrieben in `Session.end()`,
  genau einmal; die lokale Sysop-Konsole zählt nicht. Ein Fehler beim Schreiben bricht die
  Trennung nie ab.
- Befehl **`QSO`**: die letzten 10 Connects des eigenen Rufzeichens (alle SSIDs), `QSO 30`
  mehr (max. 100). Sysop: `QSO ALL [n]`, `QSO <call> [n]`. In der Hilfe (`H`).
- Sysop-Weboberfläche: Seite **Connection log** (Filter nach Rufzeichen, Knöpfe CSV und
  ADIF; `GET /api/connlog`, `/api/connlog.csv`, `/api/connlog.adi?call=…`).
- ADIF: `[station] freq` (MHz) und `[station] locator` in `tinybox.conf`; ohne `freq` fehlen
  `FREQ`/`BAND` in der Datei.

### Client

- `data/tbclient/connlog.db`: jede Verbindung, auch nicht zustande gekommene (`failed`
  = keine Antwort, `cancelled` = selbst abgebrochen; Dauer 0, ohne Bytes). Bytes =
  Nutzdaten am Link. `ended`: `user`, `remote`, `failed`, `cancelled`. Mit der Frequenz
  der Sitzung.
- **Frequenz:** Beim ersten Öffnen der Oberfläche nach dem Start fragt ein Dialog nach der
  Frequenz (letzte vorbelegt, „Skip“ = ohne). Änderbar unter Settings → Connection log.
- Settings → **Connection log**: die letzten 200 Einträge, Links CSV (alles) und ADIF (nur
  zustande gekommene Verbindungen, älteste zuerst). `[station] locator` in `tbclient.conf`.

### ADIF

ADIF 3.1.4 (`.adi`): `CALL`, `QSO_DATE`/`TIME_ON`, `QSO_DATE_OFF`/`TIME_OFF`, `MODE` = `PKT`,
`STATION_CALLSIGN`, `OPERATOR`, `FREQ`, `BAND`, `MY_GRIDSQUARE`, `COMMENT`. Rufzeichen ohne
SSID (Logbuchprogramme erwarten ein Rufzeichen); das volle Rufzeichen, Weg, Dauer und Bytes
stehen im `COMMENT`. Gemeinsamer Code: `tinybox/connlog.py`. Tests: `tests/test_connlog.py`,
`FreeConnectTests` in `tests/test_tbclient.py`.

## CR45 – Multi-Connect im Client (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Den Client zu einem Multi-Connect-Programm ausbauen: max. 5 Verbindungen gleichzeitig,
umschaltbar, jede Verbindung in einem eigenen Fenster (nicht gleichzeitig angezeigt, immer
nur abwechselnd).

### Vorschlag (Claude, 15.10.2026)

1. Kanalleiste unter der Titelleiste, Kanal 1–5, Umschalten per Klick oder Alt+1 … Alt+5;
   die Titelleiste (CR42) zeigt immer den aktiven Kanal.
2. Kanal 0 = Monitor (alles Gehörte), zählt nicht zu den 5.
3. Jeder Kanal mit seiner Ansicht: TinyBox → Chat/Mailbox, sonst Terminal.
4. Hintergrund-Aktivität am Kanal-Chip sichtbar.
5. Dieselbe Station nur einmal; Mailbox-Abgleich über den Kanal der Heim-TinyBox.
6. Kanal bleibt nach Disconnect mit Verlauf stehen, bis man ihn schließt.
7. Sendewarteschlange aller Kanäle im Monitor (gemeinsamer Funkkanal).

### Entscheidungen (OE3GAS, 15.10.2026)

- Zu 4: **Chip blinkt**, wenn im Hintergrund neuer Input kam; **rot blinkend**, wenn im
  Hintergrund ein Disconnect erfolgte.
- Nur **eine** TinyBox im Chat-Modus gleichzeitig; eine weitere TinyBox öffnet als Terminal.
- Telnet-Link: erreicht nur den Testport der eigenen TinyBox (nur auf `127.0.0.1`, also nur
  am TinyBox-PC – praktisch der Zugang des Sysops). Er bleibt **Einkanal-Betrieb**;
  Multi-Connect gibt es nur über Funk (`link = agw`).

### Umsetzung

- **Links:** `AgwPort` hält die eine TCP-Verbindung zu Direwolf (Registrierung, Monitor `k`)
  und verteilt die AGW-Frames nach Gegenstation an die `AgwLink`s – einer je AX.25-
  Verbindung. Ein neuer Connect beginnt mit frischem Zeilenpuffer und Zählern.
- **Kanäle** (`tbclient/channels.py`): Kanal 1–5, je ein Link mit eigenem Zustand
  (connecting … disconnecting), Ende, Terminalzeilen (500), Logbuch-Eintrag und einem
  Aktivitätszähler für das Blinken. Kanal 1 gibt es immer; weitere entstehen beim Connect
  und verschwinden mit dem Kreuz (nur getrennt). Die gleiche Station nur in einem Kanal.
- **Chat-Kanal:** Meldet sich eine TinyBox („Welcome to TinyBox“, oder nach 6 s eine
  bekannte), wird ihr Kanal der Chat-Kanal – sofern nicht schon ein anderer Kanal mit einer
  TinyBox im Client-Modus läuft; dann bleibt er Terminal. Boards, Mailbox, Bilder und Sync
  arbeiten immer mit dem Chat-Kanal. Der Mail-Abgleich ohne Verbindung öffnet einen eigenen
  Kanal zur Heim-TinyBox, der danach wieder verschwindet.
- **Monitor (Kanal 0):** jeder gehörte Frame als Zeile im Stil der klassischen Monitore
  (`fm OE3XYZ to APRS via OE1XAR <UI>: …`, `<I 3,2>`, `<SABM+>`, `<RR 4>`); in der
  Kopfzeile, wie viele Frames je Kanal noch bei Direwolf warten (AGW `Y`, alle 3 s).
- **Oberfläche:** Kanalleiste unter der Titelleiste (Chips mit Nummer, Zustandspunkt,
  Rufzeichen, „chat“ beim Chat-Kanal), „+ new“, Kreuz zum Schließen, Alt+0 … Alt+5. Die
  Titelleiste (CR42) zeigt immer den aktiven Kanal. Chat-Kanal → Chat/Mailbox, jeder
  andere Kanal → Terminal. Der Browser holt mit `/api/state?ch=n` nur die Zeilen des
  gezeigten Kanals; beim Umschalten wird die wartende Abfrage abgebrochen.
- **Blinken:** blau blinkend bei neuem Input im Hintergrund (Terminalzeile oder Chat),
  rot blinkend, wenn dort eine Verbindung von der Gegenseite getrennt wurde oder nicht
  zustande kam; selbst getrennte blinken nicht. Aufrufen des Kanals beendet das Blinken.
- API: `POST /api/connect {"target", "ch"}`, `/api/disconnect {"ch"}`,
  `/api/channel/close {"ch"}`, `/api/term {"text", "ch"}`.
- Tests: `FreeConnectTests` (TinyBox-Chat und BBS-Terminal parallel, zweite Station gleich
  nicht doppelt, nur eine TinyBox im Client-Modus, Kanäle schließen, Monitorzeilen).

## CR46 – Client über kisshub (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Der Client soll auch mit dem kisshub arbeiten, wenn ein KISS-TNC am PC hängt – damit ist er
allein, ohne TinyBox, ein vollwertiges Packet-Radio-Programm. Ohne Eintrag bleibt
`link = agw` (Direwolf).

### Umsetzung

- `tbclient.conf`: `[tinybox] link = kiss`, dazu `[kiss]` (host, port 8101, status_port
  8102, channel, air_baud, txdelay_ms) und `[ax25]` (version, paclen, maxframe,
  maxframe_ext, srej, n2, T1/T2/T3) – dieselben Werte wie `[ax25]` der TinyBox.
- `tbclient/kisslink.py`: `KissPort` (KISS-TCP zum kisshub über `tinybox.ax25.kissio`,
  Router Frame → Verbindung, Timer aller Verbindungen, Monitor) und `KissLink` (eine
  `Ax25Link` aus `tinybox/ax25` je Kanal, gleiche Schnittstelle wie `AgwLink`). Gesendete
  Frames halten die Timer der anderen Verbindungen an (ein Sender für alle), gehörte
  ebenso (Halbduplex). Stationen, die SABME mit DM beantworten, werden gemerkt (nächstes
  Mal SABM).
- **Gründe beim Trennen:** normal/Zeitüberschreitung → „disconnected“ (beim Connecten
  „no answer from …“), DM → „refused (DM)“, Retries aus → „link lost (no answer)“.
- **kisshub-Status:** alle 30 s `GET /status` (welcher TNC, im KISS-Modus?). Monitor-Kopf
  z. B. „PK-232 ready via KISS · 22 frames · waiting to send 1: 0, 2: 0“; ist der kisshub
  (oder bei AGW Direwolf) nicht erreichbar, zeigt das die Titelleiste rot.
- **Eingehende Connects** (KISS und AGW): ruft eine Station uns an, nimmt sie der erste
  freie Kanal als Terminal; der Chip blinkt. Kein Kanal frei oder die Station schon
  verbunden → DM (KISS) bzw. sofortiges Trennen (AGW).
- **Monitor:** zeigt mit KISS auch die eigenen Frames; Paare, die nach SABME mit
  Modulo 128 arbeiten, werden mit zwei Steuerbytes richtig gelesen (`<I 1,5>`).
- Mit KISS gilt die Verbindung als Funk wie AGW: Bilder (IMG), UI-Frames, Sync-Pausen.
- Tests: `tests/test_tbclient_kiss.py` (Chat mit der TinyBox über deren KISS-Adapter,
  Client zu Client mit eingehendem Connect, Fehl-Connect), AGW-Gegenstück in
  `FreeConnectTests.test_incoming_connect_over_agw`.

### Betrieb

kisshub lauscht nur auf `127.0.0.1`: Client und kisshub laufen auf dem PC mit dem TNC.
Start: `kisshub.bat`, dann `tbclient.bat`. TinyBox und Client können sich denselben
kisshub teilen (unterschiedliche Rufzeichen); kisshub gibt gesendete Frames auch an die
anderen Clients weiter.

## CR47 – Post sofort aussenden (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Wenn eine Mail vom User geschrieben wurde und in die Outbox geht, soll sie gleich
ausgesendet werden.

### Umsetzung

- Neuer Sync-Umfang **`send`**: nur die Outbox (`//SEND` je Mail), kein Abholen, setzt
  „last sync“ nicht. `ClientCore.send_outbox()` startet ihn gleich nach dem Speichern
  (`POST /api/mail/save`).
- **Verbunden mit der eigenen TinyBox:** geht über diese Verbindung, sie bleibt stehen.
- **Offline:** der Sync baut die Verbindung zur eigenen TinyBox in einem freien Kanal auf,
  sendet und trennt wieder (Kanal verschwindet).
- **Ein Abgleich läuft gerade:** die Mail geht gleich danach hinaus (`send_again`).
- **Chat-Kanal mit einer anderen TinyBox / Verbindung im Auf- oder Abbau / Bild-Upload
  / kein Kanal frei:** die Mail wartet in der Outbox; der Grund steht als Hinweis in der
  Mailbox. Sie geht mit dem nächsten Sync (auch dem nach dem Anmelden) hinaus.
- Hinweis im Composer: „Goes out right away to your TinyBox“.
- Tests: `SendAtOnceTests` in `tests/test_mailsync.py`.

## CR48 – Bake der TinyBox (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Eine Bake für die TinyBox-BBS: in der Konfiguration unter `[beacon]` steht, welcher Text
in welchem Intervall gesendet wird. Liegen neue Mails für User vor, kommt das in die
Bakenaussendung hinein.

### Umsetzung

- `tinybox.conf` `[beacon]`: `enabled` (Standard no), `interval_min` (5–1440), `dest`
  (Ziel des UI-Frames, Standard BEACON), `path` (bis 2 Digis, z. B. WIDE1-1), `text`
  (`{call}` = mailbox_call, `{qth}`), `mail_list` (yes), `first_after_sec` (60).
- `tinybox/beacon.py`: ein UI-Frame vom Mailbox-Rufzeichen, z. B.
  `TinyBox OE3GAS-1 - connect for mail and chat - Mail for: OE1ABC OE3TEC`. In die Liste
  kommen die Rufzeichen (ohne SSID, alphabetisch) mit **ungelesener persönlicher Post**
  hier – nur lokale Post, nicht wartende Forward-Post oder gehaltene. Gelesen → fällt aus
  der Liste. Mehr als in einen Frame passt (256 Byte): Rest als „+n“. Leerer Text und
  keine neue Post → keine Aussendung.
- AGW: mit Digi-Pfad als `V`-Frame, sonst wie bisher `M`; KISS: UI-Frame mit Pfad.
- Sysop-Konsole: **`BEACON`** sendet sofort und zeigt den Text (auch bei
  `enabled = no`, zum Testen). Die Werte stehen in der Sysop-Weboberfläche unter Settings.
- Nur TinyBox, daher keine neue Client-Version und keine TBNEWS.
- Tests: `tests/test_beacon.py`.

## CR49 – Suche in Mails und Bulletins (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Suchfunktion im Client und in der TinyBox, um in den Mails und Bulletins zu suchen:
String im Suchfeld eingeben → der Client zeigt die Mails bzw. Bulletins, die den String
enthalten.

### Umsetzung

- **Client:** Suchfeld über der Nachrichtenliste der Mailbox; ab 2 Zeichen sucht er beim
  Tippen (250 ms Pause) in allen Mails und Bulletins hier – Betreff, Text, Absender,
  Empfänger (bei Bulletins die Rubrik), @-Adresse; Groß-/Kleinschreibung egal. Treffer
  als eigene Liste „Search "…"“, neueste zuerst, mit Kennzeichen persönlich / Bulletin
  und Rubrik, bei Treffern im Text mit Ausschnitt. Leeres Feld → zurück zum Ordner davor.
  Gesucht wird nur, was hier liegt: Texte, die noch nicht geholt sind (CR40), nur über den
  Kopf; nicht abonnierte Rubriken gar nicht. `GET /api/mail?folder=s:<text>`,
  `MailStore.search()`.
- **TinyBox:** Befehl **`F text`** (auch `FIND text`): Liste wie `L`, nur Nachrichten, die
  der User sehen darf (eigene persönliche Post, alle Bulletins; Sysop alles). In der
  Hilfe und im Prompt. `MessageService.search()`.
- **Sysop-Weboberfläche:** Das Suchfeld bei Messages findet jetzt auch im Text
  (`GET /api/messages?q=…`), bisher nur Rufzeichen und Betreff.
- Tests: `tests/test_search.py`.

## CR50 – Monitor überarbeitet (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

1. Den Monitor unter „Settings“ entfernen – brauchen wir nicht mehr.
2. Wozu ist das „Terminal“ in der Seitenleiste, brauchen wir das noch?
3. Im Monitor das „fm“ entfernen, die Rufzeichen farblich unterscheiden – jedes durchgehend
   in derselben Farbe.
4. Suchfeld im Monitor: nur Zeilen mit dem Suchstring, auch bei neu hereinkommenden Frames.
5. Knopf „Clear“.
6. Welche speziellen Frames sendet die TinyBox? Filter, der nur diese zeigt.

### Umsetzung

1. Abschnitt „Monitor“ (die alte Protokollzeilen-Konsole) aus den Settings entfernt; der
   Eintrag „Monitor“ in der Seitenleiste schaltet jetzt auf Kanal 0. Die Konsole wird nicht
   mehr mit jedem Snapshot übertragen (spart Bandbreite im LAN).
2. „Terminal“ in der Seitenleiste bleibt, heißt jetzt **„TinyBox terminal“**: Es ist der
   einzige Weg, der TinyBox im Chat-Kanal klassische Befehle zu schicken (`L`, `R`, `F`,
   `QSO`, `J` …) – ein zweiter Kanal zur selben Station geht nicht (eine AX.25-Verbindung
   je Rufzeichenpaar). Für alle anderen Stationen ist das Terminal ohnehin die
   Kanalansicht.
3. Zeilen `20:59:00 OE1ABC → OE3GAS <I 0,0>: Hallo`; jedes Rufzeichen (mit SSID) bekommt
   aus einem Hash eine feste Farbe – dieselbe in jeder Sitzung.
4. Feld **Filter**: zeigt nur Zeilen mit dem Text (Zeit, Rufzeichen, Typ, Art, Inhalt;
   Groß-/Kleinschreibung egal); neue Frames werden beim Eintreffen gefiltert.
5. **Clear** leert den Monitor im Client (`POST /api/monitor/clear`).
6. Auswahl der **TinyBox-Sonderframes** (Kennzeichen am Ende der Kopfzeile):
   - `chat` – UI an `TBCHAT-n`: Chat-Ereignisse (`#seq` …) für Clients im UI-Modus
   - `quality` – `%Q`-Zeilen: die Zahlen hinter den Qualitätsbalken (UI an `TBCHAT-n`)
   - `mail` – UI an `TBMAIL`: Post-Hinweis „OE3ABC 2 new“
   - `beacon` – jede andere UI-Aussendung einer TinyBox (die Bake, CR48)
   - `proto` – I-Frames mit Client-Protokoll (`//CLIENT`, `//OK`, `//IN`, `//SYNC` …)
   Wählbar einzeln oder „all special frames“.
- **Nebenbei behoben:** I- und S-Frames mit Modulo 128 (AX.25 v2.2) wurden im Monitor
  falsch gelesen (Zeichen „�“ vor dem Text, falsche Zähler), wenn das eigene SABME nicht
  zu hören war (Direwolf zeigt die eigenen Frames nicht). Jetzt erkennt der Monitor
  Modulo 128 auch an der Lage der PID bzw. der Länge des S-Frames. Und „Welcome to
  TinyBox“ stand im TinyBox-Terminal doppelt.
- Tests: `RadioTests`/`FreeConnectTests.test_monitor_lines` in `tests/test_tbclient.py`,
  `tests/test_tbclient_kiss.py`.


## CR51 – TinyBox-Web-GUI: Liste bleibt beim Lesen sichtbar (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

Betrifft die Sysop-Web-GUI der TinyBox (http://127.0.0.1:8080/), nicht den Client.

1. Beim Öffnen einer Nachricht verschwindet die Liste, die Nachricht füllt die Seite, rechts
   steht immer das Formular „New message“. Die Übersicht soll sichtbar bleiben, der Text
   darunter angezeigt werden.
2. Das Formular „New message“ nur zeigen, wenn der Knopf „New message“ gedrückt wird – das
   ist ein eigener Vorgang. Beim Lesen fällt es weg; der Knopf „New message“ steht im Kopf
   der Liste.

### Umsetzung

1. `#/message/<Nr>`: oben die Nachrichtenliste (alle Spalten, Filter, Suche, Rubrik bleiben
   erhalten, ca. 38 % der Höhe), darunter die Nachricht mit Reply / Edit header / Kill. Die
   offene Zeile ist markiert. Ein Klick auf eine andere Zeile tauscht nur die Nachricht
   unten aus – die Liste behält ihre Scroll-Position.
2. Das Formular rechts beim Lesen ist entfernt. „New message“ (im Listenkopf) öffnet wie
   bisher `#/compose`. **Reply** führt jetzt ebenfalls dorthin, mit vorausgefülltem
   Empfänger und Betreff; „Cancel“ geht zurück zur Nachricht.
- Dateien: `tinybox/web/app.js` (`viewMessage`, `viewCompose`, `route`),
  `tinybox/web/app.css` (`main.split`). Nur die TinyBox, kein neuer Client.

## CR52 – TinyBox-Web-GUI: Monitor wie im Client (✅ 15.10.2026)

### Erfassung (OE3GAS, 15.10.2026)

1. Die Monitor-Ansicht der TinyBox für den Sysop so gestalten wie im Client (CR50): Rufzeichen
   farblich unterschieden, Suchfeld für Strings.
2. Frage: Sehen wir als Sysop die ausgesendeten Frames der TinyBox? Gemonitort werden sie
   bisher nicht.

### Umsetzung

1. **Monitor** (Seite und Karte im Dashboard):
   - Jedes Rufzeichen hat eine feste Farbe (Hash, wie im Client; dunkler für den hellen
     Hintergrund).
   - Feld **Filter**: nur Zeilen mit dem Text (Zeit, Rufzeichen, Typ, Art, Inhalt;
     Groß-/Kleinschreibung egal), auch für neu eintreffende Zeilen.
   - Auswahl: alles · Kanal-Frames · eigene Frames (TX) · Sitzungstext · Log ·
     TinyBox-Sonderframes (alle, `chat`, `quality`, `mail`, `beacon`, `proto` – wie CR50).
     Ersetzt das bisherige Kästchen „MON“.
   - **Clear** leert den Monitor auch in der TinyBox (`POST /api/monitor/clear`), ein Reload
     bringt die alten Zeilen nicht zurück. Der Rückblick fasst jetzt 600 Zeilen (vorher 300).
2. **Frames im Monitor (KISS-Mode):** Im KISS-Mode macht die TinyBox AX.25 selbst und
   kennt daher jeden Frame – die gehörten und **die eigenen**. Neues Modul
   `tinybox/framemon.py`: jeder Frame wird eine Zeile
   `21:40:02 TX OE3GAS-1 → OE3TEC <I 0,0>: Welcome …` (`RX` gehört, `TX` gesendet; I-, S-,
   U-Frames mit Zählern und P/F, Modulo 128 aus der Verbindung oder geschätzt).
   Die Frames gehen nur an die Web-GUI (Logger `tinybox.frames` ohne Weitergabe), nicht in
   Logdatei oder Konsole.
   - Im **AGW-Mode** (Direwolf) gibt es weiterhin keine Frames, nur Sitzungstext und Log:
     Dort macht Direwolf AX.25 und meldet der TinyBox keine eigenen Frames.
   - Sitzungstext (`TXT`) zeigt jetzt auch das Rufzeichen der Gegenstation
     (`OE3GAS-1 → OE3TEC: …`); bisher stand dort nur `> Text`.
- Dateien: `tinybox/framemon.py` (neu), `tinybox/adapters/kiss.py`, `tinybox/adapters/web.py`,
  `tinybox/web/app.js`, `tinybox/web/app.css`. Test: `tests/test_framemon.py`.
  Nur die TinyBox, kein neuer Client.

## CR53 – TinyBox-Web-GUI: Monitor auf schwarzem Hintergrund (✅ 16.10.2026)

**Wunsch (OE3GAS):** Der Live-Monitor der TinyBox-Web-GUI soll wie der Monitor im Client einen
schwarzen Hintergrund haben.

**Lösung:** Gleiche Farben wie der Client-Monitor (CR50): Grund `#0c1218`, Text hellgrün-grau, Zeit und
Frametyp gedämpft grau, eigene Frames (TX) und Eingaben hellblau, Warnungen hellrot. Die Rufzeichen
bekommen hellere Farben (wie im Client), die TinyBox-Sonderframes (chat, quality, mail, beacon, proto)
farbige Marken. Nur `tinybox/web/app.css` und `tinybox/web/app.js` – nur die TinyBox, kein neuer Client.

## CR54 – Client: Farbbereiche links, neuer Kopf, Knöpfe Chat und Mailbox (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Farbliche Trennung der Bereiche „Chat Boards“, „Mail“, „Bulletins“ und „Station“ – nach
   Mockup (Variante E): Bereiche nicht füllen, sondern in ihrer Farbe umranden, Kopf als
   farbiges Band, gewählter Eintrag voll in der Bereichsfarbe.
2. „Rubrics…“ (Bulletins) und „Settings“ (Station) als Einträge entfernen; dafür ein Zahnrad
   rechts im Kopf von „Bulletins“ und „Station“.
3. Kopfzeile: neben dem Logo zweizeilig „TinyBox Client“, etwas Abstand, dann der Call-Avatar.
4. Der Knopf zurück aus der Mailbox hieß „Terminal“, führte aber zum Monitor – Tooltip
   korrigieren; neben dem Mail-Knopf auch einen Chat-Knopf.

### Umsetzung

1. Farben: Chat Boards violett `#6d4bd1`, Mail petrol `#0b7f86`, Bulletins ocker `#b06a00`,
   Station schiefergrau `#52606e` (unterscheiden sich auch in der Helligkeit; Grün/Rot/Gelb
   bleiben dem Verbindungsstatus und den Qualitätsbalken). Im Dunkelmodus sind Rahmen und
   Symbole aufgehellt. Gilt auch für die Ordnerliste der Mailbox am Handy.
2. Zahnrad bei Bulletins öffnet die Rubrikenliste, bei Station die Settings. Ohne abonnierte
   Rubrik steht im Bulletin-Bereich „No rubric subscribed“.
3. „TinyBox / Client“ neben dem Logo, feiner Trennstrich, dann Avatar und Call. Unter 760 px
   Breite fällt der Schriftzug weg (Platz für „Connect to“).
4. Zwei Knöpfe oben rechts: **Chat** und **Mailbox**; der Knopf der offenen Ansicht ist weiß
   gefüllt. Chat schaltet auf den Chat-Kanal. Mailbox nochmals gedrückt führt zurück, der
   Tooltip sagt wohin: „Back to Chat“, „Back to Monitor“ (Kanal 0) oder „Back to Terminal“.
   Monitor und TinyBox terminal sind in der Seitenleiste markiert, wenn sie offen sind.
- Client-Version 2026.10.16.

## CR55 – Monitor: APRS im Klartext, lehrreich (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. APRS-Pakete im Monitor von TinyBox und Client für Menschen lesbar darstellen, wenn ein
   Toggle „APRS“ aktiv ist – nach Variante A: Rohzeile bleibt, darunter die Übersetzung.
2. Die Einzelteile des Pakets grafisch auf die Klartextteile abbilden: Wer sich APRS im Client
   ansieht, interessiert sich für Struktur und „Grammatik“ von APRS.
3. Links zu aprs.fi und OpenStreetMap.
4. Erklären, dass „AP…“-Ziele auf eine Liste definierter Geräte verweisen, andere Ziele (Mic-E)
   eigentlich Nutzdaten sind.
- Entwurf: Design-Canvas „APRS-Monitor lehrreich“ (claude.ai).

### Umsetzung

1. **Decoder `tinybox/aprs.py`** (eine Stelle für TinyBox und Client): zerlegt einen UI-Frame
   in Teile (Rolle = Farbe, Schlüssel, Bezeichnung, Bedeutung, Rechenweg) und Klartext-Chips.
   Die Teile ergeben zusammen wieder das Infofeld. Verstanden werden: Positionen
   unkomprimiert, komprimiert (base-91) und Mic-E (inkl. Längen-Offset, Message-Bits,
   Mehrdeutigkeit, Höhe, Gerät aus Präfix/Suffix, abgeschnittene Pakete); Wetter (mit
   Umrechnung °F→°C, mph→km/h; fehlerhafte Felder wie `h0` rot); Kurs/Geschwindigkeit, PHG,
   RNG, `/A=` Höhe; Zeitstempel (mit Hinweis, wenn die Uhr des Senders falsch geht); Status;
   Nachrichten (Empfänger, Nummer, ack/rej, Bulletins); Telemetrie **skaliert** mit den vorher
   gehörten PARM/UNIT/EQNS/BITS (Speicher je Station); Third-Party (`}`, inneres Paket
   rekursiv); Objekte und Items; positionsloses Wetter.
   - **Zielfeld**: `device ID` (Eintrag der Geräteliste aprs-deviceid), `payload` (Mic-E: die
     Breite + Message-Bits, in der Lupe als sechs Kästchen zerlegt) oder `free word`.
   - **Pfad**: je Eintrag eine Erklärung (wer hat weitergegeben, was ist noch offen), Summe
     und Warnung bei langen Pfaden (WIDE3 und mehr).
   - Entfernung und Richtung vom eigenen `locator` (tinybox.conf / tbclient.conf).
   - Daten: `tinybox/aprs_data.json` – Geräteliste aus aprs-deviceid (CC BY-SA 2.0, Quelle in
     der Lupe genannt) und Symbolnamen aus dem Symbolsatz des Clients.
2. **Monitore**: `tbclient/radio.monitor_entry` und `tinybox/framemon.entry` hängen das Ergebnis
   als `aprs` an den Eintrag (nur UI-Frames mit PID F0, nicht die TinyBox-Sonderframes).
   Der Client liest jetzt auch das H-Bit der Digipeater: der Pfad zeigt `*` wie in der TinyBox.
3. **Anzeige** (`tinybox/web/aprsview.js` + `.css`, eine Kopie für beide GUIs – der Client
   liefert sie aus `tinybox/web` aus):
   - Knopf **APRS** in der Monitor-Leiste (Zustand je Browser gemerkt). An: das Infofeld in
     Farben je Rolle, das Ziel mit Marke `device ID`/`payload`, Marke `aprs`, darunter die
     Klartextzeile mit Links **aprs.fi ↗** und **map ↗**.
   - **Hover**: ein Teil der Rohzeile leuchtet zusammen mit seinem Klartextteil auf (und
     umgekehrt), auch in der Lupe.
   - **Lupe** (rechts neben dem Monitor; Client: Kanal 0, TinyBox: Seite „Monitor“): Klick auf
     eine APRS-Zeile zeigt 1 · Adressteil (From, „To“ mit Erklärung, Pfad), bei Mic-E die
     sechs Zeichen des Zielfelds, 2 · Infofeld Teil für Teil mit Bedeutung und Rechenweg,
     Knöpfe zu aprs.fi und OpenStreetMap. Unter 900 px Breite nur die Klartextzeile.
   - Auswahl „APRS frames“ im Filter; das Suchfeld findet auch den Klartext.
- Tests: `tests/test_aprs.py` (echte Pakete vom 16.10.2026 auf 144.800 MHz, Monitore beider Seiten).
- Client-Version 2026.10.16.2.

## CR56 – APRS-Lense: Feinschliff und Fragen aus dem Betrieb (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Die APRS-Lense-Leiste erst einblenden, wenn der Knopf gedrückt ist. Knopf umbenennen auf
   „APRS Lense“.
2. Zwischen den einzelnen APRS-Aussendungen eine Trennlinie.
3. Frage zu einer Telemetrie-Definition von OE3CRA-2 über OE3XWJ-10: Welche Station habe ich
   hier tatsächlich gehört?
4. Frage zu OE3MZC-2: Was bedeutet „hF gateway“?
5. Diese Fragen soll auch die APRS-Lense beantworten.

### Umsetzung

1. Knopf **APRS Lense** (TinyBox und Client); aus, bis er gedrückt wird. Erst dann erscheinen
   Klartextzeilen und die Leiste. Der Zustand wird je Browser gemerkt (neuer Schlüssel, startet
   also bei allen einmal „aus“).
2. Jede APRS-Aussendung hat oben und unten eine feine Linie.
3. Neue Zeile **Heard** im Adressteil der Lense, dazu der Chip „heard from …“ in der
   Klartextzeile: gehört hat man den **letzten Digipeater, der das Paket weitergegeben hat** (er
   steht mit `*` als letzter Rufzeichen-Eintrag vor den verbrauchten Aliasen), ohne `*` im Pfad
   den Absender selbst. Hat der letzte Digipeater sein Rufzeichen nicht eingetragen, sagt die
   Lense, dass es nicht erkennbar ist. Hover zeigt den passenden Pfad-Eintrag.
4. „hF gateway“ war ein Fehler beim Kleinschreiben – jetzt „HF gateway“. Die Lense erklärt
   Symbole, wo der Name allein nicht reicht: `/&` (ursprünglich HF↔VHF-Gateway, heute meist
   iGates; sauberer wären Overlays I&, R&, T&, 2&), Digipeater-Overlays (1# Fill-in, S# regional,
   I# mit iGate …), Gateway-Overlays, `/_`, `/r`, `/-`.
- Nebenbei: PARM/UNIT/EQNS zeigen ihre Werte jetzt Kanal für Kanal (A1 Volt · A2 Pkt …), lange
  Werte brechen in der Lense um.
- Tests in `tests/test_aprs.py`. Client-Version 2026.10.16.3.

## CR57 – APRS-Lense: Zeilen neu geordnet, Pfad als Kette (✅ 16.10.2026)

### Erfassung (OE3GAS, 16.10.2026)

1. Monitorzeile umbauen: nach `<UI>` neue Zeile, dort ohne „aprs:“ gleich die Payload; neue Zeile,
   dann die Interpretation. „heard from“ entfällt in der Zeile (steht in der Detailansicht).
2. Den Pfad in der Lense grafisch darstellen: Chips mit kleinen Richtungspfeilen, z. B.
   OM0ODX → OE6XTR → OE3XWJ-10, sonst kein Text beim Pfad.

### Umsetzung

1. APRS-Zeilen (Knopf an): Kopf bis `<UI>`, darunter die farbige Payload, darunter der Klartext.
   Marke `aprs` und Chip „heard from …“ sind weg. Ohne Knopf bleibt die Zeile wie bisher.
   TinyBox-Web-GUI und Client gleich.
2. Lense, Zeile **Path**: nur noch die Kette Absender → Digipeater, die weitergegeben haben (mit
   Rufzeichen im Pfad). Die gehörte Station ist hervorgehoben; Hover verbindet sie mit der Zeile
   **Heard**. Ohne Digipeater steht nur der Absender da; hat ein Digi kein Rufzeichen
   eingetragen, endet die Kette mit „?“. Die Texte zu Aliasen und Resthops entfallen.
- Decoder liefert dafür `chain`. Tests in `tests/test_aprs.py`. Client-Version 2026.10.16.4.

## CR58 – Bug: Monitor startet nach Mailbox nicht (✅ 16.10.2026)

**Fehler (OE3GAS):** Nach einem anderen Knopf (z. B. Inbox) reagierte „Monitor“ in der Seitenleiste
nicht; erst nach „TinyBox terminal“ ging es.

**Ursache:** Der Monitor ist Kanal 0. War Kanal 0 schon der aktive Kanal (man kam aus dem Monitor in
die Mailbox), brach der Kanalwechsel sofort ab und die Mailbox blieb stehen. „TinyBox terminal“
wechselte vorher auf den Chat-Kanal, danach ging der Wechsel auf 0 wieder.

**Lösung:** Ein Klick auf den schon aktiven Kanal (Monitor, Kanal-Chip, Alt+Zahl) schaltet jetzt
dessen Ansicht ein. Client-Version 2026.10.16.5.

## CR59 – APRS-Lense: Symbol als Bild, Gerätename gelb (✅ 16.10.2026)

**Wunsch (OE3GAS):** In der Detailansicht beim Symbol-Code auch das Symbol zeigen („> = car“ + Bild) –
die Symbole hat der Client ja schon. Den Gerätenamen (z. B. „WB2OSZ DireWolf“) in der Erklärung zum
„To“-Feld auch gelb.

**Lösung:** Der Decoder gibt beim Symbol-Code das Symbol (Tabelle + Code) mit; die Lense zeigt davor
das Bild aus dem Symbolsatz des Clients (`/aprs/symbols-*.png`). Die TinyBox-Web-GUI hat keine
Symbolbilder und zeigt weiter nur den Text. Der Gerätename in der Erklärung hat die Gerätefarbe (gelb),
Hover verbindet ihn mit dem „To“-Feld. Client-Version 2026.10.16.6.

## CR60 – APRS-Lense am Handy (✅ 16.10.2026)

**Wunsch (OE3GAS):** Am Handy ist die Detailleiste der APRS-Lense nicht zu sehen. Gewählt: Variante A
(Bottom Sheet).

**Lösung** (TinyBox-Web-GUI und Client gleich, `tinybox/web/aprsview.js` + `.css`):
- Unter 900 px Breite ist die Lense ein **Bottom Sheet**: Tippen auf eine APRS-Zeile lässt es von
  unten heraufgleiten (75 % der Höhe); die angetippte Zeile rückt nach oben und bleibt sichtbar, der
  Monitor läuft weiter. Schließen mit ✕, Wisch nach unten (am Griff oder ganz oben im Sheet), Tippen
  außerhalb oder Esc. Tippen auf eine andere APRS-Zeile wechselt den Inhalt.
- **Antippen statt Darüberfahren:** Ein Tipp auf einen Teil der Payload oder des Klartexts hält das
  Paar hervorgehoben (auch in der Lense, die dorthin scrollt); ein Tipp in der Lense markiert den Teil
  oben in der Zeile. Am PC wirkt ein Klick genauso, das Darüberfahren bleibt.
- TinyBox-Dashboard (ohne eigene Lense-Leiste): am Handy erscheint dasselbe Sheet.
- Client-Version 2026.10.16.7.

## CR61 – APRS-Lense: Klartext als Karte; APRS-Statistik mit „Sünden“ (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

1. Zwischen APRS-Paket und Interpretation zu wenig Trennung – gewählt: Variante B (Klartext als Karte).
2. Kleines Statistik-Tool: Frames je gehörter Station, je Sender, je AP-Device und was sonst
   interessant ist – ausdrücklich auch die „Sünden“ ausweisen.

### Umsetzung

1. Die Interpretation steht in einer eigenen, leicht helleren Karte mit runden Ecken unter der
   Payload; die gewählte Zeile hebt auch ihre Karte hervor (TinyBox und Client).
2. **APRS statistics** (Client, Station > APRS statistics). Modul `tinybox/aprsstats.py`, Daten in
   `data/tbclient/aprsstats.db` (bis 7 Tage, Neustart verliert nichts). Zeitfenster letzte Stunde,
   24 h oder seit Start; Reset mit zweitem Klick; alle 15 s aktualisiert.
   - Kacheln: Frames (je Minute), Stationen, Kanalauslastung (geschätzte Sendezeit bei 1200 Bd),
     Internet → Funk. Verlauf als Balken.
   - **Sins**: zu häufige Positionsbaken im Stand (< 5 min) bzw. in Fahrt (< 30 s); unveränderte
     Wiederholungen (< 10 min, Zeitstempel ignoriert; Telemetrie-Definitionen: einmal pro Stunde
     reicht); lange Pfade (WIDE3 und mehr); falsche Uhr; fehlerhafte Pakete; iGates mit viel
     Internet-Verkehr auf Funk (≥ 5 % des Kanals oder ≥ 30/h).
   - Tabellen (sortierbar): Heard, Senders (Third-Party zählt für die innere Station; Abstand,
     Entfernung, Typen, Gerät), Devices, Packet types, Digipeaters mit Wegen und Hop-Verteilung,
     iGates, Range (weiteste direkt/über Digis, Entfernungsklassen; braucht `locator`), Countries.
   - Klick auf ein Rufzeichen öffnet den Monitor, gefiltert auf diese Station.
   - Die TinyBox-Web-GUI bekommt die Statistik vorerst nicht (sieht Frames nur im KISS-Mode).
3. Decoder: Mic-E-Gerät wird auch ohne Präfix und mit CR am Ende erkannt (FT1D, FTM-400, TH-D72);
   Wetterfelder mit zu vielen Ziffern (`h074`, `b125031`) sind jetzt als fehlerhaft markiert.
- Tests: `tests/test_aprsstats.py`, `tests/test_aprs.py`. Client-Version 2026.10.17.

## CR62 – APRS-Lense: Aussendung als Karte, Knopf in drei Stufen (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

1. Die gewählte Aussendung viel deutlicher markieren: die Aussendung als Ganzes, darin die Teile
   „Frame“ und „Interpretation“. Entwurf im Canvas „APRS-Monitor lehrreich“ – gewählt Variante 2
   (Karte mit farbigem Kopfband).
2. Die APRS-Lense ausblendbar: 1. Klick auf „APRS Lense“ = Interpretationssicht (Knopf blau),
   2. Klick = dazu die Lense rechts (Knopf grün wie „Mail“ links), 3. Klick = alles aus, zurück zum
   Monitor (Knopf weiß).
3. In der Interpretationssicht ohne Lense schaltet ein Klick rechts im Kopfband der gewählten
   Aussendung die Lense ein; Text „view Frame in APRS lense“.

### Umsetzung

1. Jede APRS-Aussendung ist eine Karte: oben **Frame** (Kopfzeile + Payload, dunkel), darunter
   **Interpretation** (heller), beide mit kleinem Etikett, gestrichelt getrennt. Die gewählte Karte hat
   einen blauen Rahmen (2 px) und ein blaues Kopfband mit Zeit und Rufzeichen.
2. Knopf in drei Stufen (weiß → blau → grün `#0b7f86` → weiß), Tooltip sagt die nächste Stufe; die
   Stufe wird je Browser gemerkt. Die Lense (rechts bzw. am Handy das Bottom Sheet) gibt es nur in der
   grünen Stufe.
3. Kopfband rechts: Knopf **view Frame in APRS lense** (schaltet auf grün und zeigt die Aussendung in
   der Lense); in der grünen Stufe steht dort „shown in the APRS lense“.
- Gleich in TinyBox-Web-GUI und Client (`tinybox/web/aprsview.js` + `.css`). Client-Version 2026.10.17.2.

## CR63 – APRS-Statistik: Reihenfolge, Geräte-Filter; Kopfband mit Symbol und Entfernung (✅ 17.10.2026)

**Wunsch (OE3GAS):** In der Statistik „Sins“ ganz nach unten, oben „Heard“, „iGates“, „Packet types“;
bei den Pakettypen zuerst die Prozent, dahinter in Klammer die Anzahl; Geräte filterbar wie die
Rufzeichen. Im blauen Kopfband der gewählten Aussendung neben dem Rufzeichen das APRS-Symbol und
„Distance“: ohne Locator „unknown“, sonst km und Richtung.

**Lösung:**
- Statistik: Heard · iGates · Packet types, dann Senders, Devices, Digipeaters, Range, Countries,
  zuletzt Sins (über die ganze Breite). Pakettypen als „12.3 % (45)“.
- Geräte (Tabelle Devices und Spalte Device bei Senders) sind anklickbar: der Monitor zeigt die
  Aussendungen dieses Geräts (bei Third-Party-Paketen auch das Gerät der inneren Station).
- Kopfband: Symbol (Bild aus dem Symbolsatz des Clients) und „Distance: 37 km, 179° S“ (Richtung mit
  16 Himmelsrichtungen); ohne `locator` „unknown (no locator)“, bei Paketen ohne Position
  „no position in this packet“. Decoder liefert dafür `dist`, `home`, `symbol`.
- Client-Version 2026.10.17.3.

## CR64 – APRS-Statistik: Zeitfenster als Knöpfe, Datei laufend aufräumen (✅ 17.10.2026)

**Wunsch (OE3GAS):** Die Statistik zeigte nur die letzte Stunde – Anzeige für letzte Stunde, 24 h und
alles. Die Datei `aprsstats.db` auch im laufenden Betrieb aufräumen, nicht nur beim Start.

**Lösung:**
- Die Auswahl war ein Klappmenü und leicht zu übersehen; jetzt drei Knöpfe **Last hour · 24 h · All**
  in der Kopfleiste, der gewählte blau. „All“ = alles Gespeicherte (max. 7 Tage bzw. seit dem
  letzten Reset). Die Wahl wird je Browser gemerkt.
- `tinybox/aprsstats.py`: einmal pro Stunde werden Datensätze älter als 7 Tage (und über 200 000)
  aus der Datei gelöscht; der freie Platz wird von SQLite wiederverwendet.
- Test `test_file_is_tidied_while_running`. Client-Version 2026.10.17.4.

## CR65 – Statistik je Rufzeichen (Stationsseite) (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

Statistik je Call: Art der Frames, Zeitverlauf Frames/h und was sonst interessant ist. Erreichbar aus
der Monitoransicht (Klick auf ein Rufzeichen) und aus der Übersichts-Statistik. Umfang: Vorschlag
Punkte 1–10 (letzte Texte und Messwert-Verläufe später).

### Umsetzung

- **Zugänge:** Klick auf ein Rufzeichen im Monitor (Absender, Digipeater im Pfad; alle Stufen des
  APRS-Lense-Knopfs; Rufzeichen unterstreichen sich beim Darüberfahren); im blauen Kopfband
  **Station statistics** (bei Third-Party zusätzlich die innere Station); Rufzeichen der Pfad-Kette in
  der Lense; jedes Rufzeichen in der Übersichts-Statistik (statt direkt in den Monitor). Auf der
  Stationsseite sind Rufzeichen wieder anklickbar; **‹ Back** geht Schritt für Schritt zurück, zuletzt
  an dieselbe Stelle im Monitor bzw. in die Übersicht. **Show in monitor** filtert den Monitor.
- **Inhalt** (Zeitfenster Last hour / 24 h / All): Kopf mit Symbol, Rolle (mobil/fix, Digipeater,
  iGate, Wetter, Objekte, Telemetrie), Gerät, Land, Entfernung + Richtung, zuerst/zuletzt gehört,
  Links aprs.fi / Karte / Track; Kacheln (Frames, Kanalanteil und Sendezeit, für andere weitergegeben,
  Internet → Funk, von deinem Funkgerät empfangen); Frames pro Zeiteinheit; Art der Frames;
  Bakenverhalten (typischer/kürzester/längster Abstand, fester Takt?, Verteilung); Wie sie zu dir kommt
  (direkt/über Digis, Wege, Hops, verlangter Pfad, wer sie dir gebracht hat); Aktivität Wochentag ×
  Stunde (alles Gespeicherte); Bewegung (Strecke, Höchstgeschwindigkeit, Höhe); als Digipeater bzw.
  iGate: für welche Stationen; Sünden dieser Station.
- Datensätze speichern dafür zusätzlich Symbol, Geschwindigkeit und Höhe (`tinybox/aprs.py` liefert
  `speed`, `alt`). API `GET /api/aprs/station?call=..&win=..`.
- Tests `test_station_page`. Client-Version 2026.10.17.5.


## CR66 – UI-Frame aus dem Monitor senden (✅ 17.10.2026)

### Erfassung (OE3GAS, 17.10.2026)

Der Client soll einen UI-Frame senden können, am besten in der Monitoransicht vor dem Filterfeld –
für den Test von VARA FM als KISS-TNC über kisshub („Wrong KISS frame“ bei SABM/SABME).

### Umsetzung

- Knopf **Send UI** in der Monitorleiste vor dem Filterfeld klappt eine Zeile auf: **To** (Standard
  `CQ`), **Via** (optional, Digipeater mit Komma oder Leerzeichen, höchstens 8), **Text** (bis
  1024 Byte, Bytezähler), **Send** bzw. Enter. Die Antwort steht daneben („sent 23:45:12 (17 B)“
  oder der Grund, z. B. „kisshub not reachable“, „not a callsign“). Der Text bleibt markiert stehen:
  Enter sendet denselben Frame noch einmal. To/Via merkt sich der Browser.
- Geht über KISS (eigener AX.25-Frame, PID F0, Command-Bit) und über AGW (Direwolf `M` bzw. `V`
  mit Pfad). Über den Telnet-Testport nicht.
- Der eigene Frame erscheint im Monitor wie gehört.
- API `POST /api/ui {"dest", "via", "text"}`, `ClientCore.send_ui()`, Prüfung in `ui_request()`.
- Tests `tests/test_tbclient_ui.py`. Client-Version 2026.10.17.8.

## CR67 – VARA-Monitoring im kisshub: Werte aus 8300, 8100 und passive AX.25-Auswertung (kisshub-Teil umgesetzt 18.10.2026, Anzeige in TinyBox/Client offen)

### Erfassung (OE3GAS, 18.10.2026)

Mit VARA FM als KISS-TNC (Profil `vara-fm`, Tunnel, Konzept 8c) möglichst viele Werte über Kanal,
Gegensignal und Verbindungszustand gewinnen. kisshub wertet aus und stellt die Werte TinyBox und
Client zur Verfügung. Grundlage: statische Analyse VARA HF 4.9.0 / VARA FM 4.3.9 (Projekt „VARA
verstehen“), VARA-Changelog, Pat-Vara, Mercury (VARA-kompatible TNC-Schnittstelle).

**Reihenfolge:** zuerst der Funktest des Tunnels (vollwertiges AX.25 über VARA FM möglich?). CR67
wird erst danach umgesetzt; ohne funktionierenden Tunnel bleibt nur Teil B für UI-Verkehr.

**Regeln:** nur lesend beobachten. Am Befehlsport zunächst **kein Kommando** senden. Keine
Auswertung oder Nachbildung von Lizenz- und Krypto-Meldungen (`REGISTERED`, `LINK (UN)REGISTERED`,
`ENCRYPTION …`) – nur als Text protokollieren. Alle VARA-Ports nur über Loopback.

### Quelle A – VARA-Befehlsport 8300 (neuer Teil `VaraMonitor` im kisshub)

kisshub verbindet sich zusätzlich mit 8300, liest zeilenweise (CR-getrennt, ASCII), sendet nichts.
Unbekannte Zeilen werden roh mit Zeitstempel geloggt. Wiederverbindung wie beim TNC.

| Meldung | Format (Mercury, in VARA noch zu bestätigen) | Auswertung |
|---|---|---|
| `SN` | `SN 8.2` (dB, 1 Nachkomma) | laut HF-Changelog v4.7.2 auch je **empfangenem KISS-Frame**: dem Frame zuordnen, der innerhalb eines kurzen Fensters (Startwert 1 s, einstellbar) an 8100 ankommt → **SN je Gegenstation**. Ohne passenden Frame: als „SN ohne Frame“ zählen |
| `PTT ON` / `PTT OFF` | so | **Sendedauer je Burst**; mit der Größe des zuletzt an 8100 übergebenen Frames → gemessene Rate und Aufwand je Burst (ersetzt die Schätzung `air_baud`/`txdelay`, Grundlage für T1). **Wartezeit bis TX**: Übergabe an 8100 → `PTT ON`. PTT länger als ein Grenzwert (z. B. 60 s) → **Alarm „PTT hängt“** |
| `BUSY ON` / `BUSY OFF` | so | Kanal belegt: Anteil je Minute/Stunde, Zahl der Belegungen, längste Belegung |
| `BITRATE` | `BITRATE (2) 600 BPS` (Speed Level, bps) | falls im KISS-Betrieb gesendet: Speed Level je Burst; Parser tolerant |
| `BUFFER` | `BUFFER 0` | nur ARQ; mitloggen |
| `IAMALIVE` | so | Lebenszeichen; bleibt es länger als 2 Intervalle aus → Warnung |
| `MISSING SOUNDCARD` | so | **Alarm** (laut EA5HVK hilft nur ein PC-Neustart) |
| `VERSION …` | so | im Status anzeigen |
| `PENDING`, `CONNECTED …`, `DISCONNECTED`, `CANCELPENDING` | so | sollten im KISS-Betrieb nicht kommen: kommt doch eins, Warnung (jemand nutzt ARQ auf dem Gerät) |
| alles andere | – | roh loggen, Zähler „unbekannt“ |

SN wird **unverändert** gespeichert und angezeigt. Bezug bei VARA HF laut Analyse 2500 Hz; für VARA FM
(Narrow 3 kHz / Wide 6 kHz NF) unbekannt – vergleichen nur innerhalb derselben Betriebsart.

### Quelle B – KISS-Port 8100 und Tunnel (misst kisshub selbst)

| Wert | Verarbeitung |
|---|---|
| Frames gesendet/empfangen | je Minute, getrennt Typ 0 (UI) und Typ 2 (Tunnel); Zeitreihe 60 min |
| Framegrößen | Verteilung (Klassen bis 64, 128, 256, 512, 1024, darüber) gesendet/empfangen; mit der PTT-Dauer die **Schwellen für Speed Level 1/2/4** ermitteln |
| `foreign`, `echoes`, unlesbare Frames | gibt es seit dem Tunnel; zusätzlich je Minute |
| Gehörte Stationen | Rufzeichen, Frames, letzter/mittlerer/min./max. SN (aus A), zuletzt gehört, über Tunnel ja/nein |
| TNC/Hub | bestehend (CR41): Zustand, Portverluste, Wiederanläufe, Wartezeit in der Hub-Queue |

### Quelle C – passive AX.25-Auswertung im kisshub (je Stationspaar)

Der Hub sieht alle Frames einer Verbindung in beide Richtungen (eigene Clients und Gegenstation).
Je Paar (Rufzeichen A ↔ B, mit SSID) wird geführt:

| Wert | Wie |
|---|---|
| Verbindungsstatus | SABM(E) gesehen → „im Aufbau“, UA → „verbunden“ (mit Version 2.0/2.2), DISC/DM → „getrennt“; Dauer der Verbindung |
| I-Frames und Nutzbytes | je Richtung |
| **Wiederholungen** | I-Frame mit gleichem N(S) und gleichem Inhalt erneut gesendet → Wiederholungsquote je Richtung |
| REJ / SREJ / RNR | je Richtung zählen |
| **Antwortzeit** | eigener I-/Poll-Frame bis zur ersten Quittung (RR/REJ/I mit passendem N(R)) → gemessene Laufzeit über VARA (Mittel, Min., Max.) |
| Abbrüche | DM auf SABM, Verbindung ohne DISC verschwunden (Zeitüberschreitung) |
| Durchsatz | Nutzbytes je Minute während der Verbindung |

Damit lässt sich „AX.25 über PK-232“ und „AX.25 über VARA FM“ mit denselben Kennzahlen
vergleichen, unabhängig davon, ob TinyBox oder Client die Verbindung führen.

### Quelle D – VARA-Logdatei (optional, zweiter Schritt)

kisshub liest `VARAFM.log` mit (Pfad in `kisshub.conf`, nur lesen, ab Dateiende). Ausgewertet:
„Soundcard … missing in action“ (Alarm), „Wrong/Invalid KISS frame“, „Exceeded KISS buffer“,
„KISS size too long“ (zählen – kommen nach bisheriger Erfahrung nicht über TCP), „VARA is not
connected to any App via TCP Port 8300“. Inhalt im KISS-Betrieb erst nach dem Mitschnitt festlegen.

### Weitergabe an TinyBox und Client

- **`GET http://127.0.0.1:8102/status`** (bestehend, nur Loopback) bekommt die Blöcke
  `vara` (Verbindung zu 8300, alive, Version, busy + Anteil, letzte/mittlere Sendedauer, Wartezeit
  bis TX, gemessene Rate und Burst-Aufwand, Alarme), `stations` (Quelle B mit SN) und
  `links` (Quelle C je Paar).
- **Neu `GET http://127.0.0.1:8102/events`**: Datenstrom, eine JSON-Zeile je Ereignis
  (`sn` mit Rufzeichen, `ptt`, `busy`, `alarm`, `link`), damit Monitor und Qualitätsanzeige live
  sind statt alle 30 s abzufragen.
- **TinyBox**: Web-GUI zeigt Kanal (busy-Anteil), SN je Station und Verbindungswerte; die
  Qualitätsbalken der Verbindungen nutzen SN und Wiederholungsquote. Alarme in der Sysop-Konsole.
- **Client**: im Monitor das SN neben jedem empfangenen Frame (falls zugeordnet), in der
  Stationsseite der SN-Verlauf; Kopfzeile mit VARA-Zustand (alive, busy, Alarm).
- Speicherung: Zeitreihen im Speicher (60 min Minutenwerte, 24 h Stundenwerte); Stationswerte wie
  die APRS-Statistik bis 7 Tage in einer Datei.

### Erster Schritt (nach dem Tunnel-Test): Mitschnitt

`tools/vara_capture.py` (kommentiert): 30 min Betrieb, verbindet sich mit 8300 und sendet nichts,
schreibt jede Zeile mit Zeitstempel (ms) in eine Datei; parallel kisshub-`/status` und das
kisshub-Log mit `LOG TRACE`. Danach Formate festlegen, Parser schreiben, Teil A–C umsetzen.

### Offene Fragen (im Mitschnitt klären)

1. Liefert VARA **FM** 4.3.9 im KISS-Betrieb `SN` je empfangenem Frame (wie HF ab 4.7.2)? Auch für
   Typ-2-Rahmen? Kommt `SN` vor oder nach dem Frame an 8100?
2. Stört eine Verbindung am Port 8300 den KISS-Betrieb? (Bekannter Fehler 2023: PTT blieb mit
   KISS plus Befehlsport hängen – beim ersten Test jemand am Funkgerät.) Schaltet sie KISS ab
   (HF-Changelog 4.6.4: „KISS interface continue disabled with Winlink apps“)? Wie viele Clients
   nimmt 8300?
3. Kommen `PTT`, `BUSY`, `BITRATE` auch für KISS-Verkehr?
4. Exakte Formate von `SN`, `BITRATE` in VARA selbst.
5. Was schreibt `VARAFM.log` im KISS-Betrieb?

### Umsetzung im kisshub (18.10.2026, kisshub 2026.10.18.2)

Tunnel-Funktest vorher erfolgreich: vollwertiges AX.25 (v2.2) zwischen TinyBox und Client über
VARA FM, 1200 Bd. Auffällig: lange Pausen zwischen den Sendungen der beiden Stationen.

- **`kisshub/linkstats.py` (Teil B + C, für jeden TNC – PK-232 genauso wie VARA):** je
  Stationspaar Aufbau (Versuche, Dauer, v2.0/2.2, abgelehnt), je Richtung I-Frames, neue Bytes,
  Wiederholungen (gleiche N(S) mit gleichem Inhalt vor der Quittung) mit Quote, RR/RNR/REJ/SREJ,
  Polls (S-Kommando mit P=1 ≈ abgelaufener T1), **Quittungszeit** (I-Frame bis zur Quittung, nur
  einmal gesendete – Karn), **Antwortabstand** (Frame von X nach dem letzten Frame von Y – die
  „langen Pausen“), Goodput, Effizienz (neue Nutzbytes / alle Bytes), geschätzte Sendezeit;
  gehörte Stationen, Framegrößen-Klassen, Minutenzähler, unlesbare Frames. Zeitpunkte: tx = an den
  TNC übergeben, rx = vom TNC geliefert – für PK-232 und VARA gleich gemessen, also vergleichbar.
- **`kisshub/varamon.py` (Teil A):** `[vara] monitor = yes` – zweite Verbindung zum Befehlsport,
  **sendet nichts**. Wertet `PTT ON/OFF` (Burst-Dauer, Wartezeit von der Übergabe bis PTT, daraus
  Ausgleichsgerade Aufwand je Burst + Rate), `BUSY ON/OFF` (Anteil 10/60 min), `SN` (dem Frame
  zugeordnet, der im Fenster `sn_window_ms` ankommt → SN je Station und je Link-Richtung),
  `BITRATE`, `IAMALIVE`, `VERSION`, `MISSING SOUNDCARD` aus; Alarme: PTT länger als 60 s, 180 s
  nichts von VARA, Soundkarte weg; ARQ-Meldungen werden gewarnt, Lizenzzeilen nur geloggt,
  unbekannte Zeilen roh geloggt.
- **Links-Datei** `[log] links_file = kisshub-links.jsonl`: je beendeter Verbindung eine
  JSON-Zeile mit TNC-Profil, Tunnel, air_baud, txdelay, VARA-Messwerten und allen Kennzahlen –
  gleiche Sitzung über PK-232 und über VARA fahren und vergleichen. Beim Ende einer Verbindung
  zusätzlich eine Zusammenfassung im kisshub-Log.
- **Status** `GET /status`: neue Blöcke `quality` (laufende + letzte 5 Verbindungen, Stationen,
  Größen, letzte 10 min) und `vara`.
- **Konsole:** `L`/`LINKS`, `V`/`VARA`, `STATIONS`.
- Tests `tests/test_kisshub_quality.py`.

Offen: Anzeige in TinyBox-Web-GUI und Client, `/events`-Datenstrom, VARA-Logdatei (Teil D).


## CR68 – Bug: Mail bleibt nach dem Senden über eine langsame Strecke im Postausgang (✅ 18.10.2026)

### Erfassung (OE3GAS, 18.10.2026)

VARA-Lauf 5: Antwort „Re: 2. Test Bulletin mit 3000 Zeichen“ (persönlich an OE3XYZ) wurde vom Client
ausgesendet, blieb aber im Outbox stehen („1 change(s) waiting“).

### Ursache

Die kisshub-Auswertung zeigt: Alle 27 I-Frames (4013 Byte) kamen bei der TinyBox an und wurden
quittiert, die TinyBox hat geantwortet. Die Übertragung dauerte über VARA FM (~13 B/s) aber mehrere
Minuten. Der Sync wartet nach `//SEND` höchstens `IDLE_SEC` = 120 s auf eine Antwort – die TinyBox
kann `//SENT` aber erst nach der letzten Zeile schicken. Der Sync gab nach 120 s mit „no answer from
the TinyBox“ auf, das `//SENT` kam danach und wurde nicht mehr zugeordnet; die Mail blieb im
Postausgang (beim nächsten Sync wäre sie erneut gesendet worden – die TinyBox erkennt sie über
`mid=` und antwortet mit den alten Nummern, doppelt wird sie also nicht abgelegt).

### Umsetzung

`tbclient/sync.py` `_next()`: Läuft die Wartezeit ab, fragt der Sync die eigene Verbindung, ob noch
Frames unterwegs sind (`outstanding()`: noch nicht gesendet oder nicht quittiert – KISS aus dem
eigenen AX.25-Automaten, AGW per Direwolf `Y`). Solange das so ist, wartet er weiter (höchstens
`SEND_WAIT_MAX_SEC` = 30 min); „keine Antwort“ gilt erst, wenn nichts Eigenes mehr unterwegs ist.
Tests `tests/test_sync_slowlink.py`. Client-Version 2026.10.18.

## CR69 – Erst fragen, dann senden: bereits vorhandene Mail nicht nochmals übertragen (✅ 18.10.2026)

### Erfassung (OE3GAS, 18.10.2026)

Zu CR68: Wird eine Mail nach verlorener `//SENT`-Antwort nochmals gesendet, erkennt die TinyBox sie
zwar an `mid=` – aber erst, nachdem der ganze Text nochmals übertragen wurde. Über VARA sind das
Minuten. Die TinyBox soll vorher sagen „die hab ich schon“.

### Umsetzung

- **Neuer Befehl** (Cap `HAVE`) `//HAVE <mid> <to>[,<to>...][@<at>]` → `//HAVE <mid> <id> ...`
  (schon gespeichert, eine Nummer je Empfänger) oder `//HAVE <mid> -` (senden). Es werden nur
  eigene Mails gefunden; Empfänger werden wie bei `//SEND` normiert (`tinybox/clientsync.py`).
- **Client** (`tbclient/sync.py`): Vor dem ersten Senden merkt er sich `out_try.<mid>`. Kommt
  `//SENT`, wird die Marke gelöscht. Ist die Marke beim nächsten Sync noch da (Antwort ging verloren,
  Sync abgebrochen, Client beendet), fragt er zuerst `//HAVE`: Ist die Mail schon da, wandert sie
  sofort in „Sent“, **ohne** dass der Text nochmals gesendet wird. Beim ersten Versuch wird nicht
  gefragt – das kostet keinen zusätzlichen Durchgang.
- Ältere TinyBox ohne Cap `HAVE`: wie bisher (senden, Duplikat über `mid=`).
- Tests in `tests/test_mailsync.py`. Client-Version 2026.10.18.2.

## CR70 – Konfiguration ohne Doppelungen: ein Besitzer je Wert ✅

### Erfassung (OE3GAS, 18.10.2026)

Mehrere conf-Dateien enthalten Einträge, die andere Komponenten betreffen (z. B. `air_baud` in
kisshub.conf und tinybox.conf). Die confs sollen schlanker und redundanzfrei werden. Der
Zielordner von Direwolf bzw. die `direwolf.conf` wird unter `[agw]` erfasst. Ein Handbuch
`MANUAL.md` mit den exemplarischen confs anlegen.

### Konzept

`PLANUNG.md` 17.2, Zielaufbau aller confs und Tabelle alt → neu in `MANUAL.md` Abschnitt 2.
Umsetzung in vier Schritten; alte Schlüssel bleiben lesbar.

### Umsetzung (18.10.2026) ✅

- `prcore/direwolfconf.py`: liest `direwolf.conf` (Ordner oder Datei; AGWPORT, KISSPORT, MODEM,
  TXDELAY, PERSIST, SLOTTIME je CHANNEL/ADEVICE, PACLEN, MAXFRAME, EMAXFRAME, FRACK, RETRY).
- kisshub 2026.10.18.7: Profile tragen air_baud/txdelay/max_lead/Port und eine AX.25-Empfehlung
  (VARA FM gemessen: 350 / 2700 / 12000, 256 B, Fenster 4, T1 18–90 s, T2 0,3 s); neues Profil
  `direwolf`; `[kiss]`/`[ax25]` nur Überschreibung; Status = Port + 1; `/status` mit Block
  `radio` inkl. Herkunft; Startzeilen nennen die Quelle jedes Werts.
- TinyBox: `[agw] direwolf_conf / host / port / channel / quality_*` (alt `[direwolf]`),
  paclen/Fenster aus direwolf.conf, `[kiss] port`; KISS-Werte aus dem kisshub-Status für neue
  Verbindungen, Werte aus tinybox.conf gewinnen; Startlog mit Quellen und `config hint`.
- Client 2026.10.18.3: `[radio] interface` (alt `[tinybox] link`), `[agw]`, `[kiss] port`,
  Werte vom kisshub; Bildschätzung aus der Funkrate, solange nichts gemessen ist.
- brocastd: `[radio]/[agw]/[kiss]`, baud/TXDELAY aus direwolf.conf bzw. kisshub.
- dxfeed: Inbox aus `tinybox.conf`; fwdsim: Mailbox-Call, haddress, Telnet-Port, DB aus
  `tinybox.conf`, AGW-Werte aus direwolf.conf.
- kisshub 2026.10.18.8: **eine kisshub.conf für alle TNCs** – Startschalter `-p <profil>`,
  Abschnitte `[<abschnitt>.<profil>]` nur für ein Profil, `{profile}` in Log-Dateinamen,
  `[vara] monitor` bei anderen Profilen nur Hinweis; Hilfe mit `-h` / `-?`.
- Alte Schlüssel gelten als Überschreibung, mit Hinweis beim Start. Tests:
  `tests/test_direwolfconf.py`, `RadioValuesTests`, `KissConfigTests`, Client-/brocastd-/
  dxfeed-/fwdsim-Konfigtests.

## CR71 – Connect über Digipeater (✅ 18.10.2026)

### Erfassung (OE3GAS, 17./18.10.2026)

Der Client soll Stationen über einen oder mehrere Digipeater connecten können (Test über den
TM-D710 OE3XTC-5). Frage: eigenes Via-Feld oder alles in das bestehende Eingabefeld?

### Entscheidung

Ein Feld mit der klassischen TNC-Syntax (`C OE3XYZ-1 V OE3XTC-5,OE3ABC`): gewohnt seit TNC2/BPQ,
der Pfad gehört zum Ziel (Kopieren, Liste der letzten Ziele), kein zweites Feld zum Leeren.
Die Klarheit eines eigenen Felds liefert eine Vorschau unter dem Eingabefeld.

### Umsetzung

- `tbclient/target.py`: `parse()` / `label()` – Rufzeichen, dann `V` oder `VIA`, Digis mit
  Komma und/oder Leerzeichen, Groß/klein egal, höchstens 8 Digis (AX.25). Abgewiesen: fehlendes
  `V`, Digi = Ziel oder eigenes Rufzeichen, Digi doppelt, ungültiges Rufzeichen.
- Kanal (`channels.py`): `via` neben `target`; Statuszeile „connecting OE3XYZ-1 via …“;
  Snapshot mit `via` und `label`. Ankommende Verbindungen haben keinen eigenen Pfad.
- AGW (Direwolf): mit Pfad Frame `'v'` (Anzahl + je 10 Byte Rufzeichen), sonst `'C'` wie bisher.
- KISS: `KissPort.open_link(remote, via)` – der eigene Layer 2 setzt den Pfad ins Adressfeld;
  `[ax25] v20_digis` greift dort wie bei der TinyBox.
- Web-GUI: Feld wächst mit dem Pfad (bis ~46 Zeichen), darunter beim Tippen „to OE3XYZ-1 · via
  OE3XTC-5 → OE3ABC“ bzw. die Fehlermeldung (rot), ab 3 Digis Hinweis „many hops, slow“.
  Titelleiste verbunden: Rufzeichen, daneben klein „via …“. Tooltip: Via ist nur Digipeating,
  ein Node wird selbst connectet und dort mit C weiterverbunden.
- Liste der letzten Ziele speichert den ganzen Pfad (`OE3XYZ-1 via OE3XTC-5`); leeres Feld
  connectet das letzte Ziel samt Pfad. Telnet-Testport: Pfad wird ignoriert.
- Verbindungslog: Spalte Station bleibt das Rufzeichen (ADIF), ohne Pfad.
- Tests: `TargetParseTests`, `ConnectViaAgwTests` (AGW `'v'`), `ConnectViaTests` (Client →
  Digipeater → TinyBox über KISS, beide Richtungen durch den Digi). Client 2026.10.18.7.
- **Funktest und Abnahme** (OE3GAS, 18.10.2026): getestet und abgenommen ✅

## CR72 – Wetterprognose auf Anfrage: User fordert die Prognose für seinen Locator an (offen, erfasst 24.10.2026)

### Erfassung (OE3GAS, 24.10.2026)

Ziel – genau das: **Ein User fordert den Forecast für seinen Locator an.** Er bekommt die
Prognose für seinen Standort zurück, nicht nur für die fest eingestellten Locators der
Aufgabenplanung (Weg 1, PLANUNG Abschnitt 20).

### Vorschlag (zur Entscheidung)

- **Befehl in der TinyBox**, z. B. `WX JN88BN` (Name noch offen; `WX` ist auch die Rubrik).
  Ohne Locator: der Locator aus dem User-Profil (CR73 – gibt es seit 24.10.2026; für die
  Prognose muss er 6-stellig sein). Prüfung wie in `geosphere_prognose.py` (6/8-stellig, im Modellgebiet).
- **Antwort an den Fragenden**, nicht als Bulletin: im Terminal sofort der Text aus
  `geosphere_prognose.bericht()` (≤ 60 Zeichen breit); im Client als persönliche Nachricht
  bzw. eigene Ansicht mit der Prognosegrafik (gleiche Tabelle wie die brocast-Seite).
- **Abruf in der TinyBox** über dieselben Funktionen (Locator → Punkt, API, Schritte) –
  dafür die Logik aus dem Skript in ein Modul ziehen, das TinyBox importiert. Abruf
  asynchron/mit Timeout, damit eine langsame API die Verbindung nicht blockiert.
- **Cache je Locator und Modelllauf:** das Modell rechnet nur alle 3 h neu – gleiche
  Anfragen innerhalb dieser Zeit ohne neuen API-Abruf. Grenze je User/Stunde gegen Missbrauch.
- **Über Funk:** nur die Antwort an den Fragenden; keine brocast-Seite je Anfrage (sonst
  füllt jede Einzelanfrage das Karussell). Offen: Locators, die oft angefragt werden,
  automatisch in Weg 1 aufnehmen?
- Offen: Nur für angemeldete User oder für jeden Connect? Ausgabe-Schritte (3 h / 48 h wie
  Weg 1, im Terminal evtl. 24 h)?

## CR73 – Benutzerprofil: Name, Locator, Home-BBS in TinyBox und Client (✅ umgesetzt 24.10.2026, Funktest offen)

### Erfassung (OE3GAS, 19./24.10.2026)

Bei der Recherche zu den Prompts anderer PR-BBS (FBB, BPQ, BayCom/OpenBCM, JNOS) fiel auf:
Die üblichen Systeme fragen neue Benutzer nach **Name, QTH/Locator und Home-BBS**. Das soll
die TinyBox auch können – und die Daten sind im Client genauso sinnvoll. Fragen: Wo werden
sie gespeichert, und wie wird ein User, der mit dem Client kommt, zur Eingabe eingeladen?

### Entscheidung (OE3GAS, 24.10.2026)

- **Verbindlich in der TinyBox**, eine Kopie im Client. Eingegeben wird im Client (Formular)
  oder im Terminal (Fragen nach dem Login, Befehle). Die TinyBox braucht die Daten selbst
  (Home-BBS fürs Forwarding, Anzeige im Chat, Locator für CR72), auch Terminal-User haben ein
  Profil, und ein neuer PC/Client findet das Profil wieder.
- **Home-BBS gleich mitnehmen.**
- **Sichtbar für alle**: im Chat, im Terminal (`I call`), in anderen Clients.
- **Die neuere Änderung gilt**, egal ob aus Client oder Terminal.

### Umsetzung

- **Ein Profil je Rufzeichen ohne SSID** (OE3GAS-7 = OE3GAS). Felder: Name (bis 12 Buchstaben,
  Leerzeichen, `-`, `.`, `'`; Umlaute erlaubt), Locator (4 oder 6 Stellen – der User wählt die
  Genauigkeit, alle sehen genau das), Home-BBS (Rufzeichen oder hierarchische Adresse, SSID
  fällt weg). Gemeinsame Prüfung, Prüfsumme und Zeilenformat: `prcore/profile.py`.
- **TinyBox**: Tabelle `profiles` (Schema 9) mit Zeit der letzten Änderung und Zeitpunkt der
  letzten Abfrage; Logik in `tinybox/profiles.py`.
  - **Fragen nach dem Login** (nur Terminal, nicht Sysop-Konsole): nach dem Willkommenstext
    `Please introduce yourself …`, dann nur die fehlenden Felder: `Your first name:`,
    `Your locator (e.g. JN88EP):`, `Your home BBS (e.g. OE3XSR):`. Enter überspringt eine
    Frage, `/AB` alle; eine falsche Eingabe wird erklärt und nochmals gefragt. Ein
    unvollständiges Profil wird höchstens alle 30 Tage wieder abgefragt. Abschaltbar mit
    `[mailbox] ask_profile = no`.
  - Kommt währenddessen `//CLIENT` (der Client meldet sich ca. 1 s nach dem Willkommen),
    enden die Fragen still – der Client hat sein eigenes Formular. Bei Verbindungsabbruch
    bleibt, was schon beantwortet war.
  - **Befehle**: `N name`, `NL locator`, `NH home-bbs` (`-` löscht, ohne Argument das eigene
    Profil), `I [call]` zeigt das Profil einer Station. Hilfe ergänzt; der Prompt bleibt
    gleich (kein Byte mehr je Prompt).
  - **Chat im Terminal**: `/W` und die Liste beim Betreten zeigen `OE3ABC (Hans, JN88)`.
  - **Sysop-Web-GUI**: Stationsliste (JLOG) mit Name, Locator, Home-BBS.
- **Client-Protokoll TB1**, neue Fähigkeit `PROF`:
  - `//OK … prof=<crc>` (4 Hex-Stellen) bzw. `prof=-`: der Client vergleicht mit seinem
    Profil – **gleich = nichts über Funk** (ca. 10 Byte je Login).
  - `//PROF t=<unix> loc=… home=… name=…` speichert (Antwort `//PROF OK <crc>`,
    `//PROF ERR <feld>`; ist das Profil in der TinyBox neuer, kommt es als `//PROF = …` zurück).
  - `//PROF ?` → `//PROF = <crc> t=… loc=… home=… name=…` bzw. `//PROF -`.
  - `//WHOIS call,call…` (max. 10) → je Station `//WI <call> loc=… home=… name=…` bzw.
    `//WI <call> -`, dann `//WIEND`.
- **Client** (`tbclient/profiles.py`, Version 2026.10.24):
  - Profil in den Client-Settings (nicht in `tbclient.conf`); Vorschlag für den Locator ist
    `[station] locator`. Nach `//OK`: gleiche Prüfsumme → nichts; TinyBox ohne Profil und im
    Client eingegeben → senden; sonst `//PROF ?` und die neuere Fassung (Zeit `t`) gewinnt.
  - **Einladung**: Balken über dem Chat „Introduce yourself …“ mit *Fill in* / *Later*,
    solange Name oder Locator fehlen und der Client mit einer TinyBox mit `PROF` verbunden ist;
    *Later* = in einer Woche wieder. Formular „My profile“ (auch unter Settings > My profile).
    Lehnt die TinyBox ab, öffnet sich das Formular mit dem Hinweis.
  - **Andere Stationen**: für die Teilnehmer im Board (`//WHO`, Join) einmal `//WHOIS`
    (gesammelt, eine Zeile für alle), eine Woche im Client gemerkt. Teilnehmerliste:
    „Gerhard · JN88EP · 45 km NE“ (Entfernung vom eigenen Locator).
- Tests: `tests/test_profile.py` (Prüfung, Format, TinyBox-Fragen, Befehle, `/W`, TB1,
  Client-Abgleich in beide Richtungen, Einladung, `//WHOIS`).
- **Offen / nächste Schritte**: Funktest PC1 ↔ PC2; Home-BBS für die Zustellung persönlicher
  Post an andere Mailboxen nutzen (White Pages, mit dem Forwarding); CR72 kann den Locator
  aus dem Profil nehmen (braucht 6 Stellen).

## CR74 – Heard: Rauschen mit gültiger Prüfsumme als „Rufzeichen“ (✅ 27.10.2026)

- **Beobachtung**: In „Heard on the channel“ standen Einträge wie `^?kDa?-8`, `??&/K?-8`
  oder `?%j?K-8`, in den kisshub-Verbindungsdaten eine Verbindung mit `OE3cAS-1`.
- **Ursache**: kisshub mit dem TNC des TM-D710 (9600 Bd, Datenband). Bei offener
  Rauschsperre wertet der TNC laufend Rauschen aus; ab und zu stimmt die 16-Bit-Prüfsumme
  zufällig. Weder kisshub noch Client prüften die Adressen – der Client nahm jede
  Quelladresse in die Heard-Liste.
- **Umsetzung**:
  - `prcore/ax25/frame.py`: `addresses_valid()` – Adressfeld vollständig, Rufzeichen nur
    A–Z und 0–9 (1–6 Zeichen), SSID 0–15.
  - kisshub 2026.10.27: Frames vom TNC mit ungültigem Adressfeld werden verworfen und gezählt
    (`invalid` in der Statuszeile und unter `queue` der Statusabfrage, INFO-Logzeile mit den
    ersten 32 Bytes hex). TinyBox-Kanalkarte zeigt „Dropped / invalid“.
  - Client 2026.10.27: `radio.decode()` liefert für solche Frames `None` (auch über
    Direwolf/AGW).
- Tests: `tests/test_kisshub.py` (`test_garbage_address_dropped`), `tests/test_ax25_v22.py`
  (`AddressesValidTests`).
- **Hinweis**: Ein Bitfehler, der zufällig ein gültiges Rufzeichen ergibt, kommt durch –
  dagegen hilft nur die Rauschsperre des Datenbands etwas zuzudrehen.

## CR75 – Eingehender Connect: gleich ins Terminal (✅ 07.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

Wenn eine Station mit dem Client connected, soll gleich in den Terminal-Mode umgeschaltet
werden – außer es handelt sich um eine TinyBox.

### Umsetzung (Client 2026.11.07)

- Bisher: Der eingehende Connect bekam einen freien Kanal als Terminal (CR46), die GUI blieb
  aber auf dem gerade gezeigten Kanal – nur der Chip blinkte.
- Jetzt: Geht der eingehende Kanal online und ist die Gegenstation **keine bekannte TinyBox**,
  setzt `ClientCore.focus_channel()` `focus = {n, seq}` im Snapshot. Die Web-GUI springt bei
  jedem neuen `seq` auf diesen Kanal und zeigt sein Terminal (auch aus Mailbox/Chat heraus).
  Beim Laden der Seite wird ein alter `seq` nur gemerkt, nicht angesprungen.
- „Bekannte TinyBox“ = `known_tinybox()`: die eigene TinyBox aus `tbclient.conf` oder eine,
  die schon einmal als TinyBox erkannt wurde (Settings `tinyboxes`). Dann bleibt die Ansicht,
  der Chip blinkt wie bisher.
- Gilt für AGW, KISS und AXUDP.
- Test: `tests/test_tbclient.py` (`test_incoming_connect_over_agw`, um CR75 erweitert).
- **08.11.2026:** Die Ausnahme „bekannte TinyBox“ ist entfernt – eine TinyBox ruft nie selbst
  einen Client an (Entscheidung OE3GAS, CR76). Jeder eingehende Connect springt in seine Ansicht.

## CR76 – Kennung `//TB?` nach dem Connect: TinyBox, TBClient oder fremde Station (✅ 07.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

Der Client soll gleich nach dem Connect eine Kennung schicken, auf die eine TinyBox reagiert,
eine andere BBS oder ein anderer Connect-Partner aber nicht. Eine TinyBox ruft nie von sich aus
einen Client an – ein SID-Austausch wie beim Forwarding ist daher nicht nötig. Zwei Clients
sollen sich ebenfalls erkennen (CR78).

### Umsetzung (Client 2026.11.07.2, TinyBox)

- Client: nach jedem **ausgehenden** Connect (Funk und AXUDP, nicht Telnet) eine Zeile
  `//TB? CLIENT v=<Version> caps=PROF,HEARD` (im Terminal als gesendete Zeile sichtbar).
- TinyBox (`clientproto.tb_probe()`): Antwort `//TB BOX v=<RELEASE> call=<Mailbox>`, sonst
  nichts – die Sitzung bleibt, wie sie ist. Kommt `//TB?` während der Profilfragen (CR73), wird
  die Frage danach noch einmal gestellt, statt sie zu beenden.
- Client auf `//TB BOX`: `//CLIENT`-Handshake, sofern kein anderer Kanal eine TinyBox im
  Client-Modus hat (**CR45 bleibt**); sonst bleibt der Kanal Terminal mit Hinweis. Auch eine
  späte Antwort (nach den 6 s Erkennungszeit, langsamer Weg) wird noch genommen.
- Client auf `//TB CLIENT …`: der Kanal ist Terminal mit Peer-Funktionen (CR78).
- Fremde Stationen: sehen die eine Zeile, antworten evtl. „unknown command“; der Kanal wird wie
  bisher nach 6 s Terminal. Ältere TinyBoxen ohne `//TB?` erkennt der Client weiter an
  „Welcome to TinyBox“.
- Tests: `tests/test_clientproto.py` (`test_tb_probe_*`), `tests/test_tbclient.py`
  (`test_foreign_bbs_terminal_and_states`, `test_incoming_connect_over_agw`).

## CR77 – Mehrere TinyBoxen gleichzeitig im Client-Modus (abgelehnt, 07.11.2026)

Vorschlag: Chat-Zustand je Kanal, damit mehrere TinyBoxen mit vollen Funktionen verbunden sein
können. **Entscheidung OE3GAS:** nein – die Grenze aus CR45 bleibt: eine TinyBox mit vollen
Funktionen, jede weitere als Terminal.

## CR78 – TBClient zu TBClient: Profile, Heard-Liste, Version (✅ Stufe 1, 07.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

Wenn sich zwei Clients connecten, sollen sie sich erkennen und gemeinsame Funktionen
freischalten.

### Umsetzung Stufe 1 (Client 2026.11.07.2, `tbclient/peer.py`)

- Erkennung über CR76: Der Anrufer schickt `//TB? CLIENT v=… caps=…`, der Angerufene antwortet
  `//TB CLIENT v=… caps=PROF,HEARD`. Beide Kanäle bleiben Terminal; Steuerzeilen (`//…`) des
  Gegenübers erscheinen nicht als Text, sondern als `***`-Hinweise.
- **Profil:** Jede Seite schickt einmal `//PROF loc=.. home=.. name=..` (nur ein selbst
  eingetragenes Profil). Anzeige in der Terminal-Leiste: Name, Locator, Entfernung und Richtung
  aus den Locatoren, Home-BBS; das Profil kommt auch in den Profil-Speicher (wie `//WI`).
- **Heard-Liste:** Knopf „Heard there“ → `//HEARD?`, Antwort
  `//HEARD <call>=<min> …` (bis 10 Stationen, `//HEARD -` = niemand); im Terminal als Zeile.
- **Version:** Die Leiste zeigt „TBClient <Version>“, die Kopfzeile „connected · TBClient …“;
  ist der andere Client neuer, steht ein Hinweis im Terminal.
- API: `POST /api/peer/heard {"ch": n}`; Snapshot: `channels[].peer`.

### Fehler behoben (Client 2026.11.07.3)

- **Beobachtung** (OE3XHU ↔ OE3GAS-10): Kanal mit dem Tag „chat“, Chat-Ansicht mit „Join a
  board first“, keine Eingabe, obwohl die Kopfzeile „connected · TBClient …“ zeigte.
- **Ursache:** Der Kanal war vorher der Chat-Kanal einer TinyBox-Verbindung und blieb es nach
  deren Ende. Früher löste das die 6-s-Erkennung (`to_terminal()` → `detach()`); seit CR76/78
  bricht die Erkennung beim `//TB CLIENT` ab, und auch ein eingehender Connect hat nie gelöst.
- **Umsetzung:** `Channel._terminal()` – Terminal-Modus, Ansicht Terminal, und war der Kanal
  der Chat-Kanal, wird er gelöst. Gilt für Peer (beide Seiten), eingehenden Connect und die
  zweite TinyBox. Test: `test_incoming_connect_over_agw`.

### TinyBox in jedem Kanal (Client 2026.11.07.4)

- **Beobachtung (OE3GAS):** Ein Connect zur TinyBox klappte nur auf Kanal 1.
- **Ursache:** „Connect“ in der Chat-Ansicht („Not connected to OE3GAS-1“) und in den
  Einstellungen schickte keinen Zielruf – der Client nahm die letzte Station *dieses Kanals*
  bzw. die zuletzt verbundene (z. B. den TBClient OE3GAS-10). Nur Kanal 1 hatte noch die
  TinyBox als letzte Station.
- **Umsetzung:** `connectTinybox()` in `app.js`: Ziel ist immer die angezeigte TinyBox; im
  gezeigten Kanal, wenn er frei ist, sonst im ersten freien.
- Dazu: `//TB BOX` kommt jetzt auf einer eigenen Zeile (TinyBox); steht es bei einer älteren
  TinyBox direkt hinter dem Prompt, trennt der Client es ab (`test_tb_box_behind_the_prompt`).

### Stufe 2: eigene Ansicht „TBClient“ (Client 2026.11.07.5)

- **Wunsch (OE3GAS):** Nach dem Connect zu einem TBClient nicht das Terminal, sondern eine
  eigene Ansicht, an der man sieht, dass man mit einem TBClient verbunden ist.
- **Umsetzung (`app.js`, Ansicht `peer`):** Sobald der Kanal einen Peer hat, schaltet die GUI
  von selbst um (beide Seiten, beim Angerufenen mit CR75). Oben eine Karte: Rufzeichen (mit
  Digi-Pfad), Name, Locator, Entfernung/Richtung, Home-BBS, TBClient-Version, seit wann
  verbunden, zuletzt „Hears: …“. Darunter die Zeilen als Sprechblasen – die eigenen rechts, die
  des anderen links, mit Uhrzeit; `***`-Hinweise klein dazwischen, Protokollzeilen (`//TB?` …)
  ausgeblendet. Eingabe „Message to <call>“. Knopf „Terminal“ ↔ „TBClient view“ schaltet auf
  die rohe Terminal-Ansicht und zurück; „Heard there“ wie bisher.
- Die Uhrzeit der Blasen ist die, zu der die Zeile in der GUI erschienen ist (nach Neuladen der
  Seite die Zeit des Neuladens).

### Stufe 3: Ansicht schmäler, Linkqualität (Client 2026.11.07.6)

- **Wunsch (OE3GAS, 07.11.2026):** Chat-Feld schmäler und zentriert, keine Hinweise wie
  „online“/„disconnected“, Linkqualität anzeigen. Keine Trennlinie (die Uhrzeit steht in den
  Blasen).
- Karte, Blasen und Eingabe in einer Spalte von höchstens 760 px, mittig; am Handy volle Breite.
  `***`-Zeilen erscheinen nur noch in der rohen Terminal-Ansicht.
- **Linkqualität:** keine Zeilen über Funk. Jede Seite liest die Zähler ihrer eigenen Verbindung
  alle 30 s (`PEER_Q_SEC`): über AGW mit `Q` beim TinyBox-Fork von Direwolf
  (oe3gas/direwolf-tinybox, `TINYBOX.md`), über KISS/AXUDP aus dem eigenen AX.25
  (`Ax25Link.counters()`, dieselben Namen). Die Auswertung (Fenster 50 Frames / 30 min, Balken
  nach Verlust) ist jetzt `prcore/linkq.py` – TinyBox und Client rechnen gleich
  (`tinybox/linkq.py` importiert nur noch). Aus den eigenen Zählern kommen beide Richtungen:
  → `i_retry / (i_new + i_retry)`, ← `(rej_tx + retry_rx) / i_rx`.
- Karte: „→ Balken OE3GAS-10 ← Balken“, Tippen zeigt Frames, Wiederholungen, REJ, T1, SRT und den
  Netto-Durchsatz (`bytes_new / tx_busy_ms`). Unter 20 Frames je Richtung graue Balken. Direwolf
  ohne Fork: „no link data (Direwolf without the TinyBox fork)“; AXUDP: kein Funkweg.

### Stufe 4: Chat-Verlauf (Client 2026.11.07.6, `tbclient/peerchat.py`)

- **Wunsch (OE3GAS):** Verlauf behalten; beide müssen dasselbe sehen – Hash austauschen, Löschen
  per Knopf, der Partner löscht mit; passt es nicht zusammen, löschen beide.
- **Speicher:** `data/tbclient/peerchat.db` (SQLite, nicht im Repo), je Gegenstation (Rufzeichen
  mit SSID) die letzten **100** Zeilen je Richtung.
- **Zwei Ströme mit Hash-Kette:** gesendet und empfangen getrennt (AX.25 hält die Reihenfolge je
  Richtung; gekreuzte Zeilen machen so keinen Unterschied). `h(n) = sha1(h(n-1) + LF + Text)[:8]`.
  Dazu eine **Generation** (Zufall, neu bei jedem Löschen).
- **Beim Connect** (beide kennen `HIST`): `//HIST g=<gen> m=<n>:<h> y=<n>:<h>`. Jede Seite prüft
  ihren gesendeten Strom gegen das, was die andere empfangen hat:
  - gleich → nichts;
  - der anderen fehlt nur das Ende (höchstens 10 Zeilen, z. B. beim Disconnect verloren) → die
    Zeilen gehen noch einmal hinaus (`//HM <n> <unix> <text>`), kein Schaden;
  - sonst → `//HIST CLR g=<neu>`, beide löschen, Hinweis „chat history removed (not the same on
    both sides)“.
  - Andere Generation (einer hat gelöscht, als keine Verbindung bestand, oder erster Kontakt) →
    beide löschen und nehmen die größere Generation; ein Hinweis nur, wenn wirklich etwas weg war.
- **Knopf „Delete history“:** löscht hier, neue Generation, Hinweis „chat history removed“. Ist der
  andere verbunden: `//HIST DEL g=<gen>` – er löscht sofort, Hinweis „chat history removed by …“.
  Sonst merkt er es beim nächsten Connect an der Generation.
- Die TBClient-Ansicht zeigt den gespeicherten Verlauf (auch nach dem Disconnect, Eingabe dann
  gesperrt); `POST /api/peer/clear {"ch": n}`, Snapshot `peerchat`.
- Tests: `tests/test_peerchat.py`.

### Status-Chips (Client 2026.11.07.9)

- **Wunsch (OE3GAS, 07.11.2026):** „not connected“ als orangefarbener Chip (Kopfzeile und Karte
  der TBClient-Ansicht), neben „TBClient“ ein grüner Chip „connected to <call>“, in der
  Bulletin-/Mail-Liste „not loaded · Größe“ als orangefarbener Chip.
- Umsetzung: `.st-chip.ok` / `.st-chip.warn` (`--ok`/`--warn`), `.tag.notloaded`.
- 08.11.2026: Größe neben „not loaded“ in Bytes („not loaded · 512 bytes“).

### Bewertung bei wenigen Frames (07.11.2026, TinyBox und Client)

- **Anmerkung (OE3GAS):** Erst ab 20 Frames zu bewerten ist zu streng – 5 Frames ohne REJ sind
  schon ein sehr guter Link.
- **Umsetzung (`prcore/linkq.py`, gilt für beide):** unter `quality_min_frames` (20) zählen die
  Ereignisse statt der Prozente: 0 Wiederholungen/REJ → 5 Balken, jede kostet einen, ab 5 → rot;
  T1 wie bisher −1. „Vorläufig“ (`tentative`), solange keine Richtung 20 Frames hat: blasser in
  TinyBox-Web, Client-Chat, TBClient-Karte, `STAT` zeigt `~~~~~`. Ohne Frames grau. Siehe
  PLANUNG 14.

### Stufe 5: Emoticons/Emoji (Client 2026.11.08.2)

- Dieselbe Regel wie im TinyBox-Chat (PLANUNG 12.6, CR28): Emojis gehen nie als Unicode über
  Funk, sondern als klassisches Emoticon (`:-)`) bzw. `~XY`, `~~` = Tilde. Getippte Emoticons
  werden sofort zum Emoji, Knopf ☺ öffnet die Auswahl (ASCII-Smileys zuerst); darüber die
  Anzeige „n bytes on air: …“ bzw. welche Emojis nicht sendbar sind.
- Im Verlauf steht, was über Funk ging (beide Seiten gleich, Hash-Kette bleibt stimmig); die Blasen
  zeigen es als Emoji. Die rohe Terminal-Ansicht zeigt die Funkform.
- Ältere Clients (vor 2026.11.08.2) zeigen in ihrer Ansicht die Funkform `:-)`.

### Stufe 6: Bilder (Client 2026.11.08.3, `tbclient/peerimg.py`)

- Wie CR12, nur ohne TinyBox: Der Sender behält das Bild (verkleinert im Browser, derselbe
  Dialog mit klein/normal/groß, höchstens 8 KB). Über Funk geht nur der Verweis
  `~#<hash><größe><blurhash> Bildunterschrift` als Chat-Zeile – er steht im Verlauf beider Seiten.
- Der andere sieht den unscharfen Platzhalter mit Größe und Ladezeit und holt das Bild **per
  Antippen direkt beim Sender**: `//IMG <hash>` → `//I <hash> <offset> <gesamt>` + die Bytes am
  Stück (das AX.25-Fenster regelt das Tempo) bzw. `//NOIMG <hash>`.
- Ein Client gibt ein Bild nur der Station, der er es geschickt hat (Verweis in seinem
  gesendeten Verlauf mit ihr).
- Ein abgebrochener Download beginnt beim nächsten Antippen von vorn (Offset ist im Protokoll
  vorgesehen). Beide brauchen die Fähigkeit `IMG`; nicht über Telnet. Ablage wie die
  TinyBox-Bilder in `data/tbclient/images/`.
- Test: `tests/test_peerchat.py` (`test_picture_between_clients`).

### Stufe 7: Dateien und Uhrzeit (Client 2026.11.08.4, `tbclient/peerfile.py`)

- **Dateien** (Knopf 📎, höchstens 64 KB): wie die Bilder – der Sender behält die Datei
  (`data/tbclient/files/<hash>`), über Funk geht nur die Chat-Zeile
  `~%<hash> <bytes> <bytes on air> <name>` (im Verlauf beider Seiten). Der andere sieht Name,
  Größe und Zeit auf Funk und holt sie per Antippen: `//FGET <hash>` →
  `//F <hash> <z|r> <n>` + n Bytes bzw. `//NOFILE <hash>`. `z` = LZHUF (B0), `r` = roh, wenn LZHUF
  nichts bringt (ZIP, JPEG). Der Hash geht über die Datei selbst, der Empfänger prüft nach dem
  Entpacken. Nur an die Station, der sie angeboten wurde. Danach „Save“ (Download
  `/file/<hash>/<name>`, Name entschärft). Packen im Thread (64 KB ≈ 0,3 s).
- **Uhrzeit:** `//TB?` und `//TB CLIENT` tragen `t=<Unix-Zeit>`. Die Karte zeigt „🕒 clocks agree“
  (bis 10 s, die Zeile war ja kurz unterwegs) oder „their clock is 3 min ahead/behind“, ab einer
  Minute als orangefarbener Chip.
- Test: `tests/test_peerchat.py` (`test_file_between_clients`).

### Stufe 8: Ping, Speedtest, Schach, QSL, Karte, Zustellhaken (Client 2026.11.08.5)

Auf Vorschlag Claude, freigegeben von OE3GAS (08.11.2026). Fähigkeit `FUN`
(`tbclient/peerfun.py`, `tbclient/web/chess.js`):

- **Ping:** `//PING <token>` → `//PONG <token>`, Laufzeit hin und zurück (letzte 5) in der Karte.
- **Speedtest:** ein Knopf, beide Richtungen: `//ST 2048 go` + 2048 Bytes → `//STR 2048 <ms>`, dann
  `//ST 2048 back` + 2048 Bytes zurück. Der Empfänger misst von der Zeile bis zum letzten Byte;
  Ergebnis „→ … B/s ← … B/s“ (4 KB auf Funk je Test).
- **Schach:** `//CHESS NEW w|b`, `//CHESS M <uci>`, `//CHESS RESIGN`. Regeln (Zugerzeugung,
  Schach, Rochade, en passant, Umwandlung in Dame, Matt/Patt) im Browser, `chess.js` – geprüft mit
  Perft bis Tiefe 3 (8902). Der Client prüft nur, wer am Zug ist; die Partie liegt in den
  Einstellungen je Station und geht nach Neustart/nächstem Connect weiter. Brett mit der eigenen
  Farbe unten, Zug per Antippen; Hinweise im Verlauf („started a chess game“, „resigned“).
- **QSL:** Knopf „QSL“ schickt eine Chat-Zeile `~Q f=<MHz> t=<UTC> loc=<Locator> q=<Balken>`; beide
  Seiten zeigen eine QSL-Karte, „ADIF“ lädt den QSO-Eintrag (CALL, QSO_DATE, TIME_ON, FREQ,
  MODE=PKT, GRIDSQUARE/MY_GRIDSQUARE, QSL_RCVD/QSL_SENT).
- **Mini-Karte** in der Karte: beide Stationen aus den Locatoren, Linie, Locator-Gitter (2°×1°),
  Norden oben, Entfernung und Richtung; Klick öffnet die Route bei OpenStreetMap. Ohne Kacheln,
  nichts aus dem Netz.
- **Zustellhaken:** Eigene Zeilen zeigen „·“ unterwegs und „✓“, sobald Direwolf/KISS nichts mehr
  ausstehend meldet (Abfrage alle 3 s, nur Zeilen dieser Verbindung). Spalte `ok` in
  `peerchat.db` (wird beim Start ergänzt).
- Test: `tests/test_peerchat.py` (`test_ping_speed_chess_tick`).

### Später (eigene Stufen)

- Reaktionen auf Blasen in der TBClient-Ansicht.
- Sprachnachrichten mit Codec2 (WebAssembly im Browser, ~1,5 KB je 10 s) – eigenes Projekt.

## Kanal-Maximum in `tbclient.conf` (✅ 07.11.2026, zu CR45)

`[tinybox] max_channels` (Standard 5, erlaubt 1 … 10) ersetzt die feste Grenze 5 aus CR45.
Eingehende Connects und der Kanal des Mail-Abgleichs zählen mit. Alt+1 … Alt+9 schalten um,
Kanal 10 nur per Klick (Alt+0 bleibt der Monitor).

## CR79 – APRS-Statistik: Netzgraph und Geräte-Torte (✅ Stufe 1 07.11.2026, Stufe 2 08.11.2026)

### Erfassung (OE3GAS, 07.11.2026)

- Eine anschauliche Grafik zur APRS-Statistik mit Bubbles, Knoten und Verbindungsvektoren:
  wer erreicht mich über wen.
- Filter nach Art der Pakete: alle, Position, Telemetrie usw.
- Auswertung der verwendeten Geräte als Tortendiagramm.
- Entwurf: Visualisierung im Chat (claude.ai), Varianten Kraft / Hop-Radar / Karte.

### Umsetzung Stufe 1 (Client 2026.11.07.8)

- **Daten:** `AprsStats.graph(window, me=…)` in `prcore/aprsstats.py`, API
  `GET /api/aprs/graph?win=<s>`. Knoten: Stationen, Digipeater, iGates und die eigene Station
  (`kind` = `station` / `digi` / `igate` / `me`), mit letzter bekannter Position (auch außerhalb des
  Zeitfensters, damit Digis mit eigener Bake einen Ort haben), Gerät und `moving` (Positionen
  > 1 km auseinander). Wege: Absender [→ iGate] → Digi … → ich, zusammengezählt je Weg,
  Pakettyp, Gerät und Internet-Herkunft – so filtert die GUI selbst. Höchstens die 80
  aktivsten Absender (`GRAPH_MAX_STATIONS`). Test: `test_graph`.
- **Anzeige** (`tbclient/web/aprsgraph.js`, reines SVG ohne Bibliothek – der Client läuft auch
  ohne Internet): Karte „Network“ in der APRS-Statistik nach „Frames over time“.
  - Bubbles: eigene Box grau, Digi orange, iGate grün, Station blau; mobile Stationen mit
    gestricheltem Ring, geschätzte Position (Digi ohne Bake: Mitte der Nachbarn) gepunktet.
    Größe = Frames durch den Knoten, Linienstärke = Frames je Link, Pfeil zur eigenen Station,
    Internet → Funk grün gestrichelt.
  - **Hop-Radar** (Standard): Ring = Hops (direkt gehört, 1 Hop, 2 Hops …), Winkel = Richtung vom
    eigenen Locator, Nachbarn je nach Größe auseinandergeschoben.
  - **Karte:** echte Richtung, Entfernung auf Wurzel-Skala (nahe Stationen bleiben getrennt),
    Ringe in km; nur mit Locator in `tbclient.conf`.
  - **Kraft:** nur die Struktur, Cluster um die Digis. Wechsel der Ansichten gleitend; die
    gewählte Ansicht bleibt im Browser gemerkt.
  - **Filter:** Paketart (Alle + die im Fenster vorkommenden Typen), „min. frames per link“.
    Die Knoten bleiben beim Filtern an ihrem Platz.
  - Überfahren: die Wege dieser Station hervorgehoben, Zeile darunter mit Frames, Entfernung,
    Hops, Gerät. Klick: Stationsseite (CR65).
  - **Geräte-Torte:** Anteile nach Frames oder Stationen, folgt dem Paketart-Filter; sieben
    Farben, der Rest als „Other“. Klick auf ein Stück oder eine Zeile filtert den Graphen auf die
    Stationen mit diesem Gerät (Chip „Device: … ×“ hebt es auf).

### Stufe 2 (✅ 08.11.2026, Ideen OE3GAS/Claude)

- **Zeitachse:** Regler über das Zeitfenster, Kanten blenden auf und ab – man sieht, wann ein
  Digi ausfällt oder ein Mobiler durchs Netz wandert.
- **Kanten nach Hop-Typ:** kräftig für einen Hop über WIDE1, blass für WIDE2-2-Fluten.
- **Kanal-Health:** roter Rand an Digis, über die viele „unchanged repeats“ laufen (Sins).

### Umsetzung Stufe 2 (Client 2026.11.08.13)

- **Daten** (`AprsStats.graph`): jeder Weg hat zusätzlich `tb` – Frames je Zeitabschnitt
  (`GRAPH_BUCKETS` = 24 über das Fenster, `bucket_sec` in der Antwort) – und `hop`, den Hop-Typ
  (`hop_type()` aus den angeforderten Hops der Aliase): `direct` (kein Pfad), `wide1`
  (WIDE1-1), `wide2` (WIDE2-1, WIDE1-1,WIDE2-1, WIDE2-2), `flood` (mehr, oder „long path“).
  Digipeater bekommen `through` (Frames über ihn), `rep` (Anteil), `rep_n` und `rep_calls`:
  Frames von Stationen, die die Sünden-Liste als „unchanged repeat“ oder „too often“ führt.
  Test: `test_graph_stage2`.
- **Zeitachse:** Regler „Time“ unter den Filtern. Ein Sechstel des Fensters gleitet darüber,
  ganz rechts = ganzes Fenster; ▶ spielt Abschnitt für Abschnitt ab (0,7 s, läuft über die
  15-s-Aktualisierung weiter). Wege und Bubbles ohne Frames im Ausschnitt blenden auf 6 % aus,
  die Linienstärke folgt den Frames im Ausschnitt (auf das ganze Fenster skaliert, damit sich
  Abschnitte vergleichen lassen). Die Knoten bleiben stehen. Daneben die Uhrzeit des
  Ausschnitts.
- **Linien nach Hop-Typ:** je Link der Typ mit den meisten Frames – kein Pfad/WIDE1 kräftig,
  WIDE2 blass, Flood sehr blass und gepunktet; zweite Legendenzeile; im Tooltip der Link die
  Aufteilung („WIDE2 12, flood 3“).
- **Kanal-Health:** roter Ring um Digipeater ab 10 % unnötige Wiederholungen (mind. 3 Frames),
  Ringstärke nach Anteil; Tooltip und Hover-Zeile nennen Anteil und die Stationen.


## CR80 – TBClient-Ansicht in drei Spalten, Aktionen rechts (✅ 08.11.2026)

### Erfassung (OE3GAS, 08.11.2026)

- Bei einem Connect mit einem anderen TBClient bekommt die Ansicht drei Spalten:
  - links die Karten (Chat Boards, Mail, Bulletins, Station) wie bisher,
  - in der Mitte das Dialogfenster (Profil, Linkqualität, Mini-Karte, Sprechblasen, Eingabe),
  - rechts eine neue Spalte, so breit wie die linke.
- In die rechte Spalte, untereinander: **Ping**, **Speed test**, **Chess**, **QSL**, dazu
  **Heard there** und **Delete history**. In der Kopfzeile des Dialogs bleibt nur „Terminal“.
- **Speed test:** vorher eine Bestätigung einholen. Der Benutzer soll wissen, dass nun beide
  Stationen je ca. 20 s den Kanal belegen.
- Wurde schon ein Speed test gemacht: der Wert neben dem Knopf (→ … B/s ← … B/s) und
  „tested xx min ago“.
- Ebenso der Wert des letzten Ping daneben, sonst „–“.
- Entwurf: Design-Canvas „TBClient 3 Spalten“ (claude.ai) – Hauptansicht, Bestätigung,
  Zustände der rechten Spalte (nichts / läuft / schon gemacht).

### Vorschlag zur Umsetzung (Claude)

- Rechte Spalte als zwei Karten im Stil der linken: „WITH <call>“ (Ping, Speed test, Chess, QSL)
  und „CHANNEL“ (Heard there, Delete history – rot umrandet).
- Unter jedem Knopf eine Ergebniszeile: Ping „1.8 s · 4 min ago“ bzw. „–“; Speed test Wert und
  „tested 3 min ago“ bzw. „–“, beim Laufen ein Fortschrittsbalken; Chess „your move“ (pulsierend,
  Client 2026.11.08.8) bzw. „waiting for <call>“; QSL „sent hh:mm“.
- Ergebnisse von Ping und Speed test je Gegenstation in den Settings merken, damit „tested
  xx min ago“ auch nach einem neuen Connect stimmt.
- Bestätigung: Dialog „Start speed test with <call>?“ mit Datenmenge und letztem Ergebnis,
  Knöpfe Cancel / Start test. Die Dauer rechnet der Client aus dem letzten Ergebnis, sonst
  aus 1200 Bd (≈ 20 s je Richtung bei 2048 Bytes).
- Schmale Fenster / Handy: die rechte Spalte rutscht unter das Profil (eine Zeile mit den
  Knöpfen, die Werte darunter), wie heute.
- Größe des Speed tests: **1024 Bytes** je Richtung (OE3GAS 08.11.2026, Client 2026.11.08.9;
  vorher 2048). Die Bestätigung nennt dann ca. 10 s je Richtung bei 1200 Bd.

### Umsetzung (Client 2026.11.08.10)

- `#peer-side` rechts (190 px wie die linke Spalte), nur im TBClient-View ab 1000 px; dort
  verschwinden die Knopfzeile unter dem Profil und „Heard there“/„Delete history“ aus der
  Kopfzeile. Schmaler bleibt alles wie bisher.
- Karte „With <call>“: Ping, Speed test …, ♟ Chess, QSL, darunter der letzte Wert oder „–“;
  „your move“ pulsierend bzw. „waiting for <call>“. Karte „Channel“: Heard there, Delete
  history (rot, auch ohne Verbindung).
- Letzte Ergebnisse je Gegenstation in den Settings (`fun_last`, höchstens 50 Stationen):
  „1.8 s · 4 min ago“, „→ 142 B/s ← 138 B/s“ + „tested 3 min ago“.
- Speed test fragt vorher (Dialog): Dauer aus dem letzten Ergebnis, sonst ≈ 120 B/s; gilt
  auch für den Knopf in der schmalen Ansicht. Test: `test_ping_speed_chess_tick`.

## CR81 – Schiffe versenken zwischen zwei TBClients (offen, 08.11.2026)

### Erfassung (OE3GAS, 08.11.2026)

- „Schiffe versenken“ als Spiel Client zu Client, wie Schach (CR78 Stufe 8).
- Frage an Claude: andere geeignete Spiele.
- Entscheidung Prüfung am Ende (OE3GAS, 08.11.2026): **behalten**, als stille Hintergrund-
  Kontrolle. Schummeln ist kaum zu erwarten (dafür müsste jemand den Code ändern), sie findet aber
  auch Fehler, etwa einen auseinandergelaufenen Spielstand nach Neustart oder verlorener Zeile.
  Im Spiel merkt man nichts davon; nur wenn etwas nicht stimmt, steht „board does not match“ im
  Ergebnis.

### Vorschlag zur Umsetzung (Claude)

- **Regeln:** 10 × 10 Felder (A–J, 1–10), Flotte 5 – 4 – 3 – 3 – 2, Schiffe gerade, dürfen
  sich nicht berühren. Wer trifft, schießt noch einmal (Variante, beim Start wählbar?).
- **Protokoll** (Zeilen mit `//`, nichts im Chat-Verlauf außer Start und Ergebnis, Fähigkeit
  `FUN` wie bei Schach):
  - `//BS NEW <hash>` – lädt ein, `<hash>` = sha1 über die eigene Aufstellung + Zufallswert
  - `//BS OK <hash>` – nimmt an, mit dem Hash der eigenen Aufstellung
  - `//BS F E5` – Schuss
  - `//BS R E5 miss|hit|sunk 3` – Antwort
  - `//BS END <aufstellung> <salt>` – am Ende legen beide offen (rund 100 Bytes). Der Client
    des anderen prüft still den Hash und jede Antwort im Spiel; nur bei einer Abweichung steht
    „board does not match“ im Ergebnis.
  - `//BS RESIGN`
- Ein Zug sind rund 15 Bytes, ein ganzes Spiel unter 3 kB über Funk.
- **Ansicht:** zwei Raster nebeneinander (eigene Flotte, Schüsse auf den anderen), Aufstellen
  per Klick oder „random“; „your move“ pulsierend in der rechten Spalte (CR80).
- Spiel je Gegenstation in den Settings, geht nach Neustart oder neuem Connect weiter.

### Weitere Spiele (Ideen, noch nicht entschieden)

- Ein gemeinsamer Rahmen `//G <spiel> …` für alle weiteren Spiele: Einladung, Zug, Aufgabe,
  Speichern, „your move“ – ein neues Spiel bringt nur seine Regeln (in der Web-GUI) mit.
- **Vier gewinnt** – ein Zeichen je Zug, schnell, kennt jeder.
- **Mühle** – klassisch, wenige Züge, kurze Nachrichten.
- **Reversi (Othello)** – 8 × 8, ein Feld je Zug.
- **Dame** – wie Schach, einfachere Regeln.
- **Mastermind** – Geheimcode mit Hash wie bei Schiffe versenken.
- **Würfelspiele (Kniffel)** – faire Würfel ohne Schiedsrichter: beide schicken zuerst den Hash
  einer Zufallszahl, dann die Zahl; der Wurf kommt aus beiden zusammen.
- Funkerisch: **Locator-Raten** – die Gegenstation nennt ein gehörtes Rufzeichen, man tippt
  dessen Locator, Punkte nach Entfernung.

## CR82 – TinyBox: `RELOAD` – Konfiguration neu einlesen ohne Disconnect (✅ 08.11.2026)

### Erfassung (OE3GAS, 08.11.2026)

- `RESTART` trennt alle User: die Sessions werden beendet und die TinyBox schließt ihre
  AGW-Verbindung, Direwolf räumt dabei alle AX.25-Links dieses Clients ab.
- Neu: Sysop-Befehl **`RELOAD`** liest `tinybox.conf` neu ein und übernimmt **nur** die Werte, die
  sich im laufenden Betrieb ändern lassen. Kein User wird getrennt, die AGW-Verbindung bleibt stehen.
- Danach eine Liste: **geänderte Werte** (übernommen) und **ignorierte Werte**, die einen
  `RESTART` brauchen.

### Vorschlag zur Umsetzung (Claude)

- **Ablauf:** wie bei `RESTART` zuerst `config.load()`. Hat die Datei einen Fehler, wird nichts
  geändert (Meldung wie `RESTART_BAD_CONFIG`). Sonst neue und laufende Konfiguration Feld für Feld
  vergleichen (`[abschnitt] schlüssel`), live-fähige Werte übernehmen, die anderen stehen lassen.
- **Ausgabe**, z. B.:

  ```
  RELOAD tinybox.conf
  changed:
    [beacon] interval_min      30 -> 60
    [chat_boards] DX           new (24h)
  needs RESTART (ignored):
    [agw] port                 8000 -> 8001
  ```

  Nichts geändert: `RELOAD: no changes`. Passwörter und Token nur als `(changed)`, nie im Klartext.
  Dieselbe Liste geht ins Log. Ignorierte Werte wirken beim nächsten `RESTART` (der liest die
  Datei ohnehin neu).
- **Wo:** überall, wo es `RESTART` gibt – lokale Sysop-Konsole und Sysop-Web-GUI
  (Knopf neben Restart, Liste als Antwort).
- **Live-fähig (Entwurf, beim Einbauen Abschnitt für Abschnitt prüfen):**
  - `[station]` sysop_call, sysop_via_radio, haddress, qth, freq, locator
  - `[mailbox]` alle Werte (max_users, idle_timeout_min usw. gelten ab dann; laufende Sessions
    bleiben, auch wenn mehr verbunden sind als das neue max_users)
  - `[logging]` level, debug, keep_days, monitor
  - `[beacon]`, `[update]`, `[client]`, `[rubrics]`, `[chat_motd]`
  - `[chat]` history_lines, max_line, image_max; `[chat_boards]` neue und geänderte Boards.
    Ein gelöschtes Board, in dem gerade jemand ist, bleibt bis zum Leeren bzw. bis `RESTART`
    (steht dann unter „ignored“)
  - `[brocast]` publish, token, destinations, rubrics, max_bytes, sync_min, air_days,
    alert_destinations
  - `[inbox]` poll_sec
  - `[forward]` bid_days, aliases, publish_to_brocast, Partner (neu, geändert, entfernt) samt
    routes, areas, timeout, auto. Ein Partner, mit dem gerade eine Forward-Session läuft, wird
    erst nach deren Ende geändert
  - `[agw]` quality_* (Linkqualität)
- **Nur mit `RESTART`** (immer unter „ignored“):
  - `[station]` mailbox_call (ist bei Direwolf registriert)
  - `[radio]`, `[agw]` host/port/radio_port/paclen/max_outstanding, `[kiss]`, `[ax25]`
  - `[telnet]`, `[axudp]`, `[web]`, `[console]`, `[mqtt]` (Sockets, Verbindungen)
  - `[storage]`, `[logging]` log_dir, `[inbox]` enabled/directory, `[forward]` enabled/listen_*,
    `[chat]` enabled
- Unbekannte oder veraltete Schlüssel: wie beim Start als Hinweis (CR70) mit ausgeben.

### Umsetzung (08.11.2026)

- `tinybox/reload.py`: liest die Datei mit `config.load()` (Fehler → nichts geändert), vergleicht
  Feld für Feld und ändert die **laufenden Konfigurationsobjekte an Ort und Stelle** – alle Teile, die
  eine Referenz darauf halten (Sessions, Chat, Forward, brocast, Bake …), sehen die neuen Werte sofort.
  Die Regeln stehen oben in der Datei (`LIVE`).
- Was beim Start kopiert wurde, wird nachgezogen: `max_users` in der Session-Liste, Log-Level und
  `debug` in den Log-Filtern, `keep_days`, Locator für die Entfernung im APRS-Monitor, eigene Adresse
  im Forward-Router; Forward-Scheduler wird geweckt, bei geänderten Rubriken werden zurückgehaltene
  Bulletins wie beim Start entschieden; `[beacon] enabled` startet bzw. stoppt die Bake, ein neues
  `interval_min` startet sie neu (erste Bake nach `first_after_sec`).
- Gegenüber dem Entwurf **nur mit RESTART**: `[station] sysop_call` (die Konsole läuft unter diesem
  Call), alle `[agw]`-Werte inklusive `quality_*` (die Linkqualität rechnet je Verbindung mit den
  Werten vom Verbindungsaufbau), `[logging] monitor`, `[brocast] publish`, `[update] check`.
- Chat-Boards: neue Boards kommen **ans Ende** (die Nummern der anderen bleiben, die Clients kennen
  sie als `TBCHAT-n`), geänderte Boards (Haltezeit, Beschreibung, noimg, MOTD) sofort. Gelöschte
  Boards und eine neue Reihenfolge: „needs RESTART“.
- Forward-Partner: neu, geändert, entfernt sofort; eine laufende Forward-Session arbeitet mit den
  alten Werten zu Ende. Partner-`password` und `login` erscheinen nur als `(changed)`, ebenso Token.
- Ignorierte Werte bleiben auf dem alten Stand und stehen bei jedem weiteren `RELOAD` wieder in der
  Liste, bis ein `RESTART` sie übernimmt. Die Liste geht auch ins Log.
- Sysop-Konsole `RELOAD` (Hilfe ergänzt), Sysop-Web-GUI Knopf **Reload** (Ergebnis im Dialog),
  `POST /api/reload`. Tests: `tests/test_reload.py`.

## CR83 – Frame-Monitor auch im AGW-Mode (✅ 08.11.2026, Funktest offen)

### Erfassung (OE3GAS, 08.11.2026)

- Auf der Hinteralm (OE3GAS-1, AGW-Mode mit Direwolf) zeigt der Live-Monitor der TinyBox die
  Frames nicht, die Direwolf im Fenster zeigt: RR-Quittungen der eigenen Verbindungen
  (`OE3GAS-1>OE3TEC:(RR cmd …)`), fremde UI-Frames (`OE3GAS-12>CQ:test`), fremde Verbindungen
  (OE3OGC ↔ OE3GAS-10). Im Monitor stehen nur Sitzungstext (`TXT`), eigene UI-Frames und Log.
- Grund: Den Frame-Monitor (`tinybox/framemon.py`, CR52) gibt es nur im KISS-Mode. Im AGW-Mode
  macht Direwolf AX.25 und meldet der TinyBox weder gehörte noch eigene Frames.
- Entscheidung (OE3GAS, 08.11.2026): **beide Stufen** aufnehmen.

### Stufe 1 – gehörte Frames (nur TinyBox)

- Nach dem Verbinden mit Direwolf einmal AGW **`k`** schicken („raw frames on“). Direwolf
  schickt dann jeden **empfangenen** Frame als `K`: ein Byte Port/TNC, danach der Frame ohne FCS.
- Achtung: `k` ist bei Direwolf ein **Umschalter** – nur einmal pro AGW-Verbindung senden (nach
  einem Reconnect wieder einmal).
- Die Bytes ab dem zweiten gehen in `framemon.emit(data, tx=False, mycall=…)` wie im KISS-Mode:
  RX-Zeilen mit I-, S-, U-Frames, Zählern, P/F, APRS-Lens, HEX-Inspektor. Modulo 128 aus der
  Verbindung (die Verbindungen kennt die TinyBox über AGW) oder geschätzt wie bisher.
- Nur wenn die Web-GUI läuft (der Logger `tinybox.frames` hat sonst keinen Handler – dann
  nichts aufbauen, wie in `framemon`), nicht in Logdatei oder Konsole.
- Damit sieht der Sysop alles, was auf dem Kanal gehört wird, auch die Frames der Gegenstationen
  an die TinyBox (RR von OE3TEC usw.). Was fehlt: die eigenen gesendeten Frames außer UI.
- Die eigenen UI-Frames, die heute als Log-Zeile `UI …` erscheinen, bleiben so (bis Stufe 2).
- Ein Original-Direwolf kann Stufe 1 auch – sie braucht den Fork nicht.

### Stufe 2 – eigene gesendete Frames (Direwolf-Fork + TinyBox)

- Direwolf meldet über AGW von den eigenen Frames nur UI (`T` im Monitor-Format,
  `server_send_monitored(…, own_xmit=1)` in `src/xmit.c`). I-, S-, U-Frames der TinyBox
  (I, RR, REJ, UA, DISC …) sieht kein AGW-Client.
- **Fork** (oe3gas/direwolf-tinybox, Zweig `tinybox`): in `xmit.c` jeden gesendeten Frame
  zusätzlich **roh** an die AGW-Clients geben, die `k` eingeschaltet haben – als eigener neuer
  Frame-Typ **`O`** („own“, im AGW-Protokoll frei), Aufbau wie `K`: ein Byte Port, danach der
  Frame ohne FCS. Ein eigener Typ, damit Clients, die
  nur das Original kennen, nichts falsch als empfangen deuten. Kein Protokollverhalten ändert sich
  (Grundsatz des Forks). Dokumentation in `TINYBOX.md`.
- Gemeldet wird beim **tatsächlichen Senden** (nach Kanalzugang/TXDELAY), damit die Zeit stimmt
  und Wiederholungen als eigene Zeilen erscheinen.
- **TinyBox:** `O`-Frames in `framemon.emit(data, tx=True, …)` → TX-Zeilen wie im KISS-Mode. Ist
  Stufe 2 aktiv (erstes `O` gesehen oder Fork per Startmeldung erkannt), entfallen die bisherigen
  Log-Zeilen `UI …` für eigene UI-Frames im Monitor, damit nichts doppelt steht.
- Mit einem Original-Direwolf bleibt es bei Stufe 1.

### Umsetzung (08.11.2026)

- **TinyBox** (`tinybox/adapters/agw.py`): nach jedem AGW-Connect einmal `k` und `O`
  (`_monitor_on`). `K` → `framemon.emit(…, tx=False)`, `O` mit Daten → `tx=True`, nur Frames des
  eigenen Kanals (`[agw] channel`). Modulo 128 wird geschätzt (die Verbindungen hält Direwolf).
  `K`/`O` zählen nicht als Verkehr (`frames_in`) und kommen nicht ins Debug-Log.
- Ein leeres `O` (Antwort des Forks) schaltet `own_frames` ein, im Log
  `Direwolf with TinyBox extension: own frames in the monitor`. Dann erscheinen die eigenen
  UI-Frames nur noch als Frame im Monitor; die Zeile `UI … > …` geht weiter in die Logdatei, aber
  nicht mehr in den Monitor (`framed`).
- **Direwolf-Fork** (oe3gas/direwolf-tinybox `62246e8`, Fork-Version 2026.11.08): AGW `O` ist ein
  Umschalter wie `k`, die Antwort ein leeres `O`; danach jeder gesendete Frame (nach dem Senden in
  `send_one_frame()`, auch Wiederholungen) als `O`, aufgebaut wie `K`. Beschrieben in `TINYBOX.md`.
  Unter Linux geprüft: UI-Frame und SABME mit Wiederholungen kommen als `O`.
- Mit einem Original-Direwolf: einmal „Unexpected Command“ in dessen Fenster, der Monitor zeigt
  die empfangenen Frames.
- Tests: `tests/test_agw_monitor.py` (einmal `k`/`O` je Connect, RX-Frames, anderer Kanal
  ignoriert, TX-Frames mit Fork, Zähler, UI-Zeile ausgeblendet).
- Funktest auf der Hinteralm offen: neue `direwolf-tinybox.exe` und `git pull` + `RESTART` der TinyBox.

## CR84 – Zitat aus der History: Text statt „message #n“ (✅ 08.11.2026, Funktest offen)

### Erfassung (OE3GAS, 08.11.2026)

- Ein Kommentar (CR31, `~^5 …`) auf eine Nachricht, die der Client nur aus der History hat,
  zeigt „↩ message #5“. Stattdessen soll der Text der Nachricht stehen, sofern sie noch in der
  History ist.

### Umsetzung (TinyBox + Client 2026.11.08.11)

- Ursache: Ein Kommentar verweist nur auf die **Ereignisnummer** (`#5`, 0–255 je Board). Die
  History-Zeilen (`//H <unix> <call>: <text>`) hatten keine Nummer, der Client konnte das Zitat
  dort nicht finden.
- **TinyBox:** `chat_lines` bekommt die Spalte `seq` (Schema 10, alte Zeilen `NULL`); die Zeile
  wird jetzt nach dem Verteilen mit ihrer Nummer gespeichert. Neue Fähigkeit **`HSEQ`**:
  Clients damit bekommen `//H <unix> #<n hex> <call>: <text>`, ältere wie bisher (sie würden die
  Zeile sonst verwerfen).
- **Client:** meldet `HSEQ`, merkt sich die Nummer einer History-Zeile als `qseq`; die Suche nach
  dem zitierten Beitrag (`quotedMessage`) nimmt auch History-Zeilen mit dieser Nummer – wie bei
  Live-Zeilen die neueste vor dem Kommentar.
- Grenzen: Zeilen, die vor diesem Stand gespeichert wurden, haben keine Nummer (weiter
  „message #n“). Nach einem TinyBox-Neustart beginnen die Nummern wieder bei 0 – dann gewinnt
  wie bisher der neueste passende Beitrag vor dem Kommentar.
- Tests: `test_clientproto.ClientProtoTests.test_history_with_event_numbers`,
  `test_tbclient…test_history_event_number`.

## CR85 – Erwähnungs-Alarm: Popup und „BK“ in CW (✅ 08.11.2026, Funktest offen)

### Erfassung (OE3GAS, 08.11.2026)

- Schreibt jemand im Chat `@OE3GAS`, soll der Browser eine Benachrichtigung des Betriebssystems
  zeigen (Popup mit Ton). Als Ton das CW-Zeichen „BK“ mit 60 Zeichen/Minute, im Client erzeugt.

### Umsetzung (nur Client 2026.11.08.12)

- Auslöser wie die Hervorhebung aus CR15: `@CALL` (beliebige SSID) in einer fremden Live-Zeile
  oder ein Kommentar (CR31) auf einen eigenen Beitrag. History-Zeilen, eigene Zeilen und alles,
  was beim Öffnen eines Boards schon da ist, lösen nichts aus.
- **Popup** über die Notification API des Browsers – nur wenn der Client nicht vorne ist
  (Tab im Hintergrund, anderes Fenster). Titel `OE3TEC in TREFF`, Text die Zeile (max. 180
  Zeichen), Icon `logo.svg` als PNG. Kommen mehrere auf einmal: die letzte mit „(+n)“. Klick
  holt das Fenster nach vorne und springt in den Kanal.
- **Ton** „BK“ (`-... -.-`) über WebAudio: 60 BpM = 12 WpM, Punkt 100 ms, 3 Punkte zwischen B
  und K, 2,1 s; 5-ms-Rampen gegen Klicken, Tonhöhe 500–800 Hz. Er kommt auch, wenn der Client
  vorne ist. Mit Ton ist das Popup `silent` – sonst käme zusätzlich der Systemton.
- Einstellungen unter Settings > „Mention alert“ (Popup, Ton, Tonhöhe, Test), gespeichert im
  Browser (`localStorage` `tbc-notify`), Standard aus. Beim Einschalten des Popups fragt der
  Browser einmal um Erlaubnis.
- Grenzen:
  - Popups gehen nur in einem „sicheren Kontext“: `http://127.0.0.1:7744` ja, die LAN-Adresse
    (`http://192.168.…:7744`) nein – dort steht ein Hinweis, der Ton geht trotzdem.
  - Ist der Browser oder der Tab zu, kommt nichts (kein Web Push).
  - Nur der Kanal, der gerade in der GUI offen ist (die GUI holt nur dessen Zustand).
  - Das Betriebssystem muss Benachrichtigungen für den Browser erlauben (macOS: eigene
    Freigabe für Chrome). Unter Linux hängt das Aussehen vom Desktop ab.
  - Den Ton spielt der Browser erst nach einem Klick in die Seite (Autoplay-Regel).
- Geprüft mit TinyBox + Client über den Telnet-Testport und einem zweiten User (Playwright):
  Zeile ohne Erwähnung → nichts; `hallo @oe3gas …` → ein Popup `OE3TEC in TREFF`, ein BK; ist
  das Fenster vorne → nur BK.

## CR86 – Dateien im Board-Chat (✅ 10.11.2026)

### Erfassung (OE3GAS, 08.11.2026)

- Den LZHUF-Dateitransfer gibt es bisher nur von Client zu Client (CR78 Stufe 7,
  `tbclient/peerfile.py`). Neu: Dateien auch in einem **Board-Chat** teilen.

### Vorschlag (Claude, Details bei der Umsetzung)

- **Wie die Bilder (CR12), nicht wie Stufe 7:** Im Board gibt es viele Empfänger, und der Sender ist
  oft nicht mehr da. Die Datei liegt deshalb **in der TinyBox**, nicht beim Sender. Upload einmal,
  jeder holt sie bei Bedarf per I-Frame von der TinyBox.
- **Über Funk im Chat nur der Verweis**, wie bei Stufe 7: `~%<hash> <bytes> <bytes on air> <name>`.
  Terminal-Teilnehmer lesen `[File name.txt 12.3 KB - TinyBox client only]`.
- **Packen im Client:** LZHUF (B0) oder roh, wenn LZHUF nichts bringt (ZIP, JPEG). Die TinyBox
  speichert den Blob unter seinem Hash, entpackt nicht und prüft nur die Größe.
  Der Empfänger prüft den Hash nach dem Entpacken.
- **Upload/Download** wie bei den Bildern: `//FPUT <hash> <z|r> <bytes>` → `//FGO <hash> <have>` →
  Bytes am Stück → `//FOK`; `//FGET <hash> [<offset>]` → `//F <hash> <z|r> <offset> <total>` + Bytes.
  Abgebrochen geht es beim Offset weiter. Stückweise an Direwolf mit Pause wie bei den Bildern,
  damit Chat-Zeilen dazwischen durchkommen. Fortschritt in der Bubble.
- **Vor dem Hochladen** sieht der User Größe auf Funk und Dauer für Upload und Laden (wie CR12) und
  entscheidet. Laden nur per Antippen, nie automatisch.
- **Sysop:** Maximalgröße `[chat] file_max` (Vorschlag 16k), pro Board abschaltbar (`nofile`
  analog `noimg`), keine Dateien in Live-Boards. Aufbewahrung wie die History: eine Datei wird
  gelöscht, wenn keine Chat-Zeile sie mehr verwendet (Purge wie bei den Bildern).
- Neue Fähigkeit `BFILE` (Client ↔ TinyBox); nur über Funk/AXUDP, nicht Telnet. Erlaubnis beim
  Betreten (`//IN … file`), wie `img`.
- Offen zu entscheiden: Maximalgröße, ob bestimmte Dateitypen gesperrt werden (z. B. `.exe`), und ob
  der Sysop hochgeladene Dateien in der Web-GUI sehen und löschen kann.


### Ergänzung aus CR96 (OE3GAS, 09.11.2026)

- Mit CR86 kommt der **längere Hash** für alle Referenzen und Transfers (Bilder und Dateien, z. B.
  16 hex = 64 Bit statt 6 hex): neues Funkformat, neue Client- und Box-Version, **keine
  Übergangsregel** für ältere Clients. Die Absicherungen aus CR96 Stufe 1 gelten von Anfang an.

### Umsetzung (TinyBox, Client 2026.11.10.12 – 10.11.2026) ✅

- **Hash:** 16 Hex (64 Bit) für Bilder (`~#`) und Dateien (`~%`), Board und Client↔Client
  (`prcore.chatimg.HASH_LEN`); keine Übergangsregel.
- **Protokoll** (Fähigkeit `BFILE`, nur Funk/AXUDP): `//FPUT <hash> <z|r> <Bytes>` → `//FGO <hash>
  <have>` → Bytes → `//FOK`; `//FGET <hash> [<offset>]` → `//BF <hash> <z|r> <offset> <total>` +
  Bytes, sonst `//NOBFILE`. (`//F`/`//NOFILE` bleiben Client↔Client.) `//IN … file=<hex>`.
- **Box** (`tinybox/chatfile.py`): Tabelle `chat_files` (Schema 15), Größe wie gesendet bis
  `[chat] file_max` (Standard 16k, 1k–64k), `nofile` je Board, keine Live-Boards, ein Upload gehört
  der Station, die ihn begann (CR96). Die Chatzeile mit dem Verweis nur, wenn die Datei hochgeladen
  ist und ihr Name kein Programm ist (`prcore/filecheck.py`, aus dem Client hierher verschoben).
  Aufbewahrung wie die Bilder (keine Zeile mehr → weg, frühestens nach 1 h). Konsole `FILES`,
  `FILES DEL <hash>`, auch über die Sysop-Konsole im Client.
- **Client** (`tbclient/boardfiles.py`, auf Basis der Bild-Übertragung): prüft Name und Inhalt vor
  dem Hochladen, packt, eine Übertragung zugleich (auch mit Bildern), wartet auf einen laufenden
  Abgleich; beim Holen Hash und Inhalt geprüft. Web-GUI: 📎 im Board, Datei-Blase mit „Save“ bzw.
  „tap to load“ und Zeit auf Funk, Fortschritt beim Hochladen.
- Entschieden ohne Rückfrage (aus dem Vorschlag): 16 KB, Programme gesperrt wie CR96, Sysop sieht
  und löscht an der Konsole (nicht in der Web-GUI). Tests `tests/test_cr86.py`.
## CR87 – brocastd: Absturz durch ungültiges `exp` (TB-01, ✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026, aus dem Audit, PLANUNG 29)

- Ein einziges UI-Frame an BROCST mit `exp` als Text statt Zahl legt brocastd dauerhaft lahm:
  `listener.py` speichert `exp` ungeprüft als `exp_min`, `housekeeping()` rechnet
  `t + exp_min * 60` → `TypeError`; `Daemon._housekeeping` hat kein `try`, `asyncio.gather` beendet
  den Daemon. Der Eintrag bleibt in der DB, jeder Neustart stürzt wieder ab. PoC ist öffentlich.

### Vorschlag (Claude)

- Typ- und Bereichsprüfung beim Empfang (`exp` nur `int`, z. B. 1 … 525600, sonst Seite verwerfen),
  ebenso für alle anderen Envelope-Felder mit festem Typ.
- `try`/`except Exception` mit Logging in der Housekeeping-Schleife; ein Fehler darf den Daemon nie beenden.
- Beim Start ungültige `exp_min`-Einträge aussortieren (R4: Neustart ohne Handeingriff).
- Regressionstest mit dem Frame aus dem PoC.

### Umsetzung (brocast, 09.11.2026)

- `codec.py`: `_check_wire()` prüft beim Empfang jedes Umschlag-Feld gegen den Typ seines
  Dictionary-Eintrags (uint/time, int, tstr mit `max`, callsign, enum/enums, bits, subpage,
  position, pageref/pagerefs, blocks). Zahlen höchstens 2^63-1 (was SQLite speichern kann). Ein
  falscher Typ ergibt `BrocastError` → Seite verworfen, Eintrag im Empfangslog, `rx_errors`.
- `valid_exp()`: Gültigkeit nur als ganze Zahl 1 … 10 Jahre in Minuten. Gilt auch für `exp` aus dem
  `typ`-Eintrag des Dictionary (kann über Funk kommen, TB-04) – im Listener und in der Station.
- `listener.py`: Housekeeping und Seitenliste erkennen Einträge mit unbrauchbarem `t`/`exp_min`
  (ältere Datenbank) und entfernen sie mit Warnung statt abzustürzen – Neustart ohne Handeingriff.
- `daemon.py`: Housekeeping-Schleife mit `try`/`except` und Logging; ein Fehler beendet brocastd nicht.
- Tests `brocast/tests/test_cr87.py`: PoC-Frame über den ganzen Empfangsweg, zwölf falsche
  Feldtypen, vergiftete Datenbankzeile, gefälschtes Dictionary-`exp`, Housekeeping läuft nach einem
  Fehler weiter. Ohne den Fix reproduziert der PoC den `TypeError` im Housekeeping.

## CR88 – Parser-Robustheit: Zahlen, Ausnahmen, Endlosschleifen (TB-09, TB-20c, TB-23, ✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- Jede Möglichkeit, eine Fehlfunktion zu erzeugen, wird behoben.
- TB-23 (geprüft 09.11.2026): 84 Stellen mit `isdigit()`. `¹²³` (auch in Latin-1!) bestehen
  `isdigit()`, `int()` scheitert; arabische/Devanagari-Ziffern werden still als Zahl gelesen.
  Wirkung: BBS-Sitzungen und APRS-Dekoder fangen den Fehler ab (nur Log). **Problem:**
  `fwd/protocol.py:68` (Task der Forward-Sitzung stirbt, TB-20c) und die Telnet-Leseschleife im
  Client (`tbclient/links.py` `_read`, fängt nur Verbindungsfehler → Verbindung hängt stumm).
  AGW/KISS im Client: Fehler wird pro Frame abgefangen, der Rest des Frames geht verloren.
- TB-09: einzelne Frames brechen die brocast-Seitenliste oder blockieren den Daemon.

### Vorschlag (Claude)

- Zentrale Funktion in `prcore` (`isnum(s) = s.isascii() and s.isdigit()`), alle 84 Stellen umstellen.
- `except Exception` mit Logging in `ForwardSession.run` (Status setzen, Sitzung sauber beenden) und
  in der Telnet-Leseschleife; LineSplitter so, dass ein Fehler in einer Zeile die übrigen Zeilen
  des Frames nicht verwirft.
- TB-09 nachstellen und beheben; Schleifen mit Obergrenze.
- Fuzz-Tests für alle Zeilenparser (Box, Client, brocast) mit Unicode-Ziffern, Überlängen, leeren Feldern.

### Umsetzung (TinyBox, Client 2026.11.09, kisshub 2026.11.09, dxfeed 2026.11.09, brocast – 09.11.2026)

- `prcore/text.py`: `isnum()` (nur ASCII-Ziffern) und `to_int()`. Alle 84 Stellen mit `isdigit()`
  umgestellt; brocast und dxfeed (ohne `prcore`) haben ein gleiches lokales `_isnum()`.
  `tests/test_cr88.py` schlägt fehl, sobald `.isdigit()` wieder im Code auftaucht.
- `fwd/session.py`: `ForwardSession.run` fängt jede unerwartete Ausnahme, loggt sie mit Traceback,
  setzt `error = "internal error: …"` und schließt die Verbindung (TB-20c).
- `tbclient/links.py`: `LineSplitter` ruft jede Zeile (und jeden Binärblock) einzeln abgesichert auf –
  ein Fehler kostet nur diese Zeile, nicht den Rest des Frames (AGW, KISS, Telnet). Die
  Telnet-Leseschleife beendet sich bei einem unerwarteten Fehler mit Log und meldet „offline“
  statt still zu hängen.
- brocast (TB-09): `t` beim Empfang höchstens 01.01.2100, `sub` höchstens [999, 999] (schon CR87);
  eine Seite mit mehr als einem Tag Vorlauf wird nicht angenommen (Ergebnis `future`, sonst liefe
  sie nie ab); `iso()`/`iso_ms()` liefern bei unbrauchbaren Werten `None` statt die ganze
  Seitenliste mit HTTP 500 zu brechen. Die Schleife der Seitenansicht ist damit auf 999 begrenzt.
- Tests: `tests/test_cr88.py` (Unicode-Ziffern in Forward-Vorschlag, BBS-Nummernlisten, Profil;
  LineSplitter läuft nach Fehler weiter; Forward-Sitzung endet sauber), `brocast/tests/test_cr88.py`
  (absurde Zeiten, Zukunft, riesige Unterseitenzahl, kaputte Zeile in der Liste, `iso`).
- Offen: ein breiter Fuzz-Lauf über alle Zeilenparser – mit dem Client-Audit (CR98).

## CR89 – Forwarding-Robustheit: BID, Restart, Sitzungsdauer, Ctrl-Z (TB-10, TB-11, TB-20a/b, ✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- TB-10: Ist die eigene BID schon bekannt, speichert `service.py` die Nachricht **ohne BID**, `send.py`
  sendet dann ein `FB` mit leerem Feld, die Gegenstelle bricht ab, die Warteschlange zum Partner steht
  still. Auslösbar durch einen Angreifer (vorab belegte BIDs) **und ohne Angreifer** (Zählerüberlauf,
  DB-Neuaufbau).
- TB-20a: Teildaten einer abgebrochenen Übertragung werden einem späteren echten Angebot vorangestellt.
- TB-20b: `;`-Zeilen setzen den Zeilen-Timeout zurück, eine Sitzung lässt sich beliebig offen halten
  (Partner „busy“, Scheduler und `FWD` überspringen ihn).
- TB-11: Ctrl-Z in komprimierter Post schleust Protokollzeilen weiter.

### Vorschlag (Claude)

- Nie ohne BID speichern: Ausweich-BID erzeugen; nie ein leeres Feld senden; eine einzelne
  fehlerhafte Nachricht wird zurückgestellt und dem Sysop gemeldet, die Warteschlange läuft weiter.
- Restart-Daten nur innerhalb derselben, authentisierten Sitzung bzw. desselben Partners mit
  Prüfsumme verwenden, sonst verwerfen.
- Gesamtzeitgrenze pro Sitzung, Obergrenze für `;`-Zeilen.
- Ctrl-Z und Steuerzeilen im Inhalt entschärfen (mit CR95).

### Umsetzung (TinyBox, 09.11.2026)

- TB-10: `MessageService.new_bid()` – `<n>_<CALL>` wie bisher; ist die BID schon bekannt, eine
  zufällige (`addressing.random_bid`, z. B. `K7Q2X_OE3XTC`, nicht vorhersagbar). Eine neue Nachricht
  ist nie mehr ohne BID. `Sender.pending()`: eine ältere Nachricht ohne BID bekommt sie beim Senden;
  eine Nachricht mit leerem oder mehrteiligem Feld in der FB-Zeile wird für diesen Partner auf
  `rejected` gesetzt und geloggt (ERROR) – die Warteschlange läuft weiter.
- TB-11: `addressing.strip_controls()` entfernt Steuerzeichen außer Tab und Zeilenende. Beim Empfang
  (`Receiver.store`, Betreff und Text) und beim Senden (`wire_lines`, B0/B1-Payload). Die weitere
  Entschärfung von Steuerzeilen im Text (`R:`, `/EX` …) folgt mit CR95.
- TB-20a: Restart-Daten merken sich die Größe aus dem Vorschlag (Tabelle `fwd_partial.size`,
  Schema 11). Ein Restart (`!offset`) nur bei gleicher Größe, sonst werden sie verworfen und die
  Nachricht kommt ganz. Scheitert ein Restart ohne neue Daten oder mit Framing-Fehler, werden sie
  verworfen (keine zehn Fehlversuche mehr). Alte Zeilen ohne Größe werden nicht verwendet.
- TB-20b: `;`- und Leerzeilen starten den Timeout nicht neu (die Gegenstelle hat `timeout` Sekunden
  für den nächsten echten Befehl), höchstens 20 in Folge, dann wird aufgelegt. Neu je Partner
  `max_session_min` (Vorgabe 60, 1 … 1440): danach endet jede Sitzung, auch während der Daten.
- Tests `tests/test_cr89.py`.

## CR90 – Interlink-Authentisierung (TB-02, Stufe 1 ✅ 09.11.2026, Stufe 2 offen)

### Erfassung (OE3GAS, 09.11.2026)

- Ein eingehender Anruf mit dem Rufzeichen eines `transport = agw`-Partners bekommt dessen Rechte
  ohne Prüfung: Post einschleusen (auch als Sysop), für den Partner gespeicherte Post abholen,
  BIDs vergiften. Interlinks haben sehr hohen Schutzbedarf (PLANUNG 29.3).

### Vorschlag (Claude)

- Sofort: Forwarding-Post nie an eingehende Funk-Anrufer ausgeben, nur an selbst angerufene Partner.
- Challenge-Response mit Geheimnis pro Partner (HMAC-SHA256 wie GUST-S), im Handshake als `;`-Zeilen
  nach dem Vorbild Winlink `;PQ:`/`;PR:` – FBB/BPQ ignorieren `;`-Zeilen, bleibt kompatibel.
- Pro Partner konfigurierbar (`auth = hmac | none`), `none` nur bewusst (R3); Werkzeug zum Erzeugen
  und Widerrufen nach dem Vorbild `gust_keygen.py`.
- Später: Signatur statt Geheimnis (CR94).

### Diskussion und Entscheidung (OE3GAS/Claude, 09.11.2026)

- Vorschlag „Forward-Post nie an eingehende Funk-Anrufer“ verworfen. Einwand OE3GAS: ist die echte
  Station auf der Frequenz, hat sie keine Verbindung mit uns und antwortet auf unsere Polls mit
  **DM** (AX.25 2.2, Zustand disconnected) – das stört den Fälscher. Der Unterschied zwischen
  eingehendem und eigenem Anruf ist damit klein; die Sperre hätte vor allem den Partnern das
  Abholen genommen. Der Angriff gelingt im Wesentlichen nur, wenn die echte Station aus ist, nicht
  hört (Hidden Terminal) oder die Übertragung vor dem ersten Poll fertig ist.
- Stattdessen **Stufe 1: erkennen statt sperren**, dann **Stufe 2: HMAC-Challenge-Response** für
  Partner, die es können. FBB/BPQ-Partner: Rufzeichen als akzeptiertes Restrisiko.

### Umsetzung Stufe 1 (TinyBox, 09.11.2026)

- `tinybox/linkguard.py`: während einer Forward-Sitzung über Funk (AGW und KISS/AXUDP) wird jedes
  gehörte Frame vom Rufzeichen des Partners an uns geprüft. **DM**, **FRMR** oder ein **UA** mehr
  als der Verbindungsaufbau erklärt (eigener Anruf: 1, eingehend: 0) = Verdacht. Frames nach unserem
  eigenen DISC zählen nicht. AGW: aus Direwolfs Roh-Monitor (`K`), KISS: aus dem eigenen AX.25-Stack.
- Bei Verdacht (`ForwardModule._suspect`): gesendete Post dieser Sitzung wieder „offen“ (wird erneut
  angeboten, der Empfänger erkennt Doppelte an der BID), empfangene Post wird **gehalten** (`H`, Notiz
  „CR90: received while a second station used the partner's call“, Freigabe mit `REL n`), die
  Sitzung gilt als fehlgeschlagen, Warnung im Log und **persönliche Nachricht an den Sysop**.
- Fehlalarm möglich, wenn der echte Partner die Verbindung verliert (Neustart, DM): dann wird nur
  noch einmal gesendet und der Sysop gibt die gehaltene Post frei.
- Tests `tests/test_cr90.py`.

### Stufe 2 (offen)

- HMAC-SHA256-Challenge-Response pro Partner im Handshake als `;`-Zeilen (Vorbild Winlink
  `;PQ:`/`;PR:`, GUST-S), `auth = hmac | none` je Partner, Schlüsselwerkzeug nach `gust_keygen.py`.

## CR91 – Dictionary-Integrität (TB-04, ✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- `dictimport._compare` prüft nur Nummer ↔ Name und Spaltennamen; Skalierung, Einheit, Ablauf lassen
  sich still umdeuten. brocastd sendet das neue Dictionary danach selbst weiter → verbreitet sich
  von selbst. Schutzbedarf sehr hoch (PLANUNG 29.3, Objekt 4).

### Vorschlag (Claude)

- Vollständiger Vergleich der Spezifikation jedes bestehenden Eintrags; nur Anhängen erlaubt.
- Kein automatisches Installieren aus der Luft ohne Sysop-Freigabe (Vorgabe aus), keine
  Weiterverbreitung fremder Dictionaries ohne Freigabe.
- Später: signierte Dictionaries (Ed25519, CR94).

### Umsetzung (brocast, 09.11.2026)

- `dictimport._compare`: jeder bestehende Eintrag wird vollständig verglichen, ohne die
  Anzeigetexte `de`/`en`. Erlaubt sind sonst nur: `del: true` neu bei einem DXCC-Gebiet (nicht
  zurück), neue Spalten hinten bei `rows` (bestehende Spalten auch inhaltlich unverändert), und ein
  Feld vom Typ `any` darf seinen Typ bekommen (`type`, `enum`, `free_text`, `max`, `unit`) – das war
  der einzige Fall in der bisherigen Geschichte v1 → v5 (`src`). Jede andere Änderung → abgewiesen
  mit Nennung der Schlüssel, z. B. „wx: temp (Nummer 0) würde umgedeutet (scale)“.
- Automatische Installation: war schon nur für Stationen in `dict_trusted` (Vorgabe leer), sonst
  wartet das Dictionary auf Freigabe. Neu: ein automatisch übernommenes Dictionary sendet die eigene
  Station **nicht weiter** (Meta `dict_norelay`, Status `relay_held`, Hinweis in der GUI). Freigabe
  durch den Sysop: Knopf „Dictionary jetzt über Funk senden“, Import einer Datei oder Installation
  über die Freigabe. Der Hinweis bei `dict_trusted` warnt, dass Rufzeichen fälschbar sind.
- Tests `brocast/tests/test_cr91.py`: sechs Arten der Umdeutung abgewiesen, Textänderungen und die
  bisherige Geschichte v1 → v5 erlaubt, DXCC-Löschung nur in eine Richtung, automatisch übernommenes
  Dictionary wird nicht weitergesendet, Freigabe per Knopf und per Hand.
- Offen: signierte Dictionaries – mit CR94.

## CR92 – Rollen und Rechte (TB-08, TB-14, TB-15, TB-21, ✅ 10.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- Rollen: Sysop, Forward-Partner, an der Heimat-BBS authentifizierter User, nicht authentifizierter
  User (Rechtematrix PLANUNG 29.7).
- brocast-Seiten und Alarme erstellen und verbreiten nur Sysops (TB-08, TB-14, TB-21).
- Rufzeichen gleich Rubrikname darf keine Rechte an der Rubrik geben (TB-15); Plausibilitätsprüfung
  von Rufzeichen.
- Nicht authentifizierte User: kein TBClient; Post nur als Text nach PLANUNG 29.9, nur lokal oder an
  den Sysop, Weiterleitung ins Netz erst nach Freigabe.

### Vorschlag (Claude)

- Rechte zentral an einer Stelle prüfen (eine Funktion je Recht), nicht verstreut in den Befehlen.
- Alarmseiten und Seiten mit Priorität nur aus Sysop-Quellen (Ingest-API mit Token, Sysop-Konsole).
- Rufzeichen-Plausibilität: Präfix-Struktur (ITU-Präfix + Ziffer + Suffix, SSID 0–15), Abgleich mit
  Rubriknamen; bei Kollision Rechte nur über die Rolle, nie über den Namen.
- Grenzen für die Zahl der brocast-Seiten je Quelle (TB-21).

### Umsetzung (TinyBox, brocast-Listener – 10.11.2026) ✅

- `tinybox/rights.py`: Rollen `sysop` (Sitzung mit Sysop-Rechten; Konsole, Web-GUI, Inbox, MQTT),
  `user` (Login mit Schlüssel, CR93), `guest` (jede Terminal-Verbindung), Forward-Partner wie bisher.
  Alle Rechte dort, `service.create(role=…)`, `service.delete(role=…)`.
- Gast: kein `SB` (Meldung `NEED_LOGIN` schon vor dem Text; `//SEND B` → `need_login`), Post nur Text
  (`clean_text(emoji=False)`, PLANUNG 29.9), Post an eine andere BBS wird gehalten (`fwd=H`, Notiz
  „guest mail …“, Hinweis an den Gast) und mit `REL n` freigegeben. Lokale Post und Post an den Sysop
  gehen wie bisher.
- TB-15: Bulletins löscht nur der Sysop oder der angemeldete Autor – nie der „Empfänger“ (die
  Rubrik). Beim Connect (AGW, AXUDP, KISS über `prcore.kissport`, Telnet) wird die Struktur des
  Rufzeichens geprüft: Präfix 1–3 Zeichen mit Buchstabe, Ziffer(n), Suffix aus Buchstaben
  (`plausible_call`) – `70CM`, `10M`, `QO100`, `WX` sind kein Rufzeichen.
- TB-14: ein Bulletin an ein `alert_destinations`-Ziel (`WARN`) geht nur aus Sysop-Quellen
  (`origin` sysop, inbox, mqtt) an brocastd; sonst bleibt es ein Bulletin.
- TB-08 (brocast-Listener): die Seite gehört immer der Station, die den Frame sendet – ein `org` in
  den Daten wird nicht mehr genommen (brocastd sendet keins). Eine ganz abgewählte Station kommt auch
  mit Warnungen nicht mehr durch (abgewählte Rubriken weiterhin schon).
- TB-21: je Station höchstens `max_pages_per_station` (150) Seiten; beim Platzmachen gehen zuerst
  Seiten von Stationen, die seit weniger als 24 h gehört werden, dann gelesene, dann ältere –
  Warnungen zuletzt. 500 Frames erfundener Stationen verdrängen die Seiten bekannter Stationen nicht
  mehr.
- Grenzen, die bleiben (brauchen signierte Seiten, CR94): wer das AX.25-Rufzeichen einer echten
  Station fälscht, kann deren Seiten weiterhin überschreiben oder zurückziehen; die Reihenfolge der
  Fragmente (erstes gewinnt) ist unverändert.
- Tests `tests/test_cr92.py`, `brocast/tests/test_listener.py`; im Rest der Tests schaltet
  `tests/__init__.py` die Gast-Regeln ab (`rights.GUEST_LIMITS`). tbtest: Bulletins schreiben nur
  noch die Client-User.

## CR93 – User-Authentisierung tbclient ↔ Heimat-BBS (Stufe 1 ✅ 09.11.2026, Stufe 2 ✅ 10.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- TBClient darf nur ein an der Heimat-BBS authentifizierter User verwenden (PLANUNG 29.7).

### Vorschlag (Claude, Konzept zuerst)

- tbclient erzeugt bei der Registrierung ein Schlüsselpaar; die Heimat-BBS speichert den öffentlichen
  Schlüssel (Freigabe durch den Sysop). Beim Verbinden Challenge-Response, über Funk zusätzlich
  Signatur für kritische Aktionen.
- Vertrauenskette: die Heimat-BBS unterschreibt den User-Schlüssel (Mini-Zertifikat: Rufzeichen,
  Rolle, Schlüssel, Gültigkeit, Unterschrift); fremde BBS, die der Heimat-BBS vertrauen, erkennen den
  User damit auch.
- Abhängig von CR94 (Verfahren, Schlüsselformat).

### Entscheidungen (OE3GAS, 09.11.2026)

1. **Ed25519** (nicht P-256: kein Zufallswert je Signatur, einfacher; P-256 bleibt für GUST/Hardware
   später möglich).
2. **Freigabe durch den Sysop** mit Vergleich des Fingerabdrucks (kein TOFU).
3. Schutz nach dem Login: **Variante b** – kritische Befehle einzeln signiert (Stufe 2).
4. ~~Ein Schlüssel je Rufzeichen, geräteunabhängig~~ – **geändert (OE3GAS, 10.11.2026): ein
   Schlüssel je Gerät**, jeder einzeln freigegeben (siehe „Umstellung“ unten).
5. **Kein Passwort** auf der Schlüsseldatei.
6. **Sofort Pflicht** – keine Übergangsphase, keine Einstellung zum Abschalten.

### Umsetzung Stufe 1 (TinyBox, Client 2026.11.09.7 – 09.11.2026)

- `prcore/auth.py`: Ed25519 über `cryptography`, wenn installiert, sonst reine Python-Umsetzung
  nach RFC 8032 Abschnitt 6 (keine Zusatzpakete nötig; beide gegen die RFC-Testvektoren getestet,
  ~10 ms je Signatur). Schlüssel/Signatur base64url (43/86 Zeichen), Fingerabdruck 48 Bit
  (`7F3A-91C2-44E0`). `Identity`: `identity.key` (eine Zeile, Rechte 0600), eine beschädigte Datei
  wird nie stillschweigend ersetzt.
- Protokoll: auf `//CLIENT` antwortet die Box `//AUTH? n=<16 Byte zufällig> box=<Mailbox-Ruf>`, der
  Client `//AUTH sig=<…> pub=<…>`; signiert wird `TINYBOX-AUTH1|<Box>|<Rufzeichen>|<n>` (je ohne SSID).
  Freigegebener Schlüssel → `//OK` wie bisher. Neuer Schlüssel (Signatur beweist den Besitz) →
  `//AUTHWAIT fp=…`, Eintrag „pending“, persönliche Nachricht an den Sysop. Anderer als der
  freigegebene → `//ERR auth other_key`, widerrufen → `revoked`, falsche Signatur → `bad_signature`.
  Eine Challenge gilt für genau eine Antwort. Vor dem Login: `//ERR not a client session`.
- Box: Tabelle `user_keys` (Schema 12, je Basis-Rufzeichen), Sysop-Konsole `USER`, `USER OK|REVOKE|
  DEL|SHOW call`.
- Client: Schlüssel beim ersten Start, „Your key“ mit Fingerabdruck im Startblock, Hinweisbalken
  in der Web-GUI bei „wartet“ oder „abgewiesen“.
- Tests `tests/test_cr93.py`. Die übrigen Tests reden mit der Box ohne Login
  (`tests/__init__.py` schaltet `clientproto.REQUIRE_AUTH` nur dort ab).
- Doku: MANUAL 3.7a.

### Umsetzung Stufe 2 (TinyBox, Client 2026.11.10.2 – 10.11.2026) ✅

- Signiert werden nach dem Login `//SEND` (mit Betreff und Textzeilen), `//KILL`, `//SYNC` mit `k=`
  (Löschen) und `//PROF` beim Speichern. Nicht signiert: Lesen (`//GET`, `//SYNC` ohne `k=`,
  `//BSYNC`, `//PROF ?`, `//READ`, `r=`), Chat, Bilder.
- Format: an die Befehlszeile hängt der Client ` c=<n> sig=<86>`. Signiert wird
  `TINYBOX-CMD1|<Box>|<Rufzeichen>|<Login-Challenge>|<n>|<Befehlszeile ohne c=/sig=>`, bei `//SEND`
  danach `\n` + Betreff und Textzeilen (`prcore/auth.command_message`). `n` steigt je Login; die Box
  nimmt nur ein größeres `n` als das letzte → kein Wiederholen, kein Umsortieren. rund 95 Byte mehr je
  kritischem Befehl.
- Abgewiesen: `//ERR send|kill|sync sig_missing|sig_bad|sig_replay`, `//PROF ERR sig_…`; Warnung im
  Log. Der Text eines abgewiesenen `//SEND` wird trotzdem gelesen und verworfen (er läuft nie als
  Befehl).
- In einer Client-Sitzung mit Login weist die Box die Terminal-Befehle zum Schreiben/Löschen ab
  (`S`, `SP`, `SB`, `K`, `KM`, `E`, `N`, `NH`, `NL`, Text `CLIENT_SIGNS`) – sonst ginge ein
  eingeschleustes `SB ALL` an der Signatur vorbei.
- Ein neues `//CLIENT` auf derselben Verbindung (Client neu gestartet, Link blieb stehen) bedeutet
  einen neuen Login mit neuer Challenge.
- Grenze: eine **neue Terminal-Verbindung** unter dem Rufzeichen des Users kann weiterhin schreiben
  wie jeder nicht authentifizierte User – das regelt CR92 (Rechte nach Rolle, PLANUNG 29.7).
  Chatzeilen bleiben unsigniert (Aufwand je Zeile).
- Tests `tests/test_cr93.py` (`SignedCommands`, `ClientSigns`).

### Umsetzung Stufe 3 (TinyBox, Client 2026.11.10.5 – 10.11.2026) ✅

- Herausgeber: **die Heimat-BBS** (Vorschlag oben; die allgemeine Frage aus CR94 – gemeinsamer
  Herausgeber, LoTW-Anker – bleibt dort offen). Jede Box hat `data/box.key` (Ed25519, beim ersten
  Gebrauch angelegt).
- Zertifikat `TBC1:<Ruf>:<User-Schlüssel>:<Herausgeber>:<gültig bis JJJJMMTT>:<Signatur>`,
  signiert `TINYBOX-CERT1|…` (`prcore/auth.make_cert/parse_cert/check_cert`), 180 Tage gültig, ≈ 165 Byte.
- Client: nach dem `//OK` an der Heimat-BBS `//CERT?`, wenn keins da ist oder es in weniger als
  60 Tagen abläuft; Box antwortet `//CERT <…>` (nur für den hier freigegebenen Schlüssel, sonst
  `//CERT -`). Gespeichert in `settings.json` (`certs`). An einer anderen Box hängt der Client
  ` cert=<…>` an `//AUTH`.
- Andere Box: Zertifikat gilt, wenn Ruf und Schlüssel passen, der Herausgeber in `trusted_boxes`
  steht (Schema 13, Konsole `TRUST`, `TRUST ADD box key`, `TRUST DEL box`), die Signatur stimmt und
  es nicht abgelaufen ist → Client-Modus, Eintrag `cert` in `user_keys` (sichtbar in `USER`).
  Lokale Entscheidungen gehen vor: `revoked` sperrt, ein hier freigegebener anderer Schlüssel →
  `other_key`. Ungültiges Zertifikat → Warnung im Log, Schlüssel wartet wie ein neuer.
- Widerruf an der Heimat-BBS erreicht andere Boxen nicht – dort gilt das Zertifikat bis zum Ablauf
  (Widerruf über brocast: CR94).
- **Sysop-Web-GUI ✅:** Ansicht „Keys“ – Schlüssel freigeben/widerrufen/löschen (mit Hinweis auf den
  Vergleich des Fingerabdrucks), Schlüssel dieser Box, vertraute TinyBoxen hinzufügen/entfernen
  (`/api/keys`, gemeinsamer Code mit der Konsole in `tinybox/keys.py`).
- Tests `tests/test_cr93.py` (`Certificates`, `ClientCertificate`), `tests/test_web.py` (`KeysApi`).

### Umstellung: ein Schlüssel je Gerät (Client 2026.11.10.8 – 10.11.2026) ✅

- Anlass: Client am Box-PC (AXUDP) freigegeben, ein zweiter Client zu Hause über Funk bekam
  `other_key`. Entscheidung OE3GAS: je Gerät ein Schlüssel statt die Datei zu kopieren.
- Box: Tabelle `client_keys` (Schema 14, ersetzt `user_keys`, alte Einträge werden übernommen):
  je (Rufzeichen, Schlüssel) ein Eintrag mit Status und Gerätename. Ein unbekannter Schlüssel
  wartet auf `USER OK`, die anderen Geräte laufen weiter; `other_key` gibt es nicht mehr.
  Höchstens 5 nicht widerrufene Schlüssel je Rufzeichen (`too_many_keys`).
- Client schickt `dev=<8 Hex>` in `//AUTH`: HMAC-SHA256 des Rechnernamens mit dem geheimen
  Schlüssel (`auth.Identity.device`) – der Name geht nicht über Funk (OE3GAS) und lässt sich nicht
  durch Probieren üblicher Namen finden. Anzeige im Startblock und in den Settings.
- Konsole: `USER OK|REVOKE|DEL call [fp]` – fp nur nötig, wenn mehrere passen; Web-GUI „Keys“:
  Knöpfe je Schlüssel, Spalte Gerät. Zertifikat, signierte Befehle und Sysop-Konsole gelten je
  Schlüssel (der des Logins).

### Offen

- Widerruf über brocast, Notfall-Schlüssel, gemeinsamer Herausgeber (CR94).

## CR94 – Admin-Protokoll mit Signatur (Richtung entschieden 10.11.2026, Umsetzung offen)

### Erfassung (OE3GAS, 09.11.2026)

- Sysop-Zugang grundsätzlich über das Internet, bei abgesetzten Standorten auch nur über Funk.
  Eigenes Admin-Protokoll mit Zertifikat und Signatur; bestehende Protokolle/Techniken nutzen,
  auch aus GUST (`oe3gas/gust`). Notfunk ist angedacht und wird mitgedacht.

### Vorschlag (Claude) – Details PLANUNG 29.8

- Internet: SSH/WireGuard/TLS, kein Eigenbau.
- Funk: jeder Befehl einzeln signiert (`Befehl | Ziel-Box | Challenge | Zähler | Signatur`), Challenge
  statt Uhrzeit, Ed25519.
- Gemeinsames Modul `prcore/auth.py` (Signatur, HMAC, Schlüsselverwaltung), auch für CR90, CR91,
  CR93 und signierte Alarmseiten.
- Zu entscheiden: Ed25519 oder P-256 (GUST), Herausgeber der Zertifikate, TOTP für Sysops ohne
  tbclient, Widerruf über brocast, Notfall-Schlüssel.

### Entscheidungen (OE3GAS, 10.11.2026)

1. **Kein Sysop über Funk per Rufzeichen – sofort ✅.** Eine Terminal-Verbindung über Funk mit dem
   Sysop-Rufzeichen ist Gast. `[station] sysop_via_radio` wird ignoriert (Warnung beim Start, wenn
   `yes`). Jede Terminal-Sitzung (nicht der Client) mit diesem Rufzeichen über Funk steht als Warnung im
   Log, der Sysop bekommt höchstens alle 6 h eine persönliche Nachricht („Sysop call … connected
   over the radio“). Der eigene Client über Funk löst nichts aus. AXUDP von einem
   Loopback-Partner und Telnet (nur `127.0.0.1`) bleiben lokal und damit Sysop.
2. **Sysop über Funk nur mit dem Client (Variante B) ✅** (Client 2026.11.10.6): Login mit dem
   Schlüssel des Sysops (CR93), Fähigkeit `ADM` nur für das Sysop-Rufzeichen mit dem **hier**
   freigegebenen Schlüssel (nicht per Zertifikat). `//ADM <Konsolenbefehl> c=<n> sig=…` – signiert
   wie CR93 Stufe 2 –, Antwort `//ADM> …` und `//ADMEND ok|unknown|refused|sig_…`. Über Funk nur
   die Liste `SysopConsole.REMOTE` (H, INFO, WHO, STATUS, DISC, BEACON, FWD, FWQ, HOLD, REL,
   SHUTDOWN, RESTART, RELOAD, USER, TRUST); nicht WEB (Login-Link), MON, LOG, UPDATE und keine
   Mailbox-Befehle als Sysop. Jeder Befehl als Warnung im Log. Client: Karte „Sysop console“ in
   den Settings. Tests `tests/test_cr94.py`.
3. **Kein Notzugang** über Terminal (kein TOTP, kein Passwort).
- Damit entfällt auch die frühere Idee aus CR21 (`sysop_via_radio = auth` mit HMAC-Passwort):
  ersetzt durch Variante B. Die Entscheidung aus CR21 („keine Sysop-Rechte über Funk und keine im
  Client“) ist damit geändert – bestätigt von OE3GAS, 10.11.2026.

## CR95 – Zeichensatz-Policy und Ausgabe-Maskierung (TB-11, TB-12, TB-22, ✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- Auch internationale User sollen ihre Schrift verwenden können, ohne dass sich damit tricksen lässt.
- TB-12 (Escape-Sequenzen in Konsole und Logs), TB-22 (ADIF-Feldinjektion über QSL-Karte):
  Plausibilitätsprüfung.

### Vorschlag (Claude) – Details PLANUNG 29.9

- `prcore/text.py`: Protokollfelder streng ASCII, Freitext nach Unicode-Positivliste, striktes UTF-8,
  NFC, Steuerzeilen-Erkennung auf NFKC-Kopie, gemischte Schriften kennzeichnen, Grenzen in Byte.
- Maskierung bei jeder Ausgabe (Konsole, Log, HTML mit `<bdi>`, ADIF, CSV) – für alle Rollen.
- Abstufung nach Rolle (Emoji erst ab authentifiziertem User).

### Umsetzung (TinyBox, brocast, kisshub, Client 2026.11.09.3 – 09.11.2026)

- `prcore/text.py`: `clean_text()` (Positivliste nach Unicode-Kategorie: L*, M* höchstens 3 je
  Buchstabe, N*, P*, Sc, Sm, Sk, So; Leerzeichen → U+0020, Zeilenende LF, Tab bleibt; weg: Cc, Cf
  außer ZWNJ/ZWJ innerhalb eines Wortes oder einer Emoji-Folge, Co, Cs, Cn, Zl, Zp; NFC; Emoji
  abschaltbar), `defuse_lines()`/`protocol_like()` (Erkennung auf NFKC-Kopie), `visible()` (Konsole
  und Log), `mixed_script()` (lateinisch mit kyrillisch/griechisch in einem Wort).
- Angewendet: `MessageService.create` (Betreff und Text jeder Post; `defuse_lines` nur für lokal
  geschriebene, nicht für weitergeleitete), Chatboard (`ChatHub.say`), Client: empfangene Zeilen im
  Terminal/Chat (`Channel.term_line`).
- TB-12: `visible()` in `prcore.termcolor.ConsoleFormatter` (TinyBox, Client, kisshub, brocastd),
  in der TinyBox-Logdatei (`logsetup.Formatter`), in der brocastd-Logdatei (`colorlog.FileFormatter`,
  mit eigenem Ersatz, wenn brocast ohne prcore läuft) und in der Sysop-Konsole (`L`, `R n`, Chat).
- HTML: Box-, Client- und brocast-GUI setzen fremden Text schon bisher nur über `textContent`.
  Neu im Client: jeder fremde Text in einem eigenen `<bdi>` (Rechts-nach-links-Text kann Rufzeichen
  und Zeit daneben nicht umdrehen).
- TB-22: `adifField()` im Client – ADI-Werte nur ASCII (Umlaute werden zu Grundbuchstaben), ohne
  `<`/`>`; der Locator der QSL-Karte muss ein Maidenhead-Locator sein, sonst fehlt das Feld.
- Tests `tests/test_cr95.py` (mit `tests/fixtures/adif.js` für die ADIF-Funktionen).
- Offen: Abstufung nach Rolle (strengere Liste für nicht authentifizierte User, Kennzeichnung
  gemischter Schriften) – mit CR92, wenn es die Rollen gibt.

## CR96 – Datei- und Bildempfang absichern (TB-05, TB-16, Stufe 1 ✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- 24-Bit-Hash: Ersatz einer Datei/eines Bildes durch eine gezielt erzeugte Kollision (offline in
  Sekunden). Sorge: Schadcode und Binaries landen auf dem Rechner.
- Grundsätzliche Prüfung der übertragenen Daten; bei Verdacht bricht der Client den Download ab.

### Vorschlag (Claude)

- Hash mindestens 64 Bit (besser SHA-256 voll im Protokoll), Prüfung nach dem Entpacken.
- Keine ungefragten Pushes; Laden nur auf Antippen.
- Früher Abbruch: Größe, angekündigter Typ, Dateisignatur der ersten Bytes (z. B. `MZ`/ELF bei
  „Bild“), Positivliste der Typen, Packbomben (LZHUF-Verhältnis, Bildgröße in Pixeln).
- Bilder nach dem Empfang neu kodieren (Pillow) – entschärft Polyglots.
- Windows: „Mark of the Web“ (`Zone.Identifier`) für empfangene Dateien.
- Gilt auch für CR86 (Dateien im Board-Chat) – dort von Anfang an so umsetzen.

### Umsetzung Stufe 1 (Client 2026.11.09.4, TinyBox – 09.11.2026)

Ohne Änderung am Funkformat (die Referenz `~#<6 hex>…` bleibt):

- Client, Bilder von Peers (`peerimg.py`), Dateien (`peerfile.py`) und Bilder von der TinyBox
  (`images.py`): angenommen wird nur, was gerade angefordert ist; Ungefragtes wird vom Datenstrom
  genommen und verworfen (kein Eintrag in `loading`/`file_loading`). Eine Ankündigung über dem Limit
  (`PEER_IMG_MAX`, `FILE_MAX` – jetzt auch für unkomprimiert `r` –, `chatimg.MAX_SIZE`) trennt die
  Verbindung.
- `ImageStore.put` / `FileStore.put`: Empfangenes überschreibt nie einen vorhandenen Eintrag (das
  schützt auch die geteilten Board-Bilder); nur eigene Daten (`own=True`) dürfen.
- `tbclient/filecheck.py`: Programme und Skripte werden nicht angenommen – am angebotenen Namen schon
  beim Antippen (kein Byte wird geholt), am Inhalt nach dem Empfang (`MZ`, ELF, Mach-O, `#!`,
  Windows-Verknüpfung, ZIP mit Programm darin, kaputtes ZIP). Die Meldung steht beim Eintrag.
- TinyBox (`tinybox/chatimg.py`): ein Upload gehört der Station, die ihn begonnen hat. Eine andere
  bekommt `//ERR img busy` und kann ihn weder übernehmen noch mit anderer Größe ersetzen; fertig
  machen kann ihn nur der Eigentümer. Liegt unter dem Hash schon ein **anderes** Bild, wird der
  Upload mit `//ERR img collision` abgewiesen (der Client sagt: Bild leicht ändern, neu senden).
- Download im Browser: schon bisher `application/octet-stream`, `attachment`, `nosniff`.
- Tests `tests/test_cr96.py`.

Nicht umgesetzt:

- Bilder neu kodieren: der Client hat kein Pillow; der Browser dekodiert WebP/JPEG in seiner Sandbox.
- „Mark of the Web“: die Datei kommt über den Browser-Download auf den PC; ob Windows sie markiert,
  entscheidet der Browser (für 127.0.0.1 meist nicht).

### Stufe 2: längerer Hash – entschieden (OE3GAS, 09.11.2026)

- Kommt **mit CR86** (Dateien im Board-Chat) zusammen mit dem Client, als neue Version **ohne
  Übergangsregel**: der Client ist noch nicht so verbreitet, dass sich Rückwärtskompatibilität lohnt.

Hintergrund:

24 Bit lassen sich in Sekunden gezielt kollidieren. Mit Stufe 1 bringt eine Kollision allein nichts
mehr (nichts wird überschrieben, nichts Ungefragtes angenommen, ein Upload gehört seinem Beginner).
Ein längerer Hash (z. B. 16 hex = 64 Bit) wäre zusätzliche Tiefe, ändert aber das Funkformat der
Referenzen (`~#`, `~%`, `//IMG`, `//I`, `//F`, `//IMGPUT`) und braucht neue Client- und Box-Version
mit Übergangsregel für ältere Gegenstellen – kostet etwa 10 Byte je Referenz.

## CR97 – Ratenbegrenzung und Obergrenzen (TB-03, TB-13, TB-17, TB-18, TB-19, ✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- Die eigene Station darf nicht auf fremden Anstoß hin den Kanal belasten (Lizenzinhaber,
  PLANUNG 29.3 Objekt 7).
- TB-13: Linktabelle begrenzen, Fantasie-Rufzeichen abweisen. TB-19: Statistik darf nicht
  unbegrenzt wachsen.

### Vorschlag (Claude)

- Token-Bucket pro Peer für `//FGET`, `//ST` und alle Antworten, die Daten senden (TB-03).
- Obergrenze der AX.25-Linktabelle, SABM von unplausiblen Rufzeichen abweisen (TB-13).
- Leerlauf-Freigabe für Session-Slots und Client-Kanäle (TB-17).
- Grenze für Wiederholungen nach REJ/SREJ pro Zeitfenster (TB-18).
- kisshub-Statistik: feste Obergrenze, älteste Einträge verwerfen, Status-JSON begrenzen (TB-19).

### Umsetzung (Client 2026.11.09.5, TinyBox, prcore, kisshub 2026.11.09.2 – 09.11.2026)

- TB-03, Client (`tbclient/budget.py`): jede Antwort, die eine andere Station anstößt, kommt aus zwei
  Token-Buckets – je Basis-Rufzeichen 96 KB, alle zusammen 256 KB, je halbe Stunde nachgefüllt (auch
  viele erfundene Rufzeichen kommen nicht weiter). Dazu je Rufzeichen und Sache: dieselbe Datei
  (`//FGET`) höchstens 2×/h, dasselbe Bild (`//IMG`) 3×/h, Speedtest-Antwort 1× je 10 min,
  `//HEARD?` 2×/min, `//PING` 6×/min. Abgelehnt: `//NOFILE`/`//NOIMG` bzw. keine Antwort, Warnung im
  Log. Was der User selbst startet, zählt nicht.
- TB-13, `prcore/kissport.py` (TinyBox im KISS-Betrieb und Client): höchstens `MAX_LINKS = 32` Links;
  ein SABM von einem Rufzeichen ohne Buchstaben und Ziffer (`plausible_call`) wird mit DM abgewiesen;
  ist die Tabelle voll, macht der älteste Link Platz, der seit über 30 s besteht und noch nie ein
  I-Frame brachte (DM, „evicted“), sonst wird der neue abgewiesen. Nicht geändert: Antwortweg über die
  Digipeater des Anrufers, XID-Antwort an Fremde.
- TB-18, `prcore/ax25/link.py`: ein REJ/SREJ sendet dasselbe N(R) frühestens nach einer halben
  Laufzeit (`srt/2`, mind. 0,5 s) wieder (die Bestätigung darin zählt trotzdem; Zähler
  `rej_ignored`); wurde ein Frame öfter als N2-mal gesendet, endet der Link wie bei Retry-out.
- TB-17, BBS: höchstens `MAX_PER_CALL = 2` Sitzungen je Rufzeichen (alle SSIDs, der Sysop
  ausgenommen). Mitlesen im Chat bleibt ohne Zeitgrenze (`[chat] idle_min`, Vorgabe 0 = ohne Grenze;
  AX.25 selbst kennt kein Idle-Limit, T3 prüft nur, ob die Gegenstelle noch da ist). Nachgeschärft
  (OE3GAS, 09.11.2026, statt erst 120 min): ist die Box voll und **will jemand herein**, macht der
  Chat-Leser Platz, der am längsten still ist (länger als `idle_timeout_min`) – nur dieser eine und
  nur dann (`SessionRegistry._make_room`); der Neue kommt sofort herein. Client: eine eingehende Verbindung lässt den letzten Kanal frei (für Mailbox-Sync
  und eigene Verbindungen) und wird nach 30 min ohne Zeile getrennt.
- TB-19, kisshub (`linkstats.py`): höchstens 500 gehörte Stationen (wer einen Tag nicht gehört
  wurde, fällt weg), 200 verfolgte Links (der am längsten stille macht Platz), Status-JSON mit den 50
  zuletzt aktiven Links plus `links_total`; Schließen eines Links per Schlüssel statt Suche.
- Tests `tests/test_cr97.py`.

## CR98 – Client-Audit: Zugriff auf PC-Daten und In-Band-Befehle (✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- Aussage: Der Chat hat keine Möglichkeit, ohne Rückfrage auf Daten des Users am PC zuzugreifen.
  Durch ein Audit zu validieren (Claude).

### Vorschlag (Claude)

- Jeden Weg erfassen, über den eingehende Daten Dateien lesen oder schreiben; bekannt: `//FGET`
  liest angebotene Dateien ohne Rückfrage, die Prüfung „wem angeboten“ hängt am fälschbaren Rufzeichen.
- Prüfen, ob Zeilen mit `//` aus Post oder Bulletins beim Lesen/Sync als Befehl ankommen können.
- Ergebnis als Bericht in `docs/`, Befunde als eigene CRs.

### Ergebnis (Claude, 09.11.2026) – Bericht `docs/audit-client-cr98.md`

- Aussage bestätigt: über das Netz liest der Client nur eigene Bilder und selbst angebotene Dateien
  (Hash-Name im eigenen Datenordner, kein Pfad), schreibt nur in den Datenordner, startet nichts.
  Präzisierung: eine angebotene Datei kann (auch ein Fremder unter dem Rufzeichen) ohne neue
  Rückfrage wieder abrufen – seit CR97 begrenzt.
- F1 ✅ (Medium): mit `R n` gelesene Post (auch weitergeleitete) wirkte mit `//…`, `#…`, `%Q`-Zeilen
  im Client als Befehl → Box schickt solche Zeilen an Clients mit Leerzeichen (`client_safe`).
- F2 ✅ (Medium): `//TB BOX`/`//TB CLIENT` in einem Text auf einer fremden Mailbox schaltete den Kanal
  um → nur 90 s nach dem eigenen `//TB?` und nur einmal.
- F3 ✅ (Low, Fuzz-Lauf): `//IN` mit Nicht-Zahl → wird geprüft. Der breite Fuzz-Lauf aus CR88 ist
  damit erledigt (`tests/test_cr98_fuzz.py`).
- Die Befunde waren klein genug, um sie gleich zu beheben – keine eigenen CRs. Peer-Verlauf (TB-06)
  bleibt bei CR99.

## CR99 – Chatverlauf und Peer-Identität (TB-06, TB-07, ✅ 10.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- TB-06 (Chatverlauf lesen/löschen/fälschen durch gefälschten Peer) lässt sich nur durch Zertifikat
  bzw. zusätzliche Authentisierung schließen. TB-07: gefälschte TBCHAT-Zeilen.

### Vorschlag (Claude)

- Sofort: Löschen und Abgleich des lokalen Verlaufs nur nach Rückfrage beim User.
- Danach mit CR93/CR94: Peer-Nachrichten signiert, Verlauf nur mit verifizierter Gegenstelle abgleichen.

### Vorschlag Authentisierung Client ↔ Client (Claude, 10.11.2026, zu CR107)

Beide Clients haben seit CR93 einen eigenen Schlüssel (je Gerät) und ggf. ein Zertifikat ihrer
Heimat-BBS. Damit:

1. **Gegenseitige Challenge:** `//TB?` und `//TB CLIENT` tragen je eine Zufallszahl `n=`. Jede
   Seite antwortet `//PAUTH sig=<86> pub=<43> [cert=…]` – Signatur über
   `TINYBOX-PEER1|<eigener Ruf>|<Ruf der Gegenseite>|<Zufallszahl der Gegenseite>` (≈ 140 Byte,
   ≈ 300 mit Zertifikat, einmal je Verbindung).
2. **Prüfung, zwei Stufen:**
   - *Bekannt (TOFU, wie SSH):* beim ersten Kontakt merkt sich der Client den Schlüssel des
     Peers; später muss er gleich sein (ein neues Gerät des Peers: Hinweis „neuer Schlüssel“,
     bestätigen). Fingerabdruck in der Peer-Karte, zum Vergleichen im QSO.
   - *Bestätigt:* das Zertifikat der Heimat-BBS des Peers. Der Client prüft es, wenn er dieser
     BBS vertraut: der eigenen Heimat-BBS immer, anderen über deren `TRUST`-Liste (Abfrage
     `//TRUST? <box>` an die eigene Heimat-BBS). Anzeige „✓ bestätigt durch OE3GAS-1“.
3. **Was davon abhängt:** Verlauf abgleichen (`//HIST`, `//HM`), Verlauf löschen, Bilder und
   Dateien vom Peer holen erst bei „bekannt“ oder „bestätigt“; bei abweichendem Schlüssel nichts
   davon, nur Chat, mit Warnbalken (schließt TB-06).
4. **Einzelne Zeilen** bleiben unsigniert (Byte-Kosten je Zeile; Rest-Risiko eingeschleuster
   Zeilen wie im Chatboard, TB-07). Optional später: signiert nur, was etwas auslöst (Löschen).

### Umsetzung (Client 2026.11.10.10, TinyBox – 10.11.2026) ✅

- Wie vorgeschlagen (OE3GAS: „passt so“). `tbclient/peerauth.py`; Fähigkeit `AUTH`, Zufallszahl
  `n=` in `//TB?` / `//TB CLIENT` (+25 Byte), `//PAUTH sig= pub= dev= [cert=]`, signiert
  `TINYBOX-PEER1|<eigener Ruf>|<Ruf des anderen>|<seine Zufallszahl>` (`auth.peer_message`).
- Zustände `verified` (Zertifikat, Herausgeber vertraut), `known`, `first` (TOFU), `changed`,
  `bad`, `old`. Bekannte Schlüssel in `settings.json` (`peer_keys`, 5 je Rufzeichen, 300 Rufzeichen).
  Ein Zertifikat gilt auch für ein neues Gerät des anderen ohne Rückfrage.
- Vertraute Herausgeber: `//TRUST?` an die Heimat-BBS (einmal am Tag) → `//TRUST <Box>=<Schlüssel> …`
  (die Box selbst und ihre `TRUST`-Liste).
- Nur bei `verified`/`known`/`first`: `//HIST`, `//HM` (also auch Löschen auf beiden Seiten),
  eigene Bilder (`//IMG`) und Dateien (`//FGET`) an den anderen. Sonst Warnung im Log, nur Chat.
- Peer-Karte: Zeile mit Zustand, Fingerabdruck, Gerät; Knopf „Accept new key“ bei `changed`.
- Tests `tests/test_cr99.py`.

## CR107 – Gleiche Funktionen Client↔Client und im Chatboard (✅ 10.11.2026)

### Erfassung (OE3GAS, 10.11.2026)

Bei der Kommunikation Client zu Client soll die gesamte Palette an Funktionen verfügbar sein, die
es in den Chatboards schon gibt – Shoutout, Kommentar usw. Vorab prüfen, was fehlt. Dazu: wie die
Authentisierung zwischen den beiden Teilnehmern gehen kann (→ CR99, Vorschlag oben).

### Bestandsaufnahme (Claude, 10.11.2026) – Client↔TinyBox-Chatboard und Client↔Client

✓ vorhanden · ✗ fehlt · – passt hier nicht

| Bereich | Funktion | Chatboard (über TinyBox) | Client ↔ Client |
|---|---|---|---|
| Text | Text, Emoticons → Emoji (1–3 Byte über Funk) | ✓ | ✓ |
| | Ein einzelnes Emoji groß | ✓ | ✗ |
| | `Monospace` (ASCII-Art), _fett_ | ✓ | ✗ |
| | Links anklickbar | ✓ | ✗ |
| | Shoutout („Cry out“, Bang!-Blase) | ✓ | ✗ (kommt als `~!Text`) |
| | Sticker | ✓ | ✗ (kommt als `[STK]CQ`) |
| | Animationen (CR11) | ✗ | ✗ |
| Bezug | Kommentar mit Zitat (auch auf History-Zeilen) | ✓ | ✗ |
| | Reaktion (Emoji auf einen Beitrag), eigene sofort sichtbar | ✓ | ✗ |
| Aufmerksamkeit | @RUFZEICHEN hervorgehoben | ✓ | – (zu zweit) |
| | Alarm: Popup / „BK“ in CW (CR85) | ✓ bei @Ruf oder Kommentar | ✗ |
| | Kanal-Chip blinkt bei Neuem im Hintergrund | ✓ | ✓ |
| Medien | Bilder (Vorschau, holen per Antippen) | ✓ | ✓ |
| | „lädt Bild hoch“ mit Fortschritt bei den anderen | ✓ | ✗ |
| | Dateien (LZHUF) | ✗ (CR86) | ✓ |
| | QSL-Karte mit ADIF | ✗ | ✓ |
| Zustellung | Zustellhaken (von AX.25 bestätigt) | ✗ | ✓ |
| Verlauf | Verlauf beim Wiederkommen | ✓ verpasste / 10 / 20, „load all“ | ✓ 100 Zeilen, abgeglichen |
| | Verlauf löschen | – (Sysop) | ✓ beide Seiten |
| Gegenüber | Profil: Name, Locator, Entfernung/Richtung | ✓ in der Teilnehmerliste | ✓ Karte |
| | Avatar mit APRS-Symbol | ✓ | ✗ |
| | Mini-Karte aus den Locatoren | ✗ | ✓ |
| | „Heard there“ – wen hört der andere | ✗ | ✓ |
| | Uhrabweichung | – | ✓ |
| | Version des anderen, Hinweis auf neuere | ✓ (TBNEWS) | ✓ |
| Verbindung | Linkqualität (Balken, Zahlen) | ✓ je Teilnehmer zur Box | ✓ beide Richtungen |
| | Ping, Speedtest | ✗ | ✓ |
| | „Connection … lost“ | ✓ | ✓ |
| Spiel | Schach | ✗ | ✓ |
| Sicherheit | Gegenüber nachgewiesen | ✓ Login mit Schlüssel bei der Box (CR93); Zeilen unsigniert | ✗ (CR99) |
| Reichweite | mehrere Teilnehmer, einmal als UI-Frame für alle | ✓ | – (1:1) |
| | Nachricht, wenn der andere nicht da ist | ✓ History des Boards | ✗ (Idee: als Mail über die TinyBox) |

**Lücken Client ↔ Client (9):** großes Einzel-Emoji, Formatierung, Links, Shoutout, Sticker,
Kommentar, Reaktion, Alarm, Avatar; dazu „lädt Bild hoch“ und die Authentisierung (CR99).

**Lücken im Chatboard (7):** Dateien (CR86), QSL-Karte, Zustellhaken, Mini-Karte der Teilnehmer,
„Heard there“, Ping/Speedtest, Schach – nicht alles passt für viele Teilnehmer (siehe Vorschlag).

### Vorschlag (Claude)

- Dieselbe Darstellung wie im Chatboard (Shoutout-Stern, Sticker, Links, Zitat-Block,
  Reaktionen unter der Blase) und dieselben Knöpfe in der TBClient-Ansicht.
- Bezug für Kommentar und Reaktion: im Chatboard die Ereignisnummer; zwischen zwei Clients die
  Zeilennummer im Verlauf (`peerchat`, je Richtung): `~^m12` = meine Zeile 12, `~^y7` = deine
  Zeile 7 (aus Sicht des Senders). Reaktion `//R m12 :+1`, nur im Verlauf gespeichert. Ältere
  Clients sehen den Text bzw. ignorieren `//R`.
- Alarm: jede neue Zeile des Peers zählt (ein Gespräch zu zweit), wenn das Fenster nicht im
  Vordergrund ist – mit denselben Einstellungen wie CR85.
- ~~Fähigkeit `CHAT2`~~ – nicht nötig: alles sind Textzeilen, ältere Clients zeigen den Text.
- **Umgekehrt ins Chatboard** (für viele Teilnehmer sinnvoll): Dateien (CR86), Karte der Teilnehmer
  aus ihren Locatoren, Zustellhaken für die eigene Zeile (bei I-Frame: AX.25-bestätigt bis zur
  Box; bei UI: „gesendet“), QSL-Karte an einen Teilnehmer. Ping/Speedtest/Heard there/Schach gehen
  direkt Client ↔ Client – im Board als Knopf am Teilnehmer, der eine Direktverbindung aufbaut
  (wenn er direkt erreichbar ist). Zu entscheiden: OE3GAS.

### Umsetzung Teil 1: Client ↔ Client (Client 2026.11.10.11 – 10.11.2026) ✅

- Nur Web-GUI (`app.js`), keine neuen Protokollzeilen: Shoutout `~!`, Sticker `[STK]`, Kommentar
  `~^m<n>` / `~^y<n>` (m = eigene Zeile des Schreibers, y = seine empfangene), Reaktion
  `~*m<n> <Emoji>` – als Zeilen im gemeinsamen Verlauf gespeichert und abgeglichen; Reaktionen
  erscheinen als Pillen unter der Blase. Links, `Monospace`, großes Einzel-Emoji (`richText`),
  Avatar links neben den Blasen des anderen, Alarm bei jeder neuen Zeile (Fenster nicht vorne).
- „lädt Bild hoch“: zwischen zwei Clients holt der Empfänger das Bild selbst, mit Fortschritt –
  gleichwertig, nichts zu tun.

### Umsetzung Teil 2: Chatboard (Client 2026.11.10.12/.13, TinyBox – 10.11.2026) ✅

- Dateien: CR86 (mit 16-Hex-Hash).
- Karte der Teilnehmer: aus den Profilen (`profiles.snapshot` gibt `ll` und `profile_here`), SVG wie
  die Karte Client↔Client, unter „In this board“.
- Zustellhaken: ✓ an der eigenen Zeile, sobald sie von der TinyBox zurückkommt (gilt für I-Frame
  und UI – das Echo zeigt, dass die Box sie hat).
- Ping, Speedtest, Heard there, Schach, QSL: Knopf ⇄ am Teilnehmer → Direktverbindung in einem
  freien Kanal (`/api/connect`), dort die TBClient-Ansicht mit diesen Knöpfen.
- Mail an Abwesende: TBClient-Ansicht ohne Verbindung – Enter öffnet eine Mail an das Rufzeichen
  (ohne SSID) mit dem getippten Text, über die eigene TinyBox.
- Tests `tests/test_cr107.py` (Python-Seite), Ansicht im Browser geprüft.

## CR100 – Client-Web-GUI: nur eigenes Netz, Schutz gegen DNS-Rebinding (✅ 09.11.2026)

### Erfassung (Claude, 09.11.2026, beim Audit aufgefallen, PLANUNG 11/5)

- `tbclient.conf.example`: `host = 0.0.0.0` ohne Anmeldung. Wer im LAN (ggf. WAN) die Adresse kennt,
  sendet unter dem Rufzeichen des Client-Betreibers und bedient den Client. Nicht im Audit enthalten.

### Vorschlag (Claude)

- Vorgabe `host = 127.0.0.1`; LAN nur bewusst und dann mit Zugangstoken (einmal am PC angezeigt,
  als Cookie gespeichert) oder nur über VPN/HAMNET.
- Schutz gegen Aufrufe fremder Webseiten auf 127.0.0.1 (Host-Header prüfen, CSRF-Token).

### Entscheidung (OE3GAS, 09.11.2026)

- Im selben Netz soll der Client ohne Anmeldung erreichbar bleiben (Handy/Tablet). Ein Token ist am
  Handy nicht praktikabel → keine Zugriffskontrolle im eigenen Netz (PLANUNG 29.6 AR3).
- Der Bereich 10.0.0.0/8 muss dabei sein.

### Umsetzung (Client 2026.11.09.2)

- `tbclient/webguard.py`, `[web] allow` (Vorgabe `lan`): nur 127.x, **10.x**, 172.16–31.x,
  192.168.x, 169.254.x, IPv6 ::1, fc00::/7, fe80::/10 (auch als `::ffff:`-Adresse). Andere Adressen
  bekommen 403, jede wird einmal im Log gemeldet. `local` = nur dieser PC, `any` = alle, dazu
  eigene Netze, z. B. `allow = lan, 44.0.0.0/8` (HAMNET). Ungültige Angabe = Fehler beim Start.
- Host-Prüfung gegen DNS-Rebinding: angenommen werden IP-Adressen, `localhost`, Namen ohne Punkt
  (PC1), `.local`, `.lan`, `.home`, `.home.arpa`, `.internal`, `.localdomain`, `.fritz.box` und die
  Namen in `[web] hosts`. Sonst 403.
- POST mit `Origin` eines anderen Hosts: 403. (Schon vorher: POST nur mit `X-TBClient: 1` und JSON.)
- `host = 0.0.0.0` bleibt Vorgabe. Tests `tests/test_cr100.py`.

## CR101 – TinyBox-Web-GUI: Live-Monitor im Dashboard schlanker (✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- Im Live-Monitor des Dashboards die Knöpfe „APRS Lense“, „HEX“ und „Clear“ entfernen, das
  Suchfeld bleibt. Stattdessen ein Knopf „Switch to monitor screen“, der den eigentlichen
  Monitor-Bildschirm öffnet.

### Umsetzung (nur TinyBox-Web-GUI, `tinybox/web/app.js`)

- Dashboard-Karte: Filterfeld und Auswahl („Everything“ …) bleiben, dazu „Switch to monitor
  screen“ (`#/monitor`, wie „Monitor“ in der Seitenleiste). Filter und Auswahl gelten auf beiden
  Seiten gemeinsam.
- Die Karte zeigt immer Text: kein HEX, keine APRS-Karte, kein Frame-Inspektor – auch wenn HEX
  oder APRS Lense auf dem Monitor-Bildschirm eingeschaltet sind (bisher lief dann die Hex-Anzeige
  im Dashboard mit, ohne Knopf zum Abschalten).
- Der Monitor-Bildschirm bleibt unverändert (APRS Lense, HEX, Clear, Inspektor).
- Geprüft im Browser (Playwright): Dashboard mit HEX eingeschaltet → Text, Knopf führt auf
  `#/monitor` mit APRS Lense, HEX, Clear; keine JS-Fehler. `tests/test_web.py` grün.

## CR102 – APRS-Netzgraph: eigene Station, Auswahl, Färbung, km-Ringe (✅ 09.11.2026)

### Erfassung (OE3GAS, 09.11.2026)

- OE3GAS-10 hat in der Darstellung keinen Wert, er ist nur Zuhörer. Die Linien dorthin erwecken
  einen falschen Eindruck → weglassen.
- Zusätzliche Selektionsmöglichkeiten: Digipeater, iGates, Stations, Moving, Directly heard.
- Ansicht „Map“: die km-Beschriftungen der Ringe fehlen.
- Direkt gehörte Calls voller gefärbt, die anderen blasser.

### Umsetzung (Client 2026.11.09.6, News in 2026.11.09.7, `tbclient/web/aprsgraph.js`, `app.css`)

- Keine Linien mehr zur eigenen Station. Sie bleibt nur als kleiner grauer Punkt in der Mitte
  (Bezugspunkt für Hop-Radar und Karte). Die Anordnung rechnet weiter mit allen Wegen, es
  verschiebt sich also nichts.
- Neue Zeile „Show“: All / Digipeaters / iGates / Stations / Moving / Heard directly. Gezeigt
  werden die Wege, auf denen eine passende Station liegt; die übrigen Bubbles dieser Wege bleiben
  schwach sichtbar. Wirkt zusammen mit Paketart, Gerät und min. Frames.
- „Heard directly“ = die letzte Station vor uns auf einem Weg (Sender ohne Pfad, iGate oder
  Digipeater). Diese Bubbles in voller Farbe, alle anderen blass (Füllung 40 %).
- km- und Hop-Beschriftungen der Ringe liegen jetzt über der Zeichnung (vorher von Bubbles und
  Linien verdeckt), unten am Ring, mittig.
- Geprüft im Browser (Playwright) mit Testdaten: Hop-Radar, Map mit 10/50/100/200 km, Auswahl
  „Heard directly“; keine JS-Fehler.

## CR103 – APRS-Statistik bei viel Verkehr (✅ 10.11.2026, PLANUNG 30)

### Erfassung (OE3GAS, 10.11.2026)

- Code der APRS-Statistik (`prcore/aprsstats.py`) auf Überlauf prüfen. Bei uns: 12.000 Frames in
  8 Stunden. Was ist das Maximum?

### Befund (Claude, 10.11.2026)

- Kein Zahlenüberlauf (Python-Ganzzahlen). Grenzen: `KEEP_SEC` = 7 Tage und
  `MAX_RECORDS` = 200.000, was zuerst erreicht ist.
- 12.000 Frames / 8 h = 1.500/h = 36.000/Tag → 7 Tage wären 252.000. Die 200.000 sind nach
  ≈ 133 h (≈ 5,5 Tage) erreicht; „All“ umfasst dann ≈ 5,5 Tage. 7 Tage gehen sich bis
  ≈ 1.190 Frames/h aus. „1 h“ und „24 h“ sind nicht betroffen.
- Messung mit synthetischen Records (≈ 720 Byte RAM je Frame):

  | | 96.000 Frames | 200.000 Frames |
  |---|---|---|
  | RAM im Client | ≈ 69 MB | ≈ 143 MB |
  | Statistik + Graph, 1 h | ≈ 0,1 s | ≈ 0,14 s |
  | Statistik + Graph, 24 h | ≈ 1,1 s | ≈ 0,9 s |
  | Statistik + Graph, „All“ | ≈ 2,1 s | ≈ 4,1 s |

1. **Auswertung blockiert den Client:** `report()`, `graph()` und `station()` laufen direkt im
   asyncio-Loop (`tbclient/web.py`). Die Seite „APRS statistics“ fragt alle 15 s Statistik und
   Graph ab → bei „All“ und voller Statistik steht der Client ≈ 4 s still (AGW, Chat, GUI),
   bei „24 h“ knapp 1 s.
2. **Kopie pro Frame an der Grenze:** `add()` kürzt die Liste auf genau 200.000; beim nächsten
   Frame greift `len > MAX_RECORDS` wieder und die ganze Liste wird neu aufgebaut (≈ 24 ms je
   Frame statt 0,1 ms). Ebenso, sobald die 7-Tage-Grenze greift.
3. **Start:** alle Records werden aus der DB gelesen und einzeln aus JSON dekodiert – bei
   200.000 einige Sekunden. Datei `aprsstats.db` grob 70–80 MB (geschätzt).

### Vorschlag (Claude)

1. Auswertung in einen eigenen Thread (`asyncio.to_thread`), Zugriff auf die Record-Liste dabei
   über eine Kopie bzw. ein Lock absichern (`add()` läuft weiter im Loop).
2. Ergebnis je Endpunkt und Fenster ≈ 15 s zwischenspeichern – zwei offene Tabs rechnen nur
   einmal.
3. Beim Kürzen Luft lassen (z. B. auf 99 % von `MAX_RECORDS`, bzw. alles älter als 7 Tage
   plus eine Stunde) oder `collections.deque` – keine Kopie mehr pro Frame.
4. Optional: `MAX_RECORDS` ≈ 260.000, damit 7 Tage bei unserem Verkehr reichen (≈ 190 MB RAM,
   „All“ noch langsamer → nur zusammen mit Punkt 1).
5. Test: Statistik mit 200.000 Records, Event-Loop bleibt während einer Abfrage ansprechbar;
   `add()` an der Grenze ohne Neuaufbau.

## CR104 – Settings-Seite: Kosmetik und Umbau (✅ 10.11.2026)

### Erfassung (OE3GAS, 10.11.2026)

1. **Karten und Layout:** Die Sektionen als Karten darstellen (bessere visuelle Trennung).
   Gesamtbreite bleibt gleich, oben zwei Spalten:
   - links: **Connection Status** (bisher „Connection“) und **My profile**
   - rechts: **Chat history** und **Mention alert**

   Danach einspaltig: **Connection log**, **My APRS symbol**, **About**.
   - „Connection Status“: die Knöpfe Connect, Disconnect, Terminal entfallen, nur der Status wird
     angezeigt. Ergänzen um „Mailbox: x messages in the box“.
   - About: hinter der TinyBox-Client-Version „by OE3GAS“ ergänzen.
2. **Auth-Hinweis:** Anzeigen, dass der Client authentisiert ist („auth“), einen eigenen
   Schlüssel hat und mit welchen TinyBoxen er sich verbinden kann/darf.
3. **Connection log:** Spaltenkopf „In / out“ → „In/Out bytes“.
4. **Connection log, Spalte „Time“:** Leerzeichen zwischen den Einheiten, „2h41m“ → „2h 41m“.
5. **Mention alert:** CW-Tempo wählbar, kein Regler, sondern feste Stufen **60, 100, 150 BpM**.

### Hinweise (Claude, 10.11.2026)

- Zu 1: Connect/Disconnect/Terminal gibt es weiterhin an anderer Stelle (Kopfzeile/Menü) – vor
  dem Entfernen prüfen, dass jeder Knopf dort erreichbar ist.
- Zu 1: „x messages“ – gemeint vermutlich die ungelesenen persönlichen Nachrichten
  (`S.mailbox.unread`); bei Mailbox ≠ TinyBox den Ruf der Mailbox dazuschreiben.
- Zu 2: Daten aus CR93 (`identity.key`): Status (freigegeben / wartet auf Sysop), Fingerabdruck
  (`7F3A-91C2-44E0`), Heimat-BBS. „Mit welchen TinyBoxen“: in Stufe 1 nur die Heimat-BBS, bei der
  der Schlüssel freigegeben ist; fremde Boxen erst mit der Vertrauenskette (CR93 Vorschlag/CR94).
- Zu 5: BpM = Buchstaben pro Minute; derzeit fest 60 BpM (12 WpM, Dit 100 ms, CR85).
  100 BpM = 20 WpM (Dit 60 ms), 150 BpM = 30 WpM (Dit 40 ms). Speichern wie die übrigen
  Alarm-Einstellungen im Browser.
- Client-Änderung → `VERSION` erhöhen und News-Datei anlegen.

### Entscheidungen (OE3GAS, 10.11.2026)

1. **Zeitformat:** ab einer Stunde „2h 41m“, darunter Minuten und Sekunden „53m 28s“
   (also auch „0m 22s“).
2. **Mailbox im Status:** „x messages“ = Nachrichten in der Inbox, dieselbe Zahl wie in der
   bisherigen Sektion „Mailbox“ („2 message(s) in the inbox, 39 sent, …“).
3. **Auth-Hinweis:** nur die Heimat-BBS anzeigen (Status der Freigabe, Fingerabdruck) – keine
   Liste fremder TinyBoxen.
4. **Spaltenkopf:** die Spalte „In / out“ im Connection log heißt künftig „In/Out bytes“.
5. **Sektion „Mailbox“:** die ganze Zeile (Inbox, sent, Rubriken, letzter Abgleich) kommt in
   die Karte „Connection Status“, die eigene Sektion entfällt.
6. **Connection log sortieren:** nach Connect-Zeit, neueste zuerst. Derzeit stehen Einträge
   durcheinander (07.11.: 23:02, 23:16, 23:01, 23:05, 23:03), vermutlich nach Verbindungsende
   sortiert.

### Umsetzung (Client 2026.11.10.3)

- `index.html`, `app.css`: Abschnitte als Karten (`.set-card`); oben zwei Spalten
  (Connection status + My profile | Chat history + Mention alert), unter 640 px einspaltig.
  Darunter Connection log, My APRS symbol, About („… by OE3GAS“). Die Knöpfe Connect,
  Disconnect, Terminal in den Settings sind weg (bleiben in der Kopfzeile, im Offline-Bild und
  unter Station > TinyBox terminal); die eigene Sektion „Mailbox“ ist in „Connection status“
  aufgegangen.
- Connection status: „Connected: …“ / „Not connected: …“, darunter Login bei der Heimat-BBS
  (authenticated / wartet auf den Sysop / refused) mit Fingerabdruck des eigenen Schlüssels,
  dann die Mailbox-Zeile. Der Client merkt sich die letzte Antwort der Heimat-BBS
  (`auth_home` in den Client-Settings, `core._note_home_auth`) – so steht der Status auch
  ohne Verbindung da („last login …“).
- Connection log: Spaltenkopf „In/Out bytes“, Dauer „2h 41m“ bzw. „53m 28s“; sortiert nach
  Connect-Zeit absteigend (`logbook.rows`: `ORDER BY t_on DESC`, die Zeile wird erst am Ende der
  Verbindung geschrieben – daher die alte Unordnung). Gilt auch für CSV/ADIF.
- Mention alert: Auswahl „Speed“ 60/100/150 BpM (Dit = 6 s / BpM), gespeichert im Browser.
- Test: `tests/test_cr104.py` (Reihenfolge des Logbuchs).

## CR105 – Eigenes Profilfoto (offen, 10.11.2026)

### Erfassung (OE3GAS, 10.11.2026)

- In „My profile“ ein eigenes Foto vorsehen, passend in das runde Format des Call-Icons.
- Das Foto ist **optional**.
- Wenn vorhanden, im Chatboard und bei Verbindung mit einem anderen Client anzeigen, und zwar
  **links neben dem Call-Icon**.

### Offene Punkte (Claude, 10.11.2026)

- Größe über Funk: Foto im Browser rund zuschneiden und stark verkleinern (z. B. 48×48 px,
  WebP/JPEG, Ziel wenige hundert Byte), Übertragung wie bei CR12.
- Nur einmal senden: Hash im Profil mitschicken, Empfänger cachen je Rufzeichen und laden nur bei
  geändertem Hash nach (nicht bei jedem Board-Beitritt).
- Bei fremden Clients nur anzeigen, wenn der Absender verifiziert ist (CR93) – sonst könnte jeder
  ein Foto unter fremdem Rufzeichen verteilen.
- Bezug: CR7/APRS-Symbol als Badge am Avatar bleibt.

### Entscheidung (OE3GAS, 10.11.2026)

- `MAX_RECORDS` fest auf **250.000**, egal wie viele Tage da hineinpassen (keine Altersgrenze
  mehr). Der Gesamtzeitraum muss in der Statistik erkennbar sein: „All“ wird zu „Last … days“.

### Umsetzung (Client 2026.11.10)

- `prcore/aprsstats.py`: `KEEP_SEC` entfällt, `MAX_RECORDS = 250_000`. Gekürzt wird erst bei
  250.000 + `TRIM_SLACK` (2.500) auf 250.000 – eine neue Liste, keine Kopie mehr pro Frame. Die
  Datei behält stündlich die neuesten 250.000 (Abfrage über den Index statt `NOT IN`), beim
  Start werden nur diese geladen.
- Jede Auswertung arbeitet auf einer Kopie der Liste (`_snap()`), kann also in einem Thread
  laufen, während `add()` weiterläuft. „Alles“ beginnt beim Reset – oder, sobald die Grenze
  ältere Frames verworfen hat, beim ältesten noch gespeicherten Frame. Neu in Statistik, Graph
  und Stationsseite: `kept_from`, `kept_frames`, `kept_max`, `kept_full`.
- `tbclient/web.py`: Statistik, Graph und Stationsseite laufen in `asyncio.to_thread`; das
  Ergebnis gilt 10 s (`APRS_CACHE_SEC`), dieselbe Abfrage während der Rechnung wartet auf
  dieselbe Auswertung (zwei Tabs = eine Rechnung). Reset leert den Zwischenspeicher.
- GUI (`aprsstats.js`): der Knopf „All“ heißt nach dem ersten Laden z. B. „Last 6.9 days“
  (unter 48 h in Stunden, ab 10 Tagen ganze Tage), der Kopf zeigt „last 6.9 days (since …)“ und
  bei voller Grenze „limit 250,000 frames reached“.
- Gemessen mit 250.000 synthetischen Frames bei unserem Verkehr (1.500/h): „All“ = 6,9 Tage,
  Statistik + Graph ≈ 4,7 s im Hintergrund, längste Pause des Event-Loops 68 ms (vorher stand der
  Client die ganze Zeit). Zweiter Tab: aus dem Zwischenspeicher. `add()` an der Grenze im
  Schnitt 0,8 ms je Frame (vorher 24 ms). RAM ≈ 180 MB.
- Tests: `tests/test_aprsstats.py` (Grenze ohne Kopie pro Frame, keine Altersgrenze, Zeitraum,
  Datei), `tests/test_cr103.py` (Auswertung nicht im Loop-Thread, Loop läuft weiter, eine
  Rechnung für gleichzeitige Abfragen).

## CR106 – Mail-Hinweis, aber leere Inbox; Sync hängt in „connecting“ (✅ 10.11.2026)

### Erfassung (OE3GAS, 10.11.2026)

- Client zeigt „4 new messages for OE3GAS at OE3GAS-1“, die Inbox bleibt leer. Der Sync bleibt
  in „connecting“ stehen, nach Abort in „connecting (aborting)…“.

### Ursache (Claude, 10.11.2026)

- Seit CR93 antwortet die Box auf `//CLIENT` mit `//AUTH?`; solange der Login läuft, ist die
  Sitzung noch kein Client und die Box schreibt nach jeder Zeile ihren Prompt. Die Antworten
  `//AUTHWAIT fp=…` (Schlüssel wartet auf den Sysop) und `//ERR auth …` (z. B. `other_key`) kamen
  daher als `TinyBox (A,B,…) > //AUTHWAIT …` – für den Client keine Steuerzeile. Folge: kein
  Client-Modus, kein Hinweisbalken, kein Eintrag in der Konsole.
- Der Sync wartete in `_wait_ready` bis zu 90 s auf den Client-Modus und reagierte dort nicht auf
  Abort (erst der harte Abbruch nach 30 s). Läuft ein Sync, nahm er außerdem `//ERR auth` als
  eigene Zeile an sich.
- Der Mail-Hinweis selbst stimmt: er kommt aus dem Begrüßungstext „You have 4 new message(s)“.

### Umsetzung (Client 2026.11.10.4, Box)

- Box: kein Prompt, solange ein Client-Login läuft (`Session.prompt`); alle Antworten von
  `//AUTH` beginnen auf einer eigenen Zeile (`clientproto._auth`).
- Client: `//AUTHWAIT` und `//ERR auth` werden auch hinter dem Prompt einer älteren Box erkannt
  (`core.AUTH_AFTER_PROMPT`); der Sync lässt `//ERR auth` dem Core.
- Sync: wartet der Schlüssel oder ist er abgewiesen, bricht er sofort ab mit dem Grund im
  Mail-Kasten („your key … waits for the sysop of OE3GAS-1 (USER OK)“ bzw. „login with your key
  refused: other_key“); Abort wirkt beim Warten auf den Login sofort.
- Tests: `tests/test_cr106.py` (freigegeben/wartend/anderer Schlüssel Ende-zu-Ende mit Login,
  kein Prompt beim Login, ältere Box, Abort beim Warten).

## CR108 – TinyBox-Web-GUI: Seitenleiste als Buttons, Dashboard vierspaltig (✅ 10.11.2026)

### Erfassung (OE3GAS, 10.11.2026)

- Seitenleiste strukturieren: Dashboard, Messages, Monitor, Keys, Settings je ein Button;
  Rubrics mit Rahmen rundherum. Am Fuß der Spalte „TinyBox + Version“ und „by OE3GAS“.
- Breite der Fenster optimieren: nur „Connection log“ braucht annähernd die volle Breite,
  „Messages“ und „Stations (JLOG)“ kommen mit rund 40 % der bisherigen Breite aus.
- Dashboard vierspaltig: Messages | Rubrics | Stations (JLOG) | Connected; darunter
  „Connection log“ über drei Spalten, rechts daneben einspaltig „Live monitor“.

### Umsetzung (nur TinyBox-Web-GUI, `tinybox/web/app.js`, `app.css`)

- Seitenleiste: jeder Menüpunkt ein Button mit Rahmen (aktiv = schwarz), Rubrics eine
  gerahmte Gruppe mit den Rubriken darin. Fuß: „TinyBox <Version>“ / „by OE3GAS“ (darunter wie
  bisher der Hinweis auf ein neues Release); die Web-Adresse steht jetzt im Tooltip.
- Dashboard (`main.dash`): Raster mit vier Spalten im Verhältnis 1,6 : 1 : 1,2 : 1 und zwei
  gleich hohen Zeilen über die Fensterhöhe; jede Karte füllt ihre Zelle und scrollt innen. Im
  KISS-Mode steht die Kanal-Karte unter „Connected“. Zusammengeklappte Karten bleiben klein.
- Unter 1600 px Breite zwei Spalten (Connection log über beide), unter 1100 px eine.
- Geprüft im Browser (Playwright) bei 2560 und 1440 px, keine JS-Fehler; `tests/test_web.py` grün.

## CR109 – APRS-Netzgraph: Zonen statt Ringe, Vollbild, Zoom (✅ 11.11.2026)

### Erfassung (OE3GAS, 11.11.2026)

1. **Hop-Radar:** Stationen mit 2 Hops nicht auf dem Ring, sondern **zwischen** den Ringen
   „1 hop“ und „2 hops“. Den Ring größer machen, so dass er den Bereich zu 80 % füllt – jetzt
   ist links und rechts viel Platz.
2. **Map:** 4 Ringe (50, 100, 200, 400 km). Auch hier die Stationen zwischen den Ringen
   platzieren, wenn möglich entsprechend der Entfernung innerhalb des Streifens. Diagramm 80 %
   vom Platz.
3. **Force:** die Stationen mehr verteilen, auch in der Breite.
4. **Zoom:** bei vielen Stationen wird es unleserlich – in jeder Darstellung hineinzoomen können.

### Kommentar (Claude, 11.11.2026)

**Zu 1 – Zonen im Hop-Radar.** Heute ist jeder Ring eine Bahn: alle Stationen eines Hop-Werts
liegen genau auf dem Kreis (`ringR(h)`), getrennt nur über den Winkel. Bei vielen Stationen
(OK-Digis im Norden) muss der Algorithmus sie entlang des Kreises zusammenquetschen – daher die
Klumpen. Werden die Ringe zu **Zonengrenzen**, bekommt jede Station eine zweite Freiheit
(radial) und Überlappungen lassen sich deutlich besser auflösen.

- Vorschlag, für alle Zonen gleich (nicht nur 2 Hops): „heard directly“ = innere Scheibe,
  „1 hop“ = Streifen zwischen Ring 1 und 2, „2 hops“ = Streifen zwischen Ring 2 und 3. Die
  Beschriftung steht dann im Streifen, nicht am Ring.
- Position im Streifen: wie bei der Map nach Entfernung (nah = innen), ohne Locator in der
  Streifenmitte. Damit trägt der Radar zusätzlich eine grobe Entfernungsinformation.
- In der inneren Scheibe nicht bis zur Mitte gehen (z. B. ab 30 % des Radius), sonst kleben die
  direkt gehörten Stationen am eigenen Punkt.

**Zu 1/2 – 80 % der Fläche.** Die Zeichnung ist fix 720 × 470 (Seitenverhältnis ≈ 1,5 : 1) und
wird auf die Kartenbreite skaliert. Der Kreis füllt heute ≈ 93 % der **Höhe**, aber nur ≈ 61 %
der **Breite** – deshalb der Platz links und rechts. Ein Kreis, der 80 % der Breite füllt,
wäre auf einem breiten Schirm ≈ 1.100 px hoch und passt nicht mehr ins Fenster.

- Vorschlag: Zeichenfläche an das Fenster anpassen (Höhe ≈ sichtbare Fensterhöhe, Breite wie
  bisher), Kreisdurchmesser = 80 % der **kleineren** Seite. Auf breiten Schirmen bleibt trotzdem
  seitlich Platz – dort könnte die Info-Zeile (Hover: Station, Frames, km, Gerät) und die Legende
  hin, statt unter bzw. über der Zeichnung.
- Alternative: Knopf „Vollbild“ für die Zeichnung allein.
- Die Map muss kreisrund bleiben (Peilung stimmt sonst nicht); beim Radar wäre eine Ellipse
  technisch möglich, würde aber die Himmelsrichtungen verzerren – nicht empfohlen.

**Zu 2 – Streifen in der Map.** 50/100/200/400 sind Verdopplungen; gleich breite Streifen ergeben
also eine logarithmische Entfernungsskala – passt gut zu APRS (viele nahe, wenige ferne Stationen).
Innerhalb eines Streifens linear nach Entfernung.

- Die Scheibe 0–50 km ist bei uns die vollste (OE3-Umgebung). Sie sollte mehr Radius bekommen,
  z. B. 35 % des Radius für 0–50 km, die drei Streifen 50–100, 100–200, 200–400 je ≈ 22 %.
- Stationen über 400 km: in einen schmalen Randstreifen außerhalb von 400 km, oder am Rand
  festhalten und kennzeichnen. Ohne diese Regel würden einzelne ferne Stationen (S5, HG) die
  Skala sprengen.
- Feste Ringe statt der heutigen Auswahl aus 5/10/25/…/800 km. Liegt nichts über 200 km, den
  400-km-Streifen weglassen, damit kein leerer Rand entsteht.
- Das heutige Auseinanderschieben naher Stationen darf eine Station nicht aus ihrem Streifen
  schieben (radial begrenzen) – sonst stimmt die Zone nicht mehr.

**Zu 3 – Force.** Ursachen im Code: die Abstoßung ist eine feste Konstante (unabhängig von der
Zahl der Stationen), der Zug zur Mitte ist senkrecht stärker als waagrecht, und am Ende wird mit
**einem** Faktor für x und y skaliert – das Ergebnis bleibt ein runder Haufen in einer breiten
Fläche.

- Vorschlag: x und y getrennt auf die Fläche strecken (füllt die Breite), Zug zur Mitte
  schwächer und in beiden Richtungen gleich, Abstoßung und Federlänge an die Zahl der Stationen
  und die Fläche anpassen.
- Zusätzlich Kollision mit Bubble-Größe **und** Beschriftung, damit sich die Calls nicht
  überdecken.

**Zu 4 – Zoom.** Gut machbar ohne Bibliothek (der Client läuft ohne Internet): Ausschnitt der
SVG (`viewBox`) verändern.

- Bedienung: Mausrad = Zoom zum Mauszeiger, Ziehen = verschieben, Knöpfe „+ / − / Reset“ neben
  der Zeichnung. Ein Klick auf eine Station öffnet weiter ihre Seite; Ziehen darf das nicht
  auslösen.
- Wichtig: **semantischer Zoom.** Ein reines Vergrößern skaliert Bubbles und Schrift mit – die
  Überdeckungen bleiben dann genau gleich, nur größer. Deshalb beim Zoomen nur die Positionen
  auseinanderziehen, Bubble-Größe, Linienstärke und Schrift bleiben am Bildschirm gleich groß.
  Erst so wird das Gewirr beim Hineinzoomen wirklich lesbar.
- Ergänzend „Level of Detail“: in der Gesamtansicht nur die Calls großer bzw. direkt gehörter
  Stationen beschriften, beim Hineinzoomen alle.
- Zoom und Ausschnitt je Ansicht merken und über das Neuzeichnen alle 15 s erhalten (wie heute
  Modus und Filter). Beim Wechsel der Ansicht eigener Zoom je Ansicht.
- Touch (Pinch) ist möglich, aber für den Client am PC zweitrangig.

**Reihenfolge (Vorschlag):** zuerst Fläche und Zoom (bringt in allen drei Ansichten am meisten),
dann Zonen im Radar und Streifen in der Map, zuletzt das Feintuning von Force.

**Entscheidungen (OE3GAS, 11.11.2026):**

- Fläche: **Vollbild-Knopf** für die Zeichnung (statt Höhe ans Fenster anpassen).
- Radar: Zonenregel für **alle** Hop-Stufen.
- Map: Stationen über 400 km knapp außerhalb des 400-km-Rings anordnen.

- Map: Ringe bei **35 % (50 km), 57 % (100 km), 78 % (200 km), 100 % (400 km)** des
  Außenradius; innerhalb jedes Streifens linear nach Entfernung (verworfen: maßstäblich
  12,5/25/50 %, gleiche Abstände 25/50/75 %).

Damit sind alle Punkte entschieden, CR109 ist bereit zur Umsetzung.

### Umsetzung (Client 2026.11.11.4, `tbclient/web/aprsgraph.js`, `app.css`)

- **Fläche:** Zeichnung 720 × 600 statt 720 × 470 (höchstens 82 % der Fensterhöhe), äußerer
  Ring ≈ 92 % der Höhe. **Vollbild-Knopf** rechts oben an der Zeichnung: die Karte deckt das
  ganze Fenster (Browser-Vollbild), die Zeichnung wird so breit, wie der Schirm erlaubt;
  Geräte-Torte im Vollbild ausgeblendet. Beenden mit „Exit full screen“ oder Esc. Bleibt über
  das Neuzeichnen alle 15 s erhalten.
- **Zoom** in allen drei Ansichten: Mausrad = Zoom zum Mauszeiger (bis 16×), Ziehen =
  verschieben, Knöpfe + / − / 1:1, Anzeige des Faktors. Semantisch: nur die Abstände wachsen,
  Bubbles, Linien und Schrift bleiben gleich groß. Zoom je Ansicht gemerkt, übersteht das
  Neuzeichnen; Vollbild ein/aus setzt ihn zurück. Ein Klick auf eine Station öffnet ihre
  Seite, nach dem Ziehen nicht.
- **Beschriftung:** kleine Stationen (keine Digipeater), die nur über andere kommen, zeigen ihr
  Call erst ab 2× Zoom oder beim Darüberfahren.
- **Hop-Radar:** jede Hop-Stufe ist eine Zone („heard directly“ = innere Scheibe ab 30 % ihres
  Radius, „1 hop“, „2 hops“ … als Streifen; innere Scheibe etwas größer). Winkel = Peilung,
  in der Zone nah = innen (log. Skala 5–400 km), ohne Locator in der Mitte. Überlappende
  Bubbles werden auseinandergeschoben, bleiben aber in ihrer Zone. Beschriftung in der Zone.
- **Map:** feste Ringe 50/100/200/400 km bei 35/57/78/100 %, im Streifen linear. Stationen
  über 400 km knapp außerhalb des 400-km-Rings. Reicht nichts so weit, fallen die äußeren Ringe
  weg (der letzte nötige Ring liegt dann außen). Auseinanderschieben nur innerhalb des Streifens.
- **Force:** Abstoßung und Federlänge nach Fläche und Zahl der Stationen, gleicher Zug zur
  Mitte in beiden Richtungen, dann Breite und Höhe getrennt gestreckt; zum Schluss werden
  überlappende Bubbles getrennt.
- Geprüft im Browser (Playwright) mit 171 synthetischen Stationen (OE, OK, S5, HG, OM, SR, DB):
  alle drei Ansichten normal und im Vollbild, Mausrad-Zoom, Ziehen ohne Stations-Klick, Klick
  öffnet die Station, Zoom und Vollbild nach dem Neuzeichnen erhalten, Esc; keine JS-Fehler.
  `tests/test_web.py`, `tests/test_aprsstats.py` grün.
- Hinweis: über der Zeichnung zoomt das Mausrad und scrollt nicht die Seite.

## CR110 – Statusleiste: Phasen und Verkehr in Echtzeit (✅ 11.11.2026, Client 2026.11.11)

### Wunsch (OE3GAS, 11.11.2026)

Eine Echtzeit-Anzeige, welche Phase gerade läuft und welcher Verkehr zwischen Client und Box bzw.
Client und Client läuft – als Status-Chips. Entscheidungen:

- **Client↔Box, Phase:** Connecting (SABM bis UA) · Signing in (`//CLIENT` über `//AUTH` bis
  `//OK`) · Wait 4 sysop (`//AUTHWAIT`) · Disconnecting; Aktivität und Leitung wie vorgeschlagen.
- **Client↔Client:** Connecting wie oben, sonst die Vorschläge.
- **Fertig:** grün, über 5 Sekunden verblassen. **Alle Chips.**
- **Position:** ganz oben über dem Arbeitsbereich – über der Board-Zeile, über den Mail-Ordnern,
  über „TBClient – connected to …“, über der Monitor-Zeile. Im Monitor eine Zeile je Kanal.
- **Ein/aus:** Knopf in der Kopfzeile zwischen Mail und ☰, zusätzlich in den Settings. Aus = die
  Leiste verschwindet, der Inhalt rückt nach oben.

### Umsetzung

- **`tbclient/activity.py`** baut aus dem Zustand, den der Core ohnehin hat, je Kanal drei Gruppen
  (Snapshot `activity.chans`), keine Zeile mehr auf Funk:
  - **Phase:** Connecting · Connected · Signing in · Wait 4 sysop · Login refused · Client mode ·
    In board · Disconnecting · Offline/Not reached; mit einem TBClient: Probing (`//TB?` offen) ·
    Checking key · ✓ Verified by … · ✓ Known key · First contact · Other key (rot) · Wrong
    signature (rot) · Older client; sonst Terminal.
  - **Aktivität Box:** Mail-/Bulletin-Sync mit Schritt und Fortschritt (Fehler 30 s rot), History
    laden, Bild/Datei ↑ und ↓ mit Balken, Bild eines anderen, Zeilen zurückgehalten (gelb),
    Profile (`//PROF`, `//WHOIS`), Zertifikat (`//CERT?`), vertraute Boxen (`//TRUST?`),
    Sysop-Befehl (`//ADM` bis `//ADMEND`).
  - **Aktivität Client↔Client:** History compare (`//HIST` bis zur Antwort), Delivering n (noch
    nicht bestätigte Zeilen), Bild/Datei ↓, Serving (Bild, Datei, Speedtest auf Anfrage – bis
    Direwolf nichts mehr ausstehend hat), Ping, Speedtest (Ergebnis 5 s grün), Schach (am Zug),
    Heard there.
  - **Leitung:** Queue n (ausstehende Frames, ab 7 gelb), Chat via UI / I-frames, Link-Balken der
    eigenen Station, AXUDP/Telnet; mit TBClient: „Budget: answers slowed“ (CR97 hat in den letzten
    10 min eine Antwort zurückgehalten) und Qualität ↑ ↓.
- **Fertig → grün:** `activity.Tracker` merkt sich die Chips des letzten Snapshots; verschwindet
  ein Job (`fin`) bei stehender Verbindung, kommt er 5 s als `done` mit `age`. Die GUI blendet ihn
  per CSS aus (`animation-delay: -age`, so bleibt das Verblassen über neue Snapshots im Takt).
  Bricht die Verbindung ab, wird nichts grün.
- **Kopfzeile:** Direwolf/KISS/Telnet ✓/✗, TX (rot) und RX (grün) leuchten 2 s nach dem letzten
  eigenen bzw. fremden Frame oder Byte; TX auch, solange Direwolf Frames ausstehend hat.
- **GUI:** `#actbar` oben im neuen Container `#work` (Chat, Mail, Terminal/TBClient, Monitor,
  Statistik); Knopf `#btn-actbar`, Settings-Karte „Status bar“ (Leiste, Modem-Chips), gespeichert
  im Browser. Am Handy ohne Modem-Chips.
- Hooks: `sync.status.ended`, `profiles.busy_at`, `core.asking`, `core.rx_at/tx_at`,
  `peer.hist_wait/heard_wait/serving`, `peerfun.pong_at`, `budget.refused/slowed()`.
- Tests: `tests/test_activity.py`.


## CR111 – Sysop-Konsole: volle Breite, Terminal-Look (✅ 11.11.2026, Client 2026.11.11.2)

**Wunsch OE3GAS:** Die Sysop-Konsole in den Settings in voller Breite; Farbschema des Fensters
terminal-like grün auf schwarz statt schwarz auf grau.

### Umsetzung

- `tbclient/web/index.html`: Karte `#adm-card` aus dem zweispaltigen Teil (`.set-cols`) heraus,
  jetzt eigene Karte in voller Breite direkt über „Connection log“.
- `tbclient/web/app.css`: `.adm-out` schwarz mit Grün `#33ff66`, Monospace, Höhe bis 20 Zeilen;
  Eingabezeile `#adm-line` im selben Look (Cursor, Platzhalter grün).

## CR112 – Direwolf-Fork für die Statusleiste (✅ 11.11.2026, Fork 2026.11.11, Client 2026.11.11.3, Funktest offen)

### Anlass (11.11.2026)

Beim Bau der Statusleiste (CR110) fehlte Direwolf über AGW einiges: keine SABM-Versuche, TX nur geschätzt,
kein „Kanal belegt“. Claude hat aus der Arbeit hier die sinnvollen Erweiterungen des Forks
`oe3gas/direwolf-tinybox` gesammelt; OE3GAS: **alle umsetzen** – außer dem Ablehnen gesperrter Stationen im
Fork: „Die Entscheidung bleibt bei der Box. Die weiß, wen sie annimmt und wen nicht.“

### Umsetzung im Fork (Zweig `tinybox`, Fork-Version 2026.11.11, Details in seiner `TINYBOX.md`)

1. **`Q` v=3:** zusätzlich `n2`, `mod` (8/128), `k`, `n1`, `srej` (nach XID) und `load`/`load_tx` (Kanal belegt in
   der letzten Minute, gesamt und eigenes PTT). Die Verbindung wird auch beim Aufbau und Abbau gefunden:
   `state=1/5` mit `rc` = der wievielte SABM(E).
2. **AGW `E` – Ereignisse** (Umschalter wie `k`): `ptt` und `dcd` (an/aus, mit Auslastung), `link` bei jeder
   Änderung von Zustand oder Retry-Zähler (`state=4 rc=8 n2=10` = Vorwarnung vor dem Abbruch), `rx` nach jedem
   `K` mit Audiopegel, korrigierten Bits und FEC.
3. **AGW `F`:** `fork=2026.11.11 features=Q3,O,E,F,LVL,LOAD` – statt über einen Timeout zu raten.
4. Werkzeug `tinybox-tools/agw_events.py` zeigt die Ereignisse live.

Geprüft unter Linux mit zwei Instanzen über eine Audioschleife (auch der echte Client gegen den echten Fork:
„Connecting · SABME 1/10“ → „Probing“ → „Terminal“, `v2.2 · k=32`, „Channel 6 %“, TX/RX, Pegel im Monitor).
Windows-Programm mit MinGW-w64 gebaut. **Funktest mit Funk offen.**

### Umsetzung im Client

- `AgwPort` schickt nach dem Verbinden `F`, `E` und `O` (ein Original-Direwolf meldet je einmal „Unexpected
  Command“). `O` ersetzt `T`: eigene Frames (auch SABM, I, RR …) im Monitor, TX-Zeit und Modulo-128-Erkennung
  ohne Raten (Punkt 9).
- **Statusleiste:** „Connecting · SABM 3/10“, „Disconnecting · DISC 2/10“; Leitung „Retry 8/10“ (ab N2−2 rot),
  „v2.2 · k=32“, „Channel 45 %“ (ab 40 % gelb, ab 70 % rot); TX/RX in der Kopfzeile folgen PTT und DCD; der
  Modem-Chip nennt im Tooltip Fork-Version, Features und Auslastung. Ohne Events, aber mit `Q`: der Client fragt
  `Q` während des Aufbaus ab. Mit KISS/AXUDP kommen Phase und Versuche aus dem eigenen AX.25 (`KissLink.l2()`).
- **Abbruchgrund (Punkt 8, ohne Fork):** `*** DISCONNECTED RETRYOUT …` im `d` → Grund „retry-out (no answer)“,
  rote Phase „Retry-out (no answer)“. Die TinyBox wertet das schon aus (`lost=` beim Disconnect).
- **Pegel (Punkt 5):** im Monitor hinter dem Frame-Typ „lvl 45“ (gelb mit „fixed“, wenn Bits korrigiert werden
  mussten), in der APRS-Statistik bei der Station „Audio level“.
- `prcore/linkq.py` versteht `v=3` – **erst das Tinybox-Repo aktualisieren, dann die neue `direwolf.exe`**.
- Tests: `tests/test_cr111.py`.

## CR113 – LoTW als Vertrauensanker (Stufe 1 + 2 ✅ 11.11.2026, Client 2026.11.11.5 / .9, Schema 17)

### Entscheidungen (OE3GAS, 11.11.2026)

- Wer seinen Schlüssel mit einem **LoTW-Zertifikat** bestätigt, genießt in unserer Kette das **höchste
  Vertrauen**. Wer keins hat, erzeugt seinen Schlüssel wie bisher selbst (Freigabe durch den Sysop, CR93).
- Ob ein LoTW-bestätigter Schlüssel an der Heimat-BBS **ohne Sysop-Freigabe** gilt, ist **konfigurierbar,
  Vorgabe „nein“** (der Sysop gibt frei und sieht dabei „✓ LoTW“).
- Hintergrund und Abwägung (jede Box / gemeinsamer Herausgeber / LoTW) in CR94.

### Grundlagen

- LoTW-Zertifikate sind X.509, von der ARRL ausgestellt (Kette Root → Production CA → Callsign-Zertifikat).
  Das Rufzeichen steht im Subject als Attribut **AROcallsign, OID 1.3.6.1.4.1.12348.1.1** (tqsllib),
  DXCC als 1.3.6.1.4.1.12348.1.4. Fälschen hieße den CA-Schlüssel der ARRL haben; die echten Risiken sind
  eine gestohlene `.p12` (Passwort in TQSL optional) und ein Widerruf durch die ARRL, den offline niemand
  sieht → die Bestätigung gilt nur bis zum Ende des LoTW-Zertifikats.
- **Gegenzeichnen, nicht ableiten:** der Ed25519-Schlüssel entsteht wie bisher aus 32 Zufallsbytes des
  Betriebssystems (`os.urandom`, kein Seed zu wählen); der LoTW-Schlüssel unterschreibt einmal
  `TINYBOX-LOTW1|<Basis-Call>|<Ed25519-Schlüssel>|<JJJJMMTT>` (RSA-PKCS#1-v1.5/SHA-256, EC auch).
- Die ARRL-Stammzertifikate sind nicht öffentlich abrufbar: der Sysop nimmt sie aus einer `.p12` und
  vergleicht den Fingerprint (wie es auch andere Projekte machen).

### Stufe 1: Client signiert (✅ 11.11.2026)

- `prcore/lotw.py` (gemeinsam für Client und Box): `load_p12`, `sign_binding`, `verify(proof, roots)`
  (Unterschrift, Rufzeichen = Basis-Call, Gültigkeit, Kette in sich, mit `roots` bis zur ARRL),
  `describe`. Braucht `cryptography` (RSA, PKCS#12 auch mit alter 3DES/SHA1-Verschlüsselung von TQSL).
- Client: Settings-Karte **„LoTW confirmation“** – `.p12` wählen, Passwort, „Sign“. Der Nachweis
  (`data/tbclient/lotw.json`, ≈ 2 KB: Call, Schlüssel, Datum, Unterschrift, Zertifikate, gültig bis) gehört
  zum aktuellen Schlüssel; die `.p12` und das Passwort werden nur für die Unterschrift benutzt und **nicht
  gespeichert**. „Forget“ löscht den Nachweis.
- **Nur am PC selbst:** `/api/lotw` nimmt die Datei nur von 127.0.0.1/::1 an (über das LAN liefe die
  `.p12` unverschlüsselt durchs Netz); die GUI blendet das Formular sonst aus und sagt es.
- Abgelehnt: anderes Rufzeichen im Zertifikat als der Client, abgelaufenes Zertifikat, falsches Passwort,
  `.p12` ohne privaten Schlüssel (in TQSL „Save Callsign Certificate“).
- Tests `tests/test_cr113.py` (nachgebaute LoTW-Kette).

### Stufe 2: Prüfung in der Box (✅ 11.11.2026)

Frage OE3GAS: Ein schon vom Sysop freigegebener Schlüssel, später mit LoTW signiert – erkennt die Box das?
Jetzt ja: die Freigabe bleibt, der Schlüssel bekommt den Vermerk „LoTW bis …“.

- **Protokoll** (`tinybox/lotwbox.py`, Fähigkeit `LOTW`, im Client-Modus und während der Schlüssel auf den
  Sysop wartet): `//LOTW?` → `//LOTW until=JJJJ-MM-TT` | `-` | `off`; `//LOTWP i/n <Stück>` (der Nachweis als
  kompaktes JSON, base64url, Stücke ≤ 200 Zeichen, höchstens 64) → `//LOTW ok until=…` | `//LOTW err <Grund>`.
  Der Nachweis ist an den eingeloggten Schlüssel gebunden (Call und Ed25519-Schlüssel darin, mit LoTW
  unterschrieben) – für einen anderen Schlüssel taugt er nicht, das Hochladen braucht daher keine eigene
  Signatur. Über Funk einmalig ≈ 3–6 KB, danach bei jedem Login nur `//LOTW?`.
- **Client:** fragt nach dem `//OK` (und während `//AUTHWAIT`) einmal je Verbindung, schickt den Nachweis nur,
  wenn die Box ihn nicht oder älter hat; danach `//CERT?` für das Zertifikat mit Stufe. Settings-Karte:
  „✓ OE3XBS knows it“, „cannot check LoTW yet“, „did not take it: …“.
- **Box:** prüft mit `prcore.lotw.verify` gegen die **vertrauten ARRL-Zertifikate** (Tabelle `lotw_roots`):
  Konsole `LOTW`, `LOTW ADD <Datei> [Passwort]` (.p12 von TQSL – nur deren CA-Zertifikate werden übernommen –,
  .pem, .der, .cer), `LOTW DEL <Fingerprint>`; Web-GUI „Keys“, Karte „LoTW (ARRL certificates)“. Nicht über
  `//ADM` (das Passwort stünde im Klartext auf Funk). Vermerk `client_keys.lotw` (bis), in `USER`, `USER SHOW`
  und der Spalte „LoTW“ der Web-GUI; nach Ablauf verschwindet er.
- **`[client] lotw_release`** (Vorgabe `no`, wie entschieden): `yes` = ein **neuer** LoTW-bestätigter Schlüssel
  gilt sofort, der Client ist ohne `USER OK` im Client-Modus. Ein widerrufener Schlüssel bleibt widerrufen.
- **Zertifikat TBC2:** `TBC2:call:pub:issuer:until:lotw:sig`, die Stufe ist mit unterschrieben, Laufzeit
  höchstens bis zum Ende des LoTW-Zertifikats. Ohne LoTW bleibt es TBC1 – ältere Clients und Boxen kennen nur
  TBC1 und nehmen ein TBC2 nicht an (betrifft nur LoTW-bestätigte Schlüssel).
- Tests `tests/test_cr113_box.py`, Client-Teil in `tests/test_cr113.py`.

**Live über Funk (OE3GAS, 11.11.2026):** die erste Form (JSON in base64url, ganze Kette: Callsign-
Zertifikat ≈ 1,2 KB, Production CA ≈ 1,6 KB, Root CA mit 4096-Bit-Schlüssel ≈ 1,9 KB, alles doppelt kodiert)
brauchte 45 Zeilen, ≈ 9,4 KB, ≈ 75 s bei 1200 Bd – geprüft und angenommen. **Seit Client 2026.11.11.10 kompakt**
(`prcore.lotw.wire_encode`): `2.<call>.<key>.<datum>.<alg>.<sig>.<bis>.<zertifikate>`, jedes binäre Feld einmal
base64url, und **nur das Callsign-Zertifikat** – die ARRL-Zertifikate hat die Box aus `LOTW ADD`. Kann sie die
Kette damit nicht schließen, antwortet sie `//LOTW more` und der Client schickt einmal alle. Erwartet ≈ 11 Zeilen,
≈ 2,2 KB, ≈ 18 s. Die Box versteht beide Formen.

### Gerät bürgt für Gerät (offen, besprochen 11.11.2026)

Ein neues Gerät desselben Calls ist nicht automatisch LoTW-bestätigt (die Bestätigung gilt einem Schlüssel,
nicht dem Rufzeichen). Heute: auf jedem Gerät einmal signieren. Später möglich: ein LoTW-bestätigtes Gerät
unterschreibt den Schlüssel des neuen (`TINYBOX-DEV1|call|neuer Schlüssel`), Widerruf nimmt die verbürgten mit.

### Stufe 3: Anzeige (offen)

- „✓ LoTW“ bei Client↔Client (CR99) und im Chatboard bei Mitgliedern mit LoTW-Stufe.

## CR114 – APRS-Statistik: Karten aufklappbar, Netzgraph-Filter und Suche (✅ 11.11.2026)

### Erfassung (OE3GAS, 11.11.2026)

- Die Inhalte der Spalten liegen zu weit auseinander. Inhalte aufklappbar machen, alle gleich
  hoch, wenn offen, wenn nötig mit Scrollbalken.
- Was bedeutet in der Radar-Ansicht „unneeded repeats through the digipeater“? Passenden
  Begriff finden.
- In die Leiste oben zusätzlich: „via internet“, „WIDE1“, „WIDE2“, „flood (WIDE3)“ und die
  „unneeded repeats“.
- Filterfenster für die Suche nach Rufzeichen bzw. Teilen davon.
- Rote Ringe: werden sie breiter, wenn mehr Wiederholungen erkannt werden? Wenn nein, dünner
  machen.

### Antworten (Claude, 11.11.2026)

- **Bedeutung:** Der rote Ring zeigt den Anteil der Frames über diesen Digipeater, die von
  Stationen aus der Liste „Sins“ stammen, und zwar mit „too often“ (zu oft gebakt) oder
  „unchanged repeat“ (unverändert wiederholt). Gezählt werden *alle* Frames dieser Stationen
  über den Digi, nicht nur die überzähligen. Es misst also, wie viel Ballast der Digi trägt, und
  ist kein Fehler des Digis selbst.
- **Begriff:** „sin load“, passend zur Karte „Sins“ (im Tooltip: „x % of the frames through …
  come from stations in "Sins"“).
- **Ringbreite:** Die Ringe sind schon proportional (Strich 1,5 + 4 × Anteil, also ≈ 1,9 px bei
  10 % bis 5,5 px bei 100 %), daher unverändert. Dass bei uns viele dick sind, liegt an den
  OE3-Stationen, die alle 1–2 s baken.

### Umsetzung (Client 2026.11.11.6, `tbclient/web/aprsstats.js`, `aprsgraph.js`, `app.css`)

- Jede Karte der APRS-Statistik (Übersicht und Stationsseite) klappt mit Klick auf den Titel
  (oder Enter) auf und zu; der Zustand wird je Titel gemerkt (`localStorage`) und übersteht das
  Neuzeichnen alle 15 s. Offene Karten im Raster sind alle 400 px hoch, der Inhalt scrollt in
  der Karte (Tabellenkopf bleibt stehen); die inneren Scrollbereiche der Tabellen entfallen
  dort.
- Netzgraph, Zeile „Show“: zweite Knopfgruppe **via internet / WIDE1 / WIDE2 / flood (WIDE3) /
  sin load**. Die Weg-Arten zeigen nur Wege dieser Art (nach Pfad des Wegs bzw. Internet →
  Funk), „sin load“ die Wege über Digipeater mit rotem Ring (die übrigen Bubbles blass). Wirkt
  zusammen mit Paketart, Gerät und min. Frames; die Rollen-Auswahl und diese Gruppe schließen
  einander aus.
- **Suchfeld** „find call…“ daneben: Teil eines Rufzeichens, Groß/Klein egal. Gezeigt werden
  die Wege, auf denen ein Treffer liegt; Treffer fett beschriftet, die übrigen Bubbles blass;
  Anzahl der Treffer daneben. Tippen übersteht das Neuzeichnen (auch alle 15 s).
- Legende und Tooltips sagen „sin load“ statt „unneeded repeats“.
- Geprüft im Browser (Playwright) mit Testdaten aus `AprsStats` (6000 Frames, 140 Stationen):
  Karten gleich hoch, Zuklappen bleibt nach dem Neuladen, WIDE2, sin load, Suche mit
  Neuzeichnen dazwischen; keine JS-Fehler. `tests/test_web.py`, `tests/test_aprsstats.py` grün.
- Nachtrag (OE3GAS, 11.11.2026): Suche nur für den Graphen, nicht für die Tabellen. Die Zeile
  heißt jetzt „Show in graph“ statt „Show“, damit klar ist, dass Auswahl und Suche nur den
  Graphen betreffen (Client 2026.11.11.7).

## CR115 – Station sperren und entfernen: BAN, UNBAN, PURGE (✅ 11.11.2026, Schema 16)

### Wunsch und Entscheidungen (OE3GAS, 11.11.2026)

Einen User in der TinyBox komplett entfernen können. Entschieden:

- **Post und Bulletins bleiben** (gehören auch anderen, sind ggf. schon weitergeleitet).
- **Verbindungsprotokoll bleibt**, nicht anonymisiert.
- Zwei Optionen: **PURGE** = löschen **und** sperren; **BAN** = sperren, aber nicht löschen –
  „wenn er brav ist, darf er wieder mitspielen“ (**UNBAN**).

### Umsetzung

- Tabelle `banned` (Basis-Call, also alle SSIDs; seit, Grund, purged), Schema 16.
- **BAN call [Grund]:** die Station kann sich nicht mehr verbinden – Funk/KISS/AXUDP (`agw.py`
  `_on_connect`, vor allem anderen nach der Call-Prüfung, auch für Forward-Partner) und Telnet (nach
  dem Login): Text „*** CALL: no access to this TinyBox - ask the sysop.“, dann Trennen. Laufende
  Sitzungen dieses Calls enden sofort. Daten bleiben. `BAN` allein: Liste.
- **UNBAN call:** darf wieder. Nach einem PURGE beginnt er als neuer User (Schlüssel neu freigeben).
- **PURGE call [Grund]:** zeigt zuerst, was gelöscht würde (Schlüssel, Profil, Logins, Chatzeilen,
  Board-Dateien), erst `PURGE call CONFIRM [Grund]` löscht und sperrt. Bilder im Chat verschwinden
  mit den Zeilen über das normale Aufräumen (keine Referenz mehr).
- Das Sysop-Rufzeichen kann nicht gesperrt werden.
- Konsole (auch per signiertem `//ADM` aus dem Client, CR94), Web-GUI: Seite **Keys**, Karte
  „Banned stations“ (Ban, Purge mit Rückfrage samt Anzahl, Unban). Jede Aktion als Warnung im Log.
- Tests `tests/test_cr115.py`.

## CR116 – APRS-Bewegung: 3000 km/h bei einer festen iGate-Station (✅ 11.11.2026)

### Erfassung (OE3GAS, 11.11.2026)

OE3MZC-2 (fester iGate, Microsat WX3in1, sendet Objekte für Repeater/Events) zeigt auf der
Stationsseite „Moving: about 1140.2 km covered, up to 3019 km/h“ und die Rolle „mobile“. Woher
kommt die Fehlberechnung?

### Ursache (Claude)

- `AprsStats` nahm **jede** Position eines Frames als Position des Absenders, auch die von
  **Objekten und Items** (`;OE3XWR *…` – Lage des Repeaters, nicht der Station). OE3MZC-2 sendet
  zu ≈ 40 % Objekte; die „Spur“ sprang also im Takt zwischen iGate und Repeater-Standorten hin
  und her. Jeder Sprung (< 50 km, also nicht als Fehlfix verworfen) zählte als gefahrene
  Strecke, und z. B. 17 km in 20 s ergeben ≈ 3000 km/h. Da die Station dabei „mehr als 1 km
  vom ersten Punkt“ war, wurde sie zudem als „mobile“ eingestuft.
- Betroffen waren auch: Entfernung/Richtung im Kopf der Stationsseite (konnte auf ein Objekt
  zeigen), km in „Senders“, die Reichweite („Range“, auch „Farthest heard“), Lage und
  „moving“-Kennzeichen im Netzgraphen.
- Nachgestellt mit Position + Repeater-Objekt im 30-s-Takt: 497 km, 3141 km/h, „mobile“.

### Umsetzung (Client 2026.11.11.11, `prcore/aprsstats.py`)

- Neu `AprsStats._at(r)`: ein Frame zeigt nur dann den Ort des Absenders, wenn er eine Position
  hat **und kein Objekt/Item** ist. Verwendet für Senders-km, Range, Graph (Lage, „moving“) und
  die Stationsseite (letzte Position, Entfernung, Bewegung, Rolle). Die Sins-Prüfung nahm schon
  bisher nur Position/Mic-E/Wetter.
- Zusätzlich: ein Sprung zwischen zwei Positionen, der schneller als 1000 km/h wäre
  (`MAX_KMH`), gilt als Fehlfix – zählt weder zur Strecke noch zur Höchstgeschwindigkeit. Sonst
  macht ein einzelner GPS-Ausreißer auch bei echten Mobilen absurde Spitzen.
- Unverändert: Wird im Paket eine Geschwindigkeit mitgesendet (Course/Speed, Mic-E), zeigt
  „up to“ weiterhin deren Höchstwert.
- Tests: `test_objects_are_not_the_senders_position`, `test_wrong_fix_is_no_top_speed`; ganze
  Testsuite grün (1129).
- Hinweis: Die Statistik wird aus den gespeicherten Frames neu berechnet – nach dem Update
  stimmt die Anzeige auch für die bereits gehörten Frames.

## CR117 – Bild-Upload: Fortschritt und TX passen nicht zum Senden (✅ 11.11.2026, Client 2026.11.11.12, Funktest offen)

### Meldung (OE3GAS, 11.11.2026)

Beim Senden eines Bildes bewegt sich der Fortschrittsbalken gar nicht, der TX-Chip oben in der
Aktionsleiste leuchtet nicht, obwohl gesendet wird.

### Befund

- **TX:** eigene I-Frames (Fork `O`, KISS) setzten zwar die TX-Zeit, schickten aber keinen
  Snapshot an die GUI; die Abfrage der wartenden Frames (AGW `Y`, alle 3 s) auch nicht. Die GUI
  sah die TX-Zeit nur, wenn zufällig etwas anderes einen Snapshot auslöste – und löschte TX nach
  2 s wieder. Ohne Fork-PTT blieb TX während des ganzen Uploads praktisch dunkel.
- **Balken:** der Balken lebt nur von AGW `Y`. War die erste Antwort 0 (Antwort zu früh oder
  `Y` nicht nutzbar), rechnete der Client „alles drüben“ – der Balken sprang sofort ans Ende und
  stand dort minutenlang. Bewegte sich `Y` nicht, kam auch kein Snapshot.

### Umsetzung

- Ein Frame auf der Frequenz (eigen oder fremd) schickt höchstens alle 0,5 s einen Snapshot – TX/RX
  in der Kopfzeile folgen den Frames.
- Die `Y`-Abfrage meldet jede Änderung sofort (Queue-Chip, TX) und fragt jede Sekunde, solange
  Frames warten. Der Snapshot trägt `txq` (wartende Frames aller Kanäle): TX leuchtet, solange
  etwas wartet; Tooltip „n frame(s) waiting to go out“.
- Upload-Fortschritt: eine 0 am Anfang heißt nicht mehr „fertig“. Solange `Y` nichts über 0 sagt,
  zählen die eigenen I-Frames an die TinyBox (Fork `O`, KISS) als „on air“, höchstens 95 % bis
  `//IMGOK` (Wiederholungen zählen sonst doppelt). Gilt auch für Dateien im Chatboard (CR86).
  Wartende Frames gelten als lebendige Übertragung (AX.25 gibt selbst nach N2 auf).
- Client↔Client: „Serving picture to …“ zeigt jetzt Bytes und Balken aus `Y`.
- Log: „image …: n bytes handed over, m frame(s) waiting“ (INFO), jede Abfrage als DEBUG – damit
  lässt sich beim Funktest sehen, was Direwolf auf `Y` antwortet.
- Tests `tests/test_cr117.py`.

### Nachtrag (OE3GAS, 11.11.2026, Client 2026.11.11.13)

„TX reagiert zu langsam; hängt es mit den wartenden Frames zusammen, braucht es eine eigene
Anzeige. TX nur, wenn die PTT aktiv ist.“ Umgesetzt:

- **TX = PTT:** mit Direwolf-Fork (Ereignisse `E`) leuchtet TX genau solange `ptt on=1` – kein
  Nachleuchten, keine wartenden Frames. Der Snapshot trägt `ptt` (true/false, `null` = kein
  PTT-Signal bekannt). Ohne Fork (Original-Direwolf, KISS): TX 2 s nach einem eigenen Frame auf der
  Luft (Fork `O`, KISS, Original-Direwolf nur eigene UI-Frames über `T`). Übergebene Bytes zählen
  nicht mehr als TX. Tooltip sagt, woher TX kommt.
- **Queue n:** eigener Chip (gelb) in der Kopfzeile neben TX/RX, solange Frames warten oder auf
  die Bestätigung warten (AGW `Y`, Summe aller Kanäle).
- Ein eigenes Frame schickt den Snapshot sofort (fremde Frames weiter höchstens alle 0,5 s).

### Nachtrag 2 (OE3GAS, 11.11.2026, Client 2026.11.11.14)

„Die Queue zählt nicht runter: sie zeigt die Anzahl Frames, TX leuchtet, nach einiger Zeit sind die
Frames weg. Bitte mehr Echtzeit.“

**Ursache:** AGW `Y` zählt gesendete, aber noch unbestätigte Frames mit. Mit großem Fenster (v2.2,
k=32) geht ein ganzes Bild in einem Durchgang hinaus und bleibt bis zur Bestätigung „wartend“ – die
Zahl steht und fällt dann auf einmal auf 0.

**Umsetzung** (`tbclient/airq.py`): der Monitor hört beide Richtungen. Eigene I-Frames auf der Luft
(Fork `O`, KISS) schieben V(S), N(R) der I-/S-Frames der Gegenstelle schiebt V(A).

- **Queue n** = noch nicht gesendet (`Y` − auf der Luft) – zählt mit jedem eigenen Frame herunter;
  **ack m** = gesendet, Bestätigung ausständig – fällt mit jedem RR/I-Frame der Gegenstelle.
- Eine Bestätigung senkt die Zahl sofort, `Y` korrigiert bei jeder Abfrage (alle 0,5 s, solange
  etwas wartet). Wiederholungen (N(S) schon gesehen) zählen nicht. Modulo 8 und 128.
- Kopfzeile „Queue n · ack m“, ebenso der Queue-Chip im Kanal.
- Ohne Fork (Original-Direwolf) sieht der Client die eigenen I-Frames nicht: dann bleibt es bei `Y`.

## CR118 – Begrüßungsdialog der TinyBox (✅ 11.11.2026, Client 2026.11.11.15)

### Wunsch (OE3GAS, 11.11.2026)

Beim Begrüßungsdialog (Fragen nach dem Login, CR73):

1. Nach dem Namen ein kurzer Gruß „Hello [name], great to copy you!“ – dazu 7 weitere freundliche,
   kurze Floskeln, die Box wählt zufällig.
2. Beim Home-BBS dieselben Plausibilitätsprüfungen wie schon eingebaut (eingegeben wurde `jn77ss`
   und durchgelassen).
3. `S SYSOP` soll erlaubt sein und eine Mail an den Sysop erzeugen.

### Umsetzung

- `texts.PROFILE_GREET` (8 Floskeln, ASCII): „Hello {name}, great to copy you!“, „Hi {name}, nice to
  have you on frequency!“, „Welcome aboard, {name}!“, „Good to see you here, {name}!“, „Hello {name},
  you are 5/9 here!“, „Hi {name}, glad you found your way to us!“, „Nice to meet you, {name}!“,
  „Hello {name}, thanks for dropping in!“. Nur wenn ein Name angegeben wurde.
- Home-BBS (`prcore/profile.check_home`, also Box, N/NH, Client-Formular und `//PROF`): zusätzlich
  `plausible_call` aus CR92 (Präfix mit Buchstabe, Ziffern, Suffix; kein `70CM`, `QO100`) und
  **kein Locator** (`JN77SS`, `JO44KT` haben Rufzeichenform, sind aber ein Feld).
- `S SYSOP` / `SP SYSOP`: Empfänger `SYSOP` = Sysop-Rufzeichen der Box (`[station] sysop_call`),
  überall, auch in einer Liste. Mitten in den Fragen beendet `S SYSOP` den Dialog (Antworten bleiben)
  und startet die Mail. Hinweis in der Einleitung: „… /AB all of them, S SYSOP writes to the sysop.“
  Gäste dürfen das wie bisher (Post an den Sysop geht immer).
- Tests `tests/test_cr118.py`.

### Nachtrag (OE3GAS, 11.11.2026): dieselbe Prüfung beim Senden

- **Empfänger bei `S`/`SP`** (Terminal und `//SEND` des Clients, `check_send_list`): Rufzeichen
  plausibel (`prcore.profile.plausible_station` = CR92-Struktur, kein Locator; SSID egal). `SYSOP`
  bleibt erlaubt. Bulletins (`SB 70CM`, `SB ALL`) wie bisher.
- **`@` bei persönlicher Mail**, nur bei Eingabe durch einen User (Funk, AXUDP, Telnet): das erste
  Element (die Mailbox) wird genauso geprüft. Steht vorne ein Gebiet (`#NOE`, `AUT`, `EU`), bleibt es
  bei der Formprüfung. Fehler `invalid_address`.
- **Nicht geprüft:** Post von Forward-Partnern, Inbox/MQTT-Skripte, Sysop-Konsole und Web-GUI.

## CR119 – `SB` aus dem Terminalmenü für Gäste (✅ 11.11.2026)

**Wunsch (OE3GAS, 11.11.2026):** Im Terminalmenü der Box muss `SB` weg – Bulletins dürfen nur
authentifizierte User schreiben (CR92), ein Gast am Terminal kann es ohnehin nicht.

**Umsetzung:**
- Hilfe (`H`/`?`): die zwei `SB`-Zeilen (`texts.HELP_BULLETIN`) nur, wenn die Sitzung Bulletins
  schreiben darf (`rights.may_write_bulletin` – Sysop, Login mit Schlüssel); für Gäste fehlen sie.
- Usage von `S` ohne den `SB`-Teil; `SB` allein zeigt dem Gast gleich den Hinweis `NEED_LOGIN`
  („Bulletins only with the TinyBox client …“), dem Sysop `Usage: SB topic [@ area] [$BID]`.
- Der Befehl selbst war schon gesperrt (CR92), daran ändert sich nichts.
- Tests `tests/test_cr119.py`.

## CR120 – Terminal-User in der User-Ansicht kennzeichnen (offen, entschieden 11.11.2026)

### Wunsch (OE3GAS, 11.11.2026)

OE3NIX ist im Chatboard ein Terminal-User. Das soll in der User-Ansicht („In this board“) des
Clients zu sehen sein, damit die anderen wissen, dass er im Chatboard nicht alles sieht und nicht
alles schreiben kann.

### Was ein Terminal-User nicht hat (Stand CR92/CR119)

- Bilder und Dateien nur als Textzeile („[Image 5.0 KB - TinyBox client only]“), keine Reaktionen,
  Sticker, Karte, Shoutouts in der Client-Darstellung; Emojis erst ab authentifiziertem User (29.9).
- Kein Login mit Schlüssel → Gast (keine Bulletins, Post nur lokal/an den Sysop).

### Visueller Vorschlag (Claude, 11.11.2026) – Entscheidung offen

Zeile in „In this board“, Avatar und Signalbalken bleiben:

- **A – Pill neben dem Call:** `OE3NIX [terminal]`, kleine gelbe Pille. Sofort sichtbar, kurz.
- **B – Icon + Untertitel:** Terminal-Icon hinter dem Call, Untertitel „nixon · terminal: text only“.
  Sagt gleich, was es bedeutet.
- **C – gestrichelter Ring um den Avatar:** dezent, Erklärung nur im Tooltip („Terminal user, sees
  chat as text only, no pictures, files, reactions“).

In allen Varianten zusätzlich ein Tooltip mit dieser Erklärung.

### Was dafür nötig ist (Skizze, noch nicht umgesetzt)

- **TinyBox:** sie weiß es (Sitzung ohne `//CLIENT` = Terminal), sagt es den Clients aber noch nicht.
  `//WHO` (`n call[=sym]`) und das Join-Ereignis `+n call /sym` brauchen eine Kennung, z. B. ein
  Zeichen hinter dem Call (`OE3NIX=/-~t`) – nur an Clients mit neuer Cap (z. B. `TERM`), ältere
  bekommen die Zeile wie bisher. Kostet wenige Byte je Member, einmal beim Join.
- **Client:** Kennung aus `//WHO`/Join merken, in der User-Ansicht nach gewählter Variante zeigen;
  evtl. auch im Profil-Popup des Users.
- Offen: auch „Client ohne Login mit Schlüssel“ (Gast im Client, falls es das gibt) kennzeichnen?

### Entscheidung (OE3GAS, 11.11.2026)

1. **Variante A:** kleine gelbe Pille `terminal` neben dem Call in „In this board“, dazu der Tooltip
   „Terminal user, sees chat as text only, no pictures, files, reactions“.
2. **Systemmeldung beim Betreten:** kommt ein Terminal-User in den Chat, sehen alle im Board eine
   kurze Systemzeile:

   `OE3NIX enters chat. Terminal user, sees chat as text only, no pictures, files, reactions.`

   Hinweise für die Umsetzung:
   - Die Box erzeugt die Zeile (dann sehen sie auch andere Terminal-User und ältere Clients) oder
     der Client erzeugt sie aus der neuen Kennung im Join-Ereignis (kostet keine Bytes über Funk).
     Zu klären: Bytes zählen – der Client-Weg spart die Zeile auf der Frequenz; Terminal-User
     bräuchten den Hinweis über andere Terminal-User eher nicht.
   - Im Client als Systemzeile wie „joined/left“ (grau, ohne Bubble), nur einmal je Betreten,
     nicht beim Laden der History wiederholen.

## CR121 – Eine Verbindung je Rufzeichen (✅ 11.11.2026, Funktest offen)

### Vorfall (OE3GAS, 11.11.2026, 23:24)

OE3NIX war mit dem TBClient mit der Box verbunden, zusätzlich mit QTerm – beide über **denselben
Direwolf**, beide als `OE3NIX` ohne SSID. Der Connect von QTerm ging durch, danach minutenlang:

    OE3NIX → OE3GAS-1 <SABME+>  ...  OE3GAS-1 → OE3NIX <UA+>  <XID+>
    OE3NIX → OE3GAS-1 <RR 8+>        OE3GAS-1 → OE3NIX <RR 0+> <SABME+>
    OE3NIX → OE3GAS-1 <UA+>  <XID+>  ... (alle 3–4 s von vorne)

### Ursache

AX.25 kennt eine Verbindung nur am Paar eigenes Call ↔ fremdes Call; es setzt voraus, dass ein
Call mit SSID auf dem Kanal nur einmal aktiv ist, und kann Doppelte weder erkennen noch auflösen.
Für die Box waren beide Stationen **eine** Verbindung. QTerms SABME setzte sie zurück (UA, Zähler 0,
normgerecht), der TBClient bestätigte mit seinem alten Stand (`RR 8`), die Box sah einen N(R)-Fehler
und baute neu auf (`SABME`) – beide antworteten, und so weiter.

Direwolf verhindert das nicht: er führt Verbindungen je AGW-Client (`ax25_link.c`
`get_link_handle`), zwei Clients mit demselben Paar bekommen zwei Zustandsmaschinen, beide senden.

### Entscheidung (OE3GAS, 11.11.2026)

Die Box hilft nach (wirkt für alle Stationen, egal welche Software): wenn eine Station einen neuen
Connect schickt, obwohl sie schon verbunden ist, wird getrennt – „dann ist wieder Ordnung“.

### Umsetzung (TinyBox mit eigenem AX.25: KISS, AXUDP)

- `LinkCfg.refuse_reconnect` (prcore/ax25/link.py), in der TinyBox an (`adapters/kiss.py`,
  `adapters/axudp.py`), im Client aus (dort bleibt das Verhalten der Norm).
- **SABM/SABME auf eine laufende Verbindung → DM**, Verbindung und Sitzung enden (Grund
  `reconnect`, Warnung im Log: „new connect while connected - DM, session ended (station restarted,
  or the same call twice on the air?)“). DM statt DISC: DISC ist ein eigener Abbau mit UA-Antwort,
  bei zwei Stationen antworten beide; DM ist die Antwort der Norm auf ein abgewiesenes SABM.
- Das **nächste SABM ist ein frischer Connect** – neue Sitzung mit Login und Begrüßung. Die andere
  Station sendet mit altem Stand weiter, bekommt DM und ist offline.
- **N(R)-Fehler → DISC** statt Neuaufbau (Ereignis `nr_error`, Warnung im Log) – sonst stößt die Box
  bei zwei Stationen selbst die nächste Runde an.
- Preis: eine Station, die nach einem Absturz neu verbindet, braucht einen SABM mehr (erst DM, dann
  UA) und bekommt eine frische Sitzung – statt wie bisher die alte mit halb offenen Vorgängen
  (Mail-Eingabe, Bildbytes) weiterzuführen.
- **Nicht abgedeckt:** TinyBox über Direwolf (AGW) – dort beantwortet Direwolf das SABM selbst.
  Lösung dafür wäre der Fork (zweites `C` für ein schon verbundenes Paar mit `d` abweisen, verhindert
  auch den Doppel-Connect über denselben Direwolf an der Quelle) – offen, eigener Schritt.
- Für Tests mit zwei Programmen an einem PC: verschiedene SSIDs (OE3NIX, OE3NIX-1).
- Tests `tests/test_cr121.py`.

## CR122 – CQ contest: Schiffe versenken mit Amateurfunk-Touch (✅ 12.11.2026, Client 2026.11.12, Funktest offen)

### Erfassung (OE3GAS, 12.11.2026)

Variante zu CR81 („Schiffe versenken“). Spielfeld aus Großfeldern, in der Mitte das Großfeld der
Box, in der sich die Clients treffen, oder bei Direct Connect das eines der beiden Clients.
Hinter den Großfeldern verbergen sich 10 Conteststationen, 5 je Spieler, frei platziert; das
System vergibt passende Rufzeichen (DE, SP, OE, HG …). Jeder „Schuss“ ist ein `CQ <Großfeld>` –
meldet sich dort eine Station, ist sie gearbeitet, sonst ein CQ ohne Antwort. Abwechselnd; wer
zuerst alle 5 gearbeitet hat, gewinnt.

Entscheidungen nach dem Mockup (OE3GAS, 12.11.2026):
- Felder mit dem Locator beschriftet (JN88, JN89 …), keine Zeilen-/Spaltenbeschriftung.
- Spielfeld **8 × 8**.
- Rufzeichen immer 4–5 Zeichen (DL1AB, S57DT, OE3A).
- Gearbeitet grün, am Ende nicht gefundene Stationen („missed“) rosa.
- Ausbreitungshinweis standardmäßig **ein**.
- Auch **gegen die Box** spielbar – im Chat (TBClient mit der Box verbunden), nicht im Terminal.
- Rundenende als feste Regel: **ja**. Mehrere Spiele der Box gleichzeitig, eines je Client: **ja**.

### Regeln (umgesetzt)

- Brett: 8 × 8 Großfelder (2° × 1°), das Zentrum in Spalte 4, Zeile 4 von oben (8 hat keine Mitte).
  Zentrum: bei Direct Connect der Locator des Einladenden, gegen die Box der Locator der Box
  (`[station] locator` in `tinybox.conf`). Beide Seiten berechnen das Brett aus dem Zentrum.
- Rufzeichen aus einer Tabelle Land je Großfeld (40–56° N, 0–30° O; Meer zählt zur nächsten
  Küste), Felder mit mehreren Ländern losen (JN88: OE3, OE1, OK, OM); bei OE passt die Ziffer zum
  Bundesland (JN77 → OE6, JN67 → OE2, JN57 → OE7 …). Außerhalb der Tabelle: OE.
- Ausbreitungshinweis: keine Station im Feld, aber im Nachbarfeld → „QRZ? weak sigs“. Beim Start
  abwählbar. Mit Hinweis rund 23 Rufe je Spieler, ohne rund 50 (Simulation).
- Der Einladende ruft zuerst. Das Spiel endet nur nach dem Zug des Zweiten (Runde fertig): wer
  alle 5 hat, gewinnt; beide 5 → die Entfernung der gearbeiteten Stationen (km vom Zentrum)
  entscheidet, gleich → Unentschieden.
- Stille Prüfung am Ende (wie bei CR81 entschieden): Hash der Aufstellung beim Start, am Ende
  legen beide offen, der andere prüft Hash und jede Antwort („log check ok“ / „board does not match“).

### Protokoll (Zeilen `//CT …`, Fähigkeit `CT` – zwischen Clients in `//TB`, bei der Box in `//CLIENT`/`//OK`)

    //CT NEW h=<0|1> [c=<loc>]      Einladung (ohne c: der andere bestimmt das Zentrum – die Box)
    //CT OK c=<loc> h=<0|1>         angenommen
    //CT READY <hash>               Stationen gesetzt (sha256 über Aufstellung + Salz, 16 hex)
    //CT CQ <loc>                   ein Zug
    //CT R <loc> <call> <nr>        Station antwortet (5NN wird nicht gesendet)
    //CT R <loc> NIL | WEAK         keine Antwort / schwach im Nachbarfeld
    //CT END <loc:call,...> <salt>  Offenlegen am Ende
    //CT RESIGN
    //CT ERR no_locator | no_game   (nur die Box)

Ein Zug rund 15–25 Bytes; ein Spiel mit Hinweis rund 1,5 kB über Funk.

### Umsetzung

- `prcore/contest.py`: Regeln, Brett, Rufzeichen, Hash und Prüfung, einfacher Gegner (sucht
  neben „QRZ?“, meidet die Nachbarn eines „no answer“) – für Client und Box gemeinsam.
- TinyBox `tinybox/contest.py`: die Box als Gegner, ein Spiel je Rufzeichen (ohne SSID), beliebig
  viele gleichzeitig, im Speicher (einen Tag; nach einem Neustart der Box weg). Die Box setzt
  zufällig und ruft gleich nach ihrer Antwort selbst. Ohne Locator spielt sie nicht.
- TBClient `tbclient/contest.py`: ein Spiel je Gegner in den Settings (geht nach Neustart oder neuem
  Connect weiter); der Client beantwortet die CQ-Rufe des anderen selbst aus der eigenen Aufstellung.
- Web-GUI `contest.js`: Knopf „📻 CQ contest“ in der TBClient-Ansicht (Zeile und rechte Spalte, mit
  „your move“) und links unter „Station“ bzw. in „Choose a board“ gegen die TinyBox. Setzen per
  Klick oder „Random“, dann „Ready“; Ruf per Klick aufs Feld oder Eingabe `CQ KN08`. Großes Brett =
  eigene Rufe, kleines = eigene Stationen (vom Gegner gearbeitet: rot durchgestrichen), Log,
  Meldung zum letzten Ruf, Siegerkarte bzw. Niederlage mit den verpassten Stationen in Rosa.
- Bei Direct Connect braucht der Einladende einen Locator im Profil (sonst Hinweis); ältere Clients
  ohne `CT` sehen den Knopf nicht.
- Tests `tests/test_cr122.py` (Regeln, ganze Spiele, Betrugsprüfung, Box mit zwei Spielen, zwei Clients).

### Nachtrag (OE3GAS, 12.11.2026, nach dem ersten Spiel gegen die Box: „funktioniert sehr gut“)

- Client gegen Client: startet einer das Spiel, poppt beim anderen eine **Einladung** auf, die er
  annehmen oder ablehnen kann.
- **Log in zwei Spalten:** links das eigene, rechts das des Spielpartners; die Rufe als **Chips** –
  hellgrau ohne Antwort, hellbraun bei QRZ?, grün mit Häkchen bei Erfolg.
- Ein abgesetzter CQ: das Feld **blinkt leicht**, bis die Antwort kommt; bei Erfolg wird das Feld
  **3× invertiert**.

### Umsetzung Nachtrag (Client 2026.11.12.2 – 12.11.2026) ✅

- Neue Zeile `//CT NO` (abgelehnt). `//CT NEW` legt beim Eingeladenen das Spiel mit Stand „invited“
  an; erst „Accept“ schickt `//CT OK`, „Decline“ `//CT NO` – beim Einladenden verschwindet das Spiel
  mit dem Hinweis „… declined the CQ contest“. Der Einladende darf schon setzen und „Ready“ geben,
  der Kopf zeigt „waiting for … to accept“. Die Box nimmt wie bisher sofort an.
- Einladungskarte unten rechts über jeder Ansicht (Accept wechselt in den Kanal und öffnet das
  Spiel), dazu Popup bzw. „BK“ in CW nach den Einstellungen von CR85.
- Log unter den Brettern in zwei Spalten, neueste oben, der laufende Ruf als blinkender Chip
  „calling …“; Chips mit Rapport, Nummer und km.
- Blinken und Invertieren laufen über das Neuzeichnen der Ansicht hinweg weiter (Phase über die Uhr).
  Bei „reduzierte Bewegung“ im System: kein Blinken, das QSO-Feld bekommt nur einen Rahmen.
- Tests `tests/test_cr122.py`: Einladung annehmen (mit „Ready“ vor der Annahme) und ablehnen.

### Nachtrag 2 (OE3GAS, 12.11.2026): Pause-Taste und Spiel hochklappen – für Client↔Client und gegen die Box

Umsetzung (Client 2026.11.12.3) ✅:
- „⏸ Pause“ im Kopf des Spiels (nur während des Spiels): `//CT PAUSE`, bis `//CT RESUME` ruft niemand;
  der andere sieht „⏸ paused by …“. Fortsetzen („▶ Resume“) darf jede Seite – sonst hinge das Spiel,
  wenn der Pausierende geht. Die Box merkt sich die Pause nur (sie ruft ohnehin erst nach dem Client).
- „▴“ klappt das Spiel auf die Kopfzeile hoch (Stand, „your move“, Pause, Spielstand in einer Zeile),
  „▾“ wieder auf; je Gegner im Browser gemerkt.

### Nachtrag 3 (OE3GAS, 12.11.2026): im Chatboard gegen einen einzelnen Client spielen – über die Box

Bisher im Board nur gegen die Box; gegen einen Teilnehmer nur über eine Direktverbindung (⇄).
Jetzt reicht die Box die Zeilen zwischen zwei ihrer Clients weiter (Client 2026.11.12.4) ✅:

- Fähigkeit `CTR`: `//CTR <an> <Zeile>` vom Client an die Box, die Box schickt
  `//CTR <von> <Zeile>` an die neueste Sitzung dieses Rufzeichens (mit `CTR`) – „von“ ist immer das
  angemeldete Rufzeichen, niemand spielt im Namen eines anderen.
- Zentrum: das Großfeld der Box – sie setzt `c=` in das `NEW` (ein mitgeschicktes `c=` gilt nicht).
  Der Einladende bekommt das Brett mit der Antwort (`OK c=…`); bis dahin „waiting … to accept“.
- Nur `NEW` öffnet ein Paar; alle anderen Zeilen gehen nur zwischen zwei Rufzeichen mit Spiel (einen
  Tag, `NO` beendet es). Fehler an den Sender: `//CTR <an> ERR offline | no_game | no_locator | bad`
  (`offline` auch, wenn der andere einen älteren TBClient ohne `CTR` hat).
- Jede Zeile geht zweimal über Funk (zur Box, von der Box) – rund 3 kB je Spiel.
- Client: Knopf 📻 neben dem Teilnehmer in „In this board“ (neben ⇄) lädt ein; die Einladung
  erscheint beim anderen wie bei Client↔Client („through <Box>“); die Spiele stehen im Panel
  „CQ contest“ links unter Station, über dem Spiel gegen die Box. Gespeichert je Box und Gegner.
- Tests `tests/test_cr122.py`: ganzes Spiel über die Box, Fehlerfälle, älterer Client, Client-Kern.

## CR123 – Prefix raten im Chatboard (✅ 12.11.2026, Client 2026.11.12.5, Funktest offen)

### Erfassung (OE3GAS, 12.11.2026)

Die Box gibt ein fiktives Rufzeichen vor, das einer DXCC-Entität zugeordnet werden muss (ARRL-DXCC-Liste,
ITU-Präfixe; M0 ist ebenso UK wie G5). Drei Vorschläge A, B, C; jeder Spieler tippt; am Ende gewinnt, wer
die meisten richtigen Antworten hat. Die Teilnehmer im Chatboard starten gemeinsam. Beim Start einstellbar:
IARU-Regionen 1, 2, 3 (einzeln oder kombiniert), Stufe Newcomer / OM / Pro / DX-God, Anzahl der Calls.
Wer im Board ist, aber nicht spielen will, schaut zu. 30 s je Tipp mit Timer für alle; Spielzeilen
einklappbar. Regeln, Stufen und Spielliste: PLANUNG 31.

### Protokoll (Fähigkeit `PR`; Terminal-User tippen `/PR …`)

Vom Board-Mitglied an die Box, Antwort nur an den Sender:

    //PR START s=<NC|OM|PRO|GOD> r=<123> n=<1-50>   -> //PR OK START
    //PR JOIN                (oder die Chatzeile „mit“ / „join“)  -> //PR OK JOIN
    //PR A | B | C           der Tipp, geht an niemanden weiter     -> //PR OK TIP <k> <A>
    //PR STOP                nur wer gestartet hat
    //PR ERR busy|no_game|no_board|bad|no_pool|not_player|late|twice|not_starter

Die Box an alle im Board, als Systemereignis (ältere Clients zeigen den Text, Terminals lesbaren Text):

    #<n> !PR OPEN <starter> <stufe> R<regionen> <calls> <entitäten> <anmeldung s>
    #<n> !PR IN <call>                       spielt mit (Anmeldung oder ab dem nächsten Call)
    #<n> !PR GO <call> ...                   Anmeldung zu, die Spieler
    #<n> !PR Q <k>/<n> <rufzeichen> <s> <A>|<B>|<C>
    #<n> !PR TIP <call>                      hat getippt (ohne Buchstaben)
    #<n> !PR RES <k> <buchstabe> <call>=<punkte>[+] ...   + = diesmal richtig
    #<n> !PR END <call>=<punkte> ...
    #<n> !PR STOP by <call> | no_players

Ein Call mit Auflösung rund 150 Bytes über Funk (einmal als UI-Frame an alle).

### Umsetzung

- `prcore/prefixgame.py`: Spielliste laden, Pool (Stufe + Regionen, Auffüllen auf 50 aus der nächst
  schwächeren Stufe, seltenste zuerst; weniger als 50 erlaubt), Rufzeichen aus dem Muster, Frage mit zwei
  falschen Antworten aus demselben Pool, jede Entität einmal je Spiel.
- TinyBox `tinybox/prefixgame.py`: ein Spiel je Board, im Speicher. Anmeldung 60 s, der Starter spielt
  mit. 30 s je Call, die Box nimmt Tipps 5 s länger an (Laufzeit); Auflösung sobald alle Spieler im Board
  getippt haben, sonst nach 35 s; 5 s Pause bis zum nächsten Call. Wer später einsteigt, spielt ab dem
  nächsten Call; wer das Board verlässt, auf den wartet die Box nicht mehr; ist kein Spieler mehr da,
  bricht sie ab. Terminal: `/PR …` und Hilfe unter `/H`.
- TBClient `tbclient/prefixgame.py` (Zustand aus den Ereignissen), Web-GUI `prefix.js`: Knopf
  „🎯 Prefix raten“ im Kopf des Boards; Startformular (Stufe, R1–R3, Anzahl); Panel über dem Chat mit
  Rufzeichen, A/B/C, Countdown (der Client zählt selbst, rot ab 5 s), wer getippt hat, Auflösung grün/rot,
  Stand, Sieger. „Play along“ für Zuschauer. „▴“ klappt Panel und Spielzeilen im Chat ein (im Browser gemerkt).
- Tests `tests/test_cr123.py`: Liste, Stufengrößen, Auffüllen, Muster, ganzes Spiel mit Zuschauer,
  Terminal, Fehler und Stop, später Einsteigen und Gehen, Client-Zustand aus einem echten Spiel.

### Fehler (OE3GAS, 12.11.2026, Spiel gegen die TinyBox): „die Hints passen nicht“ – behoben (Client 2026.11.12.5) ✅

- Ursache: Auch eine schon **gearbeitete** Station gab im Nachbarfeld weiter „QRZ? weak sigs“. Nach
  4 von 5 Stationen war fast jedes Feld rundherum gelb – nach den Regeln richtig, beim Spielen aber
  irreführend (der Hinweis soll zur nächsten Station führen).
- Jetzt: Hinweis nur noch für Stationen, die der Rufende **noch nicht** gearbeitet hat. Gilt für die
  Antwort (Client und Box) und für die Prüfung am Ende (in der Reihenfolge des Spiels).
- Gelbe Felder aus der Zeit vor einem QSO bleiben stehen (sie stimmten, als gerufen wurde).
- Beide Seiten brauchen den neuen Stand – mit einem älteren Gegner meldet die Prüfung am Ende sonst
  „board does not match“.

## CR124 – Prefix raten: deutsche Oberfläche, Kreis-Timer, Einladung, Start vorzeitig (✅ 13.11.2026, Client 2026.11.13)

### Erfassung (OE3GAS, 12.11.2026, nach dem ersten Test von CR123)

1. **Oberfläche auf Deutsch** (Panel, Formular, Spielzeilen im Chat, Fehlertexte).
2. **Timer als Kreis:** eine Kreisfläche, die mit der Zeit kleiner wird (Tortenstück schrumpft im
   Uhrzeigersinn), in der Mitte die Sekunden. Für die Anmeldung und für die Tipp-Abgabe.
3. **Anmeldung vorzeitig beenden:** Der Starter kann die Anmeldezeit übergehen – sind z.B. nach
   25 s alle angemeldet, startet er das Spiel sofort.
4. **Startformular:** statt „R1 R2 R3“ die Regionen ausgeschrieben, statt „Calls“ die Frage
   „Wie viele Calls sollen gefragt werden?“.
5. **Einladung attraktiver** (Bild 2: „OE3GAS starts a game. Who plays along?“ mit einem Knopf).
6. **Gewählter Tipp mit Hintergrundfarbe**, nicht nur mit Rahmen.

### Vorschlag

**Texte (Client):**

| bisher | neu |
|---|---|
| Stage | Stufe |
| R1 / R2 / R3 | IARU-Region 1 / 2 / 3 (gewünscht war „Zone“ – siehe Hinweis) |
| Calls | Wie viele Calls sollen gefragt werden? |
| Start | Spiel starten |
| Play along | Ich spiele mit! |
| Play along (from the next call) | Ab dem nächsten Call mitspielen |
| signup | Anmeldung |
| tipped: … / nobody has tipped yet | Getippt: … / Noch kein Tipp |
| Right! / A was right. | Richtig! / Richtig war A. |
| Called off – nobody plays. | Abgebrochen – niemand spielt mit. |
| Nobody scored. / 🏆 OE3GAS | Keine Punkte vergeben. / 🏆 Sieger: OE3GAS |
| New game / Stop | Neues Spiel / Abbrechen |
| 10 calls · 261 entities | 10 Calls · 261 Entitäten |
| Spielzeilen im Chat („… plays along“, „… has tipped“ …) | „… spielt mit“, „… hat getippt“, „Richtig war A“, „Spielende“ |

Hinweis „Zone“: Die Regionen der IARU heißen Region 1–3; „Zone“ sind die ITU- und CQ-Zonen
(1–90 bzw. 1–40). Vorschlag daher „IARU-Region 1“; Entscheidung bei Gerhard.
Die Texte der Box für Terminal-User bleiben englisch wie der Rest der Box.

**Kreis-Timer:** rund 56 px, Fläche als `conic-gradient` (Rest der Zeit gefüllt), Sekunden mittig.
Farbe: blau, ab 10 s orange, ab 5 s rot. Bei der Anmeldung kleiner im Kopf der Einladung, bei der
Frage neben dem Rufzeichen. Läuft weiter ohne Funkverkehr (der Client zählt selbst, wie bisher).

**Anmeldung vorzeitig beenden:** Der Starter sieht in der Einladung „Alle da? Jetzt starten“ (ab
einem Mitspieler außer ihm aktiv, allein auch möglich). Protokoll neu: `//PR GO` (nur der Starter,
sonst `//PR ERR not_starter`; außerhalb der Anmeldung `//PR ERR not_open`); die Box schließt die
Anmeldung sofort und sendet wie bisher `!PR GO …`. Terminal: `/PR GO`.

**Einladung (Vorschläge):**

- Eigene Karte statt Textzeile: farbiger Rand und leicht getönter Hintergrund, großes 🎯.
- Überschrift „OE3GAS fordert euch heraus!“, darunter „Welches Land steckt hinter dem Rufzeichen?“.
- Die Einstellungen als Chips: Stufe, Regionen, Anzahl Calls, Entitäten.
- Kreis-Timer der Anmeldung rechts oben.
- Mitspieler als Chips mit Häkchen („Schon dabei: OE3GAS ✓ OE3TEC ✓“), neue kommen mit kurzer
  Einblend-Animation.
- Großer Knopf „Ich spiele mit!“ (leicht pulsierend, solange man nicht dabei ist); danach
  „Du bist dabei ✓ – gleich geht's los“.
- Für den Starter zusätzlich „Alle da? Jetzt starten“.
- Optional: Ist man gerade nicht im Chat-Fenster, zeigt der Board-Eintrag links ein 🎯-Abzeichen,
  solange die Anmeldung läuft.

**Gewählter Tipp:** Hintergrund in Akzentfarbe (hell getönt) plus Rahmen, „Dein Tipp“ klein darunter;
nach der Auflösung wie bisher grün (richtig) bzw. rot (falsch).

### Nachtrag (OE3GAS, 13.11.2026)

7. **Weltkarte als Hintergrund** (Amateurfunk-Weltkarte mit DXCC-Präfixen und CQ-Zonen, von Gerhard
   geliefert): Teil des Spiels, wird mit dem Client ausgeliefert (`tbclient/web/prefix-map.jpg`,
   Titelzeile abgeschnitten, 106 kB), nicht über Funk. Nur Hintergrund, keine Infoquelle: im
   Setup und in der Einladung rechts sichtbar (links abgedeckt für die Schrift, bei genau einer
   Region der passende Ausschnitt), im Spiel stark gedämpft und unscharf.
   Entschieden: „IARU-Region“ (nicht „Zone“), die Vorschläge zur Einladung, Ring-Timer mit den
   Sekunden in einem weißen Kreis; vier Screens wie im Entwurf (Setup, Einladung Mitspieler,
   Einladung Einladender, Spiel).

### Umsetzung (Client 2026.11.13)

- `tbclient/web/prefix.js` neu: Setup-Karte (Stufe als Leiste mit Erklärung, Regionen als Kacheln
  mit Namen, Anzahl mit −/+ und geschätzter Dauer, „Einladung senden“; die Auswahl bleibt beim
  Neuzeichnen erhalten), Einladung für Mitspieler („… fordert euch heraus!“, Chips, „Schon dabei“,
  pulsierender Knopf „Ich spiele mit!“, danach „Du bist dabei ✓“), Einladung für den Starter („Alle
  da? Jetzt starten“ bzw. „Allein starten“, „Abbrechen“), Spiel-Screen (Rufzeichen groß, Ring-Timer,
  A/B/C, „Dein Tipp“ farbig hinterlegt, Getippt/warten auf, Stand), Ergebnis („🏆 Sieger“), deutsche
  Spielzeilen im Chat, eingeklappt eine Zeile mit kleinem Ring. Ring: blau, ab 10 s orange, ab 5 s rot.
- `tbclient/prefixgame.py`: Aktion `go`; die Anmeldedauer aus `PR OPEN` für den Ring.
- TinyBox: `//PR GO` bzw. `/PR GO` – nur der Starter, nur in der Anmeldung (sonst `not_starter`,
  `not_open`); schließt die Anmeldung sofort.
- Die News-Zeile zu Prefix raten fehlte in 2026.11.12.5 (vom CR122-Fix mit derselben Version
  überschrieben) – steht jetzt in `news/2026.11.13.txt`.
- Herkunft der Karte: von OE3GAS selbst erstellt (mit KI), keine fremden Rechte (13.11.2026).

## CR125 – Mehrere Sysops (bis zu 5) (offen)

**Wunsch (OE3GAS, 12.11.2026):** Eine TinyBox soll mehr als einen Sysop haben können, höchstens 5.
Angelegt werden sie einfach in der `tinybox.conf`, ohne Konsolenbefehl und ohne Web-GUI.

**Ist-Stand:** `[station] sysop_call` nimmt genau ein Rufzeichen (`config.py`, `_require_call`), eine
Liste wird als ungültiges Rufzeichen abgelehnt. `service.is_sysop_call()` vergleicht das Basisrufzeichen,
jede SSID ist Sysop. An vielen Stellen wird `cfg.station.sysop_call` direkt als *der* Sysop verwendet:
Systemnachrichten an den Sysop (`service.py`, `forward.py`), Identität von Sysop-Konsole und
Web-GUI (`adapters/sysop.py`, `adapters/web.py`), `SHUTDOWN`/`RESTART` (`shutdown.py`), Texte an
User (`session.py`: Gast gehalten, Third-Party aus), Inbox-Absender, Logkopf, Stationsprofil.

**Vorschlag:**

- `sysop_call` nimmt eine Liste, getrennt durch Komma und/oder Leerzeichen:
  `sysop_call = OE3GAS, OE3TEC`. Ein einzelnes Rufzeichen bleibt gültig (abwärtskompatibel).
- Höchstens 5 Rufzeichen; mehr → `ConfigError` beim Start. Jedes muss ein gültiges Rufzeichen sein,
  doppelte (gleiches Basisrufzeichen) werden einmal gezählt bzw. mit Warnung entfernt.
- **Alle Sysops sind gleich**, es gibt keinen Haupt-Sysop (OE3GAS, 12.11.2026). Wo der Code heute
  `cfg.station.sysop_call` als einzelnes Rufzeichen verwendet, kommt statt eines Rufzeichens die
  Adresse `SYSOP` bzw. die Liste aller Sysops:
  - **Post an den Sysop** (Systemnachrichten der Box wie gehaltene Post, Sysop-Rufzeichen auf Funk,
    Forward-Fehler, Schlüssel wartet auf Freigabe; und `S SYSOP` von Usern) hat als Empfänger
    **`SYSOP`**, nicht das Rufzeichen eines Sysops. Jeder Sysop sieht diese Post (`list_for`/`read`
    mit Sysop-Rechten), egal mit welchem Rufzeichen und über welchen Zugang. `check_send` setzt
    `SYSOP` nicht mehr in `sysop_call` um; `SYSOP` ist als Empfänger erlaubt, obwohl es kein
    gültiges Rufzeichen ist, und bleibt lokal (kein Forwarding, kein `@`).
  - Absender bzw. „by“ bei lokalen Sysop-Quellen (Konsole, Web-GUI, `SHUTDOWN`/`RESTART`,
    Inbox ohne Absender): `SYSOP`.
  - Texte an User (Gast gehalten, Third-Party aus), Logkopf, `STATUS`/`INFO`, Stationsprofil,
    Web-GUI: alle Sysop-Rufzeichen bzw. „the sysop“.
- Freigabe der Schlüssel (CR93) für weitere Sysops: die bestehende Prozedur genügt (`USER OK`,
  Web-GUI „Keys“), nichts Neues nötig.
- `is_sysop_call()` prüft gegen alle Einträge (jede SSID). Damit gelten für alle Sysops dieselben
  Rechte wie heute: Telnet, AXUDP, Client über Funk mit Schlüssel und signierten `//ADM`-Befehlen
  (CR94), Rubriken, `WARN`, brocast-Quellen. Über Funk per Terminal bleibt jeder Sysop Gast.
- `RELOAD` (CR82) übernimmt eine geänderte Liste ohne Neustart.
- `tinybox.conf.example`: Kommentar zur Liste und zur Höchstzahl.

### Rechte – gelten für jeden Sysop der Liste

Gerhard (12.11.2026): alle Sysop-Rechte für alle Sysops mitbedenken, z. B. das erweiterte
Funktionsschema beim Connect über den TBClient. Bestand im Code: Fast alle Rechte hängen schon an
`service.is_sysop_call()` bzw. an `clientproto.admin_allowed()`, das wiederum `is_sysop_call()`
prüft. Mit der Liste in `is_sysop_call()` bekommen sie alle Sysops automatisch; bei der Umsetzung
trotzdem jede Stelle prüfen und mit einem **zweiten Sysop-Rufzeichen testen**:

| Recht | Stelle heute | mit CR125 |
|-------|--------------|-----------|
| TBClient: erweitertes Schema – Cap `ADM`, Sysop-Konsole im Client, „Sysop ▾“ im Leser (CR94, CR21) | `clientproto.admin_allowed()`, Caps-Abgleich (`caps.discard("ADM")`) | jeder Sysop mit seinem in dieser Box freigegebenen Schlüssel |
| TBClient: schreibt als Sysop (Rolle `sysop`, Origin `sysop`, Bulletin an `WARN` → Warnseite, freie Rubriken) | `clientsync.py` (`admin_allowed`) | jeder Sysop |
| Sysop-Sitzung über Telnet, AXUDP (Prompt `TinyBox SYSOP`, `HELP_SYSOP`, Sysop-Befehle) | `telnet.py`, `axudp.py` (`_sysop_allowed`) | jedes Rufzeichen der Liste, jede SSID |
| Funk/Terminal: Sysop-Rufzeichen ist Gast, Meldung „Sysop-Rufzeichen auf Funk“ | `agw.py` (`_sysop_allowed`, `sysop_call_on_air`) | gilt für jedes Rufzeichen der Liste; Meldung an `SYSOP` |
| Rollen und Rechte (Bulletins löschen, brocast-Seiten/`WARN`, Rubriken frei, kein Gast-Halt) | `rights.py`, `service.py` (`is_sysop_call` bei Rolle/Third-Party) | jeder Sysop |
| Mehrfach-Verbindungen je Rufzeichen (Ausnahme für den Sysop) | `session.py` (`MAX_PER_CALL`, `session.sysop`) | jeder Sysop |
| Web-GUI „Keys“: Kennzeichen „sysop“ | `keys.py` | bei jedem Sysop |
| Third-Party-Sperre: Post von/an den Sysop erlaubt | `service.check_send` | Post von jedem Sysop und an `SYSOP` erlaubt |

Zusätzlich:

- **Wer war es?** Befehle eines Sysops über den Client (`//ADM`) laufen heute in einer
  `SysopConsole`, die `cfg.station.sysop_call` als „by“ nimmt (`SHUTDOWN`/`RESTART`, `MOVE`/`COPY`/
  `KILL`). Künftig das Rufzeichen des angemeldeten Sysops eintragen, damit Log, Systemmeldung und
  „(copied from …)“ zeigen, welcher Sysop es war. Lokal (Konsole, Web-GUI) bleibt es `SYSOP`.
- **Client:** braucht keine Änderung – er schaltet die Sysop-Funktionen nur nach dem `ADM`-Cap der
  Box frei, nicht nach einem Rufzeichen-Vergleich. Bei der Umsetzung gegenprüfen.
- Andere Dienste (brocastd, kisshub, dxfeed) kennen kein Sysop-Rufzeichen; nichts zu tun.

### Entschieden (OE3GAS, 12.11.2026)

- Alle Sysops gleich, kein Haupt-Sysop, alle Rechte für alle – auch das erweiterte Schema im TBClient.
- Alle Nachrichten an den Sysop gehen an alle Sysops, Empfänger `SYSOP`.
- Schlüssel: bestehende Freigabe-Prozedur.
- Testbed (`tbtest/bed.py`): braucht keine Änderung, ein einzelnes Rufzeichen bleibt gültig.

### Offen

- Lesestatus der `SYSOP`-Post: gemeinsam (einer liest → für alle gelesen) oder je Sysop? Vorschlag:
  gemeinsam, wie ein geteiltes Postfach; Löschen wirkt für alle.
- Bestehende Post an das Rufzeichen des bisherigen Sysops bleibt, wie sie ist (keine Migration),
  oder auf `SYSOP` umschreiben? Vorschlag: bleibt.

## CR126 – Prefix raten: Antwortzeit, Ergebnisse, Spielerliste; Scores aller Spiele löschen (✅ 13.11.2026, Client 2026.11.13.3)

### Erfassung (OE3GAS, 13.11.2026)

1. Antwortzeit beim Start einstellbar, 5 bis 30 Sekunden.
2. Nach jedem Call eine Ergebnisübersicht: Call – richtige Tipps gesamt in diesem Call.
3. Am Ende eines Spiels eine Übersicht der Ergebnisse aller Teilnehmer, für alle sichtbar.
4. Gespeicherte Spielerliste auf der TinyBox: Anzahl gespielter Spiele, richtige Tipps gegen alle Tipps.
5. Der Sysop kann Scores und Spielerlisten löschen – so gebaut, dass auch die anderen Spiele
   (Schach, CQ Contest und kommende) dazugehören.

### Vorschlag

**1 Antwortzeit:** im Setup eine Zeile „Wie lange darf getippt werden?“ mit −/+ in 5-s-Schritten
(5, 10 … 30, Standard 30); die geschätzte Spieldauer rechnet sie mit. Protokoll: `//PR START … t=<5-30>`;
`!PR OPEN` bekommt die Zeit als 7. Wert, `!PR Q` trägt sie schon. Die Box nimmt weiter 5 s länger an.

**2 Nach jedem Call:** In der Auflösung „VP2EAU = Anguilla · 2 von 3 richtig“ und die Chips mit dem Stand;
wer richtig lag: grüner Chip mit Häkchen („✓ OE3GAS 3“). Keine eigene Zeile „Richtig: … / daneben: …“
(entschieden 13.11.2026). Protokoll: `!PR RES <k> <buchstabe> <x>/<y> …`
(y = Spieler, die gefragt waren, auch ohne Tipp).

**3 Spielende:** Panel für alle im Board (Entwurf `prefix_raten_spielende.png`): Sieger mit Punkten,
Summe (Spieler, Tipps, richtig, Quote); Tabelle Teilnehmer (Platz mit Medaille, richtig/gefragt, Quote
als Balken, „insgesamt“ = alle Spiele dieses Spielers auf der Box); Tabelle der Calls (#, Call, Lösung,
richtig x/y, 0 rot). Knöpfe „Neues Spiel“ und „Bestenliste“. Protokoll: `!PR END <call>=<richtig>/<gefragt> …`
und danach `!PR ALL <call>=<spiele>/<quote %> …` aus der Spielerliste. Die Liste der Calls baut der Client
aus den `RES`-Zeilen, die er gesehen hat (wer später kam, sieht die Calls ab seinem Einstieg).

**4 Spielerliste auf der Box:** neue Tabelle für alle Spiele

    game_stats(game, call, games, wins, hits, tries, asked, last)   Schlüssel (game, call)
    game = "prefix" | "chess" | "contest" | …   call ohne SSID

Prefix raten zählt am Spielende je Spieler: games +1, wins +1 für den/die Sieger (nur mit Punkten),
hits = richtige Tipps, tries = abgegebene Tipps, asked = Calls, bei denen er gefragt war. Abgebrochene
Spiele zählen nicht.

**Leaderboards (entschieden 13.11.2026, Entwurf `leaderboards.png`)** – für alle, sortiert nach Quote,
mit Anzahl der Spiele:

- **LB1 – Leaderboard der Box:** alle Spiele der Box in Sektionen, je Spiel die Top 3 (Call, Spiele,
  Quote als Balken), Kopf der Sektion: Spiele gesamt, Anzahl Spieler, was die Quote bedeutet;
  „Alle anzeigen →“ öffnet LB2.
- **LB2 – Leaderboard je Spiel:** Top 10 mit Spiele und Quote; die eigene Zeile hervorgehoben (ist man
  nicht in den Top 10, steht die eigene Zeile darunter). Prefix raten zusätzlich „richtig / Tipps“.
- Quote: Prefix raten = richtige Tipps / Tipps; CQ Contest = gewonnene / gespielte Spiele;
  Schach = Punkte (Sieg 1, Remis ½) / Spiele.
- Abfrage: `//GAMES TOP` (LB1) und `//GAMES TOP <spiel>` (LB2), Antwort nur an den Fragenden;
  Client: Knopf „Bestenliste“ (im Board-Kopf und am Spielende), Terminal `/TOP` bzw. `/TOP <spiel>`.
- Jeder erscheint ab dem 1. Spiel (entschieden 13.11.2026).

**5 Sysop löscht:** Konsolenbefehl der Box, auch über die Fernverwaltung im TBClient (`//ADM`):

    GAMES                         Übersicht: je Spiel Anzahl Spieler und Spiele
    GAMES CLEAR <spiel|ALL>       Liste eines Spiels bzw. aller Spiele löschen
    GAMES CLEAR <spiel|ALL> <call>  nur diesen Spieler

Mit Rückfrage („wirklich? J/N“) und Eintrag im Log. Andere Spiele schreiben über dieselbe Funktion
`games.record(game, call, …)` in die Tabelle.

### Offen

- Entschieden: „nach jeder Runde“ = nach jedem Call.
- Entschieden: Tabelle, Leaderboards und Löschen jetzt für alle Spiele; dass Schach und CQ Contest ihre
  Ergebnisse an die Box melden (die Box sieht sie heute nicht – Schach direkt zwischen den Clients, CQ
  Contest nur weitergereicht; wäre Selbstauskunft), kommt als eigener CR. Bis dahin zeigen deren
  Sektionen „noch keine Spiele“.
- Entschieden: Leaderboards ab dem 1. Spiel. Das Melden von Schach und CQ Contest: CR127.

### Umsetzung (13.11.2026, Client 2026.11.13.3)

- TinyBox `games.py` (neu): Tabelle `game_stats` (game, call ohne SSID, games, wins, draws, hits, tries,
  asked, last) und `game_totals`; Quote je Spiel, Ränge, `//GAMES TOP [spiel]` (Antwort `//GAMES G/R/ME/END`),
  Terminal `/TOP [spiel]` im Board, Sysop-Konsole `GAMES` und `GAMES CLEAR <spiel|ALL> [call]` – zeigt
  zuerst, löscht mit `CONFIRM`; auch über `//ADM`. PURGE löscht die Spielstände des Calls mit.
- `prefixgame.py`: `t=5..30` (Standard 30), `PR OPEN` mit der Tippzeit, `PR RES … x/y`,
  `PR END call=richtig/gefragt`, danach `PR ALL call=spiele/quote`; ein fertiges Spiel geht in die
  Spielstände (abgebrochene nicht). Quote Prefix raten = richtige / abgegebene Tipps.
- Client: Setup mit „Wie lange darf getippt werden?“ (−/+ in 5-s-Schritten) und Spieldauer; nach jedem
  Call „= Lösung“ und „x von y richtig“, Chips der Richtigen grün mit ✓; Übersicht am Spielende
  (Sieger, Summe, Teilnehmer mit Quote und „insgesamt“, die Calls); Knopf „🏆 Bestenliste“ im Board-Kopf
  und am Spielende: LB1 (alle Spiele, Top 3) und LB2 (je Spiel Top 10, eigene Zeile darunter).
- Tests `tests/test_cr126.py`.

## CR127 – Spielergebnisse signiert an die Box melden (Schach, CQ Contest) (✅ 13.11.2026, Client 2026.11.13.5)

### Erfassung (OE3GAS, 13.11.2026)

Schach und CQ Contest laufen zwischen den Clients; die Box sieht die Ergebnisse nicht. Für die
Leaderboards (CR126) melden die Clients die Ergebnisse an die Box – **signiert**, damit keine
Scherz-Ergebnisse in die Liste kommen.

### Vorschlag

**Grundsatz: Ein Ergebnis zählt nur, wenn beide Spieler es melden – jeder signiert mit seinem
eigenen Schlüssel, und beide Meldungen stimmen überein.** Ein Spieler allein kann sich so keinen Sieg
eintragen, und niemand kann im Namen eines anderen melden.

**Signatur:** Die Meldung ist ein Befehl wie `//SEND` oder `//PROF`, signiert mit dem Geräteschlüssel
aus CR93 (`auth.command_message`: Box, Call, Nonce der Sitzung, Zähler, Zeile). Die Box nimmt sie nur
von einem Call mit freigegebenem Schlüssel an (aktiv an dieser Box oder per Zertifikat einer
vertrauten Box). Ohne Schlüssel: kein Eintrag, der Client sagt warum.

**Spiel-ID und Verlauf:** Beim Spielstart erzeugt der Einladende eine Zufalls-ID (16 Hex) und schickt
sie mit der Einladung; beide Clients merken sie. Am Ende bildet jeder Client einen Hash über den
Spielverlauf (Schach: die Züge, CQ Contest: Aufstellung und Schüsse; SHA-256, 16 Hex). Beide Clients
haben denselben Verlauf, also denselben Hash – ein ausgedachtes Spiel passt nicht dazu.

**Protokoll (Fähigkeit `GAME`):**

    //GAME RES g=<chess|contest> id=<16 hex> vs=<call> r=<win|loss|draw> h=<16 hex> n=<züge> t=<ende unix> c=<n> sig=..
    -> //GAME OK <id> pending      erste Meldung, wartet auf den Gegner
    -> //GAME OK <id> counted      beide Meldungen passen: eingetragen
    -> //GAME ERR <id> nokey|unsigned|mismatch|dup|old|self|limit|bad

**Abgleich auf der Box** (neue Tabelle `game_reports`, Schlüssel id + call):

- Die zweite Meldung zählt, wenn: gleiches Spiel, gleiche ID, die Calls über Kreuz (A vs B / B vs A),
  Ergebnis passend (win ↔ loss, draw ↔ draw), gleicher Hash, gleiche Zügezahl, Spielende höchstens
  10 min auseinander. Dann schreibt die Box beide in `game_stats` (CR126): games +1, wins bzw. Punkte
  (Schach: Sieg 1, Remis ½).
- Passt es nicht: beide Meldungen „strittig“, nichts wird gezählt, Eintrag im Log; der Sysop sieht
  strittige Spiele bei `GAMES`.
- Meldet der Gegner nicht innerhalb von 7 Tagen: die Meldung verfällt, nichts wird gezählt.
- Meldungen älter als 7 Tage nimmt die Box nicht an (`old`), dieselbe ID kein zweites Mal (`dup`),
  gegen sich selbst nicht (`self`, auch nicht mit anderer SSID).
- Abgebrochene Spiele werden nicht gemeldet.

**Client:**

- Fertige Spiele kommen in eine Warteschlange (bleibt über Neustarts) und gehen beim nächsten
  Login an die Heimat-Box; danach steht am Spiel „Ergebnis gemeldet ✓“, „wartet auf den Gegner“
  oder „nicht gezählt (…)“.
- Schach direkt über Funk (ohne Box) wird so später nachgemeldet; CQ Contest über die Box
  (`//CTR`) genauso.

### Grenzen

- Zwei Spieler, die sich absprechen, können gemeinsam ein ausgedachtes Spiel melden – beide müssten
  dafür ihren eigenen Schlüssel einsetzen. Begrenzt auf höchstens 50 gezählte Spiele je Paar und Tag.
- Beide müssen an **dieselbe** Box melden. Haben die Spieler verschiedene Heimat-Boxen, zählt das Spiel
  dort nicht (später ggf. über Forwarding).

### Entschieden (OE3GAS, 13.11.2026)

- Höchstens 50 gezählte Spiele je Spielerpaar und Tag (UTC); weitere Meldungen: `//GAME ERR <id> limit`.
- Spiele zwischen Spielern verschiedener Heimat-Boxen zählen vorerst nicht (später ggf. über Forwarding).

### Nachtrag 4 (OE3GAS, 13.11.2026): Ansicht – umgesetzt (Client 2026.11.13.2) ✅

- Setzen: die Knöpfe rechts neben dem Brett – „Place your stations by tapping squares or: [Random]“,
  darunter „Start game“ (statt „Ready“) und „Cancel game“ (statt „Give up“).
- Im Spiel beide Bretter gleich groß.
- Meldung zum letzten Ruf: „no answer“ mit 😢, QSO mit 😍.
- Ende: verloren mit 😢, gewonnen mit 🎆 (Unentschieden 🤝).
- Nachtrag (OE3GAS, 13.11.2026): die Ankündigung zum Spielstart („New CQ contest …“) blau hinterlegt,
  damit sie sich vom Chat abhebt – Client 2026.11.13.4 ✅

### Umsetzung (13.11.2026, Client 2026.11.13.5)

- TinyBox `gamereport.py` (neu), Tabelle `game_reports`: `//GAME RES` gehört zu den signierten Befehlen
  (`clientproto.critical`), ohne Signatur `//GAME ERR <id> unsigned`, ohne Login mit Schlüssel `nokey`.
  Abgleich wie oben beschrieben, dann `games.record()` (Schach: Remis in `draws`). `//GAME ST <id>` für den
  Stand. Strittige Meldungen zeigt `GAMES` an der Konsole. Fähigkeit `GAME`.
- TBClient `gamereport.py` (neu): Spiel-ID beim Einladen (`//CHESS NEW w id=…`, `//CT NEW … id=…`, auch über
  `//CTR`), Hash über den Verlauf (Schach: Züge; CQ Contest: Zusagen der Aufstellungen und die Calls beider
  Seiten, der Einladende zuerst), Warteschlange in den Einstellungen, Versand signiert beim Login an der
  Heimat-Box, offene Meldungen werden bei jedem Login nachgefragt. Ergebnis als Hinweis im Peer-Chat
  („📊 …“), Summe in der Bestenliste („Deine Schach- und Contest-Ergebnisse …“).
- Nicht gemeldet: Spiele gegen die TinyBox selbst, Spiele mit einem älteren Client ohne Spiel-ID,
  abgebrochene Spiele.
- Tests `tests/test_cr127.py`.

## CR128 – Spiele: keine Terminal-User, Zuschauer sehen nur „Spiel läuft“ (offen)

### Erfassung (OE3GAS, 13.11.2026)

- Keine Spiele für Terminal-User (gilt für alle Spiele, PLANUNG 33).
- Zuschauer sehen nur, **dass** ein Spiel läuft – keine Fragen, Antworten, Auflösungen oder Stände.
  „Wer nicht mitspielt, interessiert sich eh nicht für die Ergebnisse.“ Gilt für Prefix raten (heute
  sehen Zuschauer alles, CR123) und das geplante Elmer Quiz.

### Vorschlag (noch nicht entschieden)

- **Box:** `/PR …` von Terminal-Usern mit Hinweis ablehnen („Spiele nur mit TBClient“). Terminals bekommen
  keine `!PR`-Ereignisse mehr als Text, nur eine Zeile beim Start („Prefix raten läuft“) und eine beim Ende.
- **Client:** Für Zuschauer statt Panel und Spielzeilen nur ein Hinweis „🎯 Prefix raten läuft (x Spieler)“
  mit „Mitspielen“ (Einstieg ab dem nächsten Call bleibt).
- **Über Funk:** Die Ereignisse gehen weiter einmal als UI-Frame an alle im Board; der Client des
  Zuschauers blendet sie aus. Sie nur an die Spieler zu schicken hieße je Spieler eigene I-Frames –
  bei mehreren Spielern mehr Bytes, nicht weniger. Mitlesen mit einem Monitor bleibt möglich (Funk ist
  offen); für ein Spiel unerheblich.

### Nachtrag 5 (OE3GAS, 13.11.2026): Startseite im Stil von „Prefix raten“ – umgesetzt (Client 2026.11.13.7) ✅

- Karte mit Gerhards Contest-Foto (eigener Fundus, ohne Copyright) rechts im Hintergrund,
  links überblendet: 📻, „CQ Contest“, „Schiffe versenken mit Contest-Stationen – wer loggt zuerst
  alle fünf?“, Gegner und Zentrum, Ausbreitungshinweis „Ein | Aus“, Knopf „Contest starten“ (Box)
  bzw. „Einladung senden“ (Station, Board-Teilnehmer) und „Abbrechen“. Gegen die Box dazu die Regeln
  als Chips. Texte der Startseite deutsch wie bei Prefix raten.
- 📻 neben einem Teilnehmer im Board öffnet jetzt diese Startseite (statt sofort einzuladen).
- Die Einladung beim anderen (Karte unten rechts und im Spiel-Panel) im selben Stil:
  „<Call> lädt zum CQ Contest“, „Annehmen / Ablehnen“.
- Foto `tbclient/web/contest-room.jpg` (ca. 115 kB), Entwurf vorab als Bild abgestimmt.

### Nachtrag 6 (OE3GAS, 14.11.2026): Spieltexte deutsch – umgesetzt (Client 2026.11.14) ✅

- Alle Texte des Spiels (Kopf, Stand, Setzen, Rufen, Meldungen, Log, Ende, Einladung, Hinweise in
  der rechten Spalte und links unter Station, Fehler, Popup, Chat-Notizen) deutsch.
- Die Texte stehen in **einer Tabelle** in `contest.js` (`TX.de` und `TX.en`), die englische Fassung
  bleibt erhalten; `Contest.setLang("en")` schaltet um. Das Protokoll (`//CT`, `//CTR`) hat keine
  Sprache – Vorbereitung für die Sprachwahl je Spiel in der Konfiguration (Frage von OE3GAS, noch
  zu entscheiden). Die Chat-Notizen in `tbclient/contest.py` sind vorerst nur deutsch.
- Funk-Jargon bleibt: „QRZ?“, „5NN“, „73 de … · gl next time“, „tnx fer the contest“, „QRV“.

