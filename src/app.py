import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import urllib.request
import urllib.error
import re
import io
import json
import sys
import os

# Modül yolunu ekle
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils.visitor_counter import VisitorCounter
from utils.config import *

import hashlib
import time
import uuid

# Simple persistence for user history (last loads/exports)
HISTORY_FILE = "history.json"

def _load_history():
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def _save_history(hist):
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def add_history(entry):
    hist = _load_history()
    hist.append(entry)
    _save_history(hist)

# Sayfa Ayarları
st.set_page_config(
    page_title=PAGE_TITLE,
    layout="wide",
    page_icon=PAGE_ICON,
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/yourusername/m3uedit',
        'Report a bug': 'https://github.com/yourusername/m3uedit/issues',
        'About': '# M3U Editör Pro\nIPTV playlist yönetim aracı'
    }
)

# Özel CSS yükle
try:
    with open('static/styles.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except:
    pass

# --- GLOBAL TANIMLAMALAR ---

# TR kanal tespiti için regex pattern (parse ve filter'da ortak kullanılıyor)
TR_PATTERN = re.compile(
    r'(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)', 
    re.IGNORECASE
)

# --- FONKSİYONLAR ---

def parse_m3u_lines(iterator):
    """
    urllib veya dosya satırları üzerinde döner.
    M3U formatındaki kanalları parse eder ve liste olarak döner.
    """
    channels = []
    current_info = None

    for line in iterator:
        # Gelen satır byte ise decode et, string ise olduğu gibi al
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
            info = {"Grup": "Genel", "Kanal Adı": "Bilinmeyen", "URL": "", "LogoURL": ""}
            # TVG logos may be provided as tvg-logo="<url>"
            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            if logo_match:
                info["LogoURL"] = logo_match.group(1)
            
            grp = re.search(r'group-title="([^"]*)"', line)
            if grp:
                info["Grup"] = grp.group(1)
            
            parts = line.split(",")
            if len(parts) > 1:
                info["Kanal Adı"] = parts[-1].strip()
            
            current_info = info
            
        elif line and not line.startswith("#"):
            if current_info:
                current_info["URL"] = line
                channels.append(current_info)
                current_info = None

    return channels

def filter_channels(channels, only_tr=False):
    """
    Kanalları filtreler.
    only_tr=True ise sadece Türk kanallarını döner (TR_PATTERN ile eşleşenler).
    """
    if not only_tr:
        return channels
        
    filtered = []
    
    for ch in channels:
        if TR_PATTERN.search(ch["Grup"]):
            filtered.append(ch)
            
    return filtered

def convert_df_to_m3u(df):
    """Dataframe'i indirilebilir M3U formatına çevirir."""
    content = "#EXTM3U\n"
    for index, row in df.iterrows():
        content += f'#EXTINF:-1 group-title="{row["Grup"]}",{row["Kanal Adı"]}\n{row["URL"]}\n'
    return content

def render_live_player(stream_url: str, height: int = 420) -> str:
    """HTML snippet to embed a video player with better error handling."""
    url = stream_url if stream_url else ""
    h = str(height) if height else "420"
    
    html = f"""
    <div style='width:100%; height:{h}px; background:#000; border-radius:8px; overflow:hidden;'>
        <video id='m3u_player' controls autoplay playsinline style='width:100%; height:100%;'></video>
        <div id='error_msg' style='display:none; color:#fff; padding:20px; text-align:center;'>
            <p>⚠️ Video yüklenemedi. URL geçerli olmayabilir veya CORS hatası olabilir.</p>
        </div>
    </div>
    <script src='https://cdn.jsdelivr.net/npm/hls.js@latest'></script>
    <script>
        var video = document.getElementById('m3u_player');
        var errorDiv = document.getElementById('error_msg');
        var url = '{url}';
        
        if (!url) {{
            errorDiv.style.display = 'block';
            video.style.display = 'none';
        }} else if (Hls.isSupported()) {{
            var hls = new Hls({{
                enableWorker: true,
                lowLatencyMode: true,
                backBufferLength: 90
            }});
            
            hls.loadSource(url);
            hls.attachMedia(video);
            
            hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                video.play().catch(function(e) {{
                    console.log('Autoplay engellendi:', e);
                }});
            }});
            
            hls.on(Hls.Events.ERROR, function(event, data) {{
                if (data.fatal) {{
                    console.error('HLS Hatası:', data);
                    errorDiv.style.display = 'block';
                    video.style.display = 'none';
                }}
            }});
        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = url;
            video.addEventListener('loadedmetadata', function() {{
                video.play().catch(function(e) {{
                    console.log('Autoplay engellendi:', e);
                }});
            }});
            video.addEventListener('error', function() {{
                errorDiv.style.display = 'block';
                video.style.display = 'none';
            }});
        }} else {{
            errorDiv.innerHTML = '<p>⚠️ Tarayıcınız HLS formatını desteklemiyor.</p>';
            errorDiv.style.display = 'block';
            video.style.display = 'none';
        }}
    </script>
    """
    return html

# --- ARAYÜZ (UI) ---

# Ziyaretçi sayacı başlat
if 'visitor_counter' not in st.session_state:
    st.session_state.visitor_counter = VisitorCounter()

# Benzersiz session ID oluştur (her Streamlit session için)
if 'session_id' not in st.session_state:
    # UUID kullanarak benzersiz ID oluştur
    st.session_state.session_id = str(uuid.uuid4())
    # İlk session açılışında sayacı artır
    st.session_state.visitor_counter.increment_visit(st.session_state.session_id)

if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Seç", "Grup", "Kanal Adı", "URL"])

with st.sidebar:
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0;'>
            <h1 style='margin: 0; font-size: 2rem;'>📺</h1>
            <h2 style='margin: 0.5rem 0 0 0; font-size: 1.5rem;'>M3U Editör Pro</h2>
            <p style='margin: 0.25rem 0 0 0; color: #888; font-size: 0.9rem;'>IPTV Yönetim Aracı</p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    mode = st.radio("Yükleme Yöntemi", ["🌐 Linkten Yükle", "📂 Dosya Yükle"])
    # Basit tema desteği
    if 'theme' not in st.session_state:
        st.session_state.theme = 'Açık'
    theme = st.radio("Tema", ["Açık", "Koyu"], index=0 if st.session_state.theme == 'Açık' else 1)
    if theme != st.session_state.theme:
        st.session_state.theme = theme
        # Basit CSS teması uygulama
        if theme == 'Koyu':
            st.markdown("""
                <style>
                [data-testid="stAppViewContainer"]{ background: #0b1020; color: #e6e6e6; }
                </style>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
                <style>
                [data-testid="stAppViewContainer"]{ background: #ffffff; color: #000000; }
                </style>
            """, unsafe_allow_html=True)

    # Grup bazlı filtreleme (kenar durumlarda veri olduğunda etkinleşir)
    selected_groups = []
    if not st.session_state.data.empty:
        # Basit sıralama seçeneği
        sort_by = st.sidebar.selectbox("Sırala", ["Grup", "Kanal Adı", "URL"] , index=0)
        sort_dir = st.sidebar.radio("Yön", ["A → Z", "Z → A"], index=0)
        if sort_by and not st.session_state.data.empty:
            st.session_state.data = st.session_state.data.sort_values(by=sort_by, ascending=(sort_dir=="A → Z"))
        try:
            group_options = sorted(st.session_state.data["Grup"].astype(str).dropna().unique())
        except Exception:
            group_options = []
        if group_options:
            selected_groups = st.multiselect("Grupları filtrele", group_options, default=group_options)
    
    new_data = None
    
    if mode == "🌐 Linkten Yükle":
        url = st.text_input("M3U Linki Yapıştır:")
        only_tr = st.checkbox("🇹🇷 SADECE GRUPTA ARA (TR Filtresi)", value=True)
        
        if st.button("Listeyi Çek ve Tara", use_container_width=True):
            if url:
                try:
                    with st.spinner('Link indiriliyor ve taranıyor...'):
                        # --- DEĞİŞİKLİK BURADA: URLLIB KULLANIMI ---
                        # Masaüstü uygulamasındaki yöntemin aynısı
                        headers = {'User-Agent': 'Mozilla/5.0'}
                        req = urllib.request.Request(url, headers=headers)
                        
                        # SSL sertifika hatalarını yok saymak için context (gerekirse)
                        import ssl
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        
                        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                            duplicates = 0
                            raw_channels = parse_m3u_lines(response)
                            final_channels = filter_channels(raw_channels, only_tr)
                            new_data = pd.DataFrame(final_channels)
                            duplicates = new_data.duplicated(subset=["Grup", "Kanal Adı", "URL"]).sum() if not new_data.empty else 0
                            
                            if not final_channels:
                                st.warning("⚠️ Linkten veri çekildi ama kanal bulunamadı veya format hatalı.")
                            else:
                                st.success(f"✅ İşlem Tamam! Toplam {len(final_channels)} kanal bulundu.")
                                add_history({"type": "load", "count": int(len(final_channels)), "url": url, "time": time.time()})
                            if duplicates:
                                st.info(f"⚠️ Tespit edilen tekrarlı kanal sayısı: {int(duplicates)}. Çiftleri temizlemek için 'Çiftleri Temizle' tuşuna basabilirsiniz.")
                            
                except urllib.error.HTTPError as e:
                     st.error(f"🚫 HTTP Hatası: {e.code} - {e.reason}")
                     st.info("💡 İpucu: Link doğru mu? Bazı sağlayıcılar erişim kısıtlaması olabilir.")
                except urllib.error.URLError as e:
                     st.error(f"🔌 Bağlantı Hatası: {e.reason}")
                     st.info("💡 İpucu: İnternet bağlantınızı kontrol edin veya VPN kullanmayı deneyin.")
                except TimeoutError:
                      st.error("⏱️ Zaman Aşımı: Sunucu çok yavaş yanıt veriyor (30 saniye)")
                      st.info("💡 İpucu: Daha sonra tekrar deneyin veya başka bir link kullanın.")
                except Exception as e:
                    st.error(f"❌ Beklenmeyen Hata: {str(e)}")
                    st.info("💡 İpucu: Link formatı M3U olmalı. Örnek: http://example.com/playlist.m3u")
            else:
                st.warning("Lütfen bir link girin.")

    elif mode == "📂 Dosya Yükle":
        uploaded_file = st.file_uploader("M3U Dosyası Seç", type=['m3u', 'm3u8'])
        if uploaded_file is not None:
            # Dosyayı satır satır okumak için
            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8", errors='ignore'))
            raw_channels = parse_m3u_lines(stringio)
            new_data = pd.DataFrame(raw_channels)
            st.success(f"Dosya yüklendi. {len(raw_channels)} kanal.")

    if new_data is not None:
        # Ziyaretçi sonrası ek alanlar
        if "Seç" not in new_data.columns:
            new_data.insert(0, "Seç", False)
        if "Favori" not in new_data.columns:
            new_data.insert(1, "Favori", False)
        if "LogoURL" not in new_data.columns:
            new_data.insert(2, "LogoURL", "")
        if "Durum" not in new_data.columns:
            new_data.insert(3, "Durum", "")
        st.session_state.data = new_data

    st.markdown("---")
    
    if not st.session_state.data.empty:
        selected_rows = st.session_state.data[st.session_state.data["Seç"] == True]
        count_selected = len(selected_rows)
        
        if count_selected > 0:
            st.success(f"✅ {count_selected} kanal seçildi.")
            download_df = selected_rows
            btn_label = f"💾 SADECE SEÇİLENLERİ İNDİR ({count_selected})"
            file_name_suffix = "_secilenler"
        else:
            st.info("ℹ️ Hiçbir seçim yapmadınız, tüm liste indirilecek.")
            download_df = st.session_state.data
            btn_label = "💾 TÜM LİSTEYİ İNDİR"
            file_name_suffix = "_tum_liste"

        m3u_output = convert_df_to_m3u(download_df)
        st.download_button(
            label=btn_label,
            data=m3u_output,
            file_name=f"iptv_listesi{file_name_suffix}.m3u",
            mime="text/plain",
            type="primary",
            use_container_width=True
        )
        # URL sağlık kontrolü
        if not st.session_state.data.empty:
            if st.button("🔍 URL Sağlık Kontrolü"):
                with st.spinner("Sağlık kontrolü çalışıyor..."):
                    df = st.session_state.data.copy()
                    statuses = []
                    for url in df["URL"].astype(str):
                        if not url or url.strip() == "":
                            statuses.append("Boş URL")
                            continue
                        try:
                            with urllib.request.urlopen(url, timeout=5) as resp:
                                code = getattr(resp, 'status', 200)
                                statuses.append("OK" if int(code) < 400 else f"{code}")
                        except Exception:
                            statuses.append("HATA")
                    df.loc[:, "Durum"] = statuses
                    st.session_state.data = df
                    st.success("Durumlar güncellendi.")

# Ana Ekran
st.subheader("Kanal Listesi Düzenleyici")

if not st.session_state.data.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Kanal", len(st.session_state.data))
    
    selected_count = len(st.session_state.data[st.session_state.data["Seç"] == True])
    col2.metric("Seçilen Kanal", selected_count)
    
    unique_groups = st.session_state.data["Grup"].nunique()
    col3.metric("Grup Sayısı", unique_groups)

    search_term = st.text_input("🔍 Tablo içinde ara (Grup veya Kanal Adı):", "")

    df_display = st.session_state.data
    # Grup filtrelemesi uygulanır
    if selected_groups:
        df_display = df_display[df_display["Grup"].isin(selected_groups)]
    
    if search_term:
        df_display = df_display[
            df_display["Grup"].str.contains(search_term, case=False) | 
            df_display["Kanal Adı"].str.contains(search_term, case=False)
        ]

    # Oynatılacak kanal için session state
    if 'play_channel' not in st.session_state:
        st.session_state.play_channel = None

    # Kanal oynatma butonu için form (YUKARIDA)
    st.markdown("### 🎬 Canlı Oynatıcı")
    col_play1, col_play2 = st.columns([3, 1])
    with col_play1:
        play_channel_name = st.selectbox("Oynatılacak Kanal", 
            options=df_display["Kanal Adı"].tolist() if not df_display.empty else [],
            index=None, placeholder="Kanal seçin...", key="play_select")
    with col_play2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶ OYNAT", use_container_width=True, key="play_btn"):
            if play_channel_name:
                selected_row = df_display[df_display["Kanal Adı"] == play_channel_name]
                if not selected_row.empty:
                    st.session_state.play_channel = {
                        "name": play_channel_name,
                        "url": selected_row.iloc[0]["URL"],
                        "logo": selected_row.iloc[0].get("LogoURL", "")
                    }
                    st.rerun()

    # Player bölümü
    if st.session_state.play_channel:
        pc = st.session_state.play_channel
        st.markdown(f"**▶ Oynatılıyor:** {pc['name']}")
        
        # Logo varsa göster
        if pc.get("logo"):
            try:
                st.image(pc["logo"], width=100)
            except:
                pass
        
        # Player
        components.html(render_live_player(pc["url"], height=400), height=500)
        
        if st.button("⏹ Oynatmayı Durdur", use_container_width=True):
            st.session_state.play_channel = None
            st.rerun()
        
        st.markdown("---")

    st.caption("İstediğiniz kanalların başındaki kutucuğu işaretleyin.")

    # Mevcut kolonları kontrol et
    available_columns = list(df_display.columns) if not df_display.empty else []

    # Tabloyu düzenle
    edited_df = st.data_editor(
        df_display,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        height=600,
        key="editor"
    )

    if not edited_df.equals(df_display):
        st.session_state.data.update(edited_df)
        st.rerun()

else:
    st.info("👈 Başlamak için sol menüden bir link yapıştırın veya dosya yükleyin.")

# --- ZİYARETÇİ SAYACI (Sayfa Altı) ---
st.markdown("---")
st.markdown("### 📊 Ziyaretçi İstatistikleri")

# İstatistikleri al
stats = st.session_state.visitor_counter.get_stats()

# Görsel istatistik kartları
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🌟 Benzersiz Ziyaretçi",
        value=f"{stats['unique_visitors']:,}".replace(',', '.'),
        help="Tarayıcı çerezlerine göre benzersiz ziyaretçi sayısı"
    )

