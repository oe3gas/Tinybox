@echo off
rem DX-Zusammenfassung wieder aus der Windows-Aufgabenplanung entfernen.
schtasks /Delete /F /TN "TinyBox\DX-Zusammenfassung"
pause
