@echo OFF

setlocal

set UTILS_ROOT="%~dp0"
for %%F in (%UTILS_ROOT%\..) do set FAME_ROOT=%%~dpF
set VIRTUALENV="%FAME_ROOT%env"

if exist %VIRTUALENV% (
    echo [+] Using existing virtualenv.
) ELSE (
    echo [+] Creating virtualenv...
    call python -m virtualenv %VIRTUALENV% > nul
)

call %VIRTUALENV%\Scripts\activate

echo.
call python %*
call deactivate

endlocal
