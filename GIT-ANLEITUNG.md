# Git-Ablauf PC1 → GitHub → PC2

PC1 (E:\Tinybox) = Entwicklung. PC2 (C:\Tinybox) = Dauerbetrieb.
Im Repo liegt nur Code. Nie im Repo und nie kopiert werden:
Datenbanken (`data/`, `brocast/data/`), Logs, `eingang/`, Tokens,
`tinybox.conf` und `brocast/brocastd.conf` (Vorlagen: `*.conf.example`).

Voraussetzung auf beiden PCs: Git for Windows (https://git-scm.com/download/win).
Die Befehle sind für PowerShell.

## Einmalig auf PC1: ans GitHub-Repo anbinden

```
cd E:\Tinybox
git config --global --add safe.directory E:/Tinybox
git remote add origin https://github.com/oe3gas/Tinybox.git
git push -u origin main
```

Beim ersten Push öffnet sich ein Browserfenster für die GitHub-Anmeldung.

## Einmalig auf PC2: bestehenden Ordner übernehmen

Vorher sichern: `C:\Tinybox\tinybox.conf` und `C:\Tinybox\brocast\brocastd.conf`.
Programme (TinyBox, brocastd) beenden.

```
cd C:\Tinybox
git init -b main
git remote add origin https://github.com/oe3gas/Tinybox.git
git fetch origin
git checkout -f -B main --track origin/main
```

Das überschreibt nur die Dateien aus dem Repo. Datenbanken, Logs und die
beiden .conf-Dateien bleiben unangetastet, weil sie in `.gitignore` stehen.
Danach `git status` – es sollte „nothing to commit, working tree clean“ zeigen.

## Laufend

PC1, nach einer Änderung:

```
git add -A
git commit -m "Kurze Beschreibung"
git push
```

PC2, Update einspielen:

```
cd C:\Tinybox
git pull
```

Danach TinyBox und brocastd neu starten. Neue Einstellungen in den
`*.conf.example` bei Bedarf von Hand in die eigene .conf übernehmen.
