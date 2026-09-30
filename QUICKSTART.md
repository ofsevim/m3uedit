# Hızlı başlangıç

1. Python 3.11 veya üstünü kurun.
2. `git clone https://github.com/ofsevim/m3uedit.git` ve `cd m3uedit` çalıştırın.
3. Windows: `run.bat`; Linux/macOS: `bash run.sh`.
4. Tarayıcıda http://127.0.0.1:8501 açın.

İlk çalıştırma sanal ortamı ve bağımlılıkları hazırlar. Var olan `.venv` veya `venv` kullanılır.
Başlatıcı herhangi bir çalışma dizininden çağrılabilir. `run.bat --check` / `bash run.sh --check`
kurulumu denetler; eksik ortamı bu modda oluşturmaz.

URL yapıştırın veya dosya seçip **Listeyi Çek ve Tara** düğmesine basın.
Türkçe filtresi uygun kanal bulamıyorsa filtreyi kapatın. Hatalı yüklemelerde eski liste korunur.

**Kanallar & Düzenle:** filtreleyin, düzenleyin, satır ekleyin/silin ve kaydedin.
Görünmeyen kanallar, logolar ve M3U metadata'sı korunur.
**Canlı Oynatıcı:** kanal seçin; akış varsayılan olarak oturuma özel proxy'den geçer.
**Dışa Aktar & Paylaş:** görünen/tüm listeyi ve formatı seçip **İndirme Dosyasını Hazırla** düğmesine basın.
**VPN & Yurt Dışı Çözümleri:** HTTP proxy, cihaz profili ve sağlayıcı Referer'ını ayarlayın.

TV kullanımı: `.env.example` dosyasını `.env` olarak kopyalayıp `ENABLE_LAN_SHARING=true` yapın ve uygulamayı yeniden başlatın.
Dışa aktarma sekmesinde yerel link hazırlayın. Linkteki erişim anahtarını gizli tutun.
Özel ağdaki IPTV sunucusu için ayrıca `ALLOW_PRIVATE_NETWORKS=true` gerekir.
Yerel proxy portu varsayılan 8502'dir; uygulama ve liste linki bilgisayar açıkken kullanılabilir.

Uzak sunucu ve HTTPS kurulumları için [dağıtım rehberi](docs/DEPLOYMENT.md).
