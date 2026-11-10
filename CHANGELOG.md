# Changelog

## Unveröffentlicht

- **Ein Schlüssel je Gerät (CR93, OE3GAS):** jeder Client-PC hat seinen eigenen Schlüssel, der Sysop
  gibt jeden einzeln frei; ein neues Gerät stört die anderen nicht mehr (vorher `other_key`).
  Höchstens 5 je Rufzeichen. Box: Schema 14 (`client_keys`, die bisherigen Schlüssel werden
  übernommen); Konsole `USER OK|REVOKE|DEL call [fingerprint]`, Web-GUI „Keys“ mit Gerät und Knöpfen
  je Schlüssel. Client 2026.11.10.9 schickt ein Gerätekennzeichen (`dev=`, 8 Hex-Zeichen: Hash des
  Rechnernamens mit dem geheimen Schlüssel – der Name geht nicht über Funk).
- **Bulletins verschieben und kopieren (CR21)** – nur der Sysop: Konsole `MOVE n[,n] RUBRIK`,
  `COPY n[,n] RUBRIK`, `KILL n[,n]`; Sysop-Web-GUI: „Move / copy“ im Leser; Client (Sysop mit
  Schlüssel, Client 2026.11.10.7): Knopf „Sysop ▾“ im Leser – in der TinyBox löschen, verschieben,
  kopieren, danach Abgleich. Verschieben behält Text, Absender, Datum und BID und gibt eine neue
  Nummer (alle Clients sehen es ohne neues Protokoll), Kopieren bekommt eine eigene BID und
  „(copied from …)“; beides nur lokal, kein erneutes Forwarding. Ein Bulletin des Sysops aus dem
  Client gilt als vom Sysop (an `WARN` → Warnseite). Sysop-Konsole im Client mit Schnellknöpfen.
- **Sysop über Funk mit dem Client (CR94, Variante B):** meldet sich der Sysop mit seinem hier
  freigegebenen Schlüssel an, bekommt der Client die Fähigkeit `ADM` und in den Settings eine
  **Sysop console**. Jeder Konsolenbefehl geht einzeln signiert (`//ADM <Befehl> c= sig=`), die
  Antwort als `//ADM>`-Zeilen. Über Funk erlaubt: H, INFO, WHO, STATUS, DISC, BEACON, FWD, FWQ, HOLD,
  REL, SHUTDOWN, RESTART, RELOAD, USER, TRUST – nicht WEB, MON, LOG, UPDATE. Jeder Befehl steht im
  Log. Mit einem Zertifikat einer anderen Box gibt es kein `ADM`. Client 2026.11.10.6.
- **Kein Sysop über Funk per Rufzeichen** (CR94, OE3GAS): eine Terminal-Verbindung über Funk mit dem
  Sysop-Rufzeichen hat Gast-Rechte, `[station] sysop_via_radio` wird ignoriert (Warnung beim Start).
  Jede Terminal-Sitzung (nicht der Client) mit diesem Rufzeichen über Funk steht im Log; der Sysop
  bekommt höchstens alle 6 h eine Nachricht. Lokal
  (Konsole, Web-GUI, Telnet auf 127.0.0.1, AXUDP vom eigenen PC) bleibt alles wie bisher.
- **Rollen und Rechte CR92** (Audit TB-08, TB-14, TB-15, TB-21; MANUAL 3.7b): Terminal-Verbindungen
  sind Gäste – keine Bulletins, Post nur als Text, Post an andere BBS wird für den Sysop gehalten
  (`REL n`). Bulletins löscht nur der Sysop (oder der angemeldete Autor); ein Rufzeichen wie `70CM`
  bekommt keine Rechte an der Rubrik, und solche Nicht-Rufzeichen werden beim Connect abgewiesen.
  Warnseiten (`WARN`) gehen nur aus Sysop-Quellen an brocast. brocast-Listener: die Seite gehört
  immer der sendenden Station (`org` aus den Daten zählt nicht mehr), eine ganz abgewählte Station
  schickt auch keine Warnungen, je Station höchstens 150 Seiten, und beim Platzmachen gehen zuerst
  Seiten von Stationen, die erst seit weniger als einem Tag gehört werden – Warnungen zuletzt.
- **Zertifikat der Heimat-BBS CR93 Stufe 3** (MANUAL 3.7a): die Box hat einen eigenen Schlüssel
  (`data/box.key`) und bestätigt damit den Schlüssel ihrer User (`//CERT?`, 180 Tage). Eine andere
  TinyBox, deren Sysop ihr vertraut (`TRUST ADD box key`), lässt den User damit in den Client-Modus.
  Box: Schema 13 (`trusted_boxes`). Sysop-Web-GUI: neue Ansicht **Keys** (Schlüssel freigeben,
  widerrufen, löschen; vertraute TinyBoxen). Client 2026.11.10.5 holt und schickt das Zertifikat.
- **Fix CR106:** Wartete der Schlüssel auf den Sysop (`//AUTHWAIT`) oder wurde er abgewiesen
  (`//ERR auth`), stand die Antwort der Box hinter dem Prompt und kam beim Client nie an: kein
  Client-Modus, kein Hinweis, Mail-Hinweis „4 new messages“ bei leerer Inbox und ein Sync, der 90 s
  in „connecting“ hing (Abort: weitere 30 s). Die Box schreibt während des Logins keinen Prompt
  mehr und jede Login-Antwort auf eine eigene Zeile; Client 2026.11.10.4 liest sie auch hinter dem
  Prompt einer älteren Box, der Sync bricht sofort mit dem Grund ab, Abort wirkt sofort.
