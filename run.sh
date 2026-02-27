#!/bin/bash
# M3U Editör Pro - Linux/Mac Başlatma Scripti

echo "M3U Editör Pro başlatılıyor..."
echo ""

# Virtual environment kontrolü
if [ -d "venv" ]; then
    echo "Virtual environment bulundu, aktifleştiriliyor..."
    source venv/bin/activate
else
    echo "Virtual environment bulunamadı. Oluşturuluyor..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Bağımlılıklar yükleniyor..."
    pip install -r requirements.txt
fi

# Bağımlılık kontrolü
python -c "import streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Streamlit bulunamadı. Bağımlılıklar yükleniyor..."
    pip install -r requirements.txt
fi

# Uygulamayı başlat
echo ""
echo "Uygulama başlatılıyor..."
echo "Tarayıcınızda http://localhost:8501 adresini açın"
echo ""
streamlit run src/app.py
