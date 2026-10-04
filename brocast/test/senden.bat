@echo off
rem Testseite an brocastd uebergeben:   senden.bat wetter   oder   senden.bat bulletin
rem Zurueckziehen:                      senden.bat wetter loeschen
cd /d "%~dp0"
if "%~1"=="" (
    echo Aufruf: senden.bat wetter^|bulletin [loeschen]
    exit /b 1
)
if /i "%~2"=="loeschen" (
    curl.exe -s -X DELETE -H "Host: 127.0.0.1" http://127.0.0.1:8090/api/v1/pages/test/%~1
) else (
    curl.exe -s -X PUT -H "Content-Type: application/json" --data-binary @%~1.json ^
        http://127.0.0.1:8090/api/v1/pages/test/%~1
)
echo.
