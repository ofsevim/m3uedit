# Kurulum ve dağıtım

## Yerel

Python 3.11+ ile `run.bat` veya `bash run.sh` çalıştırın. Başlatıcı `.venv` oluşturur
veya mevcut `.venv`/`venv` kullanır; eksik bağımlılıkları yükler. `--check` yalnızca kontrol eder.
Paket kurulumu için `python -m pip install .`, ardından `m3uedit` kullanılabilir.
`.env.example` dosyasını `.env` olarak kopyalayın. Sistem ortamı ayarları önceliklidir.

Varsayılanlar: uygulama 127.0.0.1:8501, oturum proxy'si 127.0.0.1:8502; TLS açık;
özel ağ hedefleri ve LAN paylaşımı kapalı. MAX_FILE_SIZE_MB hem başlatıcının upload ayarına
hem dosya/URL okuma sınırlarına uygulanır. Doğrudan `streamlit run app.py` kullanırken
Streamlit upload sınırını `--server.maxUploadSize 50` ile ayrıca ayarlayabilirsiniz.

## LAN / Smart TV

`ENABLE_LAN_SHARING=true` yapıp yeniden başlatın. Proxy tüm arayüzlerde dinler.
8502 portunu yalnızca güvenilir ev ağınız için açın. UI'yi ağda göstermek isterseniz
ayrıca `SERVER_HOST=0.0.0.0` kullanın. İç ağdaki IPTV kaynağı için
`ALLOW_PRIVATE_NETWORKS=true` gerekir; bu ayarı internetten erişilen kurulumlarda açmayın.
Linkler rastgele erişim anahtarı içerir; token'ı bilen cihaz yayımlanmış listeyi ve akışları okuyabilir.
Link yalnızca uygulama/oturum çalıştığı sürece geçerlidir.

## HTTPS uzak sunucu

Tarayıcıdaki 127.0.0.1 sunucuyu değil kullanıcının bilgisayarını gösterir.
Uzak proxy'nin HTTPS üzerinden erişilebilir olması gerekir. Örnek `.env`:

```dotenv
SERVER_HOST=127.0.0.1
PROXY_PORT=8502
PROXY_PUBLIC_BASE_URL=https://iptv.example.org/relay
PROXY_ALLOWED_ORIGIN=https://iptv.example.org
ENABLE_LAN_SHARING=false
ALLOW_PRIVATE_NETWORKS=false
ENABLE_SSL_VERIFY=true
```

TLS sunucusu içinde örnek Nginx konumları:

```nginx
location / {
    proxy_pass http://127.0.0.1:8501;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
location /relay/ {
    proxy_pass http://127.0.0.1:8502/;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 60s;
    access_log off; # Query string contains capability/provider tokens.
}
```

`/relay/` konumu bütün proxy, playlist ve manifest segment rotalarını yönlendirmelidir.
UI erişimini kurumunuzun reverse proxy kimlik doğrulamasıyla sınırlayın.
Token uygulama hesabı yerine geçmez; proxy kabiliyet anahtarıdır.
Tek uygulama süreci desteklenir; çoklu replica kurulumu oturum yapışkanlığı ve proxy yönlendirmesi gerektirir.
Bu repoda Docker dağıtım dosyaları bulunmaz.

## Streamlit Community Cloud

Dağıtımda `main` dalındaki `app.py` giriş dosyasını ve Python 3.12 kullanın.
Bulut bağımlılıkları kökteki `requirements.txt` ile kurulur. `uv.lock` yalnızca
yerel kullanım içindir ve Git tarafından yok sayılır: Community Cloud bu dosyayı
`requirements.txt` dosyasından önce seçer; eski uv sürümleri dinamik paket sürümünü
içeren yeni kilit dosyalarını okuyamayabilir.
Bkz. [Community Cloud bağımlılık dosyası önceliği](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

Streamlit Community Cloud ve bazı managed platformlar ikinci portu dışarı açmaz.
Bu platformlarda düzenleme/indirme/sağlık kontrolü çalışır; yerel proxy oynatımı için ulaşılabilir
bir gateway gerekir. Doğrudan oynatma seçeneği sağlayıcının HTTPS/CORS desteğine bağlıdır.
Oynatıcı uzak sayfada localhost proxy'sini kullanmaz; HTTPS yayını doğrudan açmayı dener.
`extension=ts` içeren yayınlar MPEG-TS motoruyla açılır. HTTP yayınını HTTPS sayfasında
izlemek için `PROXY_PUBLIC_BASE_URL` ile erişilebilir bir HTTPS gateway yapılandırılmalıdır;
bu ayar tek başına gateway oluşturmaz. Gateway yoksa kanalı indirip VLC ile açın veya
uygulamayı yerelde çalıştırın.
CORS veya XSRF korumasını kapatmayın. Upstream proxy seçilirse onun DNS/egress davranışı güvenilir kabul edilir.
