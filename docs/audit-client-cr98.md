# Client-Audit CR98 – Zugriff auf PC-Daten und In-Band-Befehle

Stand: 09.11.2026, Client 2026.11.09.6, Repo-Stand nach CR97. Durchgeführt von Claude im Auftrag
von OE3GAS (PLANUNG 29, `docs/client-change-requests.md` CR98).

## Auftrag

1. Die Aussage prüfen: **„Der Chat hat keine Möglichkeit, ohne Rückfrage auf Daten des Users am PC
   zuzugreifen.“**
2. Prüfen, ob Zeilen mit `//` (oder anderes, das der Client als Protokoll liest) aus Post oder
   Bulletins beim Lesen oder beim Sync als Befehl ankommen können.
3. Der breite Fuzz-Lauf über alle Zeilenparser, der aus CR88 offen war.

## Methode

- Durchsicht aller Stellen im Client, die Dateien lesen, schreiben, löschen oder Programme starten
  (`open`, `read_*`, `write_*`, `unlink`, `mkdir`, `iterdir`, `glob`, `subprocess`, `webbrowser` …),
  und aller Wege, auf denen eingehende Zeilen verarbeitet werden: `ClientCore._on_line` →
  `Syncer.take`, `Images.take`, `_control`, Chat-Ereignisse (`#…`), `%Q`; `Channel._on_line` →
  `_tb_line`, `Peer.take` mit `PeerImages`, `PeerFiles`, `PeerFun`.
- Durchsicht der Web-Oberfläche (`tbclient/web.py`, `web/app.js`) auf Pfade, Header, Downloads,
  Links und das Einsetzen fremden Textes.
- Fuzz-Lauf `tests/test_cr98_fuzz.py`: zufällige Zeilen aus Protokollwörtern und schwierigen Werten
  (Unicode-Ziffern, Überlängen, Steuer- und Bidi-Zeichen, leere Felder) in den Client (TinyBox-Modus,
  Terminal, Peer), in die TinyBox-Sitzung (Terminal und Client, alle Zustände) und in die gemeinsamen
  Parser (Profil, Bildreferenz, Forward-Vorschlag, APRS). Seeds 1–8 und 98 mit je 3000 Zeilen.

## Ergebnis zu 1: Zugriff auf PC-Daten

**Die Aussage stimmt** – mit einer Präzisierung.

- Der Client **liest** über das Netz nur zwei Arten von Dateien, und nur aus seinem eigenen
  Datenordner, über einen 6-stelligen Hex-Hash als Name (kein Pfad, keine Pfadmanipulation möglich):
  - Bilder (`data/tbclient/images/<hash>`) – an einen Peer nur, wenn wir ihm genau dieses Bild selbst
    geschickt haben (`_sent_to_them`),
  - Dateien (`data/tbclient/files/<hash>`) – an einen Peer nur, wenn wir sie ihm selbst angeboten
    haben (`_offered`).
  Seit CR97 zusätzlich: höchstens 2× (Datei) bzw. 3× (Bild) je Stunde und aus dem Sendebudget.
- **Präzisierung:** Eine einmal angebotene Datei kann die Gegenstelle ohne weitere Rückfrage erneut
  abrufen (das ist der Sinn des Angebots). Weil das Rufzeichen fälschbar ist, kann das auch ein
  Fremder unter diesem Rufzeichen. Es betrifft aber nur, was der User selbst angeboten hat – keine
  anderen Dateien.
- Der Client **schreibt** nur in seinen Datenordner: Bilder und Dateien unter ihrem Hash (seit CR96
  nur Angefordertes, nichts wird überschrieben, keine Programme), `settings.json` (Einträge aus dem
  Funk sind begrenzt: Profile `CACHE_MAX`, `fun_last` 50, bekannte TinyBoxen 20), SQLite-Datenbanken
  (Mailbox, Peer-Chat mit `KEEP` Zeilen je Peer und Richtung, Verbindungslog).
