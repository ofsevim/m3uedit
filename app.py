import streamlit as st
import pandas as pd
import requests
import re
import io

# Sayfa Ayarları
st.set_page_config(page_title="M3U Editör Pro (Web)", layout="wide", page_icon="📺")

# --- FONKSİYONLAR ---

def parse_m3u_content(content):
    """M3U içeriğini parse eder ve liste döndürür."""
    lines = content.split('\n')
    channels = []
    current_info = None
    
    # Regex deseni (Tkinter kodundaki ile aynı)
    strict_pattern = re.compile(r'(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)', re.IGNORECASE)

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("#EXTINF"):
            info = {"Grup": "Genel", "Kanal Adı": "Bilinmeyen", "URL": ""}
            
            # Grup yakalama
            grp = re.search(r'group-title="([^"]*)"', line)
            if grp:
                info["Grup"] = grp.group(1)
            
            # İsim yakalama
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
    """Kanalları filtreler."""
    if not only_tr:
        return channels
        
    filtered = []
    strict_pattern = re.compile(r'(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)', re.IGNORECASE)
    
    for ch in channels:
        # Sadece GRUP adına bakıyoruz (Orijinal kodundaki mantık)
        if strict_pattern.search(ch["Grup"]):
            filtered.append(ch)
            
    return filtered

def convert_df_to_m3u(df):
    """Dataframe'i indirilebilir M3U formatına çevirir."""
    content = "#EXTM3U\n"
    for index, row in df.iterrows():
        content += f'#EXTINF:-1 group-title="{row["Grup"]}",{row["Kanal Adı"]}\n{row["URL"]}\n'
    return content

# --- ARAYÜZ (UI) ---

# Session State (Verileri hafızada tutmak için)
if 'data' not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Grup", "Kanal Adı", "URL"])

# Sol Menü (Sidebar)
with st.sidebar:
    st.title("IPTV MANAGER")
    st.markdown("---")
    
    mode = st.radio("Yükleme Yöntemi", ["🌐 Linkten Yükle", "📂 Dosya Yükle"])
    
    if mode == "🌐 Linkten Yükle":
        url = st.text_input("M3U Linki Yapıştır:")
        only_tr = st.checkbox("🇹🇷 SADECE GRUPTA ARA (TR Filtresi)", value=True)
        
        if st.button("Listeyi Çek ve Tara", use_container_width=True):
            if url:
                try:
                    with st.spinner('Link indiriliyor ve taranıyor...'):
                        response = requests.get(url, timeout=30)
                        response.raise_for_status()
                        raw_channels = parse_m3u_content(response.text)
                        
                        # Filtreleme
                        final_channels = filter_channels(raw_channels, only_tr)
                        
                        st.session_state.data = pd.DataFrame(final_channels)
                        st.success(f"İşlem Tamam! Toplam {len(final_channels)} kanal bulundu.")
                except Exception as e:
                    st.error(f"Hata oluştu: {e}")
            else:
                st.warning("Lütfen bir link girin.")

    elif mode == "📂 Dosya Yükle":
        uploaded_file = st.file_uploader("M3U Dosyası Seç", type=['m3u', 'm3u8'])
        if uploaded_file is not None:
            stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
            raw_channels = parse_m3u_content(stringio.read())
            st.session_state.data = pd.DataFrame(raw_channels)
            st.success(f"Dosya yüklendi. {len(raw_channels)} kanal.")

    st.markdown("---")
    st.info("Düzenleme yaptıktan sonra aşağıdan indirebilirsiniz.")
    
    # İndirme Butonu
    if not st.session_state.data.empty:
        m3u_output = convert_df_to_m3u(st.session_state.data)
        st.download_button(
            label="💾 Yeni M3U Olarak İndir",
            data=m3u_output,
            file_name="duzenlenmis_liste.m3u",
            mime="text/plain",
            type="primary",
            use_container_width=True
        )

# Ana Ekran
st.subheader("Kanal Listesi Düzenleyici")

if not st.session_state.data.empty:
    # İstatistikler
    col1, col2 = st.columns(2)
    col1.metric("Toplam Kanal", len(st.session_state.data))
    unique_groups = st.session_state.data["Grup"].nunique()
    col2.metric("Grup Sayısı", unique_groups)

    # Arama Kutusu
    search_term = st.text_input("🔍 Tablo içinde ara (Grup veya Kanal Adı):", "")

    # Filtreleme (Görsel filtreleme, veriyi silmez)
    df_display = st.session_state.data
    if search_term:
        df_display = df_display[
            df_display["Grup"].str.contains(search_term, case=False) | 
            df_display["Kanal Adı"].str.contains(search_term, case=False)
        ]

    # EDİTÖR TABLOSU (En önemli kısım)
    # num_rows="dynamic" ile satır ekleyip silebilirsin
    edited_df = st.data_editor(
        df_display,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "URL": st.column_config.LinkColumn("Yayın Linki")
        },
        height=600
    )

    # Değişiklikleri kaydetmek için (DataEditor anlık session'ı güncellemez, manuel update gerekir)
    # Streamlit'te data_editor zaten bir çıktı verir, biz bunu session state'e geri yazarız ki indirme butonu güncel veriyi görsün.
    if not edited_df.equals(st.session_state.data):
         # Eğer arama yapılıyorsa sadece filtrelenmiş kısmı güncellemek karmaşık olabilir.
         # Basitlik adına: Arama yokken yapılan değişiklikler ana veriyi günceller.
         if not search_term:
            st.session_state.data = edited_df

else:
    st.info("👈 Başlamak için sol menüden bir link yapıştırın veya dosya yükleyin.")