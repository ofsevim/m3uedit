@echo off
REM M3U Editör Pro - Windows Başlatma Scripti

echo M3U Editör Pro başlatılıyor...
echo.

REM Virtual environment kontrolü
if exist "venv\Scripts\activate.bat" (
    echo Virtual environment bulundu, aktifleştiriliyor...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment bulunamadı. Lütfen önce 'python -m venv venv' komutunu çalıştırın.
    pause
    exit /b 1
)

REM Bağımlılık kontrolü
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo Streamlit bulunamadı. Bağımlılıklar yükleniyor...
    pip install -r requirements.txt
)

REM Uygulamayı başlat
echo.
echo Uygulama başlatılıyor...
echo Tarayıcınızda http://localhost:8501 adresini açın
echo.
streamlit run src/app.py

pause
