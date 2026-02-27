# 🚀 Hızlı Başlangıç Rehberi

## 5 Dakikada Başlayın!

### Windows Kullanıcıları

1. **Projeyi indirin**
   ```cmd
   git clone https://github.com/kullaniciadi/m3uedit.git
   cd m3uedit
   ```

2. **Çift tıklayın**
   - `run.bat` dosyasına çift tıklayın
   - Otomatik olarak kurulum yapılacak ve uygulama başlayacak

3. **Tarayıcıda açın**
   - Otomatik olarak açılacak
   - Veya manuel: http://localhost:8501

### Linux/Mac Kullanıcıları

1. **Projeyi indirin**
   ```bash
   git clone https://github.com/kullaniciadi/m3uedit.git
   cd m3uedit
   ```

2. **Çalıştırın**
   ```bash
   chmod +x run.sh
   ./run.sh
   ```

3. **Tarayıcıda açın**
   - Otomatik olarak açılacak
   - Veya manuel: http://localhost:8501

## İlk Kullanım

### 1. M3U Listesi Yükleyin

**Seçenek A: URL ile**
- Sol menüden "🌐 Linkten Yükle" seçin
- M3U linkini yapıştırın
- "Listeyi Çek ve Tara" butonuna tıklayın

**Seçenek B: Dosya ile**
- Sol menüden "📂 Dosya Yükle" seçin
- M3U dosyasını sürükle-bırak yapın

### 2. Kanalları Düzenleyin

- ✅ İstediğiniz kanalları seçin
- 🔍 Arama yapın
- ✏️ Tabloda düzenleme yapın

### 3. İndirin

- 💾 "SADECE SEÇİLENLERİ İNDİR" butonuna tıklayın
- Veya tüm listeyi indirin

## Sorun mu Yaşıyorsunuz?

### Python bulunamadı
```bash
# Python 3.11+ yükleyin
# Windows: https://www.python.org/downloads/
# Linux: sudo apt install python3.11
# Mac: brew install python@3.11
```

### Bağımlılık hatası
```bash
pip install -r requirements.txt
```

### Port zaten kullanımda
```bash
# Farklı port kullanın
streamlit run src/app.py --server.port=8502
```

## Yardım

- 📖 [Detaylı Kullanım Kılavuzu](docs/KULLANIM_KILAVUZU.md)
- 🐛 [Sorun Bildirin](https://github.com/kullaniciadi/m3uedit/issues)
- 💬 [Soru Sorun](https://github.com/kullaniciadi/m3uedit/discussions)

---

**İyi kullanımlar! 🎉**
