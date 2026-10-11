@echo off
rem TinyBox im Dauerbetrieb: nach einem Absturz automatisch neu starten.
rem Hinweis: Auch SHUTDOWN in der Sysop-Konsole fuehrt hier zu einem Neustart.
rem RESTART in der Sysop-Konsole startet sofort neu (ohne die 15 Sekunden).
rem Zum endgueltigen Beenden das Fenster schliessen oder Strg+C und J.
cd /d "%~dp0"
title [tinyb] TinyBox
set TINYBOX_LAUNCHER=1
:loop
py -3 -m tinybox -c tinybox.conf
if %errorlevel%==3 goto loop
echo.
echo [tinyb] %date% %time%  TinyBox beendet - Neustart in 15 Sekunden (Strg+C = abbrechen)
timeout /t 15
goto loop
