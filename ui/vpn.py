"""Validated session-specific upstream settings."""

import streamlit as st

from utils.config import USER_AGENT, USER_AGENT_PROFILES


def render_vpn(df_display, get_proxy_server):
    with st.container(key="network_settings"):
        c1, c2 = st.columns(2)
        with c1:
            profile_list = list(USER_AGENT_PROFILES.keys())
            p_index = (
                profile_list.index(st.session_state.selected_ua_profile)
                if st.session_state.selected_ua_profile in profile_list
                else 0
            )
            cfg_profile = st.selectbox(
                "Cihaz Profili (User-Agent)",
                profile_list,
                index=p_index,
                key="tab_vpn_profile_select",
            )
            cfg_ref = st.text_input(
                "Özel Referer Başlığı (Opsiyonel)",
                value=st.session_state.custom_referer,
                placeholder="https://iptv-provider.com",
                key="tab_vpn_ref_input",
            )
        with c2:
            cfg_proxy = st.text_input(
                "Upstream Proxy (HTTP/HTTPS)",
                value=st.session_state.upstream_proxy,
                placeholder="http://127.0.0.1:10808",
                key="tab_vpn_proxy_input",
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
            st.caption(f"🟢 Aktif proxy: `{st.session_state.upstream_proxy}`")
        else:
            st.caption("⚪ Doğrudan bağlantı kullanılıyor.")

    with st.expander("ℹ️ Bağlantı ve Smart TV rehberi"):
        st.markdown(
            "- **Cihaz Profili:** Sağlayıcınızın engellerini aşmak için TiviMate veya VLC seçebilirsiniz.\n"
            "- **Upstream Proxy:** Yerel VPN istemcinizin HTTP portunu (örn. `http://127.0.0.1:10808`) girin.\n"
            "- **Smart TV:** *İndir & Paylaş* sekmesinden *VPN Köprüsü M3U* dosyasını veya yerel ağ linkini kullanın."
        )

