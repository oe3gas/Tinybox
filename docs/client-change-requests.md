# TinyBox-Client – Change Requests

Gesammelt beim ersten Test PC1 ↔ PC2 (OE3GAS, OE3TEC) am 09.10.2026, ergänzt laufend.
Stand: 11.10.2026

## Übersicht

| CR | Inhalt | Status |
|---|---|---|
| 1 | Einzelnes Emoji als Nachricht groß anzeigen (≥ 2×) | erledigt (c376e16) |
| 2 | Emojis 🤮 💩 ❓ dazu, dafür einige raus | offen – welche raus? Achtung: `emoji.json` ist „append only“ |
| 3 | MOTD pro Board | offen – wer setzt sie (Sysop)? |
| 4 | Schrift: `_fett_` und Monospace für ASCII-Art | erledigt: `_fett_`, `` `mono` `` (c376e16) |
| 5 | URLs erkennen und klickbar | erledigt (c376e16) |
| 6 | „Leave board“ im Chat statt in den Settings | erledigt (c376e16) |
| 7 | Bug: APRS-Symbol-Änderung wirkt erst nach Board-Wechsel – soll sofort wirken (Avatar-Update aller bleibt) | offen |
| 8 | Eigene Reaktion sofort anzeigen | erledigt: blass bis Echo, nach 2 min ohne Echo zurück (c376e16) |
| 9 | Zeilenumbruch mit Shift+Enter | offen – braucht Zeilenumbruch-Kodierung über Funk (Protokoll ist zeilenbasiert) |
| 10 | Mehrzeilige Texte einfügen | offen – wie CR9 |
| 11 | Sticker und Animationen | Sticker-Set entworfen (15), Animationen offen – siehe unten |
| 12 | Konzept: kleine Bilder anhängen – Umsetzung, Maximalgröße, Binärübertragung (7PLUS?) | Konzept offen |
| 13 | History wählbar beim Einchecken („last n lines?“, Enter = keine) | offen – auch im Client? |
| 14 | Zitatfunktion (Nachricht antippen → Zitieren, gekürzt über der Antwort) | offen |
| 15 | @CALL hebt Nachricht beim Empfänger farbig hervor | erledigt (c376e16) |
| 16 | Anstupsen: Klick auf Call in Teilnehmerliste → kurze persönliche Nachricht als Pop-up mit Klingelton | offen – über Funk für Mithörer lesbar |

## CR11 – Sticker und Animationen

### Grundsatz

- **Über Funk geht nur ein kurzer Code** (wie bei den Emojis, ca. 3 Byte), nie das Bild.
- **Die Bilder liegen fest im Client** und werden versioniert wie `emoji.json`. Ein neues Paket kommt mit einem neuen Client (Git); später ist auch die Verteilung über das brocast-Dictionary denkbar.
- **Start mit einer festen Auswahl**, dann schauen, wie sie genutzt wird.
- Offen: Format des Codes im Chattext (z. B. eigenes Escape-Zeichen) und wie Terminal-Teilnehmer ihn sehen.

### Quellen (Recherche 10.10.2026)

- Fertige, frei nutzbare **Funk-Sticker gibt es praktisch nicht**. Radioddity „Ramoji“ (6 animierte GIFs: CQCQ, QRL, Morse, Roger, Over, 73) ist „free to use“, aber © Radioddity ohne Lizenz – Weitergabe nur nach Rückfrage.
- Allgemeine Emojis mit offener Lizenz: **Noto Emoji Animation** (CC BY 4.0; Lottie/WebP/GIF), OpenMoji (CC BY-SA 4.0), Microsoft Fluent Emoji (MIT, statisch), Twemoji (CC BY 4.0). Quelle im Client-„About“ nennen.
- Entscheidung: **Funk-Sticker selbst als SVG zeichnen** (keine Lizenzfragen, wenige KB). Allgemeine Animationen von Noto.

### Sticker-Set (Entwurf 2, 15 Stück)

Dateien und Vorschau: `docs/sticker-entwurf/` (`vorschau.png`, SVGs, Generator `make_stickers.py`). Zusammen ca. 64 KB.

| Datei | Motiv |
|---|---|
| `cq.svg` | Sprechblase „CQ CQ CQ“ |
| `73.svg` | „73!“ mit Wellen |
| `88.svg` | Herz mit „88“ |
| `qsl.svg` | QSL-Karte mit grünem Haken |
| `qrm.svg` | genervtes Gesicht mit Kopfhörer, „QRM!“ |
| `qrt.svg` | schlafendes Gesicht, Mond, „QRT“ |
| `dummy.svg` | Dummy Load 50 Ω mit schlafendem Gesicht |
| `open.svg` | Globus mit Skip-Bogen, „BAND OFFEN!“ |
| `dead.svg` | Oszilloskop mit Nulllinie, „BAND TOT“ |
| `smoke.svg` | Transceiver mit ERR-Anzeige, Riss, Funken, Rauchsäule, „MAGIC SMOKE“ |
| `resistor.svg` | Widerstand 4,7 kΩ mit Gesicht, „OHM SWEET OHM“ |
| `transistor.svg` | TO-92 mit Muskeln, „GAIN!“ |
| `tube.svg` | glühende Röhre, „WARMING UP“ |
| `gonedx.svg` | Türschild „GONE DXING“ mit Globus |
| `onant.svg` | Techniker mit Helm am Yagi-Mast, „ON MY ANTENNA“ |

- Übernommen aus Entwurf 1 unverändert: 73!, 88, QSL, QRM, QRT, Dummy Load, Band offen, Band tot.
- Angepasst: CQ (nur Sprechblase, ohne Antenne), Magic Smoke (neue Grafik).
- Neu: Widerstand, Transistor, Röhre, Gone DXing, On my Antenna.
- Gestrichen: 5/9+20, QRZ?, HI HI, Pileup, SWR 1:1, SWR ∞, Lid, Kaffee, Dipol im Baum, Antennenbau.
- Offen: 5 freie Plätze bis 20 füllen oder bei 15 bleiben; deutsche Texte („BAND OFFEN!“, „BAND TOT“) evtl. englisch.

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
