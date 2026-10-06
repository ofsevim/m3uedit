"""On-demand downloads and explicit local/cloud sharing."""

import hashlib
import pickle
import socket

import streamlit as st

from utils import config, network
from utils.exports import make_export
from utils.parser import convert_df_to_m3u, convert_df_to_proxied_m3u


def render_exports(visible, get_proxy_server):
    scope = st.radio(
        "Kapsam",
        ["Görünen kanallar", "Tüm kanallar"],
        horizontal=True,
        label_visibility="collapsed",
    )
    frame = visible if scope == "Görünen kanallar" else st.session_state.data
    st.caption(f"Seçili kapsam: **{scope}** ({len(frame)} kanal)")

    download_col, cloud_col, local_col = st.columns(3)

    with download_col, st.container(key="export_download"):
        st.markdown("#### 📥 Dosya İndir")
        formats = ["M3U", "M3U8", "CSV", "JSON", "TXT", "VPN Köprüsü M3U"]
        format_name = st.selectbox("Dosya formatı", formats, key="export_format")
        fingerprint = hashlib.sha256(pickle.dumps((frame, format_name))).hexdigest()
        if st.button("📦 Dosyayı Hazırla", width="stretch", type="primary"):
            try:
                base = None
                if format_name == "VPN Köprüsü M3U":
                    server = get_proxy_server()
                    base = server.endpoint_url("proxy", host=_lan_host(), public=True)
                    if config.PROXY_BIND_HOST == "127.0.0.1" and not config.PROXY_PUBLIC_BASE_URL:
                        st.info("TV erişimi için LAN paylaşımını açın.")
                st.session_state.export_artifact = (
                    fingerprint,
                    make_export(frame, format_name, proxy_base_url=base),
                )
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        artifact = st.session_state.get("export_artifact")
        if artifact and artifact[0] == fingerprint:
            content, filename, mime = artifact[1]
            st.download_button(
                "📥 İndir",
                content,
                file_name=filename,
                mime=mime,
                width="stretch",
            )

    with cloud_col, st.container(key="export_cloud"):
        st.markdown("#### 🌐 Harici Paylaşım Linki")
        service = st.selectbox("Paylaşım servisi", ["dpaste.com", "catbox.moe", "paste.rs"])
        st.caption("dpaste.com (1 MB) · catbox.moe (50 MB) · paste.rs (64 KB)")
        consent = st.checkbox(
            f"Listenin {service} servisine gönderilmesini onaylıyorum.",
            key="share_consent_" + service,
        )
        if st.button("🌐 Harici Paylaşım Linki Oluştur", disabled=not consent, width="stretch"):
            if frame.empty:
                st.warning("Paylaşılacak kanal bulunamadı.")
            else:
                try:
                    with st.spinner("Link oluşturuluyor..."):
                        st.session_state.m3u_cloud_link = network.create_m3u_link(
                            convert_df_to_m3u(frame),
                            user_agent=config.USER_AGENT,
                            timeout=config.REQUEST_TIMEOUT,
                            service=service,
                            consent=consent,
                            proxy_url=st.session_state.get("upstream_proxy") or None,
                        )
                except (ValueError, OSError) as exc:
                    st.error(f"Paylaşım başarısız: {exc}")
        if st.session_state.get("m3u_cloud_link"):
            st.code(st.session_state.m3u_cloud_link, language=None)

    with local_col, st.container(key="export_local"):
        st.markdown("#### 📡 Yerel Ağ Linki (TV)")
        st.caption("Aynı ağdaki Smart TV veya oynatıcılar için oturum bağlantısı.")
        if st.button("📡 Yerel Link Hazırla", width="stretch"):
            try:
                server = get_proxy_server()
                proxy_base = server.endpoint_url("proxy", host=_lan_host(), public=True)
                server.set_m3u_content(
                    convert_df_to_m3u(frame), convert_df_to_proxied_m3u(frame, proxy_base)
                )
                st.session_state.local_playlist_link = server.endpoint_url(
                    "proxied_playlist.m3u", host=_lan_host(), public=True
                )
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        if st.session_state.get("local_playlist_link"):
            st.code(st.session_state.local_playlist_link, language=None)


def _lan_host():
    if config.PROXY_BIND_HOST == "127.0.0.1":
        return "127.0.0.1"
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"