- **Signierte Befehle CR93 Stufe 2** (MANUAL 3.7a): nach dem Login mit Schlüssel kommen `//SEND`
  (samt Betreff und Text), `//KILL`, `//SYNC k=` und `//PROF` (Speichern) einzeln signiert, mit
  aufsteigender Nummer und an die Login-Challenge gebunden. Unsigniert, falsch oder wiederholt →
  abgewiesen, der Text eines abgewiesenen `//SEND` läuft nie als Befehl. In so einer Client-Sitzung
  weist die Box die Terminal-Befehle zum Schreiben und Löschen ab (`S`, `SP`, `SB`, `K`, `KM`, `E`,
  `N`, `NH`, `NL`). Ein neues `//CLIENT` auf derselben Verbindung bedeutet einen neuen Login.
  Client 2026.11.10.2 signiert; **Clients bis 2026.11.10 können an einer neuen Box nicht mehr
  senden, löschen oder das Profil ändern** – alle Clients aktualisieren.
- Client 2026.11.10: **APRS-Statistik bei viel Verkehr (CR103)** – fest die neuesten 250.000 Frames
  statt 7 Tage, der Knopf „All“ zeigt den Zeitraum („Last 6.9 days“). Die Auswertung läuft in einem
  Thread und wird 10 s zwischengespeichert; der Client steht dabei nicht mehr still.
- **Client-Login mit Schlüssel CR93 Stufe 1** (MANUAL 3.7a): Client-Modus nur nach Login mit dem
  Ed25519-Schlüssel des Benutzers (Challenge-Response, `//AUTH?`/`//AUTH`); ein neuer Schlüssel
  wartet auf die Freigabe durch den Sysop (`USER OK call` nach Vergleich des Fingerabdrucks).
  Ohne Zusatzpaket (`cryptography` wird genutzt, wenn vorhanden). Box: Schema 12 (`user_keys`).
  Client 2026.11.09.7: Schlüssel `data/tbclient/identity.key` (für einen zweiten PC kopieren),
  Fingerabdruck im Startblock, Hinweisbalken in der Web-GUI. **Ältere Clients bekommen keinen
  Client-Modus mehr** – alle Clients aktualisieren.
- **Client-Audit CR98** (`docs/audit-client-cr98.md`): bestätigt, dass Peers nur auf selbst
  angebotene Dateien und gesendete Bilder zugreifen können. Behoben: eine mit `R n` gelesene Nachricht
  (auch weitergeleitete) konnte mit Zeilen wie `//SYS`, `//OK`, `#…`, `%Q` im Client als Befehl wirken
  – die TinyBox schickt solche Zeilen an Clients jetzt mit führendem Leerzeichen. Client
  2026.11.09.6: `//TB BOX`/`//TB CLIENT` gilt nur 90 s nach dem eigenen `//TB?` (eine Zeile in einer
  fremden Mail schaltet den Kanal nicht mehr um), `//IN` wird geprüft. Neuer Fuzz-Lauf über alle
  Zeilenparser (`tests/test_cr98_fuzz.py`).
- Alle Teile: **Ratenbegrenzung und Obergrenzen CR97 (Audit TB-03, TB-13, TB-17, TB-18, TB-19)** –
  Client 2026.11.09.5: was andere Stationen anfordern, kommt aus einem Sendebudget je Rufzeichen
  (96 KB) und für alle zusammen (256 KB) je halbe Stunde; dieselbe Datei höchstens zweimal, dasselbe
  Bild dreimal je Stunde, ein Speedtest je 10 min, `//HEARD?` und `//PING` begrenzt. Eingehende
  Verbindungen lassen einen Kanal frei und werden nach 30 min Schweigen getrennt. KISS-Port (Box und
  Client): höchstens 32 AX.25-Links, Verbindungen von Nicht-Rufzeichen (`ABCDEF`, `QST`) werden
  abgewiesen, und bei voller Tabelle macht ein Link Platz, der noch nie Daten brachte. AX.25: ein
  REJ/SREJ sendet frühestens nach einer halben Laufzeit wieder, nach N2 Wiederholungen eines Frames
  endet der Link. BBS: höchstens 2 Sitzungen je Rufzeichen (alle SSIDs); Mitlesen im Chat ohne
  Zeitgrenze (`[chat] idle_min = 0`), aber ist die Box voll und will jemand herein, macht der am
  längsten stille Chat-Leser Platz. kisshub
  2026.11.09.2: höchstens 500 gehörte Stationen (ein Tag), 200 verfolgte Links, 50 Links im Status.
- Client 2026.11.09.4 und TinyBox: **Datei- und Bildempfang CR96 (Audit TB-05, TB-16)** – der Client
  nimmt `//I` und `//F` nur für das an, was er gerade angefordert hat (anderes wird verworfen),
  Empfangenes überschreibt nie einen vorhandenen Eintrag (eigene Bilder schon), das Größenlimit gilt
  für jede Übertragungsart (auch `r`), und eine Ankündigung über dem Limit trennt die Verbindung.
  Programme und Skripte werden nicht angenommen – am angebotenen Namen schon vor dem ersten Byte, am
  Inhalt (`MZ`, ELF, Mach-O, `#!`, Verknüpfung, ZIP mit Programm darin) nach dem Empfang. Die TinyBox
  ordnet einen Bild-Upload der Station zu, die ihn begonnen hat: eine andere kann ihn weder übernehmen
  noch ersetzen (`//ERR img busy`), und ein anderes Bild unter demselben kurzen Hash wird abgewiesen
  (`//ERR img collision`).
