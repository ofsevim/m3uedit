# Katkıda Bulunma Rehberi

M3U Editör Pro'ya katkıda bulunmak istediğiniz için teşekkürler!

## Nasıl Katkıda Bulunabilirim?

### Hata Bildirimi
1. GitHub Issues'a gidin
2. Yeni bir issue açın
3. Hatayı detaylı açıklayın
4. Mümkünse ekran görüntüsü ekleyin

### Özellik Önerisi
1. GitHub Issues'a gidin
2. "Feature Request" etiketi ile issue açın
3. Özelliği detaylı açıklayın
4. Kullanım senaryoları ekleyin

### Kod Katkısı

#### 1. Repository'yi Fork Edin
```bash
git clone https://github.com/yourusername/m3uedit.git
cd m3uedit
```

#### 2. Yeni Branch Oluşturun
```bash
git checkout -b feature/yeni-ozellik
```

#### 3. Değişikliklerinizi Yapın
- Kod standartlarına uyun
- Yorum satırları ekleyin
- Test edin

#### 4. Commit Edin
```bash
git add .
git commit -m "feat: yeni özellik eklendi"
```

#### 5. Push Edin
```bash
git push origin feature/yeni-ozellik
```

#### 6. Pull Request Açın
- Değişikliklerinizi açıklayın
- İlgili issue'ları referans gösterin
- Ekran görüntüleri ekleyin

## Kod Standartları

### Python
- PEP 8 standartlarına uyun
- Fonksiyonlara docstring ekleyin
- Anlamlı değişken isimleri kullanın

### Commit Mesajları
- `feat:` - Yeni özellik
- `fix:` - Hata düzeltmesi
- `docs:` - Dokümantasyon
- `style:` - Kod formatı
- `refactor:` - Kod yeniden yapılandırma
- `test:` - Test ekleme
- `chore:` - Bakım işleri

## Test

Değişikliklerinizi test edin:
```bash
streamlit run src/app.py
```

## Sorularınız mı Var?

GitHub Discussions'da soru sorabilirsiniz.

## Davranış Kuralları

- Saygılı olun
- Yapıcı eleştiri yapın
- Yardımcı olun
- Topluluk kurallarına uyun

Teşekkürler! 🎉
