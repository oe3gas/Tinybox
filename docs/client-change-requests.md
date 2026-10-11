# TinyBox-Client – Change Requests

Gesammelt beim ersten Test PC1 ↔ PC2 (OE3GAS, OE3TEC) am 09.10.2026, ergänzt laufend.
Stand: 11.10.2026 (Nachmittag)

## Übersicht

| CR | Inhalt | Status |
|---|---|---|
| 1 | Einzelnes Emoji als Nachricht groß anzeigen (≥ 2×) | ✅ (c376e16) |
| 2 | Emojis: 🤮 💩 ❓ ❗ und Pfeile dazu, 🗼 raus, Auswahl nach Gruppen sortiert | ✅ siehe unten |
| 3 | MOTD pro Board | offen – wer setzt sie (Sysop)? |
| 4 | Schrift: `_fett_` und Monospace für ASCII-Art | ✅ `_fett_`, `` `mono` `` (c376e16) |
| 5 | URLs erkennen und klickbar | ✅ (c376e16) |
| 6 | „Leave board“ im Chat statt in den Settings | ✅ (c376e16) |
| 7 | Bug: APRS-Symbol-Änderung wirkt erst nach Board-Wechsel – soll sofort wirken (Avatar-Update aller bleibt) | offen |
| 8 | Eigene Reaktion sofort anzeigen | ✅ blass bis Echo, nach 2 min ohne Echo zurück (c376e16) |
| 9 | Zeilenumbruch mit Shift+Enter | offen – braucht Zeilenumbruch-Kodierung über Funk (Protokoll ist zeilenbasiert) |
| 10 | Mehrzeilige Texte einfügen | offen – wie CR9 |
| 11 | Sticker und Animationen | Sticker-Set fertig (20 Dateien), Einbau und Animationen offen – siehe unten |
| 12 | Konzept: kleine Bilder anhängen – Umsetzung, Maximalgröße, Binärübertragung (7PLUS?) | Konzept offen |
| 13 | History wählbar beim Einchecken („last n lines?“, Enter = keine) | offen – auch im Client? |
| 14 | Zitatfunktion (Nachricht antippen → Zitieren, gekürzt über der Antwort) | offen |
| 15 | @CALL hebt Nachricht beim Empfänger farbig hervor | ✅ (c376e16) |
| 16 | Anstupsen: Klick auf Call in Teilnehmerliste → kurze persönliche Nachricht als Pop-up mit Klingelton | offen – über Funk für Mithörer lesbar |
| 17 | „Cry out“: max. 32 Zeichen, sehr große Schrift in einer „Bang!“-Blase | ✅ siehe unten |

## CR2 – Emojis (erledigt 11.10.2026)

- Neu in `emoji.json` (Version 2, angehängt): 🤮 `~1Q`, 💩 `~1R`, ❓ `~1S`, ❗ `~1T`, Pfeile ⬆️ ➡️ ⬇️ ⬅️ ↗️ ↘️ ↙️ ↖️ (`~1U` … `~21`).
- 🗼 (`~10`, der rote Turm) wird nicht mehr angeboten: Eintrag in `"hidden"`. Kommt der Code an, wird er weiter angezeigt – Codes ändern nie ihre Bedeutung.
- Die Auswahl ist nach Gruppen sortiert (`"picker"` in `emoji.json`): Gesichter, Hände & Herz, Zeichen & Pfeile, Funk & Technik, Wetter & Natur, Unterwegs, Essen & Feiern, Tiere & Sonstiges.

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

## CR17 – „Cry out“ (erledigt 11.10.2026)

- Ein Beitrag mit höchstens **32 Zeichen** wird in **sehr großer Schrift** (Großbuchstaben, Comic-Stil) in einer gelb-roten **„Bang!“-Blase** angezeigt, leicht schräg.
- **Über Funk:** nur zwei Zeichen `~!` vor dem Text, z. B. `~!PILEUP!` (9 Byte). `~!` ist frei, weil eine echte Tilde als `~~` gesendet wird. Terminal-Teilnehmer sehen `~!PILEUP!`.
- **Eingabe:** Knopf 💥 neben dem Emoji-Knopf schaltet den Cry-out-Modus ein (Feld auf 32 Zeichen begrenzt, Zähler im Hinweis), nach dem Senden wieder aus.
- **Schriftgröße** passt sich an: kurze Texte 36 px, längere 28 bzw. 23 px; Wörter werden nicht mitten drin getrennt.
- Status: von Gerhard freigegeben und eingebaut; getestet mit TinyBox + zwei Clients (PC- und Handy-Ansicht).

