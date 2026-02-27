# Deployment Rehberi

## Yerel Kurulum

### Gereksinimler
- Python 3.11+
- pip

### Adımlar
```bash
# Repository'yi klonlayın
git clone https://github.com/yourusername/m3uedit.git
cd m3uedit

# Virtual environment oluşturun
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Bağımlılıkları yükleyin
pip install -r requirements.txt

# Uygulamayı başlatın
streamlit run src/app.py
```

## Streamlit Cloud

1. GitHub'a push edin
2. [share.streamlit.io](https://share.streamlit.io) adresine gidin
3. Repository'yi bağlayın
4. `src/app.py` dosyasını seçin
5. Deploy edin

## Heroku

### Procfile
```
web: streamlit run src/app.py --server.port=$PORT --server.address=0.0.0.0
```

### setup.sh
```bash
mkdir -p ~/.streamlit/
echo "\
[server]\n\
headless = true\n\
port = $PORT\n\
enableCORS = false\n\
\n\
" > ~/.streamlit/config.toml
```

### Deployment
```bash
heroku create your-app-name
git push heroku main
```

## AWS EC2

### 1. EC2 Instance Oluşturun
- Ubuntu 22.04 LTS
- t2.micro (ücretsiz tier)
- Security Group: Port 8501 açık

### 2. Bağlanın ve Kurun
```bash
ssh -i your-key.pem ubuntu@your-ec2-ip

# Güncellemeleri yapın
sudo apt update && sudo apt upgrade -y

# Python ve pip kurun
sudo apt install python3-pip -y

# Repository'yi klonlayın
git clone https://github.com/yourusername/m3uedit.git
cd m3uedit

# Bağımlılıkları yükleyin
pip3 install -r requirements.txt

# Uygulamayı başlatın
streamlit run src/app.py --server.port=8501 --server.address=0.0.0.0
```

### 3. Systemd Service (Opsiyonel)
```bash
sudo nano /etc/systemd/system/m3uedit.service
```

```ini
[Unit]
Description=M3U Editor Pro
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/m3uedit
ExecStart=/usr/local/bin/streamlit run src/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable m3uedit
sudo systemctl start m3uedit
```

## Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Güvenlik Önerileri

1. SSL/TLS kullanın (Let's Encrypt)
2. Firewall kuralları ayarlayın
3. Rate limiting ekleyin
4. Güvenli şifreler kullanın
5. Düzenli güncellemeler yapın

## Performans Optimizasyonu

1. Caching etkinleştirin
2. CDN kullanın (statik dosyalar için)
3. Database connection pooling
4. Load balancing (yüksek trafik için)

## Monitoring

- Uptime monitoring: UptimeRobot
- Error tracking: Sentry
- Analytics: Google Analytics
- Logs: CloudWatch, Papertrail

## Backup

```bash
# Visitor data backup
cp visitor_data.json visitor_data_backup_$(date +%Y%m%d).json

# Otomatik backup (crontab)
0 0 * * * cp /path/to/visitor_data.json /path/to/backups/visitor_data_$(date +\%Y\%m\%d).json
```
