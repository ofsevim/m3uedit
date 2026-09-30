"""Channel editor and health-check view."""

import time

import pandas as pd
import streamlit as st

from utils.config import (
    ENABLE_URL_HEALTH_CHECK,
    HEALTH_CHECK_MAX_WORKERS,
    HEALTH_CHECK_TIMEOUT,
    TABLE_HEIGHT,
    USER_AGENT,
    USER_AGENT_PROFILES,
)
from utils.parser import batch_check_health, detect_type
from utils.playlist import CHANNEL_ID, ensure_columns, merge_visible_edits
from utils.security import validate_url


def _safe_contains(series, term):
    return series.astype(str).str.contains(term, case=False, na=False, regex=False)


def render_editor(df_display):
    # Arama çubuğu
    search_term = st.text_input(
        "🔍 Kanal veya Grup Ara:",
        "",
        placeholder="Kanal adı veya grup yazarak anında filtreleyin...",
        key="tab_search",
    )
    if search_term:
        df_display = df_display[
            _safe_contains(df_display["Kanal Adı"], search_term)
            | _safe_contains(df_display["Grup"], search_term)
        ]

    # Hızlı Aksiyonlar
    st.caption("Tablodaki değişiklikleri uygulamak için alttaki kaydet düğmesini kullanın.")
    act1, act2, act3, act4 = st.columns([2.4, 1.4, 1.4, 1.2])

    with act1:
        c_sel, c_btn = st.columns([1, 1.4])
        with c_sel:
            h_limit = st.selectbox(
                "Tarama Limiti",
                [50, 100, 250, 500, "Tümü"],
                index=0,
                label_visibility="collapsed",
                key="h_limit_sel_editor",
            )
        with c_btn:
            run_health = st.button(
                "🔍 Sağlık Kontrolü",
                width="stretch",
                type="primary",
                disabled=not ENABLE_URL_HEALTH_CHECK,
            )

    with act2:
        has_dead = bool(
            (
                st.session_state.data["Durum"]
                .astype(str)
                .str.contains("❌|⏱️|Geçersiz|Bulunamadı", na=False)
            ).any()
        )
        clean_dead = st.button(
            "🧹 Ölüleri Temizle",
            width="stretch",
            disabled=not has_dead,
            help="❌ ve ⏱️ durumundaki kanalları listeden çıkarır.",
        )

    with act3:
        has_active = bool(
            (st.session_state.data["Durum"].astype(str).str.contains("✅", na=False)).any()
        )
        keep_active = st.button(
            "⭐ Sadece Çalışanlar",
            width="stretch",
            disabled=not has_active,
            help="Yalnızca '✅ Aktif' kanalları korur.",
        )

    with act4:
        toggle_add = st.button("➕ Kanal Ekle", width="stretch")

    if run_health:
        max_health = len(df_display) if h_limit == "Tümü" else int(h_limit)
        urls = df_display["URL"].head(max_health).tolist()
        total = len(urls)
        progress_bar = st.progress(0, text=f"🔍 Taranıyor... 0/{total}")
        start_time = time.time()

        def update_progress(completed, total_count):
            pct = completed / total_count
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            remaining = (total_count - completed) / speed if speed > 0 else 0
            progress_bar.progress(
                pct,
                text=f"🔍 {completed}/{total_count} — {pct:.0%} | ⏱️ ~{remaining:.0f}s kaldı",
            )

        active_ua = USER_AGENT_PROFILES.get(st.session_state.selected_ua_profile, USER_AGENT)
        extra_headers = (
            {"Referer": st.session_state.custom_referer}
            if st.session_state.custom_referer
            else None
        )

        results = batch_check_health(
            urls,
            max_workers=HEALTH_CHECK_MAX_WORKERS,
            timeout=HEALTH_CHECK_TIMEOUT,
            user_agent=active_ua,
            proxy_url=st.session_state.upstream_proxy or None,
            headers=extra_headers,
            progress_callback=update_progress,
        )

        elapsed = round(time.time() - start_time, 1)
        for i, u in enumerate(urls):
            st.session_state.data.loc[st.session_state.data["URL"] == u, "Durum"] = results[i]

        aktif = sum(1 for r in results if "✅" in r)
        vpn_cnt = sum(1 for r in results if "🌍" in r)
        oldu = sum(1 for r in results if "❌" in r)
        diger = total - aktif - vpn_cnt - oldu
        progress_bar.empty()
        st.success(
            f"✅ Tamamlandı ({elapsed}s) — 🟢 {aktif} aktif | 🌍 {vpn_cnt} VPN gerekli | 🔴 {oldu} ölü | 🟡 {diger} belirsiz"
        )
        time.sleep(1.2)
        st.session_state.edit_revision = st.session_state.get("edit_revision", 0) + 1
        st.rerun()

    if clean_dead:
        before_len = len(st.session_state.data)
        st.session_state.data = st.session_state.data[
            ~st.session_state.data["Durum"]
            .astype(str)
            .str.contains("❌|⏱️|Geçersiz|Bulunamadı", na=False)
        ].reset_index(drop=True)
        removed = before_len - len(st.session_state.data)
        st.toast(f"🧹 {removed} adet çalışmayan kanal temizlendi!", icon="✅")
        st.session_state.edit_revision = st.session_state.get("edit_revision", 0) + 1
        st.rerun()

    if keep_active:
        before_len = len(st.session_state.data)
        st.session_state.data = st.session_state.data[
            st.session_state.data["Durum"].astype(str).str.contains("✅", na=False)
        ].reset_index(drop=True)
        st.toast(f"⭐ Sadece {len(st.session_state.data)} aktif kanal korundu!", icon="⭐")
        st.session_state.edit_revision = st.session_state.get("edit_revision", 0) + 1
        st.rerun()

    if toggle_add:
        st.session_state.show_add_channel = not st.session_state.get("show_add_channel", False)
        st.rerun()

    if st.session_state.get("show_add_channel"):
        with st.container():
            st.markdown("##### ➕ Yeni Kanal Ekle")
            with st.form("add_channel_form_inline", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    new_name = st.text_input("Kanal Adı *")
                    new_grp = st.text_input("Grup *", value="Genel")
                with c2:
                    new_url = st.text_input("Akış URL *")
                    new_logo = st.text_input("Logo URL")
                s1, s2 = st.columns([1, 4])
                with s1:
                    add_submit = st.form_submit_button(
                        "Listeye Ekle", type="primary", width="stretch"
                    )
                with s2:
                    add_cancel = st.form_submit_button("Kapat")

                if add_submit:
                    if not new_name.strip() or not new_url.strip():
                        st.error("Kanal Adı ve Akış URL zorunludur!")
                    else:
                        try:
                            validate_url(new_url.strip())
                            if new_logo.strip():
                                validate_url(new_logo.strip())
                        except ValueError as exc:
                            st.error(str(exc))
                            st.stop()
                        new_t = detect_type(new_url.strip())
                        new_row = pd.DataFrame(
                            [
                                {
                                    "Kanal Adı": new_name.strip(),
                                    "Grup": new_grp.strip() or "Genel",
                                    "URL": new_url.strip(),
                                    "LogoURL": new_logo.strip(),
                                    "Tür": new_t,
                                    "Durum": "❔ Bekliyor",
                                }
                            ]
                        )
                        st.session_state.data = ensure_columns(
                            pd.concat([st.session_state.data, new_row], ignore_index=True)
                        )
                        st.session_state.edit_revision = (
                            st.session_state.get("edit_revision", 0) + 1
                        )
                        st.session_state.show_add_channel = False
                        st.success(f"✅ '{new_name}' eklendi!")
                        st.rerun()
                elif add_cancel:
                    st.session_state.show_add_channel = False
                    st.rerun()

    # Data Editor Tablosu
    display_cols = [
        c for c in ["Durum", "Grup", "Kanal Adı", "URL", "Tür"] if c in df_display.columns
    ]
    table_df = df_display[[CHANNEL_ID] + display_cols].reset_index(drop=True)

    edited_df = st.data_editor(
        table_df,
        width="stretch",
        hide_index=True,
        height=min(TABLE_HEIGHT, max(220, (len(table_df) + 2) * 35 + 3)),
        num_rows="dynamic",
        disabled=[CHANNEL_ID, "Durum", "Tür"],
        key="channel_data_editor_"
        + str(st.session_state.get("edit_revision", 0))
        + "_"
        + str(tuple(df_display[CHANNEL_ID])),
        column_config={
            CHANNEL_ID: None,
            "URL": st.column_config.TextColumn("URL", width="large"),
            "Tür": st.column_config.TextColumn("Tür", width="small"),
            "Durum": st.column_config.TextColumn("Durum", width="small"),
            "Grup": st.column_config.TextColumn("Grup", width="medium"),
            "Kanal Adı": st.column_config.TextColumn("Kanal Adı", width="medium"),
        },
    )

    if st.button("💾 Tablodaki Düzenlemeleri Listeye Kaydet", width="stretch"):
        try:
            st.session_state.data = merge_visible_edits(
                st.session_state.data, df_display[CHANNEL_ID].tolist(), edited_df
            )
            st.session_state.edit_revision = st.session_state.get("edit_revision", 0) + 1
            st.session_state.pop("export_artifact", None)
            st.toast("✅ Düzenlemeler kaydedildi!", icon="✅")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    return df_display
