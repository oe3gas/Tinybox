@echo off
rem brocast Funktest - auf PC2 (FT-818, TinyBox) ausfuehren. Direwolf muss laufen.
title brocast Funktest - PC2 Station
cd /d "%~dp0\.."
py -3 -c "import cbor2, yaml" 2>nul || py -3 -m pip install --quiet -r requirements.txt
py -3 funktest\funktest.py station
pause
