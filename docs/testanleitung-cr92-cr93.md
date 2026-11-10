# Testanleitung – Signieren (CR93), Rollen (CR92), Sysop über Funk (CR94)

Stand 10.11.2026 · TinyBox mit Schema 13 · Client 2026.11.10.6

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
| 0.1 | PC2: Datenbank `data\…db` sicherheitshalber wegkopieren. Dann `git pull`, TinyBox neu starten. | Start ohne Fehler. Datenbank auf Schema 13 (läuft automatisch). | |
| 0.2 | PC1: `git pull`, Client neu starten. | Startblock zeigt Version **2026.11.10.6** und „Your key … Fingerabdruck“. Fingerabdruck notieren: ________ | |
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
| 6.3 | (Optional) Auf PC1 `data\tbclient\identity.key` wegkopieren und löschen, Client starten und verbinden. | Neuer Fingerabdruck im Startblock; Box meldet „other_key“ (der alte ist freigegeben). Danach die Kopie zurücklegen, Client neu starten → wieder Client-Modus. | |

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

## 7. Was nicht getestet werden muss (automatische Tests)

Wiederholte oder verfälschte Signaturen (`sig_replay`, `sig_bad`), veränderter Text eines
`//SEND`, abgelaufene oder fremde Zertifikate und das Verdrängen von brocast-Seiten bei einer
Flut erfundener Stationen prüfen die Tests im Repo (`tests/test_cr92.py`, `tests/test_cr93.py`,
`brocast/tests/test_listener.py`).

## Rückmeldung

Bitte die Tabelle mit ✔/✘ und bei ✘ die Meldung zurückgeben – auch Auffälliges, das nicht in der
Tabelle steht (z. B. Texte, die unklar sind).