- Alle Teile: **Zeichensatz-Policy CR95 (PLANUNG 29.9, Audit TB-11/TB-12/TB-22)** – Freitext in jeder
  Schrift, aber ohne Steuer-, Bidi- und unsichtbare Zeichen, NFC, höchstens 3 Kombinationszeichen je
  Buchstabe (`prcore.text.clean_text`): beim Speichern von Post, im Chatboard und im Client für
  empfangene Zeilen. Zeilen eines lokal geschriebenen Textes, die eine Mailbox oder der Client als
  Protokoll lesen würde (`/EX`, `***`, `R:`, `F>`, `FB …`, `;`, `//` – auch in voller Breite), bekommen
  ein führendes Leerzeichen. Konsole, Sysop-Konsole und Logdateien (TinyBox, brocastd, kisshub,
  Client) zeigen Steuerzeichen als `\x1b` usw., statt sie auszuführen (Bildschirm löschen, Zeilen
  fälschen, Fenstertitel, Zwischenablage per OSC 52). Client 2026.11.09.3: Text in `<bdi>`,
  ADIF-Felder der QSL-Karte nur ASCII ohne `<`/`>`, Locator wird geprüft.
- Forwarding: **zwei Stationen unter einem Rufzeichen erkennen (CR90 Stufe 1, Audit TB-02)** – sendet
  das Rufzeichen des Partners während einer Funk-Sitzung DM, FRMR oder ein überzähliges UA (die echte
  Station antwortet so, wenn jemand anderer ihr Rufzeichen benutzt), wird gesendete Post erneut
  angeboten, empfangene für den Sysop gehalten (`REL n`), und der Sysop bekommt eine Nachricht.
- Forwarding: **Robustheit CR89 (Audit TB-10, TB-11, TB-20a/b)** – eine Nachricht bekommt immer eine
  BID: ist `<n>_<CALL>` schon bekannt (Zähler übergelaufen, Datenbank neu, oder vorab von einem
  falschen Partner belegt), eine zufällige wie `K7Q2X_OE3XTC`; ältere Nachrichten ohne BID bekommen
  sie beim Senden, und eine unbrauchbare Nachricht wird übersprungen statt die Warteschlange zu
  blockieren. Steuerzeichen (vor allem Ctrl-Z) werden beim Empfang und beim Senden entfernt.
  B1-Restart-Daten gelten nur für denselben Vorschlag (gleiche Größe, Schema 11) und werden nach
  einem gescheiterten Restart verworfen. `;`-Zeilen verlängern den Timeout nicht mehr, höchstens 20
  in Folge, und jede Sitzung endet nach `max_session_min` (Vorgabe 60 min) je Partner.
- brocastd: **Dictionary-Integrität CR91 (Audit TB-04)** – ein neues Dictionary wird gegen jeden
  bestehenden Eintrag vollständig verglichen (bisher nur der Name): `scale`, `unit`, `exp`, `type`,
  `max` … dürfen sich nicht mehr ändern, nur die Anzeigetexte. Ein von einer Station aus
  `dict_trusted` automatisch übernommenes Dictionary sendet die eigene Station nicht weiter, bis der
  Sysop es freigibt (Knopf „Dictionary jetzt über Funk senden“, Import oder Freigabe von Hand); der
  Status zeigt „Dictionary weitersenden: angehalten“. Damit kann sich ein gefälschtes Dictionary
  nicht mehr von selbst durchs Netz verbreiten.
- TinyBox-Web-GUI: **Live-Monitor im Dashboard schlanker (CR101)** – nur Filter und Auswahl, Knopf
  „Switch to monitor screen“; APRS Lense, HEX und Clear gibt es nur noch auf dem Monitor-Bildschirm.
- Client 2026.11.09.2: **Web-GUI nur aus dem eigenen Netz (CR100)** – Anfragen von öffentlichen
  Adressen bekommen 403 (`[web] allow = lan`, auch 10.x; erweiterbar, z. B. HAMNET 44.0.0.0/8),
  Host-Prüfung gegen DNS-Rebinding (`[web] hosts` für eigene Namen), POST mit fremdem `Origin`
  wird abgewiesen. Im eigenen Netz weiter ohne Anmeldung (PLANUNG 29.6 AR3).
- Alle Teile: **Robustheit CR88 (Audit TB-09, TB-20c, TB-23)** – Zahlen werden nur noch aus den
  Ziffern 0–9 gelesen (`prcore.text.isnum`, 84 Stellen; `²` bestand bisher die Prüfung und ließ
  `int()` scheitern), ein Test hält `isdigit()` aus dem Code. Die Forward-Sitzung endet bei einem
  unerwarteten Fehler sauber mit Log, der Client verliert bei einem Fehler in einer Zeile nicht mehr
  den Rest des Frames, und Telnet hängt nicht mehr still. brocastd nimmt keine Zeitstempel nach
  2100 und keine Seiten mit mehr als einem Tag Vorlauf an; die Seitenliste übersteht kaputte Zeilen.
  Client 2026.11.09, kisshub 2026.11.09, dxfeed 2026.11.09.