- Der Client **startet nichts**: kein `subprocess`, kein `os.system`, kein `webbrowser`.
- Web-Oberfläche: statische Dateien nur aus einer festen Liste; Downloads als
  `application/octet-stream`, `attachment`, `nosniff`, Dateiname über `safe_name` (ASCII, keine
  Anführungszeichen/Zeilenumbrüche); Bilder nur WebP/JPEG; fremder Text nur über `textContent`, seit
  CR95 in `<bdi>`; Links aus dem Chat nur `http(s)` mit `noopener noreferrer`. Zugriff auf die
  Oberfläche nur aus dem eigenen Netz (CR100).

## Ergebnis zu 2: Text, der als Befehl ankommt

Zwei Lücken gefunden und behoben:

### F1 – Post im Terminal der TinyBox: Textzeilen als Client-Befehl (Medium) ✅

Liest der User im Client eine Nachricht mit `R n` (manuelles Terminal der TinyBox im Client-Modus),
schickt die Box den Text Zeile für Zeile. Der Client hat jede Zeile, die mit `//`, `#` oder `%Q `
beginnt, als Protokoll behandelt. Eine Nachricht mit z. B.

    //SYS 30 The TinyBox shuts down
    //OK caps=
    #7 ^OE3GAS 12 …

zeigte eine falsche Abschaltmeldung, änderte die Fähigkeiten der Verbindung, schrieb MOTD/Profile in
`settings.json` oder fügte gefälschte Chatzeilen ein. Lokal geschriebene Post war seit CR95
entschärft, **weitergeleitete nicht**.

Behoben in der Box (`commands._show`, `prcore.text.client_safe`): an einen Client geht jede Textzeile,
die wie Client-Protokoll beginnt, mit einem führenden Leerzeichen; Terminals sehen den Text
unverändert. Der Sync-Weg (`//MSG <id> <n>`) war schon sicher: die Box zählt die Zeilen, `\r` wird
vorher entfernt, und der Client nimmt genau diese Zahl als Text.

### F2 – Terminal zu einer fremden Mailbox: `//TB BOX` in einem Text schaltet um (Medium) ✅

Nach einem eigenen Connect fragt der Client mit `//TB?`, ob dort eine TinyBox oder ein TBClient ist.
Die Antwort `//TB BOX` / `//TB CLIENT` wurde während der **ganzen** Verbindung angenommen. Las der User
auf einer fremden Mailbox eine Nachricht mit so einer Zeile, schaltete der Kanal in den
TinyBox-Client- oder Peer-Modus; danach wären weitere `//`-Zeilen des Textes als Befehle gelaufen.

Behoben (`channels.py`): die Antwort gilt nur innerhalb von 90 s nach dem eigenen `//TB?` und nur
einmal; danach ist so eine Zeile Text.

## Ergebnis zu 3: Fuzz-Lauf

### F3 – `//IN` mit einer Nicht-Zahl (Low) ✅

`//IN nan …` (oder `²`) ließ `int()` scheitern. Der Fehler wurde pro Frame abgefangen (CR88), die
Zeile ging verloren. Behoben: `//IN` wird nur mit Zahl und Hex-Wert als Beitritt genommen.

Sonst fand der Fuzz-Lauf nichts. Die TinyBox-Sitzung warf in keinem Zustand eine Ausnahme (auch
nicht hinter dem Catch-All), die gemeinsamen Parser ebenso wenig.

## Offen, nicht in CR98

- **Peer-Verlauf (`//HIST`, `//HM`)**: ein Fremder unter dem Rufzeichen eines Peers kann den
  gemeinsamen Chatverlauf abgleichen lassen (TB-06) → CR99.
- **Anzahl der Peers** im Peer-Chat und Zeilen im Verbindungslog sind nicht begrenzt; je Peer ist der
  Verlauf begrenzt, ein neuer Peer braucht einen vollständigen Handshake. Akzeptiert (geringer
  Plattenbedarf).
- Ausnahmen in Aufgaben, die eine Zeile nur anstößt (`asyncio`-Tasks), erfasst der Fuzz-Lauf nicht;
  sie werden geloggt und beenden den Client nicht.

## Tests

`tests/test_cr98.py` (F1, F2, F3), `tests/test_cr98_fuzz.py` (Fuzz-Lauf; `FUZZ_SEED`, `FUZZ_N` in
der Umgebung für andere Läufe).
