# Startet LinBPQ in WSL (Debian) auf PC2 - Gegenstelle OE3GAS fuer den TinyBox-Forward-Test.
#
# Aufruf (PowerShell, aus C:\Tinybox):
#   powershell -ExecutionPolicy Bypass -File test\bpq\start_linbpq.ps1          starten
#   powershell -ExecutionPolicy Bypass -File test\bpq\start_linbpq.ps1 -Stop    beenden
#
# Voraussetzungen (einmalig, siehe Chat-Anleitung): WSL mit Debian, LinBPQ gebaut in ~/bpq,
# ~/bpq/bpq32.cfg vorhanden, .wslconfig mit networkingMode=mirrored.

param(
    [switch]$Stop,
    [string]$Distro = "Debian",
    [string]$BpqDir = "~/bpq",
    [int]$HttpPort = 8008
)

$ErrorActionPreference = "Stop"

function Test-Port([int]$Port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $Port); return $true } catch { return $false } finally { $c.Close() }
}

function Invoke-Wsl([string]$Cmd) {
    # one bash command inside the distro; returns its output
    return (& wsl.exe -d $Distro -- bash -lc $Cmd 2>&1)
}

# --- 1. WSL und Distribution vorhanden? -----------------------------------------
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Write-Host "WSL ist nicht installiert (wsl --install -d Debian)." -ForegroundColor Red
    exit 1
}
$distros = (& wsl.exe -l -q) -replace "`0", "" | Where-Object { $_.Trim() }
if ($distros -notcontains $Distro) {
    Write-Host "WSL-Distribution '$Distro' nicht gefunden. Vorhanden: $($distros -join ', ')" -ForegroundColor Red
    exit 1
}

# --- Beenden ----------------------------------------------------------------------
if ($Stop) {
    Invoke-Wsl "pkill -INT -x linbpq && echo 'LinBPQ beendet.' || echo 'LinBPQ lief nicht.'" | Write-Host
    exit 0
}

# --- 2. Netzwerkmodus pruefen (nur Hinweis) -----------------------------------------
$wslconfig = Join-Path $env:USERPROFILE ".wslconfig"
if (-not ((Test-Path $wslconfig) -and (Select-String -Path $wslconfig -Pattern "networkingMode\s*=\s*mirrored" -Quiet))) {
    Write-Host "Hinweis: $wslconfig enthaelt kein 'networkingMode=mirrored'." -ForegroundColor Yellow
    Write-Host "         Dann erreicht LinBPQ die TinyBox unter 127.0.0.1 eventuell nicht." -ForegroundColor Yellow
}

# --- 3. Laeuft LinBPQ schon? -------------------------------------------------------
$running = Invoke-Wsl "pgrep -x linbpq >/dev/null && echo yes || echo no"
if (($running | Select-Object -Last 1) -eq "yes") {
    Write-Host "LinBPQ laeuft bereits." -ForegroundColor Green
} else {
    # --- 4. Programm und Konfiguration vorhanden? -----------------------------------
    $check = Invoke-Wsl "cd $BpqDir 2>/dev/null || { echo NODIR; exit; }; [ -x ./linbpq ] || echo NOBIN; [ -f ./bpq32.cfg ] || echo NOCFG"
    if ($check -match "NODIR") { Write-Host "Ordner $BpqDir fehlt in $Distro." -ForegroundColor Red; exit 1 }
    if ($check -match "NOBIN") { Write-Host "$BpqDir/linbpq fehlt oder ist nicht ausfuehrbar." -ForegroundColor Red; exit 1 }
    if ($check -match "NOCFG") { Write-Host "$BpqDir/bpq32.cfg fehlt (Name klein schreiben!)." -ForegroundColor Red; exit 1 }

    # --- 5. In eigenem Fenster starten (Ctrl+C dort beendet LinBPQ) -------------------
    Write-Host "Starte LinBPQ in $Distro ($BpqDir) ..."
    Start-Process -FilePath "wsl.exe" -ArgumentList "-d $Distro -- bash -lc `"cd $BpqDir && exec ./linbpq`""
}

# --- 6. Auf die Weboberflaeche warten ---------------------------------------------
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    if (Test-Port $HttpPort) { $ok = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ok) {
    Write-Host "Port $HttpPort antwortet nach 30 s nicht - Meldungen im LinBPQ-Fenster pruefen." -ForegroundColor Red
    exit 1
}
Write-Host "LinBPQ laeuft:" -ForegroundColor Green
Write-Host "  Web       http://127.0.0.1:$HttpPort"
Write-Host "  Telnet    127.0.0.1:8010 (Sysop-Login aus bpq32.cfg)"
Write-Host "  FBB-Port  127.0.0.1:8011 (TinyBox ruft hier an)"
Start-Process "http://127.0.0.1:$HttpPort"
