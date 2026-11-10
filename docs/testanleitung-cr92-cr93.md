# Testanleitung – Signieren (CR93), Rollen (CR92), Sysop über Funk (CR94), Client zu Client (CR99, CR107), Dateien im Board (CR86)

Stand 10.11.2026 · TinyBox mit Schema 15 · Client 2026.11.10.13

Vorgehen: Schritt für Schritt, jeweils **Erwartung** prüfen und ✔/✘ in die letzte Spalte.
Bei ✘ bitte die Zeile aus der TinyBox-Konsole bzw. die Meldung im Client notieren.

Begriffe: **PC2** = TinyBox (`C:\Tinybox`), **PC1** = Client (Web-GUI http://127.0.0.1:7744/),
**Konsole** = das TinyBox-Fenster auf PC2, **Sysop-Web-GUI** = http://127.0.0.1:8080/ auf PC2
(Login-Link steht in der Konsole), **Telnet** = Terminal-Verbindung auf PC2 zu `127.0.0.1:6300`
(z. B. PuTTY, Verbindungsart „Telnet“). Telnet mit dem Rufzeichen `OE3GAS` hat Sysop-Rechte – für
die Gast-Tests ein anderes Rufzeichen nehmen, z. B. `OE1TST`.

---

## 0. Vorbereitung

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 0.1 | PC2: Datenbank `data\…db` sicherheitshalber wegkopieren. Dann `git pull`, TinyBox neu starten. | Start ohne Fehler. Datenbank auf Schema 14 (läuft automatisch). | |
| 0.2 | PC1: `git pull`, Client neu starten. | Startblock zeigt Version **2026.11.10.13** und „Your key … Fingerabdruck“. Fingerabdruck notieren: ________ | |
| 0.3 | Sysop-Web-GUI öffnen. | Links neuer Menüpunkt **Keys**. | |

## 1. Login mit Schlüssel (Stufe 1) und Freigabe in der Web-GUI

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 1.1 | Web-GUI → **Keys**. | Karte „Client keys“: `OE3GAS` mit Status *released* (schon freigegeben) oder *waits*. | |
| 1.2 | Falls *waits*: Fingerabdruck mit 0.2 vergleichen, **Release**. | Meldung „released – the next login is in client mode“. | |
| 1.3 | Client mit der TinyBox verbinden. | Client-Modus (Chat, Post-Abgleich). Kein Hinweisbalken „waits“/„refused“. | |
| 1.4 | Konsole: `USER` | Zeile `OE3GAS active <Fingerabdruck>` – derselbe wie in 0.2. | |

## 2. Signierte Befehle (Stufe 2)

Alles im Client, verbunden mit der TinyBox.

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 2.1 | Persönliche Nachricht an `OE3GAS` schreiben, mit Umlauten und einem Emoji, abgleichen. | Kommt in der TinyBox an (Web-GUI → Messages), Text vollständig, Emoji bleibt (angemeldeter User). | |
| 2.2 | Bulletin an `ALL` schreiben, abgleichen. | Bulletin in der TinyBox. | |
| 2.3 | Eine eigene persönliche Nachricht im Client löschen, abgleichen. | In der TinyBox gelöscht. | |
| 2.4 | Profil ändern (z. B. Name), speichern. | Kein Fehler im Client; Web-GUI → Dashboard → Stations (JLOG) zeigt den neuen Namen. | |
| 2.5 | Konsole: nach Warnungen mit `refused (sig_` suchen (Log-Ausgabe der letzten Minuten). | **Keine** solche Warnung. | |
| 2.6 | Im Client das manuelle Terminal zur TinyBox öffnen, `SB ALL` eingeben. | „Not in client mode: write, delete and change the profile in the client …“ | |
| 2.7 | Ebenda `L` eingeben. | Liste wie gewohnt (Lesen geht). | |
| 2.8 | Client beenden und **ohne** Trennen der Funkverbindung neu starten (falls möglich), dann 2.1 wiederholen. | Neuer Login (kurz „asking“), danach Senden geht. | |

## 3. Rollen: Gast über Telnet (CR92)

Telnet auf PC2, Rufzeichen `OE1TST`.

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 3.1 | `SB ALL` | „Bulletins only with the TinyBox client (login with your key) – or ask the sysop.“ Kein Betreff wird abgefragt. | |
| 3.2 | `SP OE3GAS`, Betreff „Test Gast“, Text mit Umlauten (`Grüße`), `/EX`. | Gespeichert. In der Web-GUI ist der Text vollständig, Umlaute bleiben. | |
| 3.3 | Falls Forwarding aktiv: `SP OE5XYZ @ OE5XBL`, Text, `/EX`. | Zusätzlich: „Mail to another BBS waits until the sysop OE3GAS releases it.“ | |
| 3.4 | Web-GUI → Messages, Nachricht aus 3.3 öffnen. | Forward-Status **H** (gehalten), Notiz „guest mail – the sysop releases it (REL n)“. | |
| 3.5 | Konsole: `REL <Nummer aus 3.3>` | „released, queued for forwarding“ (gibt es keinen Weg zu OE5XBL, bleibt sie mit „no route“ gehalten – auch richtig). | |
| 3.6 | Telnet als `OE1TST`: `K <Nummer des Bulletins aus 2.2>` | „Not allowed.“ Bulletin bleibt. | |
| 3.7 | Telnet neu verbinden, als Rufzeichen `70CM` eingeben. Dann `QO100`, dann `TEST`. | Jedes Mal „Invalid callsign.“, die Frage „Callsign:“ kommt wieder (nach drei Versuchen Ende). | |
| 3.8 | Telnet als `OE3GAS` (Sysop): `SB ALL`, Betreff, Text, `/EX`. | Gespeichert – der Sysop darf. | |
| 3.9 | Ebenda: `K <Nummer aus 3.8>` | Gelöscht – der Sysop darf. | |

Über Funk gilt dasselbe: jede Terminal-Verbindung (ohne Client) ist Gast.

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 3.10 | Über Funk (anderes Gerät/Terminalprogramm) mit `OE3GAS-<SSID>` zur TinyBox verbinden, `SB ALL` und `E 1 SUBJ x` probieren. | Beides abgewiesen – auch das Sysop-Rufzeichen ist über Funk Gast. | |
| 3.11 | Konsole und Post von OE3GAS ansehen. | Nach dem Trennen: Warnung „… terminal session over … with the sysop call (guest rights …)“; persönliche Nachricht „Sysop call … connected over the radio“ (höchstens eine je 6 h). Der Client über Funk löst das nicht aus. | |
| 3.12 | Falls in `tinybox.conf` `sysop_via_radio = yes` steht: Start der TinyBox ansehen. | Warnung „sysop_via_radio = yes is ignored …“. | |

## 4. Warnseiten in brocast (nur wenn `[brocast] publish = yes`)

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 4.1 | Im Client ein Bulletin an `WARN` schreiben, abgleichen. | Bulletin in der TinyBox, aber **keine** Warnseite im brocast-Listener. | |
| 4.2 | Sysop-Web-GUI → New message, Typ Bulletin, an `WARN`. | Warnseite erscheint im brocast-Listener (hervorgehoben). | |
| 4.3 | brocast-Listener: eine Station komplett abwählen (alle Rubriken), von ihr kommt eine Warnung. | Warnung wird nicht angezeigt (eine nur abgewählte Rubrik lässt Warnungen weiter durch). | |

## 5. Zertifikat (Stufe 3)

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 5.1 | Client mit der TinyBox verbinden (nach dem Update das erste Mal). | In den Systemmeldungen des Clients die Zeile „certificate of OE3GAS-1 until JJJJ-MM-TT: other TinyBoxen that trust OE3GAS-1 let you log in“ (≈ 180 Tage). | |
| 5.2 | Noch einmal verbinden. | Keine neue Zertifikatszeile (es ist noch lange gültig – nichts geht über Funk). | |
| 5.3 | Konsole: `TRUST` | „This box OE3GAS-1: key …“ und Fingerabdruck; „No other TinyBox trusted yet.“ | |
| 5.4 | Web-GUI → Keys → Karte „Trusted TinyBoxen“. | Dieselben Werte wie 5.3. | |
| 5.5 | Web-GUI: im Feld Box `OE5XBL-1` und als Schlüssel `abc` eintragen, **Trust**. | Fehlermeldung „Not a public key …“. Nichts eingetragen. | |

**Mit einer zweiten TinyBox** (z. B. bei OE3TEC, oder eine zweite Instanz mit eigener
`tinybox.conf`, eigenem `data_dir`, eigenen Ports und anderem `mailbox_call`):

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 5.6 | An der zweiten Box: `TRUST ADD OE3GAS-1 <Schlüssel aus 5.3>`; Fingerabdruck mit 5.3 vergleichen. | „OE3GAS-1: trusted, key …“ | |
| 5.7 | Client mit der zweiten Box verbinden. | Sofort Client-Modus, ohne Warten auf deren Sysop. | |
| 5.8 | Zweite Box: `USER` | `OE3GAS cert …` mit Notiz „certificate of OE3GAS-1 …“. | |
| 5.9 | Zweite Box: `USER REVOKE OE3GAS`, Client neu verbinden. | Client meldet „login with your key refused: revoked“. | |
| 5.10 | Zweite Box: `USER DEL OE3GAS`, `TRUST DEL OE3GAS-1`, Client neu verbinden. | Schlüssel wartet dort wie ein neuer („waits for the sysop“). | |

## 6. Schlüssel widerrufen und wieder freigeben (Heimat-BBS)

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 6.1 | Web-GUI → Keys → bei `OE3GAS` **Revoke**, Client neu verbinden. | Client: „login with your key refused: revoked“, Hinweisbalken; kein Client-Modus. | |
| 6.2 | **Release**, Client neu verbinden. | Client-Modus wieder da. | |
| 6.3 | **Zweites Gerät:** Client zu Hause (über Funk) verbinden, der andere (Box-PC, AXUDP) ist schon freigegeben. | Client zu Hause: „waits for the sysop“. Web-GUI → Keys: zweite Zeile `OE3GAS` mit dem Gerätekennzeichen (8 Zeichen, wie im Startblock des Clients zu Hause „device …“) und *waits*. Der Rechnername erscheint nirgends. | |
| 6.4 | Fingerabdruck vergleichen, **Release** bei dieser Zeile. | Client zu Hause kommt in den Client-Modus; der Client am Box-PC weiterhin auch. | |
| 6.5 | Konsole: `USER REVOKE OE3GAS` | „several keys – add the fingerprint …“ mit beiden Schlüsseln. | |
| 6.6 | Konsole: `USER REVOKE OE3GAS <erste 4 Zeichen des Heim-Schlüssels>`, beide Clients neu verbinden. | Zu Hause: „refused: revoked“; am Box-PC: Client-Modus. Danach in der Web-GUI wieder **Release**. | |

## 6a. Sysop-Konsole über den Client (CR94)

Am besten über Funk (Client auf PC1, TinyBox auf PC2), mit dem Rufzeichen `OE3GAS`.

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 6a.1 | Client verbinden, Settings öffnen. | Karte **Sysop console** ist da (nur für OE3GAS mit dem hier freigegebenen Schlüssel). | |
| 6a.2 | `STATUS` eingeben, Send. | Die Statuszeilen der TinyBox erscheinen in der Karte. | |
| 6a.3 | `USER`, dann `FWQ`. | Schlüsselliste bzw. Forward-Warteschlange. | |
| 6a.4 | `WEB` | „(not possible over the radio)“ – der Login-Link geht nie über Funk. | |
| 6a.5 | Konsole am PC2 ansehen. | Je Befehl eine Warnung „OE3GAS-…: admin command over radio: …“. | |
| 6a.6 | Mit einem anderen Rufzeichen (zweiter Client oder OE3TEC) verbinden, Settings. | Keine Sysop-Konsole. | |
| 6a.7 | (Optional) `RESTART` | TinyBox startet nach der Vorwarnung neu; der Client verbindet sich danach wieder. | |

## 6b. Sysop im Client: löschen, verschieben, kopieren (CR21)

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 6b.1 | Settings → Sysop console: Knopf **Status**, dann **Keys**. | Antworten wie bei getippten Befehlen. | |
| 6b.2 | Bulletins → eine Rubrik, ein Bulletin öffnen, **Sysop ▾**. | Leiste „Sysop, in the TinyBox:“ mit Rubrik-Auswahl, Move, Copy, Delete for everybody. | |
| 6b.3 | Rubrik wählen, **Copy**. | Nach dem Abgleich: Kopie in der Ziel-Rubrik (abonniert?), Text beginnt mit „(copied from …)“. | |
| 6b.4 | Original öffnen, andere Rubrik, **Move**. | Verschwindet aus der alten Rubrik, erscheint in der neuen mit neuer Nummer; Web-GUI zeigt dieselbe BID. | |
| 6b.5 | Die Kopie öffnen, **Delete for everybody**, bestätigen. | In der TinyBox gelöscht (Web-GUI), im Client nach dem Abgleich weg. | |
| 6b.6 | Im Client ein Bulletin an `WARN` schreiben (nur mit brocast). | Wird zur Warnseite – vom Sysop. (Ein normaler User: keine Warnseite, Schritt 4.1.) | |
| 6b.7 | Sysop-Web-GUI: ein Bulletin öffnen, **Move / copy**. | Rubrik eingeben, Move bzw. Copy; die neue Nummer öffnet sich. | |
| 6b.8 | Konsole: `MOVE <n> <Rubrik>`, `COPY <n> <Rubrik>`, `KILL <n>`. | „moved to … now #…“, „copied to … as #…“, „Msg … killed.“ | |

## 8. Client zu Client: Schlüssel prüfen (CR99)

Zwei TBClients mit Version 2026.11.10.13, z. B. PC1 zu Hause und ein Client bei OE3TEC (oder ein
zweiter Client mit anderem Rufzeichen). Beide waren schon einmal an ihrer Heimat-BBS angemeldet.

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 8.1 | Client A connectet Client B direkt (Rufzeichen in „Connect to“). | TBClient-Ansicht; in der Karte des anderen: „✓ verified by OE3GAS-1“ (wenn beide dieselbe Heimat-BBS haben) oder „first contact – key stored“, dazu Fingerabdruck und Gerät. | |
| 8.2 | Trennen, noch einmal verbinden. | „✓ known key“ (oder wieder „verified“). | |
| 8.3 | Ein paar Zeilen schreiben, trennen, wieder verbinden. | Der Verlauf ist auf beiden Seiten gleich (wird nur bei ✓/first abgeglichen). | |
| 8.4 | (Optional) Auf B `identity.key` wegkopieren und löschen (neuer Schlüssel), B neu starten, A verbindet B. | A: „⚠ another key than before – history, pictures and files paused“ und Knopf **Accept new key**. Danach: „known key“. Schlüssel zurücklegen. | |
| 8.5 | Ein Client mit älterer Version am anderen Ende. | „older TBClient – no key check, chat only“. | |

## 9. Client zu Client wie im Chatboard (CR107 Teil 1)

In der TBClient-Ansicht zwischen A und B:

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 9.1 | 💥 drücken, „CQ CONTEST“ senden. | Große Bang!-Blase auf beiden Seiten. | |
| 9.2 | 🏷️ drücken, einen Sticker wählen. | Sticker auf beiden Seiten. | |
| 9.3 | Eine Blase des anderen antippen → ↩, Kommentar schreiben. | Beim anderen: Blase mit Zitat der richtigen Zeile oben drüber. | |
| 9.4 | Eine Blase antippen → 👍. | Unter der Blase „👍 1“ – auf beiden Seiten an derselben Zeile. | |
| 9.5 | Einen Link (`https://www.oevsv.at`) und `` `Code` `` schicken, dann ein einzelnes Emoji. | Link anklickbar, Code in Monospace, Emoji groß. | |
| 9.6 | Settings > Mention alert einschalten, Fenster in den Hintergrund, der andere schreibt. | Popup bzw. „BK“ in CW. | |
| 9.7 | Den anderen trennen lassen, dann in der TBClient-Ansicht etwas tippen, Enter. | Mail-Fenster öffnet sich: An = Rufzeichen des anderen, Text = das Getippte. | |

## 10. Chatboard: Dateien, Karte, Haken, Direktverbindung (CR86, CR107 Teil 2)

TinyBox mit Schema 15, `[chat] file_max = 16k` (Standard), zwei Clients im Board TREFF.

| # | Schritt | Erwartung | ✔/✘ |
|---|---|---|---|
| 10.1 | 📎 im Board, eine Textdatei (einige KB) wählen, bestätigen. | Eigene Blase mit Fortschritt, dann Datei-Blase „Save“. | |
| 10.2 | Am zweiten Client die Datei-Blase antippen. | Fortschritt, dann „Save“; die gespeicherte Datei ist identisch. | |
| 10.3 | Eine `.exe` oder `.bat` wählen. | „Not sent: … or a program file.“ | |
| 10.4 | Terminal-User im selben Board. | Liest „[File name 5.2 KB - TinyBox client only]“. | |
| 10.5 | Konsole am PC2: `FILES`. | Liste mit Hash, Größe, Rufzeichen. | |
| 10.6 | Eigene Zeile im Board senden. | Nach dem Echo „✓“ neben der Uhrzeit. | |
| 10.7 | Rechte Spalte „In this board“. | Karte mit den Teilnehmern, die einen Locator im Profil haben. | |
| 10.8 | ⇄ neben einem Teilnehmer (der ein TBClient in Reichweite ist). | Neuer Kanal, Direktverbindung, TBClient-Ansicht mit Ping, Speedtest, Chess, QSL. | |
| 10.9 | Bild im Board senden (nach dem Update). | Funktioniert wie vorher (Verweis jetzt mit 16-Zeichen-Hash). | |

## 7. Was nicht getestet werden muss (automatische Tests)

Wiederholte oder verfälschte Signaturen (`sig_replay`, `sig_bad`), veränderter Text eines
`//SEND`, abgelaufene oder fremde Zertifikate, falsche Peer-Signaturen, das Verdrängen von
brocast-Seiten bei einer Flut erfundener Stationen und abgebrochene Datei-Uploads prüfen die Tests
im Repo (`tests/test_cr86.py`, `test_cr92.py`, `test_cr93.py`, `test_cr94.py`, `test_cr99.py`,
`brocast/tests/test_listener.py`).

## Rückmeldung

Bitte die Tabelle mit ✔/✘ und bei ✘ die Meldung zurückgeben – auch Auffälliges, das nicht in der
Tabelle steht (z. B. Texte, die unklar sind).
