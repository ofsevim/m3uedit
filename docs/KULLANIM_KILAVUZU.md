# M3U Editör Pro - Kullanım Kılavuzu

## İçindekiler
1. [Giriş](#giriş)
2. [Hızlı Başlangıç](#hızlı-başlangıç)
3. [Özellikler](#özellikler)
4. [Detaylı Kullanım](#detaylı-kullanım)
5. [Sık Sorulan Sorular](#sık-sorulan-sorular)

## Giriş

M3U Editör Pro, IPTV playlist dosyalarını yönetmek için geliştirilmiş modern bir web uygulamasıdır.

## Hızlı Başlangıç

### 1. Uygulamayı Başlatma

Proje kök dizininden:
```bash
streamlit run src/app.py
```

Veya src dizinindeyseniz:
```bash
cd src
streamlit run app.py
```

### 2. M3U Listesi Yükleme

**URL ile:**
- Sol menüden "🌐 Linkten Yükle" seçin
- M3U linkini yapıştırın
- "Listeyi Çek ve Tara" butonuna tıklayın

**Dosya ile:**
- Sol menüden "📂 Dosya Yükle" seçin
- M3U dosyasını sürükle-bırak yapın

### 3. Kanalları Düzenleme
- Arama kutusunu kullanarak kanal arayın
- İstediğiniz kanalları seçin
- Tabloda doğrudan düzenleme yapın

### 4. Export
- Seçili kanalları veya tüm listeyi indirin
- M3U, JSON veya CSV formatında export edin

## Özellikler

### Filtreleme
- TR filtresi ile Türk kanallarını otomatik tespit
- Grup bazlı filtreleme
- Gelişmiş arama

### Düzenleme
- Checkbox ile kolay seçim
- Canlı tablo düzenleme
- Toplu işlemler

### Export
- M3U formatında standart export
- JSON ve CSV desteği
- Seçili veya tüm liste

### İstatistikler
- Toplam kanal sayısı
- Seçilen kanal sayısı
- Grup sayısı
- Ziyaretçi istatistikleri

## Detaylı Kullanım

### TR Filtresi
TR filtresi aşağıdaki anahtar kelimeleri arar:
- TR, TURK, TÜRK
- TURKIYE, TÜRKİYE
- YERLI, ULUSAL
- ISTANBUL

### Tema Değiştirme
Sol menüden "Açık" veya "Koyu" tema seçebilirsiniz.

### Sıralama
- Grup, Kanal Adı veya URL'ye göre sıralama
- A→Z veya Z→A yönü seçimi

### URL Sağlık Kontrolü
- Tüm kanalların URL'lerini test eder
- Çalışmayan linkleri tespit eder
- Durum sütununda sonuçları gösterir

### Canlı Oynatıcı
- Herhangi bir kanalı test edebilirsiniz
- HLS.js desteği ile geniş format uyumluluğu
- Tam ekran oynatma desteği

## Sık Sorulan Sorular

### Uygulama çok yavaş çalışıyor
- Çok büyük listeler (10,000+ kanal) performans sorunlarına yol açabilir
- Filtreleme kullanarak liste boyutunu küçültün

### SSL hatası alıyorum
- Uygulama SSL doğrulamasını bypass eder
- Sadece güvendiğiniz kaynaklardan liste yükleyin

### Kanallar oynatılmıyor
- URL'lerin geçerli olduğundan emin olun
- URL Sağlık Kontrolü ile test edin
- Bazı kanallar coğrafi kısıtlamaya sahip olabilir

### Verilerim kaydediliyor mu?
- Hayır, tüm işlemler tarayıcınızda gerçekleşir
- Export etmediğiniz sürece veriler kalıcı değildir
- Ziyaretçi sayacı dışında hiçbir veri sunucuda saklanmaz

## Destek

Sorularınız için:
- GitHub Issues: [github.com/yourusername/m3uedit/issues](https://github.com/yourusername/m3uedit/issues)
- E-posta: support@example.com