- brocastd: **Sicherheitsfix CR87 (Audit TB-01)** – ein einzelnes UI-Frame mit falsch typisiertem
  Feld (z. B. `exp` als Text) konnte brocastd dauerhaft lahmlegen, auch nach jedem Neustart.
  Jetzt: Typprüfung aller Umschlag-Felder beim Empfang (Seite wird verworfen), Gültigkeit auch aus
  einem über Funk empfangenen Dictionary nur als plausible Zahl, Housekeeping kann den Daemon nicht
  mehr beenden, und kaputte Einträge einer älteren Datenbank werden beim nächsten Durchgang
  selbsttätig entfernt (kein Handeingriff nötig).
- brocast-Web-GUI: **„n neu“ als oranger Chip** neben den Rubriken und Stationen.
- brocastd (Station): **Rücksicht auf den echten Verkehr** (`[traffic]`) – eine Seite beginnt
  erst, wenn der Kanal `quiet_s` ruhig war (nach Verbindungs-Frames `connected_quiet_s`). Die
  TinyBox meldet `PUT /busy`: Stufe 1 (Benutzer über Funk verbunden) nur neue Revisionen, kleine
  Seiten, 1 Frame je Aussendung, `busy_percent`; Stufe 2 (Forward über Funk) nichts. Notfall-Seiten
  gehen immer, die Bake nur, wenn alles ruhig ist. Kopfzeile „⏸ ZURÜCKGESTELLT“ mit Grund.
- brocastd (Station): **Bake im Klartext** – `[beacon] interval_min`, `text`, `dest`, `path`:
  ein UI-Frame (z. B. an `BEACON`), der brocast als System nennt; Platzhalter `{call}` `{version}`
  `{pages}`. Zwischen zwei Seiten, im Sendeprotokoll, in der Ansicht „Sendung“.
- brocast (Station): **Seite nicht mehr senden** – „✕“ in der Ansicht „Sendung“ bzw. „Nicht mehr
  senden“ bei einer eigenen Seite. Bisher blendete „Löschen“ nur die empfangene Kopie aus, im
  Karussell blieb die Seite. Jetzt: Rücknahme an die Hörer, und derselbe Inhalt von der Quelle
  (TinyBox-Abgleich, dxfeed) bleibt draußen (Tabelle `blocked`); neuer Inhalt oder „Wieder senden“
  bringt sie zurück.
- brocast-Web-GUI (Station): **Sendestatus** – Feld in der Kopfzeile („ON AIR P120 … 3/7“ mit
  Fortschritt, sonst nächste Seite mit Countdown, Pause bei vollem Budget, kein Sender) und neue
  Ansicht **„Sendung“**: Seite auf Sendung mit Teilen, Bytes, Airtime, Restzeit, Direwolf-Queue,
  Airtime-Budget, als Nächstes, zuletzt gesendet. Zeitnah: brocastd aktualisiert den Zustand bei
  jeder Übergabe eines Frames an AGW/KISS, `GET /api/v1/tx`, Abfrage 1 s beim Senden, sonst 5 s.
- Sysop-Konsole: **`FWD` ohne Rufzeichen startet den Forward mit allen Partnern** (nacheinander,
  ein Funkkanal); `FWD call` nur mit diesem Partner. Der Partnerstatus steht jetzt bei `FWQ`
  über der Warteschlange.
- Sysop-Web-GUI, neue Nachricht: **„To“ nimmt eine @-Adresse** (und `$BID`) wie `SB`/`SP` am
  Terminal, z. B. `TEST @ WW` oder `OE1ABC @ OE1XAB.#WIE.AUT.EU`; Fehlermeldungen für
  ungültige Adresse, bekannte BID und Forwarding aus.
- Sysop-Web-GUI, Nachricht lesen: **„To“ mit @-Adresse** (z. B. `TEST @ WW`), der Kopf ist
  kompakter (jeder Eintrag so breit wie sein Wert statt vier fester Spalten).
- TinyBox-Chat: **weniger `%Q`-Frames** – keine `%Q`-Zeile, solange alle Balken noch `?` sind;
  ist nur eine Station im Board, geht ihr `%Q` per I-Frame nur an sie statt als UI-Frame an
  TBCHAT-n (PLANUNG 14.6).
- TinyBox-Konsole: `INFO` zeigt am Ende wieder **Web GUI** und **Web GUI login** wie beim Start
  (der Login-Link nur in der Konsole, nie im Logfile).
- **Startblock auf 80 Spalten** auch bei TinyBox und Client (2026.11.05.2): lange Werte und
  Anmerkungen gehen unter dem Wert weiter, Pfade und Links werden nicht getrennt. Gemeinsam
  in `prcore/termcolor.py` (`wrap_items`), der kisshub nutzt dieselbe Funktion.
- **INFO in den Konsolen:** TinyBox-Sysop-Konsole `INFO` (nur so – `I` bleibt der
  Profil-Befehl der Mailbox) und neue Konsole im tbclient-Fenster mit `I` / `INFO` und
  `H` (Client 2026.11.05): der Startblock noch einmal, beim Client mit den Funkwerten, die
  sonst nur mit `-v` kommen.
