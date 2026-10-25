# TinyBox – Arbeitsregeln für Claude

## Arbeitsziel ist das GitHub-Repo
- Arbeitsziel ist immer das GitHub-Repo **oe3gas/Tinybox** (Zweig `main`).
- Änderungen immer zuerst dort ablegen (commit + push). Gerhard holt sie auf
  PC1 und PC2 nur mit `git pull`.
- Zu Beginn einer Session Schreibzugriff auf das Repo anfordern, falls er fehlt.
- Vor dem Arbeiten den aktuellen Stand von GitHub holen (`git pull`).
- Committen/pushen nur, wenn Gerhard es sagt bzw. die Aufgabe es vorsieht –
  im Zweifel fragen.

## Die beiden PCs
- **PC2** (`C:\Tinybox`): hier läuft die TinyBox.
- **PC1**: hier läuft der TinyBox-Client (`tbclient`). Client-Tests daher auf PC1.
- Auf den PCs nichts direkt ändern, was nicht über das Repo kommt.
- Lokale Dienste im Browser mit `127.0.0.1` aufrufen, nicht mit `localhost`
  (Client-Web-GUI: http://127.0.0.1:7744/).

## Nie ins Repo, nie anfassen
- Datenbanken, Logs und PC-spezifische Konfigurationen
  (`tinybox.conf`, `tbclient.conf`, `brocastd.conf`). Im Repo liegen nur die
  `*.conf.example`.

## Dokumentation
- Client-Change-Requests stehen nur in `docs/client-change-requests.md`.
- Erledigte CRs mit ✅ markieren (nicht mit „erledigt“).
- Planung und Entscheidungen: `PLANUNG.md`.

## Client-Versionen und News
- Bei jeder Änderung am Client `VERSION` in `tbclient/__init__.py` erhöhen
  (Datum, am selben Tag `.2`, `.3` …).
- Dazu **immer** eine News-Datei `tbclient/news/<VERSION>.txt` anlegen: nur
  das Neue dieser Version, wenige Stichwort-Zeilen, ASCII ohne Emojis. Sie
  geht als eigenes Bulletin über Funk – jedes Byte zählt, also kurz halten.
- `tbclient/FEATURES.txt` ist nur die Übersicht im Repo (wird nicht gesendet).

## Release-Version
- Eine Version für das ganze Repo: `RELEASE` in `prcore/release.py` (PLANUNG 24).
- Nur vor einem GitHub-Release erhöhen, gleich mit dem Tag (`RELEASE = "1.1.0"` ↔ Tag
  `v1.1.0`); Ablauf in `GIT-ANLEITUNG.md`. Die Datums-Versionen von Client, kisshub, dxfeed
  bleiben Build-Versionen und laufen weiter wie bisher.
