# -*- coding: utf-8 -*-
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.request
import urllib.error
import re
import io
import json
import time
import uuid
import sys
import os

# Utils klasorunu Python path'ine ekle
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'utils'))

try:
    from visitor_counter import VisitorCounter
    from m3u_parser import M3UParser
    import config
    MODULES_LOADED = True
except ImportError as e:
    print(f"Modul yukleme hatasi: {e}")
    MODULES_LOADED = False
    # Fallback basit parser
    class SimpleParser:
        def parse_m3u_lines(self, iterator):
            channels = []
            current_info = None
            for line in iterator:
                if isinstance(line, bytes):
                    try:
                        line = line.decode('utf-8', errors='ignore').strip()
                    except:
                        continue
                else:
                    line = line.strip()
                
                if not line:
                    continue
                    
                if line.startswith("#EXTINF"):
                    info = {"Grup": "Genel", "Kanal Adi": "Bilinmeyen", "URL": ""}
                    grp = re.search(r'group-title="([^"]*)"', line)
                    if grp:
                        info["Grup"] = grp.group(1)
                    
                    parts = line.split(",")
                    if len(parts) > 1:
                        info["Kanal Adi"] = parts[-1].strip()
                    
                    current_info = info
                    
                elif line and not line.startswith("#"):
                    if current_info:
                        current_info["URL"] = line
                        channels.append(current_info)
                        current_info = None
            return channels
        
        def filter_channels(self, channels, only_tr=False):
            if not only_tr:
                return channels
            tr_pattern = re.compile(r'(\b|_)(TR|TURK|TÜRK)(\b|_)', re.IGNORECASE)
            return [ch for ch in channels if tr_pattern.search(ch["Grup"])]
        
        def convert_to_m3u(self, channels):
            content = "#EXTM3U\n"
            for channel in channels:
                content += f'#EXTINF:-1 group-title="{channel["Grup"]}",{channel["Kanal Adi"]}\n{channel["URL"]}\n'
            return content
    
    m3u_parser = SimpleParser()

# Sayfa Ayarlari
st.set_page_config(
    page_title="M3U Editor Pro (Web)", 
    layout="wide", 
    page_icon="📺",
    initial_sidebar_state="expanded"
)

# Basit CSS
st.markdown("""
    <style>
    .stApp {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .main-header {
        color: #4f46e5;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8fafc;
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #4f46e5;
    }
    .metric-label {
        font-size: 0.875rem;
        color: #64748b;
        text-transform: uppercase;
    }
    </style>
""", unsafe_allow_html=True)

# M3U parser instance'i olustur
if MODULES_LOADED:
    try:
        m3u_parser = M3UParser({
            'user_agent': config.USER_AGENT,
            'timeout': config.REQUEST_TIMEOUT,
            'disable_ssl_verify': config.DISABLE_SSL_VERIFY
        })
    except:
        m3u_parser = SimpleParser()

# Session state initialization
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Sec", "Grup", "Kanal Adi", "URL"])

if 'visitor_counter' not in st.session_state and MODULES_LOADED:
    try:
        st.session_state.visitor_counter = VisitorCounter()
        if 'session_id' not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.visitor_counter.increment_visit(st.session_state.session_id)
    except:
        pass

# Sidebar
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <div style="font-size: 2rem;">📺</div>
            <h3 style="margin: 0.5rem 0 0 0; color: #4f46e5;">IPTV MANAGER</h3>
            <p style="margin: 0; color: #64748b; font-size: 0.875rem;">M3U Playlist Editor</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    mode = st.radio("**Yukleme Yontemi**", ["🌐 URL'den Yukle", "📂 Dosya Yukle"])
    
    if mode == "🌐 URL'den Yukle":
        url = st.text_input("M3U Linki:", placeholder="https://example.com/playlist.m3u")
        only_tr = st.checkbox("🇹🇷 Sadece TR Kanallari", value=True)
        
        if st.button("📥 Listeyi Yukle", type="primary", use_container_width=True):
            if url:
                with st.spinner("Liste yukleniyor..."):
                    try:
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        req = urllib.request.Request(url, headers=headers)
                        
                        import ssl
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        
                        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                            raw_channels = m3u_parser.parse_m3u_lines(response)
                            final_channels = m3u_parser.filter_channels(raw_channels, only_tr)
                            
                            if final_channels:
                                new_data = pd.DataFrame(final_channels)
                                if "Sec" not in new_data.columns:
                                    new_data.insert(0, "Sec", False)
                                st.session_state.data = new_data
                                st.success(f"✅ {len(final_channels)} kanal yuklendi!")
                            else:
                                st.warning("Kanal bulunamadi veya format hatali.")
                    except Exception as e:
                        st.error(f"Hata: {str(e)}")
            else:
                st.warning("Lutfen bir URL girin.")
    
    else:  # Dosya Yukleme
        uploaded_file = st.file_uploader("M3U Dosyasi Sec:", type=['m3u', 'm3u8'])
        if uploaded_file and st.button("📂 Dosyayi Yukle", use_container_width=True):
            try:
                stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8", errors='ignore'))
                raw_channels = m3u_parser.parse_m3u_lines(stringio)
                if raw_channels:
                    new_data = pd.DataFrame(raw_channels)
                    if "Sec" not in new_data.columns:
                        new_data.insert(0, "Sec", False)
                    st.session_state.data = new_data
                    st.success(f"✅ {len(raw_channels)} kanal yuklendi!")
                else:
                    st.warning("Dosyada kanal bulunamadi.")
            except Exception as e:
                st.error(f"Hata: {str(e)}")
    
    st.markdown("---")
    
    # Veri islemleri
    if not st.session_state.data.empty:
        st.subheader("📊 Veri Islemleri")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Tumunu Sec", use_container_width=True):
                st.session_state.data["Sec"] = True
                st.rerun()
        with col2:
            if st.button("❌ Secimi Temizle", use_container_width=True):
                st.session_state.data["Sec"] = False
                st.rerun()
        
        if st.button("🧹 Ciftleri Temizle", use_container_width=True):
            before = len(st.session_state.data)
            st.session_state.data = st.session_state.data.drop_duplicates(subset=["Grup", "Kanal Adi", "URL"], keep='first')
            after = len(st.session_state.data)
            st.success(f"✅ {before - after} cift kaldirildi.")
            st.rerun()
        
        selected_count = len(st.session_state.data[st.session_state.data["Sec"] == True])
        
        st.markdown("---")
        st.subheader("💾 Indirme")
        
        if selected_count > 0:
            download_df = st.session_state.data[st.session_state.data["Sec"] == True]
            btn_label = f"📥 Secileni Indir ({selected_count})"
        else:
            download_df = st.session_state.data
            btn_label = "📥 Tumunu Indir"
        
        # M3U Indirme
        m3u_content = m3u_parser.convert_to_m3u(download_df.to_dict('records'))
        st.download_button(
            label=btn_label,
            data=m3u_content,
            file_name="iptv_listesi.m3u",
            mime="text/plain",
            use_container_width=True
        )