- kisshub 2026.11.05.2: Konsolenbefehl **`I` / `INFO`** zeigt den Startblock noch einmal (mit
  den aktuellen Werten). Startblock auf **80 Spalten** umbrochen; „Radio values as defined in
  conf-file“ mit einer Zeile je Wert, die Herkunft steht nur noch, wenn sie nicht der
  TNC-Abschnitt ist (direwolf.conf, modem73, Konsole).
- kisshub 2026.11.05: **ein Abschnitt je TNC** in der `kisshub.conf` – alle Werte eines TNC
  (Anschluss, Weck-/Init-/Exit-Dialog, Funkwerte, AX.25-Empfehlung) stehen in seinem eigenen
  Abschnitt, z. B. `[pk232]`, `[tm-d710]`, `[vara-fm]`; im Programm stehen keine Gerätewerte
  mehr. `type = tnc | vara | direwolf | modem73` wählt den Programmteil, `base = <abschnitt>`
  übernimmt einen anderen Abschnitt (z. B. `[tm-d710-9k6]`). Eigene Profilnamen sind erlaubt,
  `kisshub -l` listet sie. Fehlende Pflichtwerte werden alle auf einmal gemeldet. Beim Profil
  `direwolf` gewinnt jetzt die `direwolf.conf`. **Die alte conf wird nicht mehr gelesen** –
  Umstellung: MANUAL 2.4.
- **Sysop-Web-GUI: Dashboard** – alle Fenster lassen sich einklappen (Klick auf den Titel oder
  das Dreieck); der Kopf mit Zähler/Status bleibt sichtbar, der Zustand wird im Browser
  gemerkt. „Connection log“ und „Stations (JLOG)“ stehen jetzt im Dashboard (links unter
  Messages) und laden bei jedem Connect/Disconnect neu; die Menüpunkte „Users“, „Stations
  (JLOG)“ und „Connection log“ sind entfallen.
- kisshub 2026.11.01: **modem73** (OFDM-Soundkarten-Modem) als neues Profil `modem73` – der
  kisshub startet modem73 selbst aus `[modem73]` in der `kisshub.conf` (Rufzeichen, Modus,
  Soundkarte, PTT) und beendet es mit Strg+C. Sendezeit, PACLEN, Fenster und T1 berechnet er
  aus dem Modus; zu lange Frames werden verworfen statt von modem73 abgeschnitten.
  Windows-Build von modem73: `tools/modem73`. `kisshub.bat -p modem73`, MANUAL 3.5a.
  Funktest steht aus.
- kisshub 2026.11.01.2: `[modem73] exe` wird schon beim Start geprüft (Ordner der
  `kisshub.conf`, dann PATH); ein Kommentar direkt hinter dem Namen (`modem73.exe; ...`)
  gilt nicht mehr als Teil des Pfads.
- kisshub 2026.10.29: **TNC7multi** (IfD) als neues Profil `tnc7multi` – Drehschalter 1k2/9k6,
  kein Init-Dialog, USB 115200 Bd bzw. RS232 38400 Bd, KISS-Parameter mit den Werten aus dem
  Handbuch (TXDELAY 150 ms, P 64, SlotTime 50 ms). **SMACK** (KISS mit CRC-16): `[tnc] smack`,
  Standard `yes` beim TNC7multi; Frames mit falscher Prüfsumme werden verworfen und gezählt.
  `kisshub.bat -p tnc7multi`, Beschreibung MANUAL 3.3a. Funktest steht aus.
- **Testbed: Werte je Bitrate** (PLANUNG 27.2): `[air.0]`, `[air.1200]`, `[air.9600]` in
  `tbtest.conf` – Kanal, AX.25 und Verhalten der User; `tbtest run --air 9600` nimmt alle Werte
  aus `[air.9600]`. Eigener Client: `tbclient-testbed-<baud>.conf` je Bitrate.

- **Testbed Teil 2** (PLANUNG 27.2): simulierter 1200-Bd-Funkkanal im AXUDP-Weg (gemeinsame
  Frequenz, CSMA, Kollisionen, versteckte Stationen, Verlust je Profil good/medium/poor),
  bis 30 User, eigener Client per `tbclient-testbed.conf`, `tbtest run -t 0` bis Strg+C,
  Kanalstatistik im Bericht.
- **AXUDP mit Sendezeit**: `[axudp] air_baud` / `txdelay_ms` in `tinybox.conf`; im Client
  (2026.10.29) `[tinybox] axudp_air_baud`, `axudp_txdelay_ms`, `axudp_paclen`,
  `axudp_maxframe`, `axudp_t1_sec`, `axudp_n2`. Standard unverändert (ohne Sendezeit).

- **Testbed `tbtest`** (PLANUNG 27): 1–10 simulierte User arbeiten über AXUDP mit einer eigenen
  Test-TinyBox – Terminal-User (tippen Mailbox-Befehle) und Client-User (echter Client-Kern).
  Funktionen `conn`, `send`, `bull`, `read`, `kill`, `info`, `chat`, `img`, wählbar per CLI
  zusammen mit Anzahl User und Dauer. Ende-zu-Ende-Prüfung mit Prüfsummen, Chat-Fan-out,
  Bildvergleich; Bericht mit Zeiten je Funktion. Nichts geht in die Luft (Funk-Attrappe).
  `tbtest.bat init`, dann `tbtest.bat run -u 10 -t 10m`; Beschreibung in `tbtest/README.md`.

