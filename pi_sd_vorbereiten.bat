@echo off
rem ======================================================================
rem  Feeder-Pi: Ordner feederpi\ auf die SD-Karte schreiben.
rem  Vorher Raspberry Pi OS Lite (32-bit) mit dem Raspberry Pi Imager auf
rem  die Karte schreiben und die Karte neu einstecken (Laufwerk "bootfs").
rem    pi_sd_vorbereiten.bat                  Boot-Partition selbst suchen
rem    pi_sd_vorbereiten.bat --ziel F:\       Laufwerk angeben
rem    pi_sd_vorbereiten.bat --locator JN88BN,JN78WM
rem  Anleitung: feederpi\README.md
rem ======================================================================
cd /d "%~dp0"
title [feederpi] SD-Karte vorbereiten
py -3 "%~dp0pi_sd_vorbereiten.py" %*
pause
