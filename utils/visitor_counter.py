import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class VisitorCounter:
    """Ziyaretçi sayacı - JSON dosyası ile ziyaretçi sayısını takip eder."""

    def __init__(self, counter_file="visitor_data.json"):
        # Streamlit Cloud uyumluluğu: yazılabilir dizin bul
        self.counter_file = self._resolve_path(counter_file)
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
        if not os.path.exists(self.counter_file):
            initial_data = {
                "total_visits": 0,
                "unique_sessions": [],
                "first_visit": datetime.now().isoformat(),
                "last_visit": datetime.now().isoformat(),
            }
            self._save_data(initial_data)

    def _load_data(self):
        """Sayaç verisini yükle."""
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

    def _save_data(self, data):
        """Sayaç verisini kaydet."""
        try:
            save_data = data.copy()
            # set -> list (JSON serileştirme için)
            sessions = data.get("unique_sessions", set())
            save_data["unique_sessions"] = list(sessions) if isinstance(sessions, set) else sessions

            with open(self.counter_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error(f"Veri kaydetme hatası: {e}", exc_info=True)

    def increment_visit(self, session_id=None):
        """Ziyaret sayısını artır."""
        data = self._load_data()
        data["total_visits"] += 1
        data["last_visit"] = datetime.now().isoformat()

        if session_id:
            data["unique_sessions"].add(session_id)

        self._save_data(data)
        return data["total_visits"]

    def get_stats(self):
        """İstatistikleri getir."""
        data = self._load_data()
        return {
            "total_visits": data["total_visits"],
            "unique_visitors": len(data["unique_sessions"]),
            "first_visit": data.get("first_visit", "Bilinmiyor"),
            "last_visit": data.get("last_visit", "Bilinmiyor"),
        }

    def reset_counter(self):
        """Sayacı sıfırla."""
        initial_data = {
            "total_visits": 0,
            "unique_sessions": set(),
            "first_visit": datetime.now().isoformat(),
            "last_visit": datetime.now().isoformat(),
        }
        self._save_data(initial_data)
