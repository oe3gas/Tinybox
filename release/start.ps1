# TinyBox start menu (Windows) - called by TinyBox-Start.bat in the installation folder.
#   TinyBox-Start.bat          menu
#   TinyBox-Start.bat 4        no menu: update and start choice 4 (for autostart)
# Choices: 1 client only, 2 client + TinyBox, 3 client + brocast listener, 4 all three.
# Before the start "git pull" fetches the newest version from GitHub; offline the
# installed version starts. Direwolf is started first if tbstart.conf says so.
param([string]$Wahl = '', [switch]$NoPull)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$Host.UI.RawUI.WindowTitle = 'TinyBox Start'

function Say($t, $c = 'Gray') { Write-Host $t -ForegroundColor $c }

function Read-Ini($path) {
    $h = @{}
    if (Test-Path $path) {
        foreach ($l in Get-Content $path) {
            if ($l -match '^\s*([A-Za-z_]+)\s*=\s*(.*?)\s*$') { $h[$Matches[1].ToLower()] = $Matches[2] }
        }
    }
    return $h
}
function Python {
    if (Get-Command py -ErrorAction SilentlyContinue) { return ,@('py', '-3') }
    return ,@('python')   # the comma keeps a one-element array an array
}
function Run-Py([string[]]$a) { $p = Python; & $p[0] @($p[1..9] | Where-Object { $_ }) @a }
function Pip-Install { Run-Py @('-m', 'pip', 'install', '--user', '--disable-pip-version-check', '-q', '-r', 'release\requirements.txt') }

function Is-Running($module) {
    # by the command line ("-m tinybox -c ..."): window titles are empty in Windows Terminal
    return [bool](Get-CimInstance Win32_Process -Filter "Name LIKE 'py%'" -ErrorAction SilentlyContinue |
                  Where-Object { $_.CommandLine -match ('-m\s+' + [regex]::Escape($module) + '\s') })
}
function Start-Bat($module, $name, $dir, $bat) {
    if (Is-Running $module) { Say "  $name laeuft schon - nicht noch einmal gestartet." Yellow; return }
    Say "  Starte $name ..." Green
    Start-Process cmd.exe -ArgumentList '/c', $bat -WorkingDirectory $dir
}

function Version-Line {
    $rel = (Select-String -Path 'prcore\release.py' -Pattern '^RELEASE = "(.*)"' | Select-Object -First 1)
    $cli = (Select-String -Path 'tbclient\__init__.py' -Pattern '^VERSION = "(.*)"' | Select-Object -First 1)
    $r = if ($rel) { $rel.Matches[0].Groups[1].Value } else { '?' }
    $c = if ($cli) { $cli.Matches[0].Groups[1].Value } else { '?' }
    $g = git log -1 --format='%h %cs' 2>$null
    return "Release $r  -  Client $c  -  Stand $g"
}

# --- menu ---------------------------------------------------------------------
$cfg = Read-Ini (Join-Path $root 'tbstart.conf')
while ($true) {
    if ($Wahl -notmatch '^[1-4]$') {
        Clear-Host
        Say '==================================================================' Cyan
        Say '  TinyBox Start' Cyan
        Say ('  ' + (Version-Line))
        Say '==================================================================' Cyan
        Say '   1  nur TBClient'
        Say '   2  TBClient + TinyBox'
        Say '   3  TBClient + brocast-Listener'
        Say '   4  alle drei (TBClient, TinyBox, brocast-Listener)'
        Say ''
        Say '   K  Konfiguration (Dialog erneut)'
        Say '   P  Python-Pakete neu installieren'
        Say '   Q  Beenden'
        if ($cfg['direwolf'] -eq 'yes') { Say '   (Direwolf wird automatisch mitgestartet)' DarkGray }
        $d = if ($cfg['tinybox'] -eq 'yes' -and $cfg['brocast'] -eq 'yes') { '4' }
             elseif ($cfg['tinybox'] -eq 'yes') { '2' } elseif ($cfg['brocast'] -eq 'yes') { '3' } else { '1' }
        $Wahl = Read-Host "Auswahl [$d]"
        if ([string]::IsNullOrWhiteSpace($Wahl)) { $Wahl = $d }
    }
    switch -regex ($Wahl.Trim()) {
        '^[kK]$' { Run-Py @('release\konfig.py'); $cfg = Read-Ini (Join-Path $root 'tbstart.conf'); Read-Host 'Enter'; $Wahl = ''; continue }
        '^[pP]$' { Pip-Install; Read-Host 'Enter'; $Wahl = ''; continue }
        '^[qQ]$' { exit 0 }
    }
    if ($Wahl -match '^[1-4]$') { break }
    $Wahl = ''
}
$box = $Wahl -in '2', '4'
$bro = $Wahl -in '3', '4'

