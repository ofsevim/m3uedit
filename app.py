"""
M3U Editör Pro - Giriş Noktası
Streamlit Cloud için kök dizinde app.py gerekli.
Çalıştırma: streamlit run app.py
"""
import importlib
import sys
import os

# src dizinini path'e ekle
src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# src/app.py'yi modül olarak yükle ve çalıştır
# Not: import * kullanmıyoruz çünkü set_page_config çakışmasına neden olur
importlib.import_module("app")
