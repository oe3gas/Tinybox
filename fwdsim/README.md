# fwdsim – Forward-Testpartner für TinyBox

fwdsim spielt zwei Partner-Mailboxen und prüft TinyBox von außen. Es nutzt dieselben Wege wie ein echter Partner, also TCP oder AX.25 über Direwolf/AGW. fwdsim importiert nichts aus `tinybox`.

```
TinyBox OE3XTC  <-- TCP / AGW -->  OE3GAS  <-- intern, gleiches Protokoll -->  DL0XTC
OE3XTC.#NOE.AUT.EU                 OE3GAS.#OOE.AUT.EU                         DL0XTC.#BAY.DEU.EU
```

- **OE3GAS** ist der einzige direkte Partner von TinyBox. Er ist Endstation und Hop zugleich.
- **DL0XTC** ist eine simulierte deutsche BBS, die nur über OE3GAS erreichbar ist. Sie sendet nie auf Funk.
- **Adressen, R:-Zeilen und BIDs** stehen ohne SSID, wie im echten Netz. BIDs haben die Form `<nr>_<CALL>`.

## Protokolle

Grundlage ist die W0RLI-BBS-Spezifikation vom 12.10.1998 (`docs/w0rli/`) und die FBB-Protokollbeschreibung.

- SID-Austausch, Kennung `[FWDSIM-0.1.0-FH$]`. Ohne `M`, weil W0RLI davon abrät.
- FBB-ASCII-Batch: `FB`, `F>` mit Prüfsumme, `FS +-=`, `FF`/`FQ`, Reverse Forward.
- MBL/RLI-ASCII nach W0RLI, wenn eine Seite kein `F` in der SID hat:
  - `S…`-Befehl, Antwort `OK`/`NO` (gewertet wird nur der erste Buchstabe), Prompt `>`.
  - Reverse Forward mit `F>`.
  - Nachrichtenende mit Ctrl-Z oder `/EX`; eine Textzeile `/EX` wird als `'/EX'` gesendet.
- Zeilen, die mit `;` beginnen, sind Nullbefehle (Feature I) und werden ignoriert.
- R:-Zeilen werden in beiden Formen gelesen: `@:BBS … #:nr` und das alte `nr@BBS`.
- Bei einem Fehler trennt fwdsim sofort und sendet vorher nichts (W0RLI, Abschnitt 6).
- B1 (komprimiert) fehlt noch. Es folgt zusammen mit TinyBox-Meilenstein F5.

## Bedienung

```
fwdsim cases                       Testfälle T01–T28 anzeigen
fwdsim run --stub                  Selbsttest: alle Fälle gegen einen fwdsim-Stellvertreter
fwdsim run T04 T05                 Fälle gegen die echte TinyBox über TCP
fwdsim run T04 --agw               dasselbe über Direwolf
fwdsim run --tinybox-db data\tinybox.db   zusätzlich das Ergebnis in TinyBox prüfen (nur lesend)

fwdsim serve [--agw]               OE3GAS wartet, bis TinyBox anruft
fwdsim call  [--agw] [--sid ...]   OE3GAS ruft TinyBox an
fwdsim send DL0XTC P OE1ABC @ OE3XTC.#NOE.AUT.EU "Betreff" -t "Text\nZeile 2"
fwdsim list [CALL]  |  show CALL NR  |  reset
```

Die Konfiguration steht in `fwdsim.conf`. Als Vorlage dient `fwdsim.conf.example`. Ohne diese Datei gelten die Standardwerte.

## Woher kommen die Testmails?

- **Netz → TinyBox (T04–T06, T08–T16, T19, T24, T25):** fwdsim legt die Mails selbst in OE3GAS oder DL0XTC an. Dann ruft OE3GAS TinyBox an. Über TCP braucht TinyBox dafür einen eingehenden Forward-Port (`[tinybox] forward_port`), über AGW nicht.
- **TinyBox → Netz (T01–T03, T07, T14, T18, T20):** fwdsim tippt die Mails über den Telnet-Port in TinyBox ein, mit `SP call @ adresse`. Danach wartet es, bis TinyBox OE3GAS von selbst anruft.

## Prüfungen

- Was bei OE3GAS und DL0XTC angekommen ist, prüft fwdsim immer selbst.
- Was in TinyBox angekommen ist, prüft es nur, wenn `[tinybox] db` bzw. `--tinybox-db` gesetzt ist. Es liest dabei die Spalten aus Schema 5 (`bid`, `status`, `fwd`, `rlines`, `origin`); gehalten heißt dort `fwd = H`. Ohne Datenbank werden diese Prüfungen als SKIP gemeldet.

## Fehlerinjektion

Die Testfälle schalten einzelne Fehler gezielt ein:

- fremde SID
- feste `FS`-Antworten
- `FB` mit 6 statt 7 Feldern
- falsche Prüfsumme
- Abbruch nach n Bytes
- fehlendes Ctrl-Z
- Knoten-Text mit `>` vor der SID
- CR LF als Zeilenende
- Text in Latin-1

## Tests

`tests/test_fwdsim.py` prüft fwdsim selbst:

- Protokollteile einzeln
- den internen Hop
- alle Testfälle gegen den Stellvertreter
- eine Forward-Sitzung über ein simuliertes Direwolf (AGW)