- **NanoPi-Deployment** (PLANUNG 26): brocastd schreibt nicht mehr bei jedem Funk-Frame in die
  Datenbank (Major Fix P1, offener Punkt 9). WAL-Journal mit `synchronous=NORMAL`; Empfangslog,
  gehörte Stationen, Sendezeitplan und Seiten-Wiederholungen gehen erst alle `db_flush_sec`
  (neu, Standard 600 s) und beim Beenden auf die Platte, echte Änderungen sofort. Leeres
  `txlog_dir` schaltet das Sendeprotokoll ab. `deploy/install.sh` installiert jetzt auch
  `prcore/`, `brocast/zdict/` und die Client-News (ohne `prcore` startete die TinyBox am NanoPi
  nicht); `build_production.sh` liefert `LICENSE` mit und schließt `kisshub/` und `*.sh` aus.

- Client 2026.10.27.2: läuft der Chat über lokales AXUDP (oder den Telnet-Testport), zeigt die
  Teilnehmerliste für die eigene Station keine Balken und keine Detailansicht, nur „you · axudp“.
  Andere lokale Teilnehmer haben keine Balken, weil die TinyBox für sie nichts mehr sendet;
  angetippt werden kann nur noch, wer Balken hat. Status-Feld `chat_link`.

- TinyBox: **keine Verbindungsqualität für lokale Stationen über AXUDP** (PLANUNG 25). Für eine
  AXUDP-Session wird nichts ermittelt (`linkq.is_local`): keine Balken in „Connected“, die
  Detailseite zeigt nur Verbindungsart, Connect-Zeit und Dauer; kein `%`-Balken im Chat,
  kein Empfangsfenster, `STAT` meldet keine Daten.

- **Feeder-Pi, späte Abholung**: `pi_abholung.py` zieht das Alter einer Datei am Pi von ihrem
  `Valid:` ab, damit ein spät abgeholter Wetterbericht nicht noch 2 h als aktuell gilt;
  schon abgelaufene Bulletins werden nicht zugestellt (nur quittiert). Dauert ein Ausfall länger
  als `--warnen-nach` (Standard 60 min), steht einmal eine `WARNUNG` im Protokoll; `--test`
  zeigt die letzte erfolgreiche Abholung.
- **CR74 – Rauschen als Rufzeichen**: Frames mit ungültigem Adressfeld (Rufzeichen nicht nur
  A–Z/0–9, SSID nicht 0–15) kommen nicht mehr in die Heard-Listen. Ursache: der TNC (TM-D710,
  9600 Bd, offene Rauschsperre) liefert ab und zu Rauschen, bei dem die Prüfsumme zufällig
  stimmt. kisshub 2026.10.27 verwirft sie gleich vom TNC (Zähler `invalid` in Statuszeile und
  Statusabfrage, INFO-Logzeile mit den ersten 32 Bytes), Client 2026.10.27 prüft dasselbe
  (`prcore.ax25.frame.addresses_valid`). TinyBox-Kanalkarte: „Dropped / invalid“.
- TinyBox-Monitor, **HEX-Ansicht**: auch die UI-Frames, die die TinyBox sendet (Baken, Chat),
  zeigen ihre Nutzlast als Hex – auch im AGW-Modus. **Frame-Inspektor**: in der HEX-Ansicht
  öffnet ein Klick auf einen Frame unten eine Leiste mit allen Bytes (Offset, 16 Bytes Hex,
  Text); Adresse, Control, PID und Info farbig, Rufzeichen-Bytes zurückgeschoben lesbar,
  Zeigen auf ein Byte erklärt es (Wert, Bits, SSID-/C-/H-Bit, PID). Esc oder Close schließt.
  `framemon` liefert dazu `raw` (ganzer Frame) und `ctl` (Offset des Control-Felds).

- kisshub 2026.10.26: **RTS/CTS wirklich ausgewertet** (PLANUNG 15). 32-Byte-Stücke, jedes
  ganz aus der Schnittstelle, bevor CTS erneut geprüft wird – nicht mehr nur der Treiber.
  **CTS-Monitor** (2 ms): Statuszeile `CTS low 3x (0.4 s, max 210 ms), writer waits …`, jeder
  Wechsel im DEBUG-Log. Linux meldet, ob der Treiber `CRTSCTS` gesetzt hat. Ein Schreibfehler
  öffnet den Port neu, statt den Sender still zu beenden. Tests in `tests/test_kisshub.py`.
- Client 2026.10.26.2 – AXUDP (PLANUNG 25, Schritt 3): mit `[tinybox] axudp =
  127.0.0.1:10093` (und `axudp_port`) erreicht der Client die Heim-TinyBox am selben PC
  über AXUDP, alle anderen Stationen weiter über Funk – ein Funkgerät für beide. Voller
  Client-Modus mit Bildern und Kompression, Mail-Sync ohne Funkpausen, Chat ohne
  UI-Frames. Kanal-Chip „AXUDP“. Tests `tests/test_tbclient_axudp.py`.
- TinyBox-Monitor (KISS-Modus): **PacLen** `[n]` hinter dem Frametyp bei I- und UI-Frames,
  Knopf **HEX** im Kopf zeigt die Nutzlast als Hex-Bytes statt Text (bleibt gemerkt, APRS-Karte
  dann aus), **Frametypen in festen Farben** (I grün, RR blau, RNR orange, REJ/SREJ rot,
  SABM violett, UA türkis, DISC/DM rosa, UI gelb). `framemon` liefert dazu `len` und `hex`.
