# Mimari

`app.py` Streamlit girişidir; `src/app.py` eski komutlar için uyumluluk sarmalayıcısıdır.

- `ui/`: düzenleme, oynatma, yükleme ve dışa aktarma görünümleri.
- `utils/playlist.py`: sabit kanal kimlikleri, doğrulanmış yüklemeler ve filtreli değişikliklerin ana listeye birleştirilmesi.
- `utils/parser.py`: M3U metadata'sı, filtreleme, format dönüşümleri ve sınırlı eşzamanlı sağlık kontrolü.
- `utils/security.py`: URL sözdizimi, IP/DNS ve proxy politikası.
- `utils/network.py`: TLS, yönlendirmeler, doğrulanmış DNS adreslerine bağlantı ve sınırlı okumalar.
- `utils/proxy_server.py`: tek dinleme portu üzerinde erişim anahtarına göre oturum yönlendirmesi.
- `utils/player.py`: güvenli HTML/JavaScript oynatıcı üretimi; otomatik üçüncü taraf rölesi yoktur.
- `utils/exports.py`: yalnızca talep edilen formatın üretilmesi.
- `utils/config.py`: `.env` ve ortam ayarları. Sürüm `utils.__version__` alanından gelir.
- `utils/launcher.py` / `bootstrap.py`: paket ve repo başlatıcıları.
- `static/styles.css`: paketlenen stil dosyası.
- `.streamlit/config.toml`: doğrudan repo çalıştırmalarında koyu widget teması.
  Paket başlatıcısı aynı renkleri `utils.config.UI_THEME` üzerinden uygular.

Her kanal `_channel_id` taşır. Tablo bu alanı gizler ve düzenlemeye kapatır.
Kaydetme, yalnızca görünür kimlikleri günceller veya siler; diğer kayıtları korur.
Gizli `_Attributes`, `_Directives`, `_Duration`, `_Header` alanları M3U dönüşümünü korur.

Ağdan/dosyadan yeni veri önce tamamen doğrulanır. Session state yalnızca başarıdan sonra değiştirilir.
Sağlık sonuçları sıra korunarak döner; ilerleme callback'i çağıran iş parçacığında çalışır.
Gönderilmiş iş sayısı worker sayısıyla sınırlıdır. İndirme satır bazında değil sınırlı byte parçalarıyla yapılır.

Proxy dinleyicisi ortak olabilir; mutable kullanıcı ayarları ortak değildir. Her oturumun rastgele token'ı,
ayrı kilidi ve ayrı geçici dizini vardır. Dinleyici zayıf referanslarla oturumlara yönlendirir.
Son oturum kapandığında dinleyici kapanır; oturum kaynakları ve süreç kapanışında dosyalar temizlenir.
Dosyalar atomik olarak değiştirilir; aynı içerik yeniden yazılmaz. En fazla 32 proxy isteği eşzamanlı işlenir.

Dışa aktarımlar oturumda saklanır ve veri/format değiştiğinde yeniden hazırlanır.
Yerel ve harici linkler kullanıcının açıkça hazırladığı anlık listeyi gösterir.
HLS alt listeleri, segmentler ve key URI'ları aynı anahtarlı proxy'ye yönlendirilir.
Sağlayıcı query token'ları yalnızca aynı authority içinde yayılır.

Testler: parser, model, güvenlik, HTTP proxy ve Streamlit AppTest akışları. Tüm ağ testleri çevrimdışıdır.
CI test, lint ve paket oluşturmayı zorunlu kılar. Gerçek sağlayıcı/DRM/codec uyumu manuel entegrasyon konusudur.
