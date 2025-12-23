import streamlit as st
import pandas as pd
import urllib.request
import urllib.error
import re
import io
from visitor_counter import VisitorCounter
import hashlib
import time
from streamlit_cookies_manager import EncryptedCookieManager

# Sayfa Ayarları
st.set_page_config(page_title="M3U Editör Pro (Web)", layout="wide", page_icon="📺")

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
            info = {"Grup": "Genel", "Kanal Adı": "Bilinmeyen", "URL": ""}
            
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

# --- ARAYÜZ (UI) ---

# Cookie Manager'ı başlat (benzersiz ziyaretçi takibi için)
if 'cookies' not in st.session_state:
    st.session_state.cookies = EncryptedCookieManager(
        prefix="m3uedit_",
        password="m3u_secret_key_2025"  # Güvenli bir şifre kullanın
    )

# Cookie'leri yükle
if not st.session_state.cookies.ready():
    st.stop()

# Ziyaretçi sayacı başlat
if 'visitor_counter' not in st.session_state:
    st.session_state.visitor_counter = VisitorCounter()

# Cookie'den session ID al veya yeni oluştur
cookies = st.session_state.cookies
if 'visitor_id' not in cookies:
    # Yeni ziyaretçi - benzersiz ID oluştur
    unique_str = f"{time.time()}_{hashlib.md5(str(time.time()).encode()).hexdigest()}"
    visitor_id = hashlib.md5(unique_str.encode()).hexdigest()
    cookies['visitor_id'] = visitor_id
    cookies.save()
    
    # İlk ziyaret, sayacı artır (hem toplam hem benzersiz)
    st.session_state.visitor_counter.increment_visit(visitor_id)
    st.session_state.is_new_visitor = True
else:
    # Mevcut ziyaretçi - sadece visitor_id'yi al, sayaçları artırma
    visitor_id = cookies['visitor_id']
    st.session_state.is_new_visitor = False

if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Seç", "Grup", "Kanal Adı", "URL"])

with st.sidebar:
    st.title("IPTV MANAGER")
    st.markdown("---")
    
    mode = st.radio("Yükleme Yöntemi", ["🌐 Linkten Yükle", "📂 Dosya Yükle"])
    
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
                            # Response bir iteratör gibi davranır
                            raw_channels = parse_m3u_lines(response)
                            final_channels = filter_channels(raw_channels, only_tr)
                            new_data = pd.DataFrame(final_channels)
                            
                        if not final_channels:
                            st.warning("⚠️ Linkten veri çekildi ama kanal bulunamadı veya format hatalı.")
                        else:
                            st.success(f"✅ İşlem Tamam! Toplam {len(final_channels)} kanal bulundu.")
                            
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
        if "Seç" not in new_data.columns:
            new_data.insert(0, "Seç", False)
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
    
    if search_term:
        df_display = df_display[
            df_display["Grup"].str.contains(search_term, case=False) | 
            df_display["Kanal Adı"].str.contains(search_term, case=False)
        ]

    st.caption("İstediğiniz kanalların başındaki kutucuğu işaretleyin.")

    edited_df = st.data_editor(
        df_display,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Seç": st.column_config.CheckboxColumn("Seç", default=False, width="small"),
            "URL": st.column_config.LinkColumn("Yayın Linki", width="medium"),
            "Grup": st.column_config.TextColumn("Grup", width="medium"),
            "Kanal Adı": st.column_config.TextColumn("Kanal Adı", width="large")
        },
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
st.markdown(
    """
    <div style='text-align: center; color: #888; padding: 20px; margin-top: 20px;'>
        <p>Made with ❤️ | M3U Editör Pro © 2025</p>
    </div>
    """,
    unsafe_allow_html=True
)