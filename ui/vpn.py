"""Validated session-specific upstream settings."""

import streamlit as st

from utils.config import USER_AGENT, USER_AGENT_PROFILES


def render_vpn(df_display, get_proxy_server):
    v_col_settings, v_col_guide = st.columns([1.2, 1.8])
    with v_col_settings:
        st.markdown("#### ⚙️ Proxy & Tünel Ayarları")
        st.caption(
            "Yurt dışı veya bölge engelli akışları aşmak için proxy ve kimlik profili yapılandırması:"
        )

        cfg_proxy = st.text_input(
            "Upstream Proxy (HTTP/HTTPS):",
            value=st.session_state.upstream_proxy,
            placeholder="http://127.0.0.1:10808 veya http://proxy:port",
            help="Yerel VPN istemcinizin (Clash, v2ray, xray vb.) veya harici proxy adresiniz.",
            key="tab_vpn_proxy_input",
        )
        profile_list = list(USER_AGENT_PROFILES.keys())
        p_index = (
            profile_list.index(st.session_state.selected_ua_profile)
            if st.session_state.selected_ua_profile in profile_list
            else 0
        )
        cfg_profile = st.selectbox(
            "Oynatıcı / Cihaz Profili (User-Agent):",
            profile_list,
            index=p_index,
            help="Sunucuların tarayıcı engellerini aşmak için TiviMate veya VLC seçebilirsiniz.",
            key="tab_vpn_profile_select",
        )
        cfg_ref = st.text_input(
            "Özel Referer Başlığı (Opsiyonel):",
            value=st.session_state.custom_referer,
            placeholder="Örn: https://iptv-provider.com",
            key="tab_vpn_ref_input",
        )

        st.checkbox("Akışı yerel proxy üzerinden oynat", value=True, key="use_player_proxy")
        try:
            get_proxy_server().set_proxy_config(
                upstream_proxy=cfg_proxy.strip(),
                custom_user_agent=USER_AGENT_PROFILES.get(cfg_profile, USER_AGENT),
                custom_referer=cfg_ref.strip(),
            )
            st.session_state.upstream_proxy = cfg_proxy.strip()
            st.session_state.selected_ua_profile = cfg_profile
            st.session_state.custom_referer = cfg_ref.strip()
        except ValueError as exc:
            st.error(str(exc))

        if st.session_state.upstream_proxy:
            st.success(
                f"🟢 **Upstream proxy yapılandırıldı:** `{st.session_state.upstream_proxy}`\n\nBağlantı kullanılabilirliği akış isteğinde doğrulanır."
            )
        else:
            st.info("⚪ **Doğrudan Bağlantı:** Herhangi bir ara proxy kullanılmıyor.")

    with v_col_guide:
        st.markdown("#### 📘 Yurt Dışı Akışları Çözüm Rehberi")
        st.markdown("""
        * **1. Cihaz Profili:** Sağlayıcınızın desteklediği User-Agent profilini seçin. Profil değişikliği erişim veya bölge kısıtlamalarının kalkacağını garanti etmez.
        * **2. Upstream Proxy:** Güvendiğiniz HTTP/HTTPS proxy adresini girin (örn: `http://127.0.0.1:10808`). Uygulamanın indirme ve kontrol istekleri ile yerel proxy üzerinden oynatılan akışlar bu bağlantıyı kullanır. Doğrudan tarayıcı oynatımı kullanmaz.
        * **3. Smart TV VPN Köprüsü:** Smart TV'nize VPN kuramıyorsanız, **'📤 Dışa Aktar & Paylaş'** sekmesinden *VPN Köprüsü M3U* dosyasını TV'nize yükleyin. TV akışları bu bilgisayar üzerinden izler.
        * **4. TV Erişimi:** LAN paylaşımını açın ve yerel liste linkini TV'ye girin. Link uygulama oturumuna bağlıdır; bilgisayar ve uygulama açık kalmalıdır.
        """)
