@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 veya ustu gerekli. Python'u kurup tekrar deneyin.
    exit /b 1
)
python bootstrap.py %*
exit /b %errorlevel%
