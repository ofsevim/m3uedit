# 📺 M3U Editör Pro

<div align="center">

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**Profesyonel IPTV M3U Playlist Yönetim Aracı**

[🚀 Hızlı Başlangıç](#-hızlı-başlangıç) • [✨ Özellikler](#-özellikler) • [📖 Kullanım](#-kullanım) • [🛠️ Geliştirme](#️-geliştirme) • [🤝 Katkı](#-katkı)

</div>

## 📋 İçindekiler

- [Genel Bakış](#-genel-bakış)
- [Özellikler](#-özellikler)
- [Hızlı Başlangıç](#-hızlı-başlangıç)
- [Kullanım](#-kullanım)
- [Proje Yapısı](#-proje-yapısı)
- [Geliştirme](#️-geliştirme)
- [Dağıtım](#-dağıtım)
- [Katkı](#-katkı)
- [Lisans](#-lisans)
- [Destek](#-destek)

## 🎯 Genel Bakış

**M3U Editör Pro**, IPTV M3U playlist dosyalarını profesyonel bir şekilde yönetmek, düzenlemek ve filtrelemek için geliştirilmiş modern bir web uygulamasıdır. Kullanıcı dostu arayüzü ve güçlü özellikleriyle IPTV içerik yöneticileri için ideal bir çözüm sunar.

### 🎨 Temel Özellikler

- **🌐 Çoklu Kaynaktan Yükleme**: URL veya dosya yükleme
- **🇹🇷 Akıllı Filtreleme**: Türk kanallarını otomatik tespit
- **✏️ İnteraktif Düzenleme**: Gerçek zamanlı tablo düzenleme
- **💾 Esnek Export**: Çoklu format desteği (M3U, JSON, CSV)
- **📊 Detaylı İstatistikler**: Kanal ve grup bazlı analizler
- **👥 Ziyaretçi Takibi**: Otomatik ziyaretçi sayacı

## ✨ Özellikler

### 📥 Veri Yükleme
- **URL'den Yükleme**: M3U linklerini doğrudan yapıştırma
- **Dosya Yükleme**: M3U/M3U8 dosyalarını sürükle-bırak
- **SSL Bypass**: Güvenilmeyen kaynaklar için SSL doğrulama atlama
- **Otomatik Kodlama**: UTF-8 ve diğer kodlamaları otomatik tespit

### 🔍 Filtreleme ve Arama
- **TR Filtresi**: Türk kanallarını otomatik tespit
- **Grup Bazlı Filtreleme**: Kanal gruplarına göre filtreleme
- **Akıllı Arama**: Grup ve kanal adı bazlı arama
- **Regex Desteği**: Gelişmiş regex pattern filtreleme

### ✏️ Düzenleme ve Yönetim
- **Checkbox Sistemi**: Kolay kanal seçimi
- **Toplu İşlemler**: Tümünü seç/seçimi kaldır
- **Çift Temizleme**: Tekrarlı kanalları otomatik temizleme
- **Canlı Düzenleme**: Tabloda doğrudan değişiklik yapma

### 💾 Export ve Paylaşım
- **Format Desteği**: M3U, JSON, CSV export
- **Seçimli Export**: Sadece seçili kanalları indirme
- **Otomatik İsimlendirme**: Tarih ve saat bazlı dosya adları
- **Batch İşlemler**: Toplu export ve import

### 📊 Analitik ve İzleme
- **Kanal İstatistikleri**: Toplam kanal, seçili kanal, grup sayısı
- **Ziyaretçi Sayacı**: Benzersiz ziyaretçi takibi
- **Performans Metrikleri**: Yükleme süreleri ve hata oranları
- **Geçmiş Kaydı**: İşlem geçmişi takibi

### 🎨 Kullanıcı Arayüzü
- **Modern Tasarım**: Temiz ve profesyonel arayüz
- **Dark/Light Mode**: Kullanıcı tercihine göre tema
- **Responsive Tasarım**: Mobil ve masaüstü uyumlu
- **Türkçe Arayüz**: Yerelleştirilmiş kullanıcı deneyimi

## 🚀 Hızlı Başlangıç

### Gereksinimler

- **Python 3.11** veya üzeri
- **pip** (Python paket yöneticisi)
- **Git** (opsiyonel)

### Kurulum

#### 1. Repository'yi Klonlayın

```bash
git clone https://github.com/yourusername/m3uedit.git
cd m3uedit
```

#### 2. Sanal Ortam Oluşturun (Önerilen)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

#### 3. Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

#### 4. Uygulamayı Başlatın

```bash
streamlit run src/app.py
```

#### 5. Tarayıcınızda Açın

- Otomatik olarak açılacaktır: [http://localhost:8501](http://localhost:8501)
- Manuel erişim için yukarıdaki linki kullanın

### 🐳 Docker ile Kullanım

```bash
# Docker image oluşturma
docker build -t m3u-editor .

# Container çalıştırma
docker run -p 8501:8501 m3u-editor
```

### 🏗️ Dev Container (VS Code)

Proje VS Code Dev Container desteği ile gelir:

1. VS Code'da projeyi açın
2. `F1` tuşuna basıp "Reopen in Container" seçin
3. Container otomatik olarak kurulup başlatılacaktır

## 📖 Kullanım

### 1. M3U Listesi Yükleme

#### URL ile Yükleme
1. Sol menüden "🌐 Linkten Yükle" seçin
2. M3U linkini yapıştırın
3. İsteğe bağlı: "🇹🇷 SADECE TR" filtresini aktifleştirin
4. "Listeyi Çek ve Tara" butonuna tıklayın

#### Dosya ile Yükleme
1. Sol menüden "📂 Dosya Yükle" seçin
2. M3U dosyasını sürükle-bırak veya seçin
3. Dosya otomatik olarak parse edilecektir

### 2. Kanalları Düzenleme

#### Temel İşlemler
- **Arama**: Üst kısımdaki arama kutusunu kullanın
- **Seçim**: İstediğiniz kanalların başındaki kutuyu işaretleyin
- **Düzenleme**: Tabloda doğrudan değişiklik yapabilirsiniz

#### Toplu İşlemler
- **Tümünü Seç**: Tüm kanalları işaretle
- **Seçimi Kaldır**: Tüm seçimleri temizle
- **Çiftleri Temizle**: Tekrarlı kanalları kaldır
- **Seçiliyi Sil**: İşaretli kanalları listeden çıkar

### 3. Export İşlemleri

#### Export Formatları
- **M3U**: Standart IPTV playlist formatı
- **JSON**: API entegrasyonları için
- **CSV**: Excel ve diğer tablo programları için

#### Export Seçenekleri
- **Seçili Kanallar**: Sadece işaretli kanalları export et
- **Tüm Liste**: Tüm kanalları export et
- **Filtrelenmiş Liste**: Aktif filtreye göre export et

### 4. Canlı Oynatıcı

1. "Canlı Oynatıcı (Test Et)" bölümüne gidin
2. Oynatılacak URL'yi girin
3. "OYNAT" butonuna tıklayın
4. Player otomatik olarak başlayacaktır

## 🏗️ Proje Yapısı

```
m3uedit/
├── .devcontainer/          # Dev Container yapılandırması
│   └── devcontainer.json
├── src/                    # Ana uygulama kaynak kodları
│   └── app.py             # Streamlit ana uygulaması
├── utils/                  # Yardımcı modüller
│   ├── m3u_parser.py      # M3U parser modülü
│   ├── visitor_counter.py # Ziyaretçi sayacı
│   └── config.py          # Yapılandırma ayarları
├── static/                 # Statik dosyalar
│   └── styles.css         # CSS stilleri
├── tests/                  # Test dosyaları
├── docs/                   # Dokümantasyon
├── requirements.txt        # Python bağımlılıkları
├── README.md              # Bu dosya
└── .gitignore             # Git ignore dosyası
```

### Modüller

#### `m3u_parser.py`
- M3U formatını parse etme
- Kanalları filtreleme
- Export formatlarına dönüştürme
- Tekrarlı kanalları tespit etme

#### `visitor_counter.py`
- Ziyaretçi sayacı yönetimi
- Session takibi
- İstatistik toplama

#### `config.py`
- Uygulama ayarları
- Network konfigürasyonu
- Filtreleme parametreleri

## 🛠️ Geliştirme

### Geliştirme Ortamı Kurulumu

```bash
# Repository'yi klonla
git clone https://github.com/yourusername/m3uedit.git
cd m3uedit

# Sanal ortam oluştur
python -m venv venv

# Sanal ortamı aktif et (Windows)
venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Geliştirme bağımlılıklarını yükle
pip install -r requirements-dev.txt  # Eğer varsa
```

### Kod Standartları

```bash
# Kod formatlama
black src/ utils/

# Lint kontrolü
flake8 src/ utils/

# Type checking
mypy src/ utils/
```

### Test Çalıştırma

```bash
# Tüm testleri çalıştır
pytest tests/

# Test coverage raporu
pytest --cov=src --cov=utils tests/
```

### Debug Modu

```bash
# Debug modunda çalıştır
streamlit run src/app.py --logger.level=debug
```

## 🌐 Dağıtım

### Streamlit Cloud

1. GitHub repository'nizi Streamlit Cloud'a bağlayın
2. `src/app.py` dosyasını ana dosya olarak seçin
3. Bağımlılıkları otomatik olarak yüklenecektir

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Self-Hosted Deployment

```bash
# Production için gunicorn kullanımı
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.app:app
```

## 🤝 Katkı

Katkılarınızı bekliyoruz! Lütfen aşağıdaki adımları izleyin:

### 1. Fork Yapın
Repository'yi fork edin ve local'inize klonlayın.

### 2. Branch Oluşturun
```bash
git checkout -b feature/amazing-feature
```

### 3. Değişikliklerinizi Yapın
Kodunuzu yazın ve test edin.

### 4. Commit Edin
```bash
git commit -m 'Add some amazing feature'
```

### 5. Push Edin
```bash
git push origin feature/amazing-feature
```

### 6. Pull Request Gönderin
GitHub üzerinden pull request gönderin.

### Katkı Kuralları

- **Kod Stili**: Black ve Flake8 standartlarını takip edin
- **Test Yazımı**: Yeni özellikler için test yazın
- **Dokümantasyon**: Değişiklikleri README'de belgeleyin
- **Commit Mesajları**: Anlamlı commit mesajları kullanın

## 📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

```
MIT License

Copyright (c) 2025 M3U Editör Pro

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

## 💬 Destek

### Sorun Bildirme
1. [GitHub Issues](https://github.com/yourusername/m3uedit/issues) sayfasını ziyaret edin
2. Yeni issue oluşturun
3. Sorununuzu detaylı bir şekilde açıklayın

### SSS (Sık Sorulan Sorular)

#### Q: Çok büyük M3U dosyalarını yükleyebilir miyim?
A: Evet, ancak çok büyük dosyalar (10,000+ kanal) performans sorunlarına yol açabilir.

#### Q: SSL sertifika hataları nasıl çözülür?
A: Uygulama SSL doğrulamayı atlayabilir, ancak sadece güvendiğiniz kaynaklar için kullanın.

#### Q: Türkçe dışında dil desteği var mı?
A: Şu anda sadece Türkçe arayüz mevcut, ancak dil dosyaları eklenebilir.

#### Q: Uygulamayı public internete açabilir miyim?
A: Localhost/local network kullanımı için tasarlanmıştır. Public deployment için ek güvenlik önlemleri alın.

### İletişim

- **GitHub Issues**: [Issue Tracker](https://github.com/yourusername/m3uedit/issues)
- **Email**: support@example.com
- **Discord**: [Sunucu Linki](https://discord.gg/example)

## ⭐ Beğendiyseniz

Projeyi beğendiyseniz GitHub'da yıldız vermeyi unutmayın! ⭐

---

<div align="center">

**Made with ❤️ by the M3U Editör Pro Team**

[![GitHub stars](https://img.shields.io/github/stars/yourusername/m3uedit?style=social)](https://github.com/yourusername/m3uedit/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/yourusername/m3uedit?style=social)](https://github.com/yourusername/m3uedit/network/members)
[![GitHub issues](https://img.shields.io/github/issues/yourusername/m3uedit)](https://github.com/yourusername/m3uedit/issues)

</div>