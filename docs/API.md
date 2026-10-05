# Python API

## Playlist

`utils.parser.parse_m3u_lines(lines)` byte/string satırları kanal dict listesine dönüştürür.
Alanlar: Grup, Kanal Adı, URL, LogoURL, Tür; gizli metadata:
_Attributes (dict), _Directives (list), _TrailingDirectives (list), _Duration, _Header, _GlobalDirectives.
`filter_channels(channels, only_tr=False, keyword="", group_filter="")` filtreler.
`convert_df_to_m3u(frame)` / `convert_df_to_proxied_m3u(frame, proxy_base_url)` metadata'yı korur.
Proxy base query taşıyabilir; URL parametresi uygun ?/& ayırıcıyla eklenir.
CSV, JSON, TXT dönüşümleri yalnızca kullanıcı alanlarını dışa aktarır.

`utils.playlist.import_playlist(source, only_tr=False)` byte içerik veya satır iterable'ını doğrulanmış
DataFrame'e çevirir; boş/uygunsuz sonuçta ValueError verir.
`ensure_columns(frame)` varsayılanları ve sabit _channel_id kimliklerini sağlar.
`merge_visible_edits(original, visible_ids, edited)` görünür satır güncellemelerini/silmelerini uygular;
gizli satır ve metadata'yı korur, geçersiz girdide original değişmeden kalır.

## Ağ

`utils.network.fetch_m3u_source(url, user_agent=..., timeout=..., disable_ssl_verify=False,
proxy_url=None, headers=None)` sınırlı byte satırları döndürür.
`open_url(request, timeout=30, disable_ssl_verify=None, proxy_url=None, allow_private=None)`
ortak URL/IP/TLS/yönlendirme politikasını uygular; dönen response context manager ile kapatılmalıdır.
`read_bounded(response, max_bytes, deadline_seconds=30)` Content-Length olmasa da boyutu ve süreyi sınırlar;
yavaş chunk başlıklarında süre dolunca bağlantı kapatılır.
`create_m3u_link(content, user_agent=..., timeout=30, service="dpaste.com", consent=False, proxy_url=None)`
yalnızca açık onayla seçilen HTTPS servisine (`dpaste.com`, `catbox.moe`, `paste.rs`) gönderir; hataları çağırana iletir.

`utils.parser.batch_check_health(urls, max_workers=50, timeout=3.0, user_agent=None,
proxy_url=None, headers=None, progress_callback=None)` sıra korunmuş durum listesi döndürür.
Callback `(completed, total)` çağıran iş parçacığında çalışır.

## Proxy ve oynatıcı

`LocalProxyServer(allow_private_networks=None)` oturuma özel ayar/dosya/token oluşturur.
`start()` ortak dinleyiciye kayıt olur; `stop()` kayıt ve dosyaları temizler.
`set_proxy_config(upstream_proxy=None, custom_user_agent=None, custom_referer=None)` doğrular ve atomik değiştirir.
`endpoint_url(path, host="127.0.0.1", public=False)` anahtarlı link üretir.
`get_proxy_url(target_url, host="127.0.0.1", public=False)` akış linki üretir.
`set_m3u_content(content, proxied_content="")` atomik yerel dosyalar yazar.
Bütün GET/HEAD/OPTIONS rotalarında token zorunludur.

`utils.player.render_live_player(url, height=420, proxy_base_url="", use_proxy=True)` güvenli iframe HTML'i döndürür.
`utils.exports.make_export(frame, format_name, proxy_base_url=None)` `(content, filename, mime)` döndürür.
