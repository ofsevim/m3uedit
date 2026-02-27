# M3U Editör Pro - Proje Yapısı

## 📁 Dizin Yapısı

```
m3uedit/
├── .devcontainer/          # Dev Container yapılandırması
│   └── devcontainer.json   # VS Code Dev Container config
├── src/                    # Ana uygulama kaynak kodları
│   └── app.py             # Streamlit ana uygulaması
├── utils/                  # Yardımcı modüller
│   ├── m3u_parser.py      # M3U parser modülü (yeni)
│   ├── visitor_counter.py # Ziyaretçi sayacı
│   └── config.py          # Yapılandırma ayarları
├── static/                 # Statik dosyalar
│   └── styles.css         # Profesyonel CSS stilleri (yeni)
├── tests/                  # Test dosyaları
│   └── test_m3u_parser.py # Unit testler (yeni)
├── docs/                   # Dokümantasyon
├── data/                   # Uygulama verileri (oluşturulacak)
├── logs/                   # Log dosyaları (oluşturulacak)
├── .env.example           # Environment variables örneği
├── .gitignore            # Git ignore dosyası
├── docker-compose.yml    # Docker Compose yapılandırması
├── Dockerfile            # Docker image yapılandırması
├── Makefile              # Geliştirme komutları
├── start.sh              # Linux/Mac başlangıç script'i
├── start.bat             # Windows başlangıç script'i
├── requirements.txt      # Python bağımlılıkları
├── README.md             # Ana dokümantasyon
├── README_HF.md          # Hugging Face dokümantasyonu
└── PROJECT_STRUCTURE.md  # Bu dosya
```

## 🏗️ Mimari

### Modüler Yapı
```
app.py (UI Layer)
    ↓
m3u_parser.py (Business Logic)
    ↓
visitor_counter.py (Persistence)
    ↓
config.py (Configuration)
```

### Ana Bileşenler

#### 1. **UI Katmanı** (`src/app.py`)
- Streamlit tabanlı web arayüzü
- Kullanıcı etkileşimleri
- Veri görselleştirme
- Tema yönetimi (Dark/Light mode)

#### 2. **İş Mantığı Katmanı** (`utils/m3u_parser.py`)
- M3U formatı parsing
- Kanal filtreleme
- Export/Import işlemleri
- Tekrarlı kanal tespiti

#### 3. **Veri Katmanı** (`utils/visitor_counter.py`)
- Ziyaretçi takibi
- Session yönetimi
- JSON tabanlı persistence

#### 4. **Konfigürasyon Katmanı** (`utils/config.py`)
- Uygulama ayarları
- Network konfigürasyonu
- Filtreleme parametreleri

## 🔧 Teknoloji Stack'i

### Backend
- **Python 3.11+**: Ana programlama dili
- **Streamlit**: Web framework
- **Pandas**: Veri işleme ve analiz
- **urllib**: HTTP istekleri

### Frontend
- **HTML/CSS/JavaScript**: Temel web teknolojileri
- **Streamlit Components**: Özel UI bileşenleri
- **HLS.js**: Video streaming desteği

### Development
- **Docker**: Containerization
- **Docker Compose**: Multi-container yönetimi
- **Pytest**: Unit testing
- **Black/Flake8**: Code formatting/linting
- **Git**: Version control

### Deployment
- **Streamlit Cloud**: Cloud hosting
- **Docker Registry**: Container registry
- **GitHub Actions**: CI/CD pipeline

## 📊 Veri Akışı

### M3U Yükleme Akışı
```
1. Kullanıcı → URL/Dosya yükleme
2. app.py → HTTP isteği veya dosya okuma
3. m3u_parser.py → Parse işlemi
4. Pandas DataFrame → Veri yapısı
5. Streamlit UI → Tablo görüntüleme
```

### Export Akışı
```
1. Kullanıcı → Export seçeneği
2. app.py → Seçili verileri topla
3. m3u_parser.py → Format dönüşümü
4. Streamlit → Dosya indirme
```

## 🎨 UI/UX Özellikleri

### Tasarım Prensipleri
- **Modern ve Temiz**: Minimalist tasarım
- **Kullanıcı Dostu**: Sezgisel navigasyon
- **Responsive**: Mobil ve masaüstü uyumlu
- **Erişilebilir**: WCAG standartlarına uygun

