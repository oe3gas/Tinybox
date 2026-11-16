# Git: Updates holen, Release veröffentlichen

Der Code liegt auf GitHub im Repo `oe3gas/Tinybox`, Zweig `main`. Jede Installation – aus dem
Release-Paket oder als Git-Clone – holt neue Stände nur mit `git pull`; geändert wird der Code
nur im Repo, nie direkt in einer Installation.

Im Repo liegt nur Code. Nie im Repo und nie überschrieben werden (`.gitignore`):
Datenbanken (`data/`, `brocast/data/`), Logs, `eingang/`, Tokens und Schlüssel, die eigenen
Konfigurationen `tinybox.conf`, `tbclient.conf`, `kisshub.conf`, `dxfeed.conf`, `tbstart.conf`,
`brocast/brocastd.conf` (im Repo liegen nur die `*.conf.example`).

Voraussetzung: Git for Windows (https://git-scm.com/download/win) bzw. `git` unter Linux. Das
Release-Paket installiert Git selbst. Die Befehle sind für PowerShell bzw. die Shell.

## Update einspielen

Mit der Steuerkonsole geht es von selbst: Beim Start holt sie den neuesten Stand, unterwegs
weist sie darauf hin, `u` holt ihn (`INSTALL.md`). Von Hand:

```
cd C:\Tinybox
git pull
```

Danach die laufenden Programme neu starten (Steuerkonsole `R`, TinyBox auch `RESTART`). Neue
Einstellungen stehen in den `*.conf.example` – bei Bedarf von Hand in die eigene `.conf`
übernehmen.

## Einmalig: einen bestehenden Ordner an das Repo anbinden

Für einen TinyBox-Ordner, der nicht aus einem Git-Clone stammt. Vorher die eigenen `.conf`
sichern und die Programme beenden.

```
cd C:\Tinybox
git init -b main
git remote add origin https://github.com/oe3gas/Tinybox.git
git fetch origin
git checkout -f -B main --track origin/main
```

Das überschreibt nur die Dateien aus dem Repo. Datenbanken, Logs und die eigenen `.conf`
bleiben, weil sie in `.gitignore` stehen. Danach `git status` – es sollte „nothing to commit,
working tree clean“ zeigen. Meldet Git „dubious ownership“:
`git config --global --add safe.directory C:/Tinybox`.

## Änderungen ins Repo bringen (Entwicklung)

```
git add -A
git commit -m "Kurze Beschreibung"
git push
```

Beim ersten Push öffnet sich ein Browserfenster für die GitHub-Anmeldung. Regeln für Versionen,
News-Dateien und Change Requests: `CLAUDE.md`.

## Release veröffentlichen (PLANUNG 24)

Eine Version für alles: ein Release `v1.1.0` gilt für TinyBox, TBClient, brocastd und kisshub.

1. In `prcore/release.py` die Zeile `RELEASE = "1.1.0"` setzen (ohne `v`), committen, pushen.
   Die TinyBox zeigt diese Version selbst an (`tinybox/__init__.py` übernimmt sie).
2. Release-Paket für Windows bauen: `release/build_release.sh /pfad/zu/direwolf-tinybox.exe`
   (baut aus `main` auf GitHub, `INSTALL.md`, „Paket bauen“).
3. Auf GitHub unter *Releases → Draft a new release* das Tag `v1.1.0` auf `main` anlegen und das
   ZIP anhängen. Der Text des Releases geht gekürzt (ASCII, einige Zeilen) ins TBNEWS-Bulletin –
   die ersten Zeilen sollten also das Wichtigste sagen.
4. Veröffentlichen. Innerhalb eines Tages melden alle laufenden Installationen den neuen
   Release; jede TinyBox schreibt dazu einmal ein Bulletin in TBNEWS.

Pre-Releases und Entwürfe werden nicht gemeldet. Tags wie `prod-…` (NanoPi-Builds) zählen
nicht als Release. Die Datums-Versionen von TBClient, kisshub und dxfeed sind Build-Versionen
und laufen unabhängig davon weiter.