# --- configuration present? -----------------------------------------------------
$need = @('tbclient.conf')
if ($box) { $need += 'tinybox.conf' }
if ($bro) { $need += 'brocast\brocastd.conf' }
$missing = @($need | Where-Object { -not (Test-Path (Join-Path $root $_)) })
if ($missing) {
    Say ('Es fehlt: ' + ($missing -join ', ')) Yellow
    if ((Read-Host 'Konfigurationsdialog jetzt starten? (j/n) [j]') -notmatch '^[nN]') { Run-Py @('release\konfig.py') }
    $missing = @($need | Where-Object { -not (Test-Path (Join-Path $root $_)) })
    if ($missing) { Say ('Start abgebrochen, es fehlt noch: ' + ($missing -join ', ')) Red; Read-Host 'Enter'; exit 1 }
    $cfg = Read-Ini (Join-Path $root 'tbstart.conf')
}

# --- update: git pull -----------------------------------------------------------
if (-not $NoPull) {
    Say 'Hole Updates von GitHub (git pull) ...' Cyan
    $before = git rev-parse HEAD 2>$null
    git pull --ff-only --quiet 2>&1 | ForEach-Object { Say "  $_" DarkGray }
    if ($LASTEXITCODE -ne 0) {
        Say '  Kein Update moeglich (offline oder lokale Aenderungen) - starte die vorhandene Version.' Yellow
    } else {
        $after = git rev-parse HEAD 2>$null
        if ($before -eq $after) { Say '  Schon aktuell.' Green }
        else {
            Say '  Neu:' Green
            git log --format='    %h %s' -n 15 "$before..$after"
            $changed = git diff --name-only $before $after
            if ($changed -match 'requirements\.txt$') { Say '  Python-Pakete werden aktualisiert ...' Cyan; Pip-Install }
            if ($changed -contains 'release/start.ps1') {
                Say '  Das Startmenue selbst wurde erneuert - starte es neu ...' Cyan
                & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'release\start.ps1') -Wahl $Wahl -NoPull
                exit $LASTEXITCODE
            }
        }
    }
}
Say ('  ' + (Version-Line))

# --- Direwolf -------------------------------------------------------------------
if ($cfg['direwolf'] -eq 'yes') {
    $dwDir = if ($cfg['direwolf_dir']) { $cfg['direwolf_dir'] } else { Join-Path $root 'direwolf' }
    $dwExe = if ($cfg['direwolf_exe']) { $cfg['direwolf_exe'] } else { 'direwolf-tinybox.exe' }
    $exe = Join-Path $dwDir $dwExe
    if (Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($dwExe)) -ErrorAction SilentlyContinue) {
        Say '  Direwolf laeuft schon.' Yellow
    } elseif (-not (Test-Path $exe)) {
        Say "  Direwolf nicht gefunden: $exe (tbstart.conf pruefen)" Red
    } elseif (-not (Test-Path (Join-Path $dwDir 'direwolf.conf'))) {
        Say "  direwolf.conf fehlt in $dwDir - Konfiguration (K) ausfuehren." Red
    } else {
        Say '  Starte Direwolf ...' Green
        Start-Process $exe -ArgumentList '-c', 'direwolf.conf' -WorkingDirectory $dwDir
        Start-Sleep -Seconds 8        # until the AGW and KISS ports are open
    }
}

# --- programs -------------------------------------------------------------------
if ($bro) { Start-Bat 'brocast.daemon' 'brocast-Listener' (Join-Path $root 'brocast') 'brocastd_dauerbetrieb.bat'; Start-Sleep 3 }
if ($box) { Start-Bat 'tinybox' 'TinyBox' $root 'tinybox_dauerbetrieb.bat'; Start-Sleep 3 }
Start-Bat 'tbclient' 'TBClient' $root 'tbclient.bat'
Start-Sleep 4
Start-Process 'http://127.0.0.1:7744/'
if ($bro) { Say '  brocast-Listener: http://127.0.0.1:7733/' }

Say ''
Say 'Gestartet. Jedes Programm laeuft in einem eigenen Fenster (beenden: Fenster schliessen).' Green
Start-Sleep 8
