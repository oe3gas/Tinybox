@echo off
rem dxfeed von Hand aufrufen, z. B.:
rem   dxfeed collect       Cluster verbinden und Spots sammeln (laeuft bis Strg+C)
rem   dxfeed status        Spots der letzten 24 h, Verbindungszeit, cty.dat
rem   dxfeed show          die letzten 20 Spots
rem   dxfeed digest        Tageszusammenfassung nur anzeigen
rem   dxfeed digest --tinybox   ... und als Bulletin in den Eingang legen
rem   dxfeed cty-update    Laendertabelle jetzt holen
title [dxfeed] dxfeed %*
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m dxfeed -c dxfeed.conf %*
) else (
    python -m dxfeed -c dxfeed.conf %*
)
pause
