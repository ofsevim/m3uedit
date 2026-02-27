# M3U Editör Pro - Dockerfile
# Python 3.11 slim image kullanıyoruz

FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem bağımlılıklarını yükle
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama dosyalarını kopyala
COPY . .

# Port'u expose et
EXPOSE 8501

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Uygulamayı çalıştır
CMD ["streamlit", "run", "src/app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.enableCORS=false", \
    "--server.enableXsrfProtection=false", \
    "--browser.serverAddress=0.0.0.0", \
    "--browser.gatherUsageStats=false"]

# Labels
LABEL maintainer="M3U Editör Pro Team <support@example.com>"
LABEL version="1.0.0"
LABEL description="Professional IPTV M3U Playlist Editor"
LABEL org.opencontainers.image.source="https://github.com/yourusername/m3uedit"