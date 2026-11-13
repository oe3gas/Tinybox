# TinyBox - installation from the release package (Windows 10/11).
# Called by install.bat in the unpacked ZIP:
#   powershell -ExecutionPolicy Bypass -File payload\release\install.ps1 -Source <unpacked folder>
# 1. asks for the target folder   2. installs Git and Python if missing (winget)
# 3. copies the files (incl. the git data for later "git pull") and the Direwolf fork
# 4. installs the Python packages   5. configuration dialog (release\konfig.py)
# 6. shortcut "TinyBox Start" on the desktop
param([string]$Source = (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))))

# Continue: Windows PowerShell 5.1 would stop on any stderr line of git/winget;
# every step checks $LASTEXITCODE itself.
$ErrorActionPreference = 'Continue'
$Host.UI.RawUI.WindowTitle = 'TinyBox - Installation'

function Say($t, $c = 'Gray') { Write-Host $t -ForegroundColor $c }
function Fail($t) { Say "FEHLER: $t" Red; Read-Host 'Enter zum Beenden'; exit 1 }
function Ask($t, $d) {
    $a = Read-Host "$t [$d]"
    if ([string]::IsNullOrWhiteSpace($a)) { return $d } else { return $a.Trim() }
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Winget-Install($id, $name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail "$name fehlt und winget ist nicht vorhanden. Bitte $name von Hand installieren und install.bat erneut starten."
    }
    Say "Installiere $name (winget $id) ..." Cyan
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { Fail "$name konnte nicht installiert werden (winget Code $LASTEXITCODE)." }
    Refresh-Path
}
function Find-Python {
    foreach ($c in @(@('py', '-3'), @('python'))) {
        if (Get-Command $c[0] -ErrorAction SilentlyContinue) {
            $args2 = @($c[1..9] | Where-Object { $_ }) + @('-c', 'import sys; print(sys.version_info >= (3, 10))')
            try { $ok = & $c[0] @args2 2>$null } catch { $ok = $null }
            if ($ok -eq 'True') { return ,$c }
        }
    }
    return $null
}

Say ''
Say '==================================================================' Cyan
Say '  TinyBox - Installation' Cyan
Say '==================================================================' Cyan

$payload = Join-Path $Source 'payload'
if (-not (Test-Path (Join-Path $payload 'tbclient'))) {
    Fail "Paket nicht gefunden ($payload). Bitte die ZIP-Datei zuerst ganz entpacken und install.bat aus dem entpackten Ordner starten."
}
$ver = Join-Path $Source 'VERSION.txt'
if (Test-Path $ver) { Get-Content $ver -TotalCount 2 | ForEach-Object { Say "  $_" } }
Say ''

# --- 1. target folder ---------------------------------------------------------
$target = Ask 'Installationsordner' 'C:\TinyBox'
$target = [IO.Path]::GetFullPath($target)
if (Test-Path (Join-Path $target '.git')) {
    Say "In $target ist TinyBox schon installiert." Yellow
    Say 'Programm-Updates holt das Startmenue selbst (git pull). Eine Neuinstallation' Yellow
    Say 'ersetzt die Programmdateien; Konfiguration, Datenbanken und Logs bleiben.' Yellow
    if ((Ask 'Trotzdem neu installieren? (j/n)' 'n') -notmatch '^[jy]') { exit 0 }
} elseif ((Test-Path $target) -and (Get-ChildItem $target -Force | Select-Object -First 1)) {
    Say "Der Ordner $target ist nicht leer." Yellow
    if ((Ask 'Trotzdem hinein installieren? (j/n)' 'n') -notmatch '^[jy]') { exit 0 }
}

# --- 2. Git and Python --------------------------------------------------------
if (Get-Command git -ErrorAction SilentlyContinue) { Say ('Git vorhanden: ' + (git --version)) Green }
else { Winget-Install 'Git.Git' 'Git' }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail 'Git ist installiert, aber noch nicht im Suchpfad. Bitte Fenster schliessen und install.bat erneut starten.'
}
$py = Find-Python
if ($py) { Say ('Python vorhanden: ' + (& $py[0] @($py[1..9] | Where-Object { $_ }) --version)) Green }
else {
    Winget-Install 'Python.Python.3.12' 'Python 3.12'
    $py = Find-Python
    if (-not $py) { Fail 'Python ist installiert, aber noch nicht im Suchpfad. Bitte Fenster schliessen und install.bat erneut starten.' }
}
$pyArgs = @($py[1..9] | Where-Object { $_ })

# --- 3. copy ------------------------------------------------------------------
Say "Kopiere Dateien nach $target ..." Cyan
New-Item -ItemType Directory -Force -Path $target | Out-Null
robocopy $payload $target /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "Kopieren fehlgeschlagen (robocopy Code $LASTEXITCODE)." }
$dwSrc = Join-Path $Source 'direwolf'
if (Test-Path $dwSrc) {
    New-Item -ItemType Directory -Force -Path (Join-Path $target 'direwolf') | Out-Null
    Copy-Item (Join-Path $dwSrc '*') (Join-Path $target 'direwolf') -Force
    Say '  Direwolf-Fork nach direwolf\ kopiert.'
}

# git: the folder belongs to this user; normalise line endings for Windows (CRLF)
git config --global --add safe.directory ($target -replace '\\', '/') 2>$null
Push-Location $target
git reset -q --hard HEAD
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail 'git konnte die Dateien nicht vorbereiten.' }
Say ('  Stand: ' + (git log -1 --format='%h %cs %s'))
Pop-Location

# --- 4. Python packages -------------------------------------------------------
Say 'Installiere Python-Pakete ...' Cyan
& $py[0] @pyArgs -m pip install --user --disable-pip-version-check -q -r (Join-Path $target 'release\requirements.txt')
if ($LASTEXITCODE -ne 0) { Say 'WARNUNG: pip meldete einen Fehler - Internet pruefen, spaeter im Startmenue Punkt P.' Yellow }

# --- 5. configuration ---------------------------------------------------------
& $py[0] @pyArgs (Join-Path $target 'release\konfig.py')

# --- 6. shortcut --------------------------------------------------------------
if ((Ask 'Verknuepfung "TinyBox Start" auf dem Desktop anlegen? (j/n)' 'j') -match '^[jy]') {
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'TinyBox Start.lnk'))
    $lnk.TargetPath = Join-Path $target 'TinyBox-Start.bat'
    $lnk.WorkingDirectory = $target
    $lnk.Save()
}

Say ''
Say 'Installation fertig.' Green
Say "Starten: $target\TinyBox-Start.bat (oder die Desktop-Verknuepfung)."
Say 'Client im Browser: http://127.0.0.1:7744/'
Read-Host 'Enter zum Beenden'
