@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: M3U Editör Pro - Başlangıç Script'i (Windows)
:: Bu script uygulamayı otomatik olarak kurar ve başlatır

:: Renkler
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "RED=%ESC%[91m"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "BLUE=%ESC%[94m"
set "NC=%ESC%[0m"

:: Logo
echo %BLUE%
echo   __  __ ____  _   _   _____           _           _ 
echo  ^|  \/  ^|  _ \^| ^| ^| ^| ^| ____^|_ __   __^| ^| ___ _ __^| ^|
echo  ^| ^|\/^| ^| ^|_)^| ^| ^| ^| ^| ^|  _^| ^| '_ \ / _\` ^|/ _ \ '__^| ^|
echo  ^| ^|  ^| ^|  __/^| ^|_^| ^| ^| ^|___^| ^| ^| ^| ^(_^| ^|  __/ ^|  ^| ^|
echo  ^|_^|  ^|_^|_^|    \___/  ^|_____^|_^| ^|_^\__,_^\___^|_^|  ^|_^|
echo %NC%
echo ======================================================
echo.

:: Fonksiyonlar
set "PYTHON_CMD="
set "PYTHON_VERSION="

:: Python kontrolü
echo %BLUE%[INFO]%NC% Python kontrol ediliyor...
where python >nul 2>nul
if %errorlevel% equ 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%i"
    set "PYTHON_CMD=python"
    echo %GREEN%[SUCCESS]%NC% Python !PYTHON_VERSION! bulundu
) else (
    where python3 >nul 2>nul
    if %errorlevel% equ 0 (
        for /f "tokens=2" %%i in ('python3 --version 2^>^&1') do set "PYTHON_VERSION=%%i"
        set "PYTHON_CMD=python3"
        echo %GREEN%[SUCCESS]%NC% Python !PYTHON_VERSION! bulundu
    ) else (
        echo %RED%[ERROR]%NC% Python bulunamadı!
        pause
        exit /b 1
    )
)

:: Sanal ortam kontrolü
echo %BLUE%[INFO]%NC% Sanal ortam kontrol ediliyor...
if exist venv (
    echo %GREEN%[SUCCESS]%NC% Sanal ortam bulundu
    set "VENV_EXISTS=1"
) else (
    if exist .venv (
        echo %GREEN%[SUCCESS]%NC% Sanal ortam bulundu
        set "VENV_EXISTS=1"
    ) else (
        echo %YELLOW%[WARNING]%NC% Sanal ortam bulunamadı
        set "VENV_EXISTS=0"
    )
)

:: Sanal ortam oluşturma
if "!VENV_EXISTS!"=="0" (
    set /p CREATE_VENV="Sanal ortam oluşturmak istiyor musunuz? (y/n): "
    if /i "!CREATE_VENV!"=="y" (
        echo %BLUE%[INFO]%NC% Sanal ortam oluşturuluyor...
        !PYTHON_CMD! -m venv venv
        if %errorlevel% neq 0 (
            echo %RED%[ERROR]%NC% Sanal ortam oluşturulamadı!
            pause
            exit /b 1
        )
        echo %GREEN%[SUCCESS]%NC% Sanal ortam oluşturuldu
        set "VENV_EXISTS=1"
    ) else (
        echo %YELLOW%[WARNING]%NC% Sanal ortam olmadan devam ediliyor...
    )
)

:: Sanal ortamı aktif et
if "!VENV_EXISTS!"=="1" (
    echo %BLUE%[INFO]%NC% Sanal ortam aktif ediliyor...
    if exist venv (
        call venv\Scripts\activate.bat
    ) else (
        if exist .venv (
            call .venv\Scripts\activate.bat
        )
    )
    if %errorlevel% neq 0 (
        echo %RED%[ERROR]%NC% Sanal ortam aktif edilemedi!
        pause
        exit /b 1
    )
    echo %GREEN%[SUCCESS]%NC% Sanal ortam aktif edildi
)

:: Bağımlılıkları yükle
echo %BLUE%[INFO]%NC% Bağımlılıklar yükleniyor...
pip install --upgrade pip
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%NC% Pip güncellenemedi!
    pause
    exit /b 1
)

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%NC% Bağımlılıklar yüklenemedi!
    pause
    exit /b 1
)
echo %GREEN%[SUCCESS]%NC% Bağımlılıklar yüklendi

:: Uygulamayı başlat
echo %BLUE%[INFO]%NC% Uygulama başlatılıyor...
echo.
echo %GREEN%======================================================%NC%
echo %GREEN%   M3U Editör Pro başarıyla başlatıldı!%NC%
echo %GREEN%======================================================%NC%
echo.
echo %YELLOW%Uygulama şu adreste çalışıyor:%NC%
echo   %BLUE%http://localhost:8501%NC%
echo.
echo %YELLOW%Durdurmak için:%NC% Ctrl+C
echo.

streamlit run src/app.py --server.port=8501 --server.address=0.0.0.0

:: Hata durumunda
if %errorlevel% neq 0 (
    echo %RED%[ERROR]%NC% Uygulama başlatılamadı!
    pause
    exit /b 1
)

endlocal