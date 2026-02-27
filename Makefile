# M3U Editör Pro - Makefile
# Geliştirme ve deployment komutları

.PHONY: help install dev test lint format clean docker-build docker-run docker-compose

# Renkler
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[0;33m
BLUE=\033[0;34m
NC=\033[0m # No Color

# Varsayılan hedef
help:
	@echo "$(BLUE)M3U Editör Pro - Komutlar$(NC)"
	@echo ""
	@echo "$(GREEN)Geliştirme:$(NC)"
	@echo "  make install      - Bağımlılıkları yükle"
	@echo "  make dev          - Geliştirme sunucusunu başlat"
	@echo "  make test         - Testleri çalıştır"
	@echo "  make lint         - Kod kalitesi kontrolü"
	@echo "  make format       - Kodu formatla"
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@echo "  make docker-build - Docker image oluştur"
	@echo "  make docker-run   - Docker container çalıştır"
	@echo "  make docker-compose - Docker Compose ile çalıştır"
	@echo ""
	@echo "$(GREEN)Temizlik:$(NC)"
	@echo "  make clean        - Cache ve geçici dosyaları temizle"
	@echo "  make clean-all    - Tüm geçici dosyaları temizle"

# Bağımlılıkları yükle
install:
	@echo "$(BLUE)Bağımlılıklar yükleniyor...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Bağımlılıklar yüklendi$(NC)"

# Geliştirme sunucusunu başlat
dev:
	@echo "$(BLUE)Geliştirme sunucusu başlatılıyor...$(NC)"
	streamlit run src/app.py

# Testleri çalıştır
test:
	@echo "$(BLUE)Testler çalıştırılıyor...$(NC)"
	python -m pytest tests/ -v --cov=src --cov=utils --cov-report=term-missing

# Kod kalitesi kontrolü
lint:
	@echo "$(BLUE)Kod kalitesi kontrol ediliyor...$(NC)"
	flake8 src/ utils/ --max-line-length=88 --extend-ignore=E203,W503
	mypy src/ utils/ --ignore-missing-imports

# Kodu formatla
format:
	@echo "$(BLUE)Kod formatlanıyor...$(NC)"
	black src/ utils/ tests/
	isort src/ utils/ tests/

# Docker image oluştur
docker-build:
	@echo "$(BLUE)Docker image oluşturuluyor...$(NC)"
	docker build -t m3u-editor-pro:latest .

# Docker container çalıştır
docker-run:
	@echo "$(BLUE)Docker container çalıştırılıyor...$(NC)"
	docker run -p 8501:8501 --name m3u-editor m3u-editor-pro:latest

# Docker Compose ile çalıştır
docker-compose:
	@echo "$(BLUE)Docker Compose ile başlatılıyor...$(NC)"
	docker-compose up -d

# Cache ve geçici dosyaları temizle
clean:
	@echo "$(BLUE)Cache temizleniyor...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage coverage.xml htmlcov
	@echo "$(GREEN)✓ Cache temizlendi$(NC)"

# Tüm geçici dosyaları temizle
clean-all: clean
	@echo "$(BLUE)Tüm geçici dosyalar temizleniyor...$(NC)"
	rm -rf build/ dist/ *.egg-info
	rm -rf .venv venv env
	@echo "$(GREEN)✓ Tüm geçici dosyalar temizlendi$(NC)"

# Sanal ortam oluştur (Windows)
venv-win:
	@echo "$(BLUE)Sanal ortam oluşturuluyor (Windows)...$(NC)"
	python -m venv venv
	@echo "$(GREEN)✓ Sanal ortam oluşturuldu$(NC)"
	@echo "$(YELLOW)Sanal ortamı aktif etmek için: venv\\Scripts\\activate$(NC)"

# Sanal ortam oluştur (Linux/Mac)
venv-unix:
	@echo "$(BLUE)Sanal ortam oluşturuluyor (Linux/Mac)...$(NC)"
	python3 -m venv venv
	@echo "$(GREEN)✓ Sanal ortam oluşturuldu$(NC)"
	@echo "$(YELLOW)Sanal ortamı aktif etmek için: source venv/bin/activate$(NC)"

# Requirements güncelle
update-requirements:
	@echo "$(BLUE)Requirements güncelleniyor...$(NC)"
	pip freeze > requirements.txt
	@echo "$(GREEN)✓ Requirements güncellendi$(NC)"

# Uygulama durumunu kontrol et
status:
	@echo "$(BLUE)Uygulama durumu kontrol ediliyor...$(NC)"
	@echo "$(GREEN)Python sürümü:$(NC) $$(python --version 2>/dev/null || echo 'Python bulunamadı')"
	@echo "$(GREEN)Pip sürümü:$(NC) $$(pip --version 2>/dev/null | head -1 || echo 'Pip bulunamadı')"
	@echo "$(GREEN)Streamlit sürümü:$(NC) $$(streamlit --version 2>/dev/null || echo 'Streamlit bulunamadı')"
	@echo "$(GREEN)Docker sürümü:$(NC) $$(docker --version 2>/dev/null || echo 'Docker bulunamadı')"
	@echo "$(GREEN)Docker Compose sürümü:$(NC) $$(docker-compose --version 2>/dev/null || echo 'Docker Compose bulunamadı')"

# Git hook'larını kur
install-hooks:
	@echo "$(BLUE)Git hook'ları kuruluyor...$(NC)"
	cp -n .githooks/* .git/hooks/ 2>/dev/null || true
	chmod +x .git/hooks/*
	@echo "$(GREEN)✓ Git hook'ları kuruldu$(NC)"

# Uygulamayı başlat (production)
start:
	@echo "$(BLUE)Uygulama başlatılıyor...$(NC)"
	streamlit run src/app.py --server.port=8501 --server.address=0.0.0.0

# Uygulamayı durdur
stop:
	@echo "$(BLUE)Uygulama durduruluyor...$(NC)"
	@pkill -f "streamlit run src/app.py" 2>/dev/null || true
	@echo "$(GREEN)✓ Uygulama durduruldu$(NC)"

# Logları göster
logs:
	@echo "$(BLUE)Loglar gösteriliyor...$(NC)"
	tail -f logs/app.log 2>/dev/null || echo "$(YELLOW)Log dosyası bulunamadı$(NC)"

# Backup al
backup:
	@echo "$(BLUE)Backup alınıyor...$(NC)"
	tar -czf backup_$$(date +%Y%m%d_%H%M%S).tar.gz --exclude=venv --exclude=__pycache__ --exclude=.git .
	@echo "$(GREEN)✓ Backup alındı: backup_$$(date +%Y%m%d_%H%M%S).tar.gz$(NC)"