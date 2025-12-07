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
    
    # Regex deseni
    strict_pattern = re.compile(r'(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)', re.IGNORECASE)

    for line in lines:
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
    """Kanalları filtreler."""
    if not only_tr:
        return channels
        
    filtered = []
    strict_pattern = re.compile(r'(\b|_|\[|\(|\|)(TR|TURK|TÜRK|TURKIYE|TÜRKİYE|YERLI|ULUSAL|ISTANBUL)(\b|_|\]|\)|\||:)', re.IGNORECASE)
    
    for ch in channels:
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
    # "Seç" sütunu eklendi (Boolean/Checkbox için)
    st.session_state.data = pd.DataFrame(columns=["Seç", "Grup", "Kanal Adı", "URL"])

# Sol Menü (Sidebar)
with st.sidebar:
    st.title("IPTV MANAGER")
    st.markdown("---")
    
    mode = st.radio("Yükleme Yöntemi", ["🌐 Linkten Yükle", "📂 Dosya Yükle"])
    
    # Veri Yükleme İşlemleri
    new_data = None
    
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
                        final_channels = filter_channels(raw_channels, only_tr)
                        new_data = pd.DataFrame(final_channels)
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
            new_data = pd.DataFrame(raw_channels)
            st.success(f"Dosya yüklendi. {len(raw_channels)} kanal.")

    # Eğer yeni veri geldiyse, başına "Seç" sütunu ekleyip state'e atıyoruz
    if new_data is not None:
        if "Seç" not in new_data.columns:
            new_data.insert(0, "Seç", False) # Varsayılan olarak seçili gelmez
        st.session_state.data = new_data

    st.markdown("---")
    
    # --- AKILLI İNDİRME BUTONU ---
    if not st.session_state.data.empty:
        # Kaç tane seçili olduğunu kontrol et
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
    # İstatistikler
    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Kanal", len(st.session_state.data))
    
    selected_count = len(st.session_state.data[st.session_state.data["Seç"] == True])
    col2.metric("Seçilen Kanal", selected_count)
    
    unique_groups = st.session_state.data["Grup"].nunique()
    col3.metric("Grup Sayısı", unique_groups)

    # Arama Kutusu
    search_term = st.text_input("🔍 Tablo içinde ara (Grup veya Kanal Adı):", "")

    # Görüntülenecek veriyi hazırla
    df_display = st.session_state.data
    
    if search_term:
        # Arama yaparken de Seç sütununu korumalıyız
        df_display = df_display[
            df_display["Grup"].str.contains(search_term, case=False) | 
            df_display["Kanal Adı"].str.contains(search_term, case=False)
        ]

    st.caption("İstediğiniz kanalların başındaki kutucuğu işaretleyin. Düzenleme yapmak için hücreye tıklayın.")

    # EDİTÖR TABLOSU
    edited_df = st.data_editor(
        df_display,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True, # Satır numaralarını gizle (daha temiz görünüm)
        column_config={
            "Seç": st.column_config.CheckboxColumn(
                "Seç",
                help="İndirmek için seçin",
                default=False,
                width="small"
            ),
            "URL": st.column_config.LinkColumn(
                "Yayın Linki",
                width="medium"
            ),
            "Grup": st.column_config.TextColumn(
                "Grup",
                width="medium"
            ),
            "Kanal Adı": st.column_config.TextColumn(
                "Kanal Adı",
                width="large"
            )
        },
        height=600,
        key="editor"
    )

    # Data editor'den gelen değişiklikleri (Checkbox tıklamaları dahil) ana veriye kaydetme
    # Bu kısım biraz trick gerektirir çünkü arama yapıldığında indexler karışabilir.
    # Pandas index'ini kullanarak update ediyoruz.
    
    if not edited_df.equals(df_display):
        # Sadece değişen kısımları ana veriye (st.session_state.data) aktar
        st.session_state.data.update(edited_df)
        # Sayfayı yenileyerek butonun güncellenmesini sağla (Checkbox'a basınca buton yazısı değişsin diye)
        st.rerun()

else:
    st.info("👈 Başlamak için sol menüden bir link yapıştırın veya dosya yükleyin.")