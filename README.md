# 📺 M3U Editör Pro (Web)

IPTV M3U playlist dosyalarını kolayca yönetmek, düzenlemek ve filtrelemek için geliştirilmiş modern bir web uygulaması.

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

2. **Bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

3. **Uygulamayı başlatın:**
```bash
streamlit run app.py
```

4. **Tarayıcınızda açın:**
   - Uygulama otomatik olarak açılacaktır
   - Manuel: http://localhost:8501

## 🐳 Docker/Dev Container ile Kullanım

Proje GitHub Codespaces ve VS Code Dev Container desteği ile gelir:

1. **VS Code'da açın**
2. **"Reopen in Container"** seçeneğine tıklayın
3. Container otomatik olarak kurulup başlatılacaktır

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
├── .devcontainer/
│   └── devcontainer.json    # Dev Container yapılandırması
├── app.py                    # Ana uygulama
├── visitor_counter.py        # Ziyaretçi sayacı modülü
├── requirements.txt          # Python bağımlılıkları
└── README.md                 # Bu dosya
```

## 🛠️ Teknoloji Stack

- **Streamlit** - Web framework
- **Pandas** - Veri işleme
- **Python urllib** - HTTP istekleri
- **Re** - Regex işlemleri

## ⚠️ Bilinen Sınırlamalar

- Çok büyük M3U dosyaları (10,000+ kanal) performans sorunlarına yol açabilir
- SSL doğrulama devre dışı bırakıldığı için güvenilmeyen kaynaklara dikkat edin

## 🔐 Güvenlik Notları

- Sadece güvendiğiniz kaynaklardan M3U listesi yükleyin
- Uygulamanın public internete açılması önerilmez
- Localhost/local network kullanımı için tasarlanmıştır

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen:
1. Fork yapın
2. Feature branch oluşturun
3. Değişikliklerinizi commit edin
4. Pull request gönderin

## 📝 Lisans

Bu proje açık kaynak kodludur. İstediğiniz gibi kullanabilirsiniz.

## 💬 Destek

Sorularınız veya önerileriniz için GitHub Issues kullanabilirsiniz.

---

**⭐ Beğendiyseniz yıldız vermeyi unutmayın!**
