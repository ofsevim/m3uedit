import os
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

from utils.proxy_server import LocalProxyServer
from utils.visitor_counter import VisitorCounter


def test_visitor_counter_thread_safety():
    """Ziyaretçi sayacının eşzamanlı istekler altında güvenli çalışmasını test eder."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_name = tmp.name

    try:
        vc = VisitorCounter(counter_file=tmp_name)

        num_threads = 10
        increments_per_thread = 20

        threads = []

        def worker(tid):
            for i in range(increments_per_thread):
                vc.increment_visit(session_id=f"session_{tid}_{i}")

        for t_idx in range(num_threads):
            t = threading.Thread(target=worker, args=(t_idx,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        stats = vc.get_stats()
        # Toplam ziyaret sayısı 200 olmalıdır
        assert stats["total_visits"] == num_threads * increments_per_thread
        # Tekil ziyaretçi sayısı 200 olmalıdır
        assert stats["unique_visitors"] == num_threads * increments_per_thread
    finally:
        if os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except OSError:
                pass


def test_proxy_server_e2e_and_security(http_source):
    proxy = LocalProxyServer(allow_private_networks=True)
    proxy.start()
    try:
        for url in ["file:///etc/passwd", "ftp://example.com/file", "gopher://example.com"]:
            try:
                urllib.request.urlopen(proxy.get_proxy_url(url), timeout=3)
                assert False, "Unsafe scheme accepted"
            except urllib.error.HTTPError as exc:
                assert exc.code == 400
                exc.close()
        base, requests = http_source
        with urllib.request.urlopen(
            proxy.get_proxy_url(base + "/stream.ts"), timeout=3
        ) as response:
            assert response.status == 200
            assert response.read() == b"LOCAL-STREAM"
        assert requests[-1]["path"] == "/stream.ts"
    finally:
        proxy.stop()


def test_proxy_server_local_playlist():
    """Proxy sunucusunun yerel M3U çalma listesi sunma özelliğini test eder."""
    proxy = LocalProxyServer()
    proxy.start()

    try:
        # 1. Henüz liste set edilmemişken 404 döndüğünü doğrula
        playlist_url = proxy.endpoint_url("playlist.m3u")
        try:
            with urllib.request.urlopen(playlist_url, timeout=3):
                assert False, "Çalma listesi set edilmemişken 404 dönmeliydi."
        except urllib.error.HTTPError as e:
            assert e.code == 404
            e.close()

        # 2. Liste set edildikten sonra 200 döndüğünü ve içeriğin doğruluğunu doğrula
        sample_m3u = "#EXTM3U\n#EXTINF:-1,Test Kanal\nhttp://example.com/test.ts"
        proxy.set_m3u_content(sample_m3u)

        with urllib.request.urlopen(playlist_url, timeout=3) as resp:
            assert resp.status == 200
            assert resp.getheader("Content-Type").startswith("application/x-mpegurl")
            content = resp.read().decode("utf-8")
            assert content == sample_m3u

        # 3. Proxied playlist rotasını doğrula
        proxied_playlist_url = proxy.endpoint_url("proxied_playlist.m3u")
        sample_proxied_m3u = "#EXTM3U\n#EXTINF:-1,Test Kanal\nhttp://127.0.0.1:8888/proxy?url=http://example.com/test.ts"
        proxy.set_m3u_content(sample_m3u, proxied_content=sample_proxied_m3u)

        with urllib.request.urlopen(proxied_playlist_url, timeout=3) as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert content == sample_proxied_m3u

    finally:
        proxy.stop()


def test_proxy_server_config_and_headers():
    """Proxy yapılandırmasının ve özel başlıkların doğruluğunu test eder."""
    proxy = LocalProxyServer()
    proxy.set_proxy_config(
        upstream_proxy="http://127.0.0.1:9999",
        custom_user_agent="TiviMate/4.7.0",
        custom_referer="https://custom-referer.com",
    )
    assert proxy.upstream_proxy == "http://127.0.0.1:9999"
    assert proxy.custom_user_agent == "TiviMate/4.7.0"
    assert proxy.custom_referer == "https://custom-referer.com"
