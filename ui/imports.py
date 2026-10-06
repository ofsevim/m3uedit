"""Atomic onboarding and playlist replacement imports."""

import logging
import time
import urllib.error

import streamlit as st

from utils import network as network_utils
from utils.config import (
    DEFAULT_TR_FILTER,
    DISABLE_SSL_VERIFY,
    REQUEST_TIMEOUT,
    USER_AGENT,
    USER_AGENT_PROFILES,
)
from utils.playlist import import_playlist

logger = logging.getLogger(__name__)


def replace_playlist(frame):
    st.session_state.data = frame
    st.session_state.play_channel = None
    st.session_state.edit_revision = st.session_state.get("edit_revision", 0) + 1
    st.session_state.pop("m3u_cloud_link", None)
    st.session_state.pop("export_artifact", None)
    st.session_state.pop("local_playlist_link", None)
    for key in (
        "group_filter",
        "type_filter",
        "status_filter",
        "tab_search",
        "player_tab_select_box",
    ):
        st.session_state.pop(key, None)


def render_source_loader():
    default_url_val = ""
    if st.session_state.recent_urls:
        chosen_recent = st.selectbox(
            "Son kullanılan linkler",
            ["(Yeni Link Girin...)"] + st.session_state.recent_urls,
            key="recent_url_selector",
        )
        if chosen_recent != "(Yeni Link Girin...)":
            default_url_val = chosen_recent

    col_url, col_file = st.columns(2)
    with col_url:
        url = st.text_input(
            "🌐 M3U Linki Yapıştır:",
            value=default_url_val,
            placeholder="https://example.com/playlist.m3u",
        )
    with col_file:
        uploaded_file = st.file_uploader("📂 veya M3U Dosyası Yükle", type=["m3u", "m3u8"])

    opt_col, btn_col = st.columns([1, 1])
    with opt_col:
        only_tr = st.checkbox("🇹🇷 Sadece TR Kanalları", value=DEFAULT_TR_FILTER)
    with btn_col:
        submit = st.button("🚀 Listeyi Çek ve Tara", width="stretch", type="primary")

    if submit:
        source_lines = None
        start = time.time()
        if url:
            try:
                with st.spinner("Link indiriliyor..."):
                    active_ua = USER_AGENT_PROFILES.get(
                        st.session_state.selected_ua_profile, USER_AGENT
                    )
                    req_headers = {}
                    if st.session_state.custom_referer:
                        req_headers["Referer"] = st.session_state.custom_referer

                    source_lines = network_utils.fetch_m3u_source(
                        url,
                        user_agent=active_ua,
                        timeout=REQUEST_TIMEOUT,
                        disable_ssl_verify=DISABLE_SSL_VERIFY,
                        proxy_url=st.session_state.upstream_proxy or None,
                        headers=req_headers or None,
                    )
                    if url and url not in st.session_state.recent_urls:
                        st.session_state.recent_urls.insert(0, url)
                        st.session_state.recent_urls = st.session_state.recent_urls[:5]
            except urllib.error.HTTPError as e:
                if e.code in (403, 451):
                    st.error(f"🚫 HTTP {e.code}: Bölgesel Kısıtlama / VPN Gerekli!")
                else:
                    st.error(f"🚫 HTTP Hatası: {e.code}")
            except urllib.error.URLError as e:
                st.error(f"🔌 Bağlantı Hatası: {e.reason}")
            except TimeoutError:
                st.error(f"⏱️ Zaman Aşımı ({REQUEST_TIMEOUT}s)")
            except Exception as e:
                logger.warning("Liste yüklenemedi (%s)", type(e).__name__)
                st.error(f"❌ Hata: {e}")
        elif uploaded_file:
            source_lines = uploaded_file.getvalue()
        else:
            st.warning("Lütfen bir link girin veya dosya yükleyin.")

        if source_lines:
            try:
                replacement = import_playlist(source_lines, only_tr=only_tr)
                replace_playlist(replacement)
                st.success(f"✅ {len(replacement)} kanal bulundu ({time.time() - start:.2f}s)")
            except ValueError as exc:
                st.error(str(exc))


def render_empty_state():
    st.markdown(
        """
        <div class='hero'>
            <h1>📺 M3U Editör Pro</h1>
            <p>M3U bağlantınızı yapıştırın veya dosyanızı seçerek hemen başlayın.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    card_c1, card_c2 = st.columns(2)
    with card_c1, st.container(key="import_url"):
        st.markdown("#### 🌐 Bağlantı ile yükle")
        quick_url = st.text_input(
            "M3U Bağlantısı:", placeholder="https://example.com/playlist.m3u", key="quick_c_url"
        )
        quick_tr = st.checkbox("🇹🇷 Sadece TR Kanalları", value=DEFAULT_TR_FILTER, key="quick_c_tr")
        if st.button("🚀 Listeyi İndir ve Aç", width="stretch", type="primary", key="quick_c_btn"):
            if quick_url:
                with st.spinner("İndiriliyor..."):
                    try:
                        active_ua = USER_AGENT_PROFILES.get(
                            st.session_state.selected_ua_profile, USER_AGENT
                        )
                        lines = network_utils.fetch_m3u_source(
                            quick_url,
                            user_agent=active_ua,
                            timeout=REQUEST_TIMEOUT,
                            disable_ssl_verify=DISABLE_SSL_VERIFY,
                            proxy_url=st.session_state.upstream_proxy or None,
                        )
                        replacement = import_playlist(lines, only_tr=quick_tr)
                        replace_playlist(replacement)
                        if quick_url not in st.session_state.recent_urls:
                            st.session_state.recent_urls = [
                                quick_url
                            ] + st.session_state.recent_urls[:4]
                        st.rerun()
                    except Exception as e:
                        st.error(f"Hata: {e}")
            else:
                st.warning("Lütfen bir link girin.")

    with card_c2, st.container(key="import_file"):
        st.markdown("#### 📂 Dosya yükle")
        center_file = st.file_uploader(
            "M3U / M3U8 Dosyası Bırakın", type=["m3u", "m3u8"], key="quick_c_file"
        )
        if center_file:
            try:
                replace_playlist(import_playlist(center_file.getvalue(), only_tr=DEFAULT_TR_FILTER))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