- AXUDP (PLANUNG 25, Schritt 2): die TinyBox hat neben dem Funk einen **AXUDP-Port**
  (`[axudp]` in `tinybox.conf`, vorerst nur 127.0.0.1). Darauf läuft das eigene AX.25 –
  auch wenn der Funk über Direwolf/AGW geht – mit Login, Chat, Mail-Sync, Bildern und
  Kompression; UI-Frames bleiben beim Funk. Nur eingetragene Gegenstellen (IP und
  Rufzeichen), Sysop nur von Loopback, dieselbe Station nur einmal. `STATUS` zeigt den
  Port. Der Client folgt mit Schritt 3. Tests `tests/test_axudp_adapter.py`.
- Live-Monitore mit **Millisekunden** (`HH:MM:SS.mmm`): TinyBox-Web-GUI (Monitor und
  Frame-Monitor), Client 2026.10.26 (Monitor), brocastd (Empfangslog; neue Zeilen speichern
  `ts` mit ms, ältere zeigen `.000`).
- AXUDP (PLANUNG 25, Schritt 1): neues Modul `prcore/axudp.py` – AX.25 über UDP im Format von
  BPQ32/LinBPQ, XNet und JNOS (Frame + FCS CRC-16/X.25). Gegenstellen fest als Rufzeichen →
  IP:Port, angenommen wird nur, wenn IP **und** Absender-Rufzeichen zu einer Gegenstelle
  passen. `AxudpEndpoint` hat dieselbe Schnittstelle wie `KissTcpClient`. Noch nicht in
  TinyBox und Client eingebunden (Schritte 2 und 3). Tests `tests/test_axudp.py`.
- kisshub 2026.10.25.3: **RTS/CTS-Flusssteuerung** zum TM-D710 (`[tnc] rtscts`, Standard `yes`
  bei `tm-d710`, sonst `no`). Das Funkgerät bremst den kisshub über CTS, wenn sein
  TNC-Puffer voll ist; geschrieben wird in 64-Byte-Stücken, Strg+C hängt nie. Warnung bei
  CTS länger als 5 s tief, Zähler `cts_waits` / `cts_wait_s` in Status und Statuszeile.
- kisshub 2026.10.25.2: TM-D710 wahlweise mit **1200 oder 9600 Bd** auf dem Funk –
  `[kiss.tm-d710] air_baud = 9600` schickt `HBAUD 9600` an den TNC (bisher fest `HBAUD 1200`).
  Andere Werte werden beim Start abgelehnt. Bei 9600 eigene AX.25-Empfehlung (Fenster 7,
  T1 1,5–15 s, T2 0,5 s). 9600 noch nicht am Funk getestet.
- Update-Hinweis (PLANUNG 24): TinyBox, Client, brocastd und kisshub fragen einmal am Tag bei
  GitHub nach dem neuesten Release (`prcore/release.py`, Cache mit ETag, still ohne
  Internet, nichts wird installiert). Eine Release-Version für das ganze Repo (`RELEASE`).
  TinyBox: Hinweis im Log, bei `STATUS` und in der Web-GUI, dazu genau **ein** Bulletin pro
  Release in TBNEWS (`[update] announce`), Konsolenbefehle `UPDATE` und `UPDATE NEWS`.
  Client 2026.10.25: Banner mit Link. brocastd: Statusseite. kisshub 2026.10.25: Logzeile.
  Neuer Abschnitt `[update]` in allen vier `*.conf.example` (Vorgabe `check = yes`).
- brocast Karussell (PLANUNG 23): **Fehler behoben** – die Alterung (`aging`) griff nie, weil der
  stündliche Sync das Alter zurücksetzte; alte Bulletins liefen dauerhaft alle 30 min. Das Alter
  zählt jetzt ab der Revision bzw. ab `born` (neues Ingest-Feld, TinyBox schickt das
  Bulletin-Datum). Neue Vorgabe `aging = 24:120, 72:360, 168:1440`. Datenbank-Schema 4
  (`pages.rev_t`, wird automatisch nachgezogen).
- TinyBox `[brocast] air_days`: Bulletins nur n Tage nach dem Schreiben über brocast, in der
  Mailbox bleiben sie länger (0 = wie bisher).
- dxfeed live (PLANUNG 16c): „DX jetzt“ (letzte 2 h, nur bei Änderung), „Bänder jetzt“
  (letzte Stunde nach Kontinent der DX-Station, alle Gebiete) und „Neu auf dem Band“
  (seltenes DX, gedrosselt) als eigene, sich selbst ersetzende Bulletins; Aufgabe/Timer
  alle 10 min. Die 24-Stunden-Übersicht läuft gleitend alle 3 Stunden.
- brocast Dictionary v5: `dxsum` kind, path und Spalte qrg; Listener zeigt das Alter der
  DX-Seiten, die Pfad-Matrix und den Neu-Hinweis.
- Feeder-Pi (PLANUNG 22, `feederpi/README.md`): dxfeed und GeoSphere laufen auf einem
  Raspberry Pi (ab Modell 1, Raspberry Pi OS Lite 32-bit) mit systemd; der TinyBox-PC holt die
  Bulletins alle 5 Minuten per SSH in den Eingang (`pi_abholung.py`, eingeschränkter Benutzer
  `abholer`). Neu: `pi_sd_vorbereiten.bat`, `pi_abholung_einrichten.bat`,
  `pi_abholung_entfernen.bat`, `feederpi/install.sh`.