# Ana Icerik
st.markdown('<h1 class="main-header">📺 M3U Editor Pro</h1>', unsafe_allow_html=True)
st.markdown("Profesyonel IPTV playlist yonetimi ve duzenleme araci")

if not st.session_state.data.empty:
    # Istatistikler
    st.subheader("📈 Istatistikler")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_channels = len(st.session_state.data)
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{total_channels}</div>
                <div class="metric-label">Toplam Kanal</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        selected_count = len(st.session_state.data[st.session_state.data["Sec"] == True])
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{selected_count}</div>
                <div class="metric-label">Secilen</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        unique_groups = st.session_state.data["Grup"].nunique()
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{unique_groups}</div>
                <div class="metric-label">Grup</div>
            </div>
        """, unsafe_allow_html=True)
    
    # Arama ve Filtreleme
    st.subheader("🔍 Kanal Listesi")
    
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_term = st.text_input("Ara:", placeholder="Kanal veya grup adi...")
    with search_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Listeyi Temizle"):
            st.session_state.data = pd.DataFrame(columns=["Sec", "Grup", "Kanal Adi", "URL"])
            st.rerun()
    
    # Filtreleme
    df_display = st.session_state.data
    if search_term:
        df_display = df_display[
            df_display["Grup"].str.contains(search_term, case=False, na=False) | 
            df_display["Kanal Adi"].str.contains(search_term, case=False, na=False)
        ]
    
    # Grup filtreleme
    if not df_display.empty:
        group_options = sorted(df_display["Grup"].dropna().unique().tolist())
        if group_options:
            selected_groups = st.multiselect("Gruplara gore filtrele:", group_options, default=group_options)
            if selected_groups:
                df_display = df_display[df_display["Grup"].isin(selected_groups)]
    
    # Tablo
    if not df_display.empty:
        st.data_editor(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Sec": st.column_config.CheckboxColumn("Sec", default=False),
                "Grup": st.column_config.TextColumn("Grup"),
                "Kanal Adi": st.column_config.TextColumn("Kanal Adi"),
                "URL": st.column_config.TextColumn("URL", width="large")
            },
            disabled=["Grup", "Kanal Adi", "URL"],
            key="channel_editor"
        )
    else:
        st.info("📭 Filtreye uygun kanal bulunamadi.")
else:
    st.info("""
    👈 **Baslamak icin sol menuden:**  
    1. M3U linki yapistirin veya  
    2. M3U dosyasi yukleyin  
    
    🚀 **Ozellikler:**  
    • TR kanal filtreleme  
    • Cift kanal temizleme  
    • Secimli indirme  
    • Grup bazli filtreleme
    """)

# Ziyaretci Sayaci (opsiyonel)
if MODULES_LOADED and 'visitor_counter' in st.session_state:
    try:
        stats = st.session_state.visitor_counter.get_stats()
        st.markdown("---")
        st.caption(f"👥 Ziyaretci: {stats.get('unique_visitors', 0)} • 📅 Ilk: {stats.get('first_visit', 'Bilinmiyor')}")
    except:
        pass

# Footer
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #64748b; padding: 1rem 0; font-size: 0.875rem;">
        <p>© 2025 M3U Editor Pro v1.0.0 • Made with Streamlit</p>
    </div>
""", unsafe_allow_html=True)
