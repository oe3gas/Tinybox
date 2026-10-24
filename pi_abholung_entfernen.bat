@echo off
rem Abholung vom Feeder-Pi aus der Windows-Aufgabenplanung entfernen.
rem Wieder einrichten: pi_abholung_einrichten.bat
rem Sollen die Bulletins wieder auf diesem PC entstehen: dxfeed.conf.vor-feederpi
rem zurueck in dxfeed.conf umbenennen, dann dxfeed_aufgabe_einrichten.bat und
rem geosphere_aufgaben_einrichten.bat ausfuehren.
schtasks /Delete /F /TN "TinyBox\Pi-Abholung"
pause