### Bileşenler
- **Metrik Kartları**: Veri görselleştirme
- **DataTable**: İnteraktif tablolar
- **Sidebar**: Navigasyon ve filtreleme
- **Player**: Canlı video oynatıcı
- **Footer**: Bilgi ve linkler

## 🔐 Güvenlik

### Önlemler
- **SSL Bypass Kontrolü**: Sadece güvenilir kaynaklar
- **Input Validation**: Kullanıcı girişi doğrulama
- **Session Management**: Güvenli oturum yönetimi
- **File Size Limits**: Dosya boyutu sınırlamaları

### Best Practices
- **Environment Variables**: Hassas verilerin şifrelenmesi
- **Logging**: Detaylı log kayıtları
- **Error Handling**: Kullanıcı dostu hata mesajları
- **Rate Limiting**: API istek sınırlaması

## 🚀 Performans

### Optimizasyonlar
- **Caching**: Sık kullanılan verilerin önbelleğe alınması
- **Lazy Loading**: Gerektiğinde yükleme
- **Batch Processing**: Toplu işlemler
- **Async Operations**: Asenkron işlemler

### Monitoring
- **Ziyaretçi İstatistikleri**: Kullanım analizi
- **Performans Metrikleri**: Yükleme süreleri
- **Hata Oranları**: Sistem sağlığı
- **Kullanıcı Davranışları**: UX iyileştirmeleri

## 📈 Ölçeklenebilirlik

### Horizontal Scaling
- **Docker Containers**: Container-based scaling
- **Load Balancing**: Yük dengeleme
- **Database Sharding**: Veri parçalama
- **CDN Integration**: Content delivery network

### Vertical Scaling
- **Resource Optimization**: Kaynak kullanımı optimizasyonu
- **Database Indexing**: Veritabanı performansı
- **Caching Strategy**: Önbellek stratejisi
- **Code Optimization**: Kod optimizasyonu

## 🔄 Geliştirme İş Akışı

### 1. Local Development
```bash
# Sanal ortam oluştur
python -m venv venv

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı başlat
streamlit run src/app.py
```

### 2. Testing
```bash
# Unit testler
pytest tests/

# Code coverage
pytest --cov=src --cov=utils tests/

# Linting
flake8 src/ utils/

# Formatting
black src/ utils/
```

### 3. Deployment
```bash
# Docker build
docker build -t m3u-editor-pro .

# Docker run
docker run -p 8501:8501 m3u-editor-pro

# Docker Compose
docker-compose up -d
```

## 🤝 Katkı Kuralları

### Kod Standartları
- **PEP 8**: Python kod standartları
- **Type Hints**: Tür ipuçları
- **Docstrings**: Dokümantasyon
- **Test Coverage**: Test kapsamı

### Git Workflow
- **Feature Branches**: Özellik bazlı branch'ler
- **Pull Requests**: Code review
- **Commit Messages**: Anlamlı commit mesajları
- **Issue Tracking**: Sorun takibi

## 📚 Dokümantasyon

### Kullanıcı Dokümantasyonu
- **README.md**: Temel kullanım kılavuzu
- **API Documentation**: API referansı
- **Tutorials**: Adım adım rehberler
- **FAQ**: Sık sorulan sorular

### Geliştirici Dokümantasyonu
- **Architecture**: Sistem mimarisi
- **Code Comments**: Kod açıklamaları
- **Setup Guide**: Kurulum rehberi
- **Deployment Guide**: Deployment rehberi

## 🔮 Gelecek Özellikler

### Planlanan Özellikler
- [ ] **User Authentication**: Kullanıcı girişi
- [ ] **Cloud Storage**: Bulut depolama entegrasyonu
- [ ] **API Endpoints**: REST API desteği
- [ ] **Mobile App**: Mobil uygulama
- [ ] **Multi-language**: Çoklu dil desteği
- [ ] **Advanced Analytics**: Gelişmiş analitik
- [ ] **WebSocket Support**: Gerçek zamanlı güncellemeler
- [ ] **Plugin System**: Eklenti sistemi

### Roadmap
- **Q1 2025**: Temel özellikler ve stabilizasyon
- **Q2 2025**: API desteği ve cloud entegrasyonu
- **Q3 2025**: Mobil uygulama ve gelişmiş analitik
- **Q4 2025**: Enterprise özellikleri ve scaling

---

*Son güncelleme: 27 Şubat 2026*