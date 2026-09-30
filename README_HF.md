---
title: M3U Editor Pro
emoji: 📺
colorFrom: blue
colorTo: purple
sdk: streamlit
streamlit_file: app.py
pinned: false
---

# M3U Editör Pro

[Özellikler ve kurulum](README.tr.md) · [Uzak sunucu dağıtımı](docs/DEPLOYMENT.md)

Ana giriş `app.py` dosyasıdır. Liste düzenleme, dosya indirme ve sağlık kontrolü desteklenir.
Managed platform ikinci proxy portunu dışarı açmıyorsa browser proxy oynatımı için ulaşılabilir
HTTPS gateway yapılandırması gerekir. Tarayıcıdaki localhost uzak sunucuyu göstermez.
TLS/CORS/XSRF korumalarını kapatmayın. Harici paylaşım yalnızca seçilen HTTPS servisine açık onayla yapılır.
