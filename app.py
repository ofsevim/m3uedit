import html
import logging
import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

# --- MODÜL YOLLARI ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# --- YAPILANDIRMA ---
from utils.config import (
    APP_VERSION,
    DEFAULT_UPSTREAM_PROXY,
    ENABLE_VISITOR_COUNTER,
    PAGE_ICON,
    PAGE_TITLE,
)

# --- LOG ---
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True
    )
logger = logging.getLogger(__name__)

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title=PAGE_TITLE,
    layout="wide",
    page_icon=PAGE_ICON,
    initial_sidebar_state="auto",
)

# --- YARDIMCI MODÜLLER ---
from ui.editor import render_editor
from ui.exports import render_exports
from ui.imports import render_empty_state, render_source_loader
from ui.player import render_player
from ui.vpn import render_vpn
from utils.playlist import ensure_columns
from utils.proxy_server import LocalProxyServer
from utils.visitor_counter import VisitorCounter


def get_proxy_server():
    if "proxy_server" not in st.session_state:
        server = LocalProxyServer()
        server.start()
        st.session_state.proxy_server = server
    return st.session_state.proxy_server


# --- CSS ---
def _load_css():
    css_path = os.path.join(current_dir, "static", "styles.css")
    try:
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except OSError:
        pass


_load_css()


# --- SİSTEMLER ---
vc = VisitorCounter() if ENABLE_VISITOR_COUNTER else None


# =====================================================================
# YARDIMCI FONKSİYONLAR
# =====================================================================


def _status_counts(df: pd.DataFrame) -> dict[str, int]:
    statuses = df.get("Durum", pd.Series(dtype=str)).astype(str)
    return {
        "active": int(statuses.str.contains("✅", na=False).sum()),
        "vpn": int(statuses.str.contains("🌍", na=False).sum()),
        "error": int(statuses.str.contains("❌", na=False).sum()),
        "pending": int(statuses.str.contains("Bekliyor", na=False).sum()),
    }


# =====================================================================
# SESSION STATE
# =====================================================================

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame()
if "play_channel" not in st.session_state:
    st.session_state.play_channel = None
if "recent_urls" not in st.session_state:
    st.session_state.recent_urls = []
if "upstream_proxy" not in st.session_state:
    st.session_state.upstream_proxy = DEFAULT_UPSTREAM_PROXY
if "selected_ua_profile" not in st.session_state:
    st.session_state.selected_ua_profile = "Standart (Tarayıcı)"
if "custom_referer" not in st.session_state:
    st.session_state.custom_referer = ""
if "show_add_channel" not in st.session_state:
    st.session_state.show_add_channel = False

# Ziyaretçi takibi
if vc is not None and "visited" not in st.session_state:
    session_id = None
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        ctx = get_script_run_ctx()
        if ctx:
            session_id = ctx.session_id
    except ImportError:
        pass
    vc.increment_visit(session_id)
    st.session_state.visited = True

# =====================================================================
# SIDEBAR
# =====================================================================

