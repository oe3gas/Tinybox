@echo off
rem Run all TinyBox tests from the TinyBox folder.
rem "runtests.bat lang" also runs the long tests (tbtest on the simulated channel, ~2 min).
cd /d "%~dp0"
if /i "%~1"=="lang" set TB_LONG_TESTS=1
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m unittest discover -s tests -t . -v
) else (
    python -m unittest discover -s tests -t . -v
)
pause
