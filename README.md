# 📺 M3U Editör Pro (Web)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

IPTV M3U playlist dosyalarını kolayca yönetmek, düzenlemek ve filtrelemek için geliştirilmiş modern bir web uygulaması.

![M3U Editor Pro](https://via.placeholder.com/800x400?text=M3U+Editor+Pro+Screenshot)

## ✨ Özellikler

### 📥 Çoklu Yükleme Desteği
- **🌐 URL'den Yükleme:** M3U linklerini doğrudan yapıştırarak yükleyin
- **📂 Dosya Yükleme:** Bilgisayarınızdaki M3U/M3U8 dosyalarını sürükle-bırak

### 🇹🇷 Akıllı Filtreleme
- Türk kanallarını otomatik tespit etme
- Grup bazlı akıllı arama
- Özel regex pattern ile hassas filtreleme

### ✏️ İnteraktif Düzenleme
- Kolay kanal seçimi (checkbox sistemi)
- Canlı tablo düzenleme
- Dinamik arama ve filtreleme
- Grup ve kanal adı bazlı arama

### 💾 Esnek İndirme
- Sadece seçili kanalları indir
- Tüm listeyi toplu indir
- Standart M3U formatında export

### 📊 Gerçek Zamanlı İstatistikler
- Toplam kanal sayısı
- Seçilen kanal sayısı
- Benzersiz grup sayısı

### 👥 Ziyaretçi Sayacı
- Toplam ziyaret sayısı
- Benzersiz ziyaretçi takibi
- İlk ve son ziyaret tarihleri
- Otomatik oturum yönetimi

## 🚀 Hızlı Başlangıç

### Gereksinimler
- Python 3.11 veya üzeri
- pip (Python paket yöneticisi)

### Kurulum

1. **Repository'yi klonlayın:**
```bash
git clone https://github.com/kullaniciadi/m3uedit.git
cd m3uedit
```

2. **Virtual environment oluşturun (önerilir):**
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. **Bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

4. **Uygulamayı başlatın:**
```bash
streamlit run src/app.py
```

**Not:** Eğer proje kök dizinindeyseniz `src/app.py` yolunu kullanın.

5. **Tarayıcınızda açın:**
   - Uygulama otomatik olarak açılacaktır
   - Manuel: http://localhost:8501

## 🐳 Docker ile Kullanım

```bash
# Docker Compose ile
docker-compose up -d

# Veya Docker ile
docker build -t m3uedit .
docker run -p 8501:8501 m3uedit
```

## 📖 Kullanım Kılavuzu

### 1️⃣ M3U Listesi Yükleme

**URL ile:**
1. Sol menüden "🌐 Linkten Yükle" seçin
2. M3U linkini yapıştırın
3. İsteğe bağlı: "🇹🇷 SADECE TR" filtresini aktifleştirin
4. "Listeyi Çek ve Tara" butonuna tıklayın

**Dosya ile:**
1. Sol menüden "📂 Dosya Yükle" seçin
2. M3U dosyasını sürükle-bırak veya seçin

### 2️⃣ Kanalları Düzenleme

- **Arama:** Üst kısımdaki arama kutusunu kullanın
- **Seçim:** İstediğiniz kanalların başındaki kutuyu işaretleyin
- **Düzenleme:** Tabloda doğrudan değişiklik yapabilirsiniz

### 3️⃣ Export

- **Seçili Kanallar:** Sadece işaretli kanalları indir
- **Tüm Liste:** Tüm kanalları indir

## 🔧 Yapılandırma

### TR Filtresi Pattern

Türk kanallar için kullanılan anahtar kelimeler:
- TR, TURK, TÜRK
- TURKIYE, TÜRKİYE
- YERLI, ULUSAL
- ISTANBUL

### SSL Sertifika Ayarları

Uygulama, bazı IPTV sağlayıcılarının SSL sertifika sorunlarını bypass eder. Güvenilir olmayan kaynaklardan liste çekerken dikkatli olun.

## 📁 Proje Yapısı

```
m3uedit/
├── .devcontainer/          # Dev Container yapılandırması
├── .streamlit/             # Streamlit yapılandırması
│   └── config.toml
├── docs/                   # Dokümantasyon
│   ├── API.md
│   ├── KULLANIM_KILAVUZU.md
│   └── DEPLOYMENT.md
├── src/                    # Kaynak kodlar
│   ├── app.py             # Ana uygulama
│   ├── app_backup.py
│   └── app_complex.py
├── static/                 # Statik dosyalar
│   └── styles.css
├── tests/                  # Test dosyaları
│   └── test_parser.py
├── utils/                  # Yardımcı modüller
│   ├── config.py          # Yapılandırma
│   └── visitor_counter.py # Ziyaretçi sayacı
├── .dockerignore
├── .gitattributes
├── .gitignore
├── CHANGELOG.md           # Değişiklik günlüğü
├── CONTRIBUTING.md        # Katkı rehberi
├── Dockerfile
├── docker-compose.yml
├── LICENSE                # MIT Lisans
├── README.md              # Bu dosya
└── requirements.txt       # Python bağımlılıkları
```

## 🛠️ Teknoloji Stack

- **Streamlit** - Web framework
- **Pandas** - Veri işleme
- **Python urllib** - HTTP istekleri
- **Re** - Regex işlemleri
- **Docker** - Containerization

## 📚 Dokümantasyon

- [Kullanım Kılavuzu](docs/KULLANIM_KILAVUZU.md)
- [API Dokümantasyonu](docs/API.md)
- [Deployment Rehberi](docs/DEPLOYMENT.md)
- [Katkı Rehberi](CONTRIBUTING.md)
- [Değişiklik Günlüğü](CHANGELOG.md)

## ⚠️ Bilinen Sınırlamalar

- Çok büyük M3U dosyaları (10,000+ kanal) performans sorunlarına yol açabilir
- SSL doğrulama devre dışı bırakıldığı için güvenilmeyen kaynaklara dikkat edin

## 🔐 Güvenlik Notları

- Sadece güvendiğiniz kaynaklardan M3U listesi yükleyin
- Uygulamanın public internete açılması önerilmez
- Localhost/local network kullanımı için tasarlanmıştır

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen [CONTRIBUTING.md](CONTRIBUTING.md) dosyasını okuyun.

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/yeni-ozellik`)
3. Değişikliklerinizi commit edin (`git commit -m 'feat: yeni özellik'`)
4. Branch'inizi push edin (`git push origin feature/yeni-ozellik`)
5. Pull request gönderin

## 📝 Lisans

Bu proje MIT lisansı altında açık kaynak kodludur. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 💬 Destek ve İletişim

- 🐛 **Bug Report:** [GitHub Issues](https://github.com/kullaniciadi/m3uedit/issues)
- 💡 **Feature Request:** [GitHub Issues](https://github.com/kullaniciadi/m3uedit/issues)
- 📧 **E-posta:** support@example.com
- 💬 **Discussions:** [GitHub Discussions](https://github.com/kullaniciadi/m3uedit/discussions)

## 🌟 Yıldız Geçmişi

[![Star History Chart](https://api.star-history.com/svg?repos=kullaniciadi/m3uedit&type=Date)](https://star-history.com/#kullaniciadi/m3uedit&Date)

## 👥 Katkıda Bulunanlar

Teşekkürler! ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

## 📊 İstatistikler

![GitHub stars](https://img.shields.io/github/stars/kullaniciadi/m3uedit?style=social)
![GitHub forks](https://img.shields.io/github/forks/kullaniciadi/m3uedit?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/kullaniciadi/m3uedit?style=social)

---

**⭐ Beğendiyseniz yıldız vermeyi unutmayın!**

<div align="center">
  Made with ❤️ by M3U Editor Pro Team
</div>
