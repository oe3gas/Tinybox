@echo off
rem GeoSphere-Aufgaben wieder aus der Windows-Aufgabenplanung entfernen.
schtasks /Delete /F /TN "brocast\GeoSphere Wetter"
schtasks /Delete /F /TN "brocast\GeoSphere Warnungen"
schtasks /Delete /F /TN "brocast\GeoSphere Prognose"
pause
