"""Validated session-specific upstream settings."""

import streamlit as st

from utils.config import PLAYER_CLOUD_PROXY_URL, USER_AGENT, USER_AGENT_PROFILES


def _apply_network_settings(get_proxy_server):
    profile = st.session_state.tab_vpn_profile_select
    referer = st.session_state.tab_vpn_ref_input.strip()
    upstream = st.session_state.tab_vpn_proxy_input.strip()
    get_proxy_server().set_proxy_config(
        upstream_proxy=upstream,
        custom_user_agent=USER_AGENT_PROFILES.get(profile, USER_AGENT),
        custom_referer=referer,
    )
    st.session_state.upstream_proxy = upstream
    st.session_state.selected_ua_profile = profile
    st.session_state.custom_referer = referer


def _sync_network_settings(get_proxy_server):
    # Widget callbacks run before the player rerenders. Invalid input is reported
    # in the settings view and does not replace the last validated configuration.
    try:
        _apply_network_settings(get_proxy_server)
    except ValueError:
        pass


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
            st.selectbox(
                "Cihaz Profili (User-Agent)",
                profile_list,
                index=p_index,
                key="tab_vpn_profile_select",
                on_change=_sync_network_settings,
                args=(get_proxy_server,),
            )
            st.text_input(
                "Özel Referer Başlığı (Opsiyonel)",
                value=st.session_state.custom_referer,
                placeholder="https://iptv-provider.com",
                key="tab_vpn_ref_input",
                on_change=_sync_network_settings,
                args=(get_proxy_server,),
            )
        with c2:
            st.text_input(
                "Upstream Proxy (HTTP/HTTPS)",
                value=st.session_state.upstream_proxy,
                placeholder="http://127.0.0.1:10808",
                key="tab_vpn_proxy_input",
                on_change=_sync_network_settings,
                args=(get_proxy_server,),
            )
            st.checkbox("Akışı proxy üzerinden oynat", value=True, key="use_player_proxy")
            if PLAYER_CLOUD_PROXY_URL:
                st.caption(
                    "Bulut oynatıcı HTTPS proxy: "
                    + PLAYER_CLOUD_PROXY_URL
                    + " · Kanal adresi ve yayın erişim bilgileri bu sunucuya iletilir."
                )

        try:
            _apply_network_settings(get_proxy_server)
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
