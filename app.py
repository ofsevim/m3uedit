"""
M3U Editör Pro - Ana Dosya
Streamlit Cloud için kök dizinde app.py gerekli
"""

# src/app.py dosyasını import et ve çalıştır
import sys
import os

# src dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Ana uygulamayı import et
from app import *
