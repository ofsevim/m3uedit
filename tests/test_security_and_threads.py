import urllib.request
import urllib.error
import urllib.parse
import threading
import os
import tempfile
from utils.visitor_counter import VisitorCounter
from utils.proxy_server import LocalProxyServer


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


def test_proxy_server_e2e_and_security():
    """Proxy sunucusunun SSRF/LFI güvenlik kontrollerini ve çalışmasını test eder."""
    proxy = LocalProxyServer()
    port = proxy.start()

    # Port atamasının doğruluğu
    assert port > 0
    assert proxy.port == port

    try:
        # 1. Güvensiz/Geçersiz şemaların engellenmesi (SSRF/LFI Koruması)
        invalid_urls = [
            "file:///etc/passwd",
            "file:///C:/Windows/win.ini",
            "ftp://example.com/file",
            "gopher://example.com",
            "/local/path/without/scheme",
        ]

        for url in invalid_urls:
            proxy_url = f"http://127.0.0.1:{port}/proxy?url={urllib.parse.quote(url, safe='')}"
            req = urllib.request.Request(proxy_url)
            try:
                with urllib.request.urlopen(req, timeout=3):
                    assert False, f"Şu URL için istek engellenmedi: {url}"
            except urllib.error.HTTPError as e:
                # 400 Bad Request dönmelidir
                assert e.code == 400, f"Beklenen: 400, Gelen: {e.code} ({url})"

        # 2. Geçerli bir HTTP istek denemesi (E2E)
        test_http_url = "http://example.com"
        proxy_url = f"http://127.0.0.1:{port}/proxy?url={urllib.parse.quote(test_http_url, safe='')}"
        req = urllib.request.Request(proxy_url)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                content = resp.read()
                assert resp.status == 200
                assert len(content) > 0
        except Exception as e:
            # Çevrimdışı olma veya internet erişimi kısıtlılıklarında testi bozmasın
            print(f"E2E proxy isteği başarısız (çevrimdışı olunabilir): {e}")

    finally:
        proxy.stop()


def test_proxy_server_local_playlist():
    """Proxy sunucusunun yerel M3U çalma listesi sunma özelliğini test eder."""
    proxy = LocalProxyServer()
    port = proxy.start()

    try:
        # 1. Henüz liste set edilmemişken 404 döndüğünü doğrula
        playlist_url = f"http://127.0.0.1:{port}/playlist.m3u"
        try:
            with urllib.request.urlopen(playlist_url, timeout=3):
                assert False, "Çalma listesi set edilmemişken 404 dönmeliydi."
        except urllib.error.HTTPError as e:
            assert e.code == 404

        # 2. Liste set edildikten sonra 200 döndüğünü ve içeriğin doğruluğunu doğrula
        sample_m3u = "#EXTM3U\n#EXTINF:-1,Test Kanal\nhttp://example.com/test.ts"
        proxy.set_m3u_content(sample_m3u)

        with urllib.request.urlopen(playlist_url, timeout=3) as resp:
            assert resp.status == 200
            assert resp.getheader("Content-Type").startswith("application/x-mpegurl")
            content = resp.read().decode("utf-8")
            assert content == sample_m3u

    finally:
        proxy.stop()

