# M3U Editör Pro - Mimari Dokümantasyonu

## Genel Bakış

M3U Editör Pro, Streamlit framework'ü üzerine inşa edilmiş bir web uygulamasıdır. Modüler yapısı sayesinde kolay genişletilebilir ve bakımı yapılabilir.

## Mimari Diyagram

```
┌─────────────────────────────────────────────────────────┐
│                    Kullanıcı Arayüzü                     │
│                    (Streamlit UI)                        │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   Ana Uygulama                           │
│                   (src/app.py)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Parser     │  │   Filter     │  │   Export     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  Yardımcı Modüller                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Config     │  │   Visitor    │  │   Utils      │  │
│  │              │  │   Counter    │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  Veri Katmanı                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Pandas     │  │   JSON       │  │   Session    │  │
│  │   DataFrame  │  │   Storage    │  │   State      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Katmanlar

### 1. Kullanıcı Arayüzü Katmanı
- **Teknoloji:** Streamlit
- **Sorumluluk:** Kullanıcı etkileşimi, görselleştirme
- **Bileşenler:**
  - Sidebar (yükleme, filtreleme)
  - Ana panel (tablo, istatistikler)
  - Player (canlı oynatıcı)

### 2. İş Mantığı Katmanı
- **Teknoloji:** Python
- **Sorumluluk:** Veri işleme, filtreleme, dönüştürme
- **Bileşenler:**
  - M3U Parser
  - TR Filter
  - Export Manager
  - URL Health Checker

### 3. Yardımcı Modüller
- **config.py:** Yapılandırma yönetimi
- **visitor_counter.py:** Ziyaretçi takibi
- **utils:** Genel yardımcı fonksiyonlar

### 4. Veri Katmanı
- **Pandas DataFrame:** Kanal verisi
- **JSON:** Kalıcı veri (ziyaretçi, geçmiş)
- **Session State:** Geçici veri

## Veri Akışı

### M3U Yükleme Akışı
```
URL/Dosya → parse_m3u_lines() → filter_channels() → DataFrame → Session State → UI
```

### Export Akışı
```
Session State → DataFrame → convert_df_to_m3u() → Download
```

### Filtreleme Akışı
```
User Input → TR_PATTERN → filter_channels() → Filtered DataFrame → UI
```

## Modüller

### src/app.py
Ana uygulama dosyası. Tüm UI ve iş mantığını içerir.

**Önemli Fonksiyonlar:**
- `parse_m3u_lines()`: M3U parse
- `filter_channels()`: Kanal filtreleme
- `convert_df_to_m3u()`: M3U export
- `render_live_player()`: Player HTML

### utils/config.py
Yapılandırma sabitleri.

**Önemli Değişkenler:**
- `PAGE_TITLE`, `PAGE_ICON`
- `REQUEST_TIMEOUT`
- `TR_KEYWORDS`
- `TABLE_HEIGHT`

### utils/visitor_counter.py
Ziyaretçi sayacı sınıfı.

**Önemli Metodlar:**
- `increment_visit()`
- `get_stats()`
- `reset_counter()`

## State Yönetimi

Streamlit'in `session_state` kullanılır:

```python
st.session_state.data          # Ana DataFrame
st.session_state.visitor_counter  # VisitorCounter instance
st.session_state.session_id    # Benzersiz ID
st.session_state.theme         # Tema
st.session_state.play_channel  # Oynatılan kanal
```

## Güvenlik

### Input Validation
- URL'ler regex ile kontrol edilir
- Dosya uzantıları sınırlandırılır
- Maksimum dosya boyutu

### SSL/TLS
- Varsayılan: SSL doğrulama kapalı
- Yapılandırılabilir: `config.py`

### XSS Koruması
- Streamlit otomatik escape yapar
- HTML injection önlenir

## Performans

### Optimizasyonlar
- Pandas DataFrame kullanımı
- Lazy loading
- Caching (Streamlit @st.cache)

### Sınırlamalar
- Maksimum 10,000 kanal önerilir
- Büyük dosyalar için memory kullanımı

## Genişletilebilirlik

### Yeni Özellik Ekleme
1. `src/app.py` içinde fonksiyon ekle
2. UI bileşeni ekle
3. Session state güncelle

### Yeni Modül Ekleme
1. `utils/` altında yeni dosya
2. `src/app.py` içinde import
3. Dokümantasyon güncelle

## Test Stratejisi

### Unit Tests
- Parser fonksiyonları
- Filter fonksiyonları
- Export fonksiyonları

### Integration Tests
- End-to-end akışlar
- UI testleri

### Manual Tests
- Tarayıcı uyumluluğu
- Responsive design
- Performans

## Deployment

### Yerel
```bash
streamlit run src/app.py
```

### Docker
```bash
docker-compose up
```

### Cloud
- Streamlit Cloud
- Heroku
- AWS EC2

## Monitoring

### Logs
- Streamlit logs
- Application logs
- Error tracking

### Metrics
- Ziyaretçi sayısı
- Kullanım istatistikleri
- Hata oranları

## Gelecek Planları

- [ ] Database entegrasyonu
- [ ] Kullanıcı hesapları
- [ ] Playlist paylaşımı
- [ ] API endpoint'leri
- [ ] Mobile app
- [ ] Gelişmiş filtreleme
- [ ] EPG desteği
- [ ] Çoklu dil desteği
