import json
import os
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


_global_vc_lock = threading.Lock()


class VisitorCounter:
    """Ziyaretçi sayacı - JSON dosyası ile ziyaretçi sayısını takip eder."""

    def __init__(self, counter_file="visitor_data.json"):
        # Streamlit Cloud uyumluluğu: yazılabilir dizin bul
        self.counter_file = self._resolve_path(counter_file)
        self.lock = _global_vc_lock
        self._ensure_file_exists()

    @staticmethod
    def _resolve_path(filename: str) -> str:
        """Yazılabilir bir dizinde dosya yolu döndürür."""
        # Zaten mutlak yol verilmişse olduğu gibi kullan
        if os.path.isabs(filename):
            return filename
        # /tmp varsa ve yazılabilirse orayı kullan (Cloud uyumlu)
        for d in ["/tmp", os.environ.get("TMPDIR", "")]:
            if d and os.path.isdir(d):
                try:
                    test = os.path.join(d, ".vc_test")
                    with open(test, "w") as f:
                        f.write("t")
                    os.remove(test)
                    return os.path.join(d, filename)
                except OSError:
                    continue
        return filename

    def _ensure_file_exists(self):
        """Sayaç dosyası yoksa oluştur."""
        with self.lock:
            if not os.path.exists(self.counter_file):
                initial_data = {
                    "total_visits": 0,
                    "unique_sessions": [],
                    "first_visit": datetime.now().isoformat(),
                    "last_visit": datetime.now().isoformat(),
                }
                self._save_data_lockless(initial_data)

    def _load_data_lockless(self):
        """Kilit olmadan sayaç verisini yükle (sadece dahili kullanım)."""
        try:
            with open(self.counter_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["unique_sessions"] = set(data.get("unique_sessions", []))
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Veri yükleme hatası: {e}", exc_info=True)
            return {
                "total_visits": 0,
                "unique_sessions": set(),
                "first_visit": datetime.now().isoformat(),
                "last_visit": datetime.now().isoformat(),
            }

    def _save_data_lockless(self, data):
        """Kilit olmadan sayaç verisini kaydet (sadece dahili kullanım)."""
        try:
            save_data = data.copy()
            # set -> list (JSON serileştirme için)
            sessions = data.get("unique_sessions", set())
            save_data["unique_sessions"] = list(sessions) if isinstance(sessions, set) else sessions

            with open(self.counter_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Veri kaydetme hatası: {e}", exc_info=True)

    def _load_data(self):
        """Sayaç verisini kilit kullanarak yükle."""
        with self.lock:
            return self._load_data_lockless()

    def _save_data(self, data):
        """Sayaç verisini kilit kullanarak kaydet."""
        with self.lock:
            self._save_data_lockless(data)

    def increment_visit(self, session_id=None):
        """Ziyaret sayısını artır."""
        with self.lock:
            data = self._load_data_lockless()
            data["total_visits"] += 1
            data["last_visit"] = datetime.now().isoformat()

            if session_id:
                data["unique_sessions"].add(session_id)

            self._save_data_lockless(data)
            return data["total_visits"]

    def get_stats(self):
        """İstatistikleri getir."""
        with self.lock:
            data = self._load_data_lockless()
            return {
                "total_visits": data["total_visits"],
                "unique_visitors": len(data["unique_sessions"]),
                "first_visit": data.get("first_visit", "Bilinmiyor"),
                "last_visit": data.get("last_visit", "Bilinmiyor"),
            }

    def reset_counter(self):
        """Sayacı sıfırla."""
        with self.lock:
            initial_data = {
                "total_visits": 0,
                "unique_sessions": set(),
                "first_visit": datetime.now().isoformat(),
                "last_visit": datetime.now().isoformat(),
            }
            self._save_data_lockless(initial_data)
