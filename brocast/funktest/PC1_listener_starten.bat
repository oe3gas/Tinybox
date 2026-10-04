@echo off
rem brocast Funktest - auf PC1 (TS-790) ausfuehren. Direwolf muss laufen.
title brocast Funktest - PC1 Listener
cd /d "%~dp0\.."
py -3 -c "import cbor2, yaml" 2>nul || py -3 -m pip install --quiet -r requirements.txt
py -3 funktest\funktest.py listener
echo.
echo Ergebnis: funktest\ergebnis_listener.txt
pause
