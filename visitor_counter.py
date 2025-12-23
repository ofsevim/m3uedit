import json
import os
from datetime import datetime
from pathlib import Path

class VisitorCounter:
    """Ziyaretçi sayacı sınıfı - JSON dosyası kullanarak ziyaretçi sayısını takip eder"""
    
    def __init__(self, counter_file='visitor_data.json'):
        self.counter_file = counter_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Sayaç dosyası yoksa oluştur"""
        if not os.path.exists(self.counter_file):
            initial_data = {
                'total_visits': 0,
                'unique_sessions': set(),
                'first_visit': datetime.now().isoformat(),
                'last_visit': datetime.now().isoformat()
            }
            self._save_data(initial_data)
    
    def _load_data(self):
        """Sayaç verisini yükle"""
        try:
            with open(self.counter_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Set'i tekrar oluştur
                data['unique_sessions'] = set(data.get('unique_sessions', []))
                return data
        except Exception as e:
            print(f"Veri yükleme hatası: {e}")
            return {
                'total_visits': 0,
                'unique_sessions': set(),
                'first_visit': datetime.now().isoformat(),
                'last_visit': datetime.now().isoformat()
            }
    
    def _save_data(self, data):
        """Sayaç verisini kaydet"""
        try:
            # Set'i listeye çevir (JSON için)
            save_data = data.copy()
            save_data['unique_sessions'] = list(data['unique_sessions'])
            
            with open(self.counter_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Veri kaydetme hatası: {e}")
    
    def increment_visit(self, session_id=None):
        """Ziyaret sayısını artır"""
        data = self._load_data()
        data['total_visits'] += 1
        data['last_visit'] = datetime.now().isoformat()
        
        if session_id:
            data['unique_sessions'].add(session_id)
        
        self._save_data(data)
        return data['total_visits']
    
    def get_stats(self):
        """İstatistikleri getir"""
        data = self._load_data()
        return {
            'total_visits': data['total_visits'],
            'unique_visitors': len(data['unique_sessions']),
            'first_visit': data.get('first_visit', 'Bilinmiyor'),
            'last_visit': data.get('last_visit', 'Bilinmiyor')
        }
    
    def reset_counter(self):
        """Sayacı sıfırla"""
        initial_data = {
            'total_visits': 0,
            'unique_sessions': set(),
            'first_visit': datetime.now().isoformat(),
            'last_visit': datetime.now().isoformat()
        }
        self._save_data(initial_data)
