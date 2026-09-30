# Güvenlik politikası

## Varsayılanlar

2.2.x: TLS sertifikası doğrulanır; HTTP(S) dışındaki kaynaklar engellenir.
Loopback, özel ağ, link-local ve diğer genel olmayan IP hedefleri, DNS yanıtları ve yönlendirmeler doğrulanır.
Doğrudan bağlantılar doğrulanmış IP'ye kurulur; HTTPS için orijinal hostname/SNI korunur.
HTTPS'ten HTTP'ye yönlendirme engellenir. Host değiştiğinde Authorization/Cookie/Referer taşınmaz.
Upstream proxy kullanıcı tarafından açıkça seçilir ve DNS/egress açısından güvenilir kabul edilir.

Proxy localhost üzerinde dinler, bütün rotalar oturuma özel rastgele anahtar ister.
Her oturum ayrı dosya/ayar kullanır. Playlist, proxy ve HLS segment linkleri kabiliyet anahtarıdır;
bu linklere sahip kişiler ilgili kaynaklara erişebilir. Linkleri herkese açık paylaşmayın.
LAN ve iç ağ kaynaklarına izin vermek ayrı ayarlardır. İç ağ iznini public kurulumda açmayın.

Playlist indirmesi ve upload sınırı varsayılan 50 MB, HLS manifest sınırı 2 MB'dır.
En fazla 32 proxy isteği eşzamanlı işlenir. Sonsuz medya stream'i parça parça iletilir.
İstek URL'leri, token'lar ve sağlayıcı kimlik bilgileri proxy loglarına yazılmaz.

Oynatıcı URL'yi güvenli JavaScript verisi olarak kullanır; dinamik hata içeriği textContent/DOM ile oluşturulur.
Otomatik üçüncü taraf akış proxy'si yoktur. Oynatma kütüphaneleri sürümü sabit CDN kaynaklarından yüklenir.
Harici playlist paylaşımı, kullanıcının seçtiği HTTPS servisine açık onayla yapılır;
başka servise sessiz fallback yapılmaz. URL içindeki sağlayıcı erişim bilgileri paylaşımın parçasıdır.
Paylaşım linkini sonradan uygulamadan kaldırmak sağlayıcıdaki içeriği silmez.

ENABLE_SSL_VERIFY=false yalnızca güvenilir yerel kaynaklar için bilinçli bir uyumluluk seçeneğidir.
Harici paylaşım bu ayardan etkilenmez; TLS doğrulamasını daima kullanır.
Uzak kullanım için UI kimlik doğrulamasını reverse proxy'de yapılandırın; yerleşik kullanıcı hesabı yoktur.

## Bildirim

Lütfen hassas token veya playlist içeriğini public issue'ya eklemeyin.
Depo sahibine GitHub üzerindeki uygun özel iletişim kanalından ulaşın:
https://github.com/ofsevim/m3uedit . Bu repoda doğrulanmış bir güvenlik e-posta adresi tanımlı değildir.

## Kontroller

CI çevrimdışı güvenlik/regresyon testlerini ve lint'i zorunlu çalıştırır.
Gerçek sağlayıcıların yetki, codec ve DRM davranışları otomatik testlerde doğrulanmaz.
