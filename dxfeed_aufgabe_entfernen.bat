@echo off
rem DX-Zusammenfassung und DX-Live wieder aus der Windows-Aufgabenplanung entfernen.
schtasks /Delete /F /TN "TinyBox\DX-Zusammenfassung"
schtasks /Delete /F /TN "TinyBox\DX-Live" 2>nul
pause
