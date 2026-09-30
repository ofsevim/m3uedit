# M3U Editör Pro

IPTV listelerini yüklemek, düzenlemek, kontrol etmek ve dışa aktarmak için Streamlit uygulaması.
[English](README.md) · [Hızlı başlangıç](QUICKSTART.md) · [Kullanım](docs/KULLANIM_KILAVUZU.md)

Python 3.11+ kurulu olmalı. Projeyi indirdikten sonra Windows'ta `run.bat`,
Linux/macOS'te `bash run.sh` çalıştırın. Eksik sanal ortam ve bağımlılıklar otomatik hazırlanır.
Uygulama http://127.0.0.1:8501 üzerinde açılır. `python bootstrap.py --check` kurulum kontrolüdür.

Manuel kurulum: `python -m pip install -e .`, ardından `m3uedit`.
`streamlit run app.py` ve eski `streamlit run src/app.py` komutları desteklenir.

- HTTP(S) linkinden veya dosyadan liste yükleyin; başarısız yüklemede mevcut liste korunur.
- Grup, tür, durum veya adla filtreleyin. Filtreli tabloyu kaydetmek görünmeyen kanalları silmez.
- Kanal ekleyin, düzenleyin veya görünen satırları silin; logo ve EPG metadata'sı korunur.
- Sağlık kontrolü yapın. HTTP erişimi, oynatmanın başarılı olacağı anlamına gelmez.
- Dışa aktarma sekmesinde kapsam ve format seçip dosyayı hazırlayın.
- Yerel liste linki erişim anahtarı taşır. Harici paylaşım yalnızca seçilen HTTPS servisine açık onayla yapılır.

`.env.example` dosyasını `.env` olarak kopyalayabilirsiniz. Ortam değişkenleri dosya ayarlarından önceliklidir.
TLS doğrulaması açık, proxy yalnızca localhost'a bağlı, iç ağ kaynaklarına erişim kapalıdır.
TV erişimi için ENABLE_LAN_SHARING, özel IPTV kaynakları için ALLOW_PRIVATE_NETWORKS ayrı ayrı açılır.
Upstream proxy HTTP/HTTPS olmalıdır; SOCKS yerine VPN istemcisinin HTTP portunu kullanın.
Uzak sunucuda oynatma için HTTPS reverse proxy ayarları gerekir: [dağıtım](docs/DEPLOYMENT.md).

Geliştirme: `python -m pip install -e ".[dev]"`, `python -m pytest`.
Testler internete liste veya kimlik bilgisi göndermez. [Güvenlik politikası](SECURITY.md). Lisans: MIT.
