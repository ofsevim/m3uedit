# M3U Editör Pro - Yapılandırma Dosyası
# Bu dosyayı düzenleyerek uygulamanın davranışını özelleştirebilirsiniz

import os
from pathlib import Path

from utils import __version__


def load_env(path=None):
    """Load simple KEY=value entries; process environment takes precedence."""
    path = Path(path) if path else Path.cwd() / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                if key.replace("_", "").isalnum():
                    os.environ.setdefault(key, value.strip().strip("\"'"))


def env_bool(key, default):
    value = os.environ.get(key)
    if value is None:
        return default
    if value.lower() not in ("true", "false", "1", "0"):
        raise ValueError(f"{key}: true veya false olmalı.")
    return value.lower() in ("true", "1")


load_env()

# === GENEL AYARLAR ===

# Streamlit sayfa başlığı
PAGE_TITLE = "M3U Editör Pro (Web)"

# Sayfa ikonu (emoji)
PAGE_ICON = "📺"

# === NETWORK & PROXY AYARLARI ===

# URL istekleri için zaman aşımı süresi (saniye)
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "30"))

# SSL sertifika doğrulamasını devre dışı bırak (güvenilmeyen kaynaklar için)
# ⚠️ Güvenlik riski: Sadece güvendiğiniz kaynaklar için True yapın
DISABLE_SSL_VERIFY = not env_bool("ENABLE_SSL_VERIFY", True)
ALLOW_PRIVATE_NETWORKS = env_bool("ALLOW_PRIVATE_NETWORKS", False)
PROXY_BIND_HOST = "0.0.0.0" if env_bool("ENABLE_LAN_SHARING", False) else "127.0.0.1"
PROXY_PUBLIC_BASE_URL = os.environ.get("PROXY_PUBLIC_BASE_URL", "").rstrip("/")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8502"))
PROXY_ALLOWED_ORIGIN = os.environ.get("PROXY_ALLOWED_ORIGIN", "")
ENABLE_VISITOR_COUNTER = env_bool("ENABLE_VISITOR_COUNTER", True)
ENABLE_LIVE_PLAYER = env_bool("ENABLE_LIVE_PLAYER", True)
ENABLE_URL_HEALTH_CHECK = env_bool("ENABLE_URL_HEALTH_CHECK", True)

# Varsayılan User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Yurt dışı & engelli kanallar için hazır Cihaz / User-Agent profilleri
# Birçok IPTV sunucusu tarayıcıları engellerken VLC, TiviMate veya Kodi'ye izin verir.
USER_AGENT_PROFILES = {
    "Standart (Tarayıcı)": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "TiviMate (IPTV)": "TiviMate/4.7.0 (Android TV)",
    "VLC Media Player": "VLC/3.0.18 LibVLC/3.0.18",
    "Smart IPTV (SIPTV)": "SmartIPTV/1.7.0 (WebOS; LG)",
    "Kodi IPTV Simple": "Kodi/20.2 (Windows NT 10.0; Win64; x64) IPTV-Simple",
    "Apple TV / iOS": "AppleCoreMedia/1.0.0.19J580 (Apple TV; CPU OS 15_6 like Mac OS X)",
}

# Varsayılan Upstream Proxy (örn: 'http://127.0.0.1:10808' veya boş)
DEFAULT_UPSTREAM_PROXY = os.environ.get("UPSTREAM_PROXY", "")

# === FİLTRELEME AYARLARI ===

# TR kanal tespiti için anahtar kelimeler
TR_KEYWORDS = ["TR", "TURK", "TÜRK", "TURKIYE", "TÜRKİYE", "YERLI", "ULUSAL", "ISTANBUL"]

# Varsayılan olarak TR filtresi aktif mi?
DEFAULT_TR_FILTER = env_bool("DEFAULT_TR_FILTER", True)

# === TABLO & DÜZENLEME AYARLARI ===

# Tablo yüksekliği (piksel)
TABLE_HEIGHT = 600

# === EXPORT AYARLARI ===

# Varsayılan export dosya adı
DEFAULT_EXPORT_FILENAME = "iptv_listesi"

# === GELİŞMİŞ AYARLAR ===

# Maksimum dosya boyutu (MB, dosya yükleme için)
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
if MAX_FILE_SIZE_MB <= 0 or REQUEST_TIMEOUT <= 0:
    raise ValueError("Dosya boyutu ve zaman aşımı pozitif olmalı.")

# === URL SAĞLIK KONTROLÜ ===

# Paralel kontrol için maksimum iş parçacığı sayısı
HEALTH_CHECK_MAX_WORKERS = 30

# Sağlık kontrolü zaman aşımı (saniye)
HEALTH_CHECK_TIMEOUT = 3

# Varsayılan kontrol edilecek maksimum kanal sayısı (0 = Tümü)
HEALTH_CHECK_MAX_CHANNELS = 50

# === UYGULAMA VERSİYONU ===
APP_VERSION = __version__
