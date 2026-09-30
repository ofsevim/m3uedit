# Kullanım kılavuzu

[Kurulum](../QUICKSTART.md) · [Dağıtım](DEPLOYMENT.md)

## Liste yükleme

Sol menüde URL girin veya dosya seçin, TR filtresini seçip **Listeyi Çek ve Tara** düğmesine basın.
Açılış kartları aynı doğrulama kurallarını kullanır. Boş/hatalı kaynak mevcut listeyi silmez.
URL HTTP/HTTPS olmalı; özel ağ kaynağı varsayılan olarak engellenir. Dosya sınırı 50 MB'dır.

## Kanallar & Düzenle

Sol menüden grup/tür/durum filtreleyin, sekmede kanal veya grup arayın.
Tabloda ad, grup ve URL düzenlenebilir; durum/tür hesaplanır. Dinamik satırlar eklenip silinebilir.
**Tablodaki Düzenlemeleri Listeye Kaydet** yalnızca görünür satırlardaki işlemleri uygular.
Görünmeyen kanallar, logo ve EPG bilgileri korunur. Geçersiz URL veya boş ad kayıt işlemini durdurur.
URL değişince eski sağlık sonucu sıfırlanır. Filtre değişmeden kaydedilmemiş değişikliklerinizi önce kaydedin.

**Sağlık Kontrolü** seçilen kapsam ve limite göre HEAD/kısa GET denemesi yapar.
Aktif, yetki gerekli, VPN gerekebilir, zaman aşımı gibi sonuçlar oynatma garantisi değildir.
**Ölüleri Temizle** ve **Sadece Çalışanlar** ana listeye uygulanır; silme öncesi M3U yedeği indirin.

## Canlı Oynatıcı

Kanal seçildiğinde HLS/MPEG-TS oynatma başlar. Varsayılan yerel proxy,
cihaz User-Agent'ı ve sağlayıcı Referer ayarını kullanır. Üçüncü taraf proxy otomatik denenmez.
Doğrudan oynatma seçeneği sağlayıcı CORS/HTTPS kurallarına bağlıdır.
Uzak sunucudaki proxy için [HTTPS dağıtım ayarları](DEPLOYMENT.md) gerekir.
DRM koruması ve tarayıcının desteklemediği codec'ler harici oynatıcı gerektirebilir.

## Dışa Aktar & Paylaş

Önce görünen/tüm kanallar kapsamını ve M3U/M3U8/CSV/JSON/TXT/VPN köprüsü formatını seçin.
**İndirme Dosyasını Hazırla**, ardından indirme düğmesini kullanın.
Veri/format değişirse dosyayı yeniden hazırlayın. M3U8 dosyası UTF-8 M3U listesidir.

**Seçilen Liste İçin Yerel Link Hazırla** oturuma özel bir snapshot yayımlar.
TV için LAN paylaşımı açılmalıdır; linkteki anahtar gizlidir. Düzenlemeden sonra linki yeniden hazırlayın.
**Harici Paylaşım** listeyi seçilen HTTPS paste servisine gönderir. URL içindeki kullanıcı bilgileri/token'lar da
aktarılır; onay kutusu seçilmeden gönderim yapılmaz. Harici linkler ayrı snapshot'lardır.

## VPN ve profil

HTTP/HTTPS upstream proxy adresi, cihaz profili ve sağlayıcının Referer başlığını ayarlayın.
SOCKS doğrudan desteklenmez; istemcinizin HTTP portunu kullanın. Proxy adresi girmek VPN hizmeti sağlamaz.
Ayarlar yalnızca sizin oturumunuza uygulanır.
