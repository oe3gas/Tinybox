# Kopiert die geänderten brocast-Dateien (AGW/KISS, Sendepausen) von E:\Tinybox nach Z:\Tinybox.
# Verzeichnisse werden angelegt. brocastd.conf wird als brocastd.conf.neu abgelegt,
# damit die Konfiguration auf PC2 (Modus station, Rufzeichen) nicht überschrieben wird.
#
# Aufruf:  powershell -ExecutionPolicy Bypass -File E:\Tinybox\kopiere_nach_nas.ps1
#          ... -WhatIf    zeigt nur an, was kopiert würde

param(
    [string]$Quelle = "E:\Tinybox",
    [string]$Ziel   = "Z:\Tinybox",
    [switch]$WhatIf
)

$dateien = @(
    "brocast\brocast\agw.py",          # neu
    "brocast\brocast\carousel.py",
    "brocast\brocast\config.py",
    "brocast\brocast\daemon.py",
    "brocast\brocast\frame.py",
    "brocast\brocast\txlog.py",
    "brocast\brocast\web\app.js",
    "brocast\funktest\funktest.py",
    "brocast\tests\test_daemon.py",
    "brocast\README.md"
)
# Konfiguration: nicht überschreiben, sondern daneben legen
$konfig = @{ "brocast\brocastd.conf" = "brocast\brocastd.conf.neu" }

if (-not (Test-Path $Ziel)) {
    Write-Host "Ziel $Ziel nicht erreichbar (NAS verbunden?)" -ForegroundColor Red
    exit 1
}

$fehler = 0
function Kopiere([string]$von, [string]$nach) {
    $src = Join-Path $Quelle $von
    $dst = Join-Path $Ziel $nach
    if (-not (Test-Path $src)) {
        Write-Host "FEHLT   $src" -ForegroundColor Red
        $script:fehler++
        return
    }
    $dir = Split-Path $dst -Parent
    if ($WhatIf) {
        Write-Host "WÜRDE   $src -> $dst"
        return
    }
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "KOPIERT $nach" -ForegroundColor Green
}

foreach ($d in $dateien) { Kopiere $d $d }
foreach ($k in $konfig.Keys) { Kopiere $k $konfig[$k] }

Write-Host ""
if ($fehler) {
    Write-Host "$fehler Datei(en) fehlen." -ForegroundColor Red
    exit 1
}
Write-Host "Fertig. Auf PC2: brocastd.conf.neu mit der bestehenden brocastd.conf abgleichen" -ForegroundColor Yellow
Write-Host "(neuer Abschnitt [direwolf] statt [kiss], burst_frames / burst_gap_s unter [station])." -ForegroundColor Yellow