with col2:
    st.metric(
        label="📊 Toplam Kayıt",
        value=f"{stats['total_visits']:,}".replace(',', '.'),
        help="Toplam kayıtlı ziyaret sayısı (benzersiz ziyaretçilere eşittir)"
    )

with col3:
    # İlk ziyaret tarihini formatla
    try:
        from datetime import datetime
        first_visit = datetime.fromisoformat(stats['first_visit'])
        first_visit_str = first_visit.strftime("%d.%m.%Y")
    except:
        first_visit_str = "Bilinmiyor"
    
    st.metric(
        label="📅 İlk Ziyaret",
        value=first_visit_str
    )

with col4:
    # Son ziyaret tarihini formatla
    try:
        from datetime import datetime
        last_visit = datetime.fromisoformat(stats['last_visit'])
        last_visit_str = last_visit.strftime("%d.%m.%Y %H:%M")
    except:
        last_visit_str = "Bilinmiyor"
    
    st.metric(
        label="🕒 Son Ziyaret",
        value=last_visit_str
    )

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888; padding: 20px; margin-top: 20px;'>
        <p style='margin: 0; font-size: 0.9rem;'>© 2025 M3U Editör Pro | 
        <a href='https://github.com/yourusername/m3uedit' target='_blank' style='color: #FF4B4B; text-decoration: none;'>GitHub</a> | 
        <a href='docs/KULLANIM_KILAVUZU.md' target='_blank' style='color: #FF4B4B; text-decoration: none;'>Dokümantasyon</a> | 
        <a href='LICENSE' target='_blank' style='color: #FF4B4B; text-decoration: none;'>MIT Lisans</a>
        </p>
        <p style='margin: 0.5rem 0 0 0; font-size: 0.8rem; color: #666;'>
        Streamlit {st.__version__} ile geliştirildi
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

