"""Channel selection and safe playback view."""

import streamlit as st
import streamlit.components.v1 as components

from utils.config import ENABLE_LIVE_PLAYER
from utils.parser import convert_df_to_m3u
from utils.player import render_live_player
from utils.security import validate_url


def _stop_player():
    st.session_state.play_channel = None
    st.session_state.player_tab_select_box = "Seçiniz..."


def render_player(df_display, get_proxy_server):
    play_options = []
    play_url_map = {}

    for idx, row in df_display.iterrows():
        durum = str(row.get("Durum", "❔")).split(" ")[0] if "Durum" in row else "❔"
        base_name = f"{durum} {row['Kanal Adı']}"

        display_name = base_name
        counter = 2
        while display_name in play_url_map:
            display_name = f"{base_name} ({counter})"
            counter += 1

        play_options.append(display_name)
        play_url_map[display_name] = {
            "name": row["Kanal Adı"],
            "url": row["URL"],
            "logo": row.get("LogoURL", ""),
            "group": row.get("Grup", ""),
            "durum": row.get("Durum", ""),
        }

    current_play = st.session_state.get("play_channel")
    default_index = 0
    if current_play:
        for i, opt in enumerate(play_options):
            info = play_url_map[opt]
            if info["name"] == current_play.get("name") and info["url"] == current_play.get("url"):
                default_index = i + 1
                break

    p_left, p_right = st.columns([1.1, 2.9])
    with p_left:
        play_name_display = st.selectbox(
            "Kanal seçin",
            options=["Seçiniz..."] + play_options,
            index=default_index,
            key="player_tab_select_box",
        )
        if play_name_display != "Seçiniz...":
            selected_info = play_url_map.get(play_name_display)
            if selected_info:
                current = st.session_state.get("play_channel")
                if (
                    not current
                    or current.get("url") != selected_info["url"]
                    or current.get("name") != selected_info["name"]
                ):
                    st.session_state.play_channel = selected_info
                    st.rerun()
        else:
            if st.session_state.play_channel:
                st.session_state.play_channel = None
                st.rerun()

        if st.session_state.play_channel:
            pc = st.session_state.play_channel
            if pc.get("logo"):
                try:
                    validate_url(pc["logo"])
                    st.image(pc["logo"], width=72)
                except (ValueError, OSError):
                    pass
            st.caption(f"{pc.get('group', 'Genel')} · {pc.get('durum', '❔')}")

            if "VPN" in pc.get("durum", ""):
                st.warning("🌍 Bölgesel kısıtlama (VPN gerekebilir)")

            b_stop, b_dl = st.columns(2)
            with b_stop:
                st.button("⏹ Durdur", width="stretch", on_click=_stop_player)
            with b_dl:
                single_m3u = convert_df_to_m3u(
                    st.session_state.data[st.session_state.data["URL"] == pc["url"]].head(1)
                )
                st.download_button(
                    "📥 İndir",
                    data=single_m3u,
                    file_name=f"{pc['name']}.m3u",
                    width="stretch",
                )

            proxy_srv = get_proxy_server()
            with st.expander("Bağlantı adresleri"):
                st.caption("Akış URL")
                st.code(pc["url"], language=None)
                st.caption("Yerel proxy URL")
                st.code(proxy_srv.get_proxy_url(pc["url"], public=True), language=None)
        else:
            st.caption("İzlemek istediğiniz kanalı listeden seçin.")

    with p_right:
        if st.session_state.play_channel:
            pc = st.session_state.play_channel
            if ENABLE_LIVE_PLAYER:
                proxy_base = get_proxy_server().endpoint_url("proxy", public=True)
                player_html = render_live_player(
                    pc["url"],
                    height=420,
                    proxy_base_url=proxy_base,
                    use_proxy=st.session_state.get("use_player_proxy", True),
                )
                if hasattr(st, "iframe"):
                    st.iframe(player_html, height=450)
                else:
                    components.html(player_html, height=450)
            else:
                st.info("Canlı oynatıcı yapılandırmada kapalı.")
        else:
            st.markdown(
                "<div class='player-placeholder'>"
                "<span class='player-placeholder__icon' aria-hidden='true'>▷</span>"
                "<p>Soldan bir kanal seçtiğinizde yayın burada başlar.</p>"
                "</div>",
                unsafe_allow_html=True,
            )

