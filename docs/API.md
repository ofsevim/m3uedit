# M3U Editör Pro - API Dokümantasyonu

## Fonksiyonlar

### parse_m3u_lines(iterator)
M3U formatındaki satırları parse eder.

**Parametreler:**
- `iterator`: Satır satır okunabilir obje (file, urllib response)

**Döndürür:**
- `list`: Kanal bilgilerini içeren dictionary listesi

**Örnek:**
```python
channels = parse_m3u_lines(file_object)
```

### filter_channels(channels, only_tr=False)
Kanalları filtreler.

**Parametreler:**
- `channels`: Kanal listesi
- `only_tr`: Sadece TR kanalları (bool)

**Döndürür:**
- `list`: Filtrelenmiş kanal listesi

### convert_df_to_m3u(df)
DataFrame'i M3U formatına çevirir.

**Parametreler:**
- `df`: Pandas DataFrame

**Döndürür:**
- `str`: M3U formatında string

### render_live_player(stream_url, height=420)
HTML video player oluşturur.

**Parametreler:**
- `stream_url`: Yayın URL'i
- `height`: Player yüksekliği (piksel)

**Döndürür:**
- `str`: HTML kodu

## Veri Yapıları

### Kanal Dictionary
```python
{
    "Grup": "Spor",
    "Kanal Adı": "Örnek Kanal",
    "URL": "http://example.com/stream.m3u8",
    "LogoURL": "http://example.com/logo.png",
    "Seç": False,
    "Favori": False,
    "Durum": "OK"
}
```

## Session State

### st.session_state.data
Ana kanal DataFrame'i

### st.session_state.visitor_counter
VisitorCounter instance

### st.session_state.session_id
Benzersiz session ID

### st.session_state.theme
Aktif tema ('Açık' veya 'Koyu')

### st.session_state.play_channel
Oynatılmakta olan kanal bilgisi

## Yapılandırma

Tüm yapılandırma seçenekleri `utils/config.py` dosyasında bulunur.

### Önemli Ayarlar

- `REQUEST_TIMEOUT`: URL istekleri için timeout (saniye)
- `DISABLE_SSL_VERIFY`: SSL doğrulamasını devre dışı bırak
- `TR_KEYWORDS`: TR filtresi için anahtar kelimeler
- `TABLE_HEIGHT`: Tablo yüksekliği (piksel)
- `MAX_FILE_SIZE_MB`: Maksimum dosya boyutu

## Visitor Counter API

### VisitorCounter.increment_visit(session_id)
Ziyaret sayısını artırır.

### VisitorCounter.get_stats()
İstatistikleri döndürür.

**Döndürür:**
```python
{
    'total_visits': 100,
    'unique_visitors': 50,
    'first_visit': '2025-01-01T00:00:00',
    'last_visit': '2025-01-15T12:30:00'
}
```

### VisitorCounter.reset_counter()
Sayacı sıfırlar.
