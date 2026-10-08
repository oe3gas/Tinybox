@echo off
rem Test-TinyBox OE3XTC fuer den Forward-Test mit LinBPQ (nicht die Betriebs-TinyBox)
cd /d "%~dp0\..\.."
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m tinybox -c test\bpq\tinybox.conf
) else (
    python -m tinybox -c test\bpq\tinybox.conf
)
pause
