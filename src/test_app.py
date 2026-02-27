import streamlit as st

# Sayfa Ayarları
st.set_page_config(page_title="Test App", layout="wide", page_icon="📺")

st.title("Test Uygulaması")
st.write("Bu bir test uygulamasıdır.")

if st.button("Test Butonu"):
    st.success("Buton çalışıyor!")

st.sidebar.title("Sidebar")
st.sidebar.write("Sidebar içeriği")