- Benutzerprofil (CR73, PLANUNG 21): Name, Locator, Home-BBS je Rufzeichen in der
  TinyBox. Terminal fragt nach dem Login nach fehlenden Angaben (`[mailbox]
  ask_profile`), Befehle `N`, `NL`, `NH`, `I call`; `/W` im Chat mit Name und Locator;
  Sysop-Web-GUI zeigt die Profile bei den Stationen. Client-Protokoll `PROF`
  (`prof=` im `//OK`, `//PROF`, `//WHOIS`). Client 2026.10.24: Formular „My profile“,
  Einladungsbalken, Teilnehmerliste mit Name, Locator und Entfernung.
- dxfeed: Most-Wanted-Rang wirkt jetzt (Club Log liefert ADIF-Nummern, nicht
  Präfixe); mindestens 10 Stationen auf der brocast-Seite (`brocast_min_rows`);
  Modes aus dem Bandplan auch für Digital-Segmente (DIGI), Region-2-Phonie und FM.
- dxfeed: Bandaktivität zählt dieselben relevanten Spots wie die Stationsliste.
- brocast Dictionary v4: Seitentyp `dxsum` (DX-Zusammenfassung), Listen `band`,
  `mode` und `dxcc` (alle DXCC-Gebiete mit ADIF-Nummer), Feldtyp `rows`,
  Blockart `data` (PLANUNG 16b). dxfeed sendet Stationen und Bandaktivität als
  zwei Bulletins mit je einer Seite in einem Frame (vorher drei Frames); der
  Most-Wanted-Rang findet jetzt auch Gebiete, die Club Log anders schreibt (1A0, IS0 ...).
- dxfeed: Relevanz der DX-Meldungen nach Club Log Most Wanted und Spotterzahl
  (Stufen A/B/C, PLANUNG 16a), neuer Befehl `mw-update`; Tabelle alphabetisch,
  Bandaktivität je Mode mit den anderen Modes namentlich. Das DX-Bulletin trägt
  eine brocast-Seite (nur Stufe A+B); der Listener zeigt sie als Band/Mode-Raster
  mit Heatmap der Bandaktivität.
- Konsole aller vier Programme (TinyBox, tbclient, kisshub, brocastd) einheitlich:
  `[ERROR]` (rot) und `[WARN]` (gelb) vor Fehlern und Warnungen, stehende
  Verbindungen grün, Startzeile hervorgehoben. Farben nur in einem echten
  Konsolenfenster, nicht in Log-Dateien; abschalten mit `[console] color = no`
  oder der Umgebungsvariable `NO_COLOR`.
- tbclient 2026.10.23: übersichtlicher Startblock (Call, Locator, TinyBox,
  Autoconnect, Verbindungsweg, Web-GUI); technische Details nur mit `-v`.
- TinyBox, kisshub und brocastd: Startblock im selben Muster (Beschriftung: Wert),
  Adressen von Web-GUI und Ports als eigene Zeilen; Inhalt unverändert.
- „Nicht erreichbar“ (Direwolf, KISS, TNC) wird nur noch einmal gemeldet, als `[ERROR]`.
- Linux-Startskripte `tinybox.sh`, `tbclient.sh`, `kisshub.sh`, `brocast/brocastd.sh`.

## v1.0.0 – 22.10.2026

Erste öffentliche Version.

**TinyBox** (Mailbox, Version 1.0.0)
- Post und Bulletins mit Rubriken, Suche (`F`), Eingangsordner für automatische Bulletins
- Chat-Boards (`C`) mit einstellbarer Aufbewahrung, auch „live“ ohne Speicherung
- Forwarding als optionales Modul: FBB-ASCII und B1 (komprimiert), Zeitplan,
  HOLD/REL, hierarchische Adressen, BID, R:-Zeilen; mit LinBPQ getestet
- Anbindung über Direwolf (AGW) oder KISS (eigenes AX.25 v2.2 mit SREJ/XID),
  auch über Digipeater; Telnet-Testport für den Betrieb ohne Funk
- Sysop-Konsole (Monitor, `SHUTDOWN`/`RESTART` mit Vorwarnung) und Sysop-Weboberfläche
- Log-Datei pro Tag mit Debug-Komponenten und `LOG BUNDLE` für Fehlerberichte

**TinyBox-Client** (`tbclient`, Version 2026.10.18.7)
- Web-Oberfläche für PC und Handy: Chat, Mailbox mit Offline-Abgleich, Suche
- bis zu 5 Verbindungen gleichzeitig, Terminal für beliebige Stationen, Monitor
- Verbindungslogbuch mit Export als CSV und ADIF
- Bilder im Chat, Post-Hinweis, Neuigkeiten als Bulletin (TBNEWS)

**Dazu**
- kisshub: ein KISS-TNC (PK-232, TM-D710, Direwolf-KISS, VARA FM) für mehrere
  Programme, mit Messung der Verbindungsqualität
- brocast: kompaktes Seitenprotokoll über UI-Frames (Wetter, Warnungen, Bilder)
- dxfeed: tägliche DX-Zusammenfassung als Bulletin
- fwdsim: Testpartner für das Forwarding

Voraussetzung: Python 3.10 oder neuer. Anleitung: `README.md` und `MANUAL.md`.
