@echo off
rem fwdsim - Forward-Testpartner fuer TinyBox
rem   fwdsim cases               Testfaelle anzeigen
rem   fwdsim run --stub          alle Faelle gegen den fwdsim-Stellvertreter (Selbsttest)
rem   fwdsim run T04 T05         Faelle gegen die echte TinyBox (TCP)
rem   fwdsim run T04 --agw       dasselbe ueber Direwolf
rem   fwdsim serve / call / send / list / show / reset
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m fwdsim %*
) else (
    python -m fwdsim %*
)
