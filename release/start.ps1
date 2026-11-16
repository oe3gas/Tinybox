# Replaced by the control console (CR138, python -m tbstart) - TinyBox-Start.bat starts
# it directly. This file only stays for installations that update from the old start
# menu: its "git pull" restarts release\start.ps1 with -NoPull, and this hands over.
param([string]$Wahl = '', [switch]$NoPull)
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$a = @('-m', 'tbstart')
if ($NoPull) { $a += '--no-pull' }
if ($Wahl -match '^[1-4]$') { $a += $Wahl }
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 @a } else { & python @a }
exit $LASTEXITCODE