with st.sidebar:
    st.markdown(
        "<div class='sidebar-brand'>"
        "<span class='sidebar-brand__icon' aria-hidden='true'>▤</span>"
        "<div>"
        "<span class='sidebar-brand__title'>M3U Editör Pro</span>"
        "<span class='sidebar-brand__subtitle'>Kanal çalışma alanınız</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Ağ & Proxy mini durum göstergesi
    if st.session_state.upstream_proxy:
        st.markdown(
            "<div class='connection-status connection-status--active'><span class='status-dot'></span>Proxy yapılandırıldı</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='connection-status'><span class='status-dot'></span>Doğrudan bağlantı</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    render_source_loader()

    # Filtreler
    selected_groups = []
    selected_types = []
    selected_statuses = []
    if not st.session_state.data.empty:
        st.markdown("#### Liste filtreleri")
        try:
            group_options = sorted(st.session_state.data["Grup"].astype(str).dropna().unique())
        except Exception:
            group_options = []
        if group_options:
            selected_groups = st.multiselect(
                "Grupları filtrele", group_options, default=None, key="group_filter"
            )

        type_options = sorted(
            st.session_state.data.get("Tür", pd.Series(dtype=str)).astype(str).dropna().unique()
        )
        if type_options:
            selected_types = st.multiselect(
                "Yayın türü", type_options, default=None, key="type_filter"
            )
        status_options = sorted(
            st.session_state.data.get("Durum", pd.Series(dtype=str)).astype(str).dropna().unique()
        )
        if status_options:
            selected_statuses = st.multiselect(
                "Duruma göre", status_options, default=None, key="status_filter"
            )

    # İstatistikler
    if vc is not None:
        stats = vc.get_stats()
        try:
            last_visit = datetime.fromisoformat(stats["last_visit"]).strftime("%d.%m.%Y %H:%M")
        except (ValueError, KeyError):
            last_visit = "—"
        with st.expander("Kullanım istatistikleri"):
            st.caption(
                f"{stats['total_visits']} ziyaret · {stats['unique_visitors']} tekil ziyaretçi"
            )
            st.caption(f"Son ziyaret: {last_visit}")

# =====================================================================
# ANA EKRAN
# =====================================================================

if not st.session_state.data.empty:
    # Filtreleme
    st.session_state.data = ensure_columns(st.session_state.data)
    df_display = st.session_state.data.copy()
    if selected_groups:
        df_display = df_display[df_display["Grup"].isin(selected_groups)]
    if selected_types:
        df_display = df_display[df_display["Tür"].isin(selected_types)]
    if selected_statuses:
        df_display = df_display[df_display["Durum"].isin(selected_statuses)]

    # Üst Başlık
    st.markdown(
        """
        <div class="page-header">
            <span class="eyebrow">ÇALIŞMA ALANI</span>
            <h1>Kanal listeniz, kontrolünüzde.</h1>
            <p>Kanalları düzenleyin, bağlantıları kontrol edin ve listenizi yanınızda götürün.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status_counts = _status_counts(df_display)
    group_count = df_display["Grup"].nunique()
    hls_count = int((df_display["Tür"] == "HLS").sum()) if "Tür" in df_display.columns else 0

    with st.container(key="workspace_summary"):
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Görünen / toplam kanal", f"{len(df_display)} / {len(st.session_state.data)}")
        mc2.metric("Kanal grubu", group_count)
        mc3.metric("Aktif bağlantı", status_counts["active"])
        mc4.metric("Bölgesel kısıtlama", status_counts["vpn"])
        mc5.metric("HLS yayını", hls_count)
        if status_counts["pending"]:
            st.caption(f"{status_counts['pending']} kanal henüz kontrol edilmedi.")

    active_filters = []
    active_filters.extend(f"Grup: {value}" for value in selected_groups)
    active_filters.extend(f"Tür: {value}" for value in selected_types)
    active_filters.extend(f"Durum: {value}" for value in selected_statuses)
    if active_filters:
        st.markdown(
            f"<div class='simple-strip'><strong>Aktif Filtreler:</strong> <span>{html.escape(' • '.join(active_filters))}</span></div>",
            unsafe_allow_html=True,
        )

    # 4 ANA ODAKLI SEKME
    tab_editor, tab_player, tab_export, tab_vpn = st.tabs(
        [
            "Kanallar",
            "Canlı oynatıcı",
            "Dışa aktar & paylaş",
            "Ağ ayarları",
        ]
    )

    # =====================================================================
    # SEKME 1: KANALLAR & DÜZENLEME
    # =====================================================================
    with tab_editor:
        df_display = render_editor(df_display)

    # =====================================================================
    # SEKME 2: CANLI OYNATICI (SİNEMATİK MOD)
    # =====================================================================
    with tab_player:
        render_player(df_display, get_proxy_server)

    # =====================================================================
    # SEKME 3: DIŞA AKTAR & PAYLAŞ
    # =====================================================================
    with tab_export:
        render_exports(df_display, get_proxy_server)

    # =====================================================================
    # SEKME 4: VPN & YURT DIŞI ÇÖZÜMLERİ
    # =====================================================================
    with tab_vpn:
        render_vpn(df_display, get_proxy_server)

else:
    render_empty_state()

# --- Footer ---
st.markdown(
    "<div class='app-footer'>"
    f"<span>M3U Editör Pro · {APP_VERSION}</span>"
    "<span>Yükle. Düzenle. İzle.</span>"
    "</div>",
    unsafe_allow_html=True,
)
