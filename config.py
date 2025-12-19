# M3U Editör Pro - Yapılandırma Dosyası
# Bu dosyayı düzenleyerek uygulamanın davranışını özelleştirebilirsiniz

# === GENEL AYARLAR ===

# Streamlit sayfa başlığı
PAGE_TITLE = "M3U Editör Pro (Web)"

# Sayfa ikonu (emoji)
PAGE_ICON = "📺"

# === NETWORK AYARLARI ===

# URL istekleri için zaman aşımı süresi (saniye)
REQUEST_TIMEOUT = 30

# SSL sertifika doğrulamasını devre dışı bırak (güvenilmeyen kaynaklar için)
# ⚠️ Güvenlik riski: Sadece güvendiğiniz kaynaklar için True yapın
DISABLE_SSL_VERIFY = True

# User-Agent header (bazı sunucular bot tespiti yapar)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

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

# === TABLO AYARLARI ===

# Tablo yüksekliği (piksel)
TABLE_HEIGHT = 600

# Sayfa başına maksimum kayıt sayısı (0 = sınırsız)
# Not: Çok büyük listeler performans sorunlarına yol açabilir
MAX_ROWS_PER_PAGE = 0

# === EXPORT AYARLARI ===

# Varsayılan export dosya adı
DEFAULT_EXPORT_FILENAME = "iptv_listesi"

# Export dosya uzantısı
EXPORT_FILE_EXTENSION = ".m3u"

# === GELİŞMİŞ AYARLAR ===

# Debug modu (daha fazla log mesajı)
DEBUG_MODE = False

# Cache süresi (saniye, 0 = cache yok)
CACHE_TTL = 300

# Maksimum dosya boyutu (MB, dosya yükleme için)
MAX_FILE_SIZE_MB = 50
