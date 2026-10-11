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
