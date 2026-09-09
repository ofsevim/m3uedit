# M3U Editör Pro - Yapılandırma Dosyası
# Bu dosyayı düzenleyerek uygulamanın davranışını özelleştirebilirsiniz

# === GENEL AYARLAR ===

# Streamlit sayfa başlığı
PAGE_TITLE = "M3U Editör Pro (Web)"

# Sayfa ikonu (emoji)
PAGE_ICON = "📺"

# === NETWORK & PROXY AYARLARI ===

# URL istekleri için zaman aşımı süresi (saniye)
REQUEST_TIMEOUT = 30

# SSL sertifika doğrulamasını devre dışı bırak (güvenilmeyen kaynaklar için)
# ⚠️ Güvenlik riski: Sadece güvendiğiniz kaynaklar için True yapın
DISABLE_SSL_VERIFY = True

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
DEFAULT_UPSTREAM_PROXY = ""

# === FİLTRELEME AYARLARI ===

# TR kanal tespiti için anahtar kelimeler
TR_KEYWORDS = [
    "TR", "TURK", "TÜRK", 
    "TURKIYE", "TÜRKİYE", 
    "YERLI", "ULUSAL", 
    "ISTANBUL"
]

# Varsayılan olarak TR filtresi aktif mi?
DEFAULT_TR_FILTER = True

# === TABLO & DÜZENLEME AYARLARI ===

# Tablo yüksekliği (piksel)
TABLE_HEIGHT = 600

# === EXPORT AYARLARI ===

# Varsayılan export dosya adı
DEFAULT_EXPORT_FILENAME = "iptv_listesi"

# === GELİŞMİŞ AYARLAR ===

# Maksimum dosya boyutu (MB, dosya yükleme için)
MAX_FILE_SIZE_MB = 50

# === URL SAĞLIK KONTROLÜ ===

# Paralel kontrol için maksimum iş parçacığı sayısı
HEALTH_CHECK_MAX_WORKERS = 30

# Sağlık kontrolü zaman aşımı (saniye)
HEALTH_CHECK_TIMEOUT = 3

# Varsayılan kontrol edilecek maksimum kanal sayısı (0 = Tümü)
HEALTH_CHECK_MAX_CHANNELS = 50

# === UYGULAMA VERSİYONU ===
APP_VERSION = "2.1.0"

