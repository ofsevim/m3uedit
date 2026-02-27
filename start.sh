#!/bin/bash

# M3U Editör Pro - Başlangıç Script'i
# Linux/Mac için

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logo
echo -e "${BLUE}"
echo "  __  __ ____  _   _   _____           _           _ "
echo " |  \/  |  _ \| | | | | ____|_ __   __| | ___ _ __| |"
echo " | |\/| | |_) | | | | |  _| | '_ \ / _\` |/ _ \ '__| |"
echo " | |  | |  __/| |_| | | |___| | | | (_| |  __/ |  | |"
echo " |_|  |_|_|    \___/  |_____|_| |_|\__,_|\___|_|  |_|"
echo -e "${NC}"
echo "======================================================"
echo ""

# Fonksiyonlar
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Python kontrolü
check_python() {
    print_info "Python kontrol ediliyor..."
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "Python bulunamadı!"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    print_success "Python $PYTHON_VERSION bulundu"
}

# Sanal ortam kontrolü
check_venv() {
    print_info "Sanal ortam kontrol ediliyor..."
    if [ -d "venv" ] || [ -d ".venv" ]; then
        print_success "Sanal ortam bulundu"
        return 0
    else
        print_warning "Sanal ortam bulunamadı"
        return 1
    fi
}

# Sanal ortam oluştur
create_venv() {
    print_info "Sanal ortam oluşturuluyor..."
    $PYTHON_CMD -m venv venv
    print_success "Sanal ortam oluşturuldu"
}

# Sanal ortamı aktif et
activate_venv() {
    print_info "Sanal ortam aktif ediliyor..."
    if [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        print_error "Sanal ortam aktivasyon dosyası bulunamadı!"
        exit 1
    fi
    print_success "Sanal ortam aktif edildi"
}

# Bağımlılıkları yükle
install_dependencies() {
    print_info "Bağımlılıklar yükleniyor..."
    pip install --upgrade pip
    pip install -r requirements.txt
    print_success "Bağımlılıklar yüklendi"
}

# Uygulamayı başlat
start_app() {
    print_info "Uygulama başlatılıyor..."
    echo ""
    echo -e "${GREEN}======================================================${NC}"
    echo -e "${GREEN}   M3U Editör Pro başarıyla başlatıldı!${NC}"
    echo -e "${GREEN}======================================================${NC}"
    echo ""
    echo -e "${YELLOW}Uygulama şu adreste çalışıyor:${NC}"
    echo -e "  ${BLUE}http://localhost:8501${NC}"
    echo ""
    echo -e "${YELLOW}Durdurmak için:${NC} Ctrl+C"
    echo ""
    
    streamlit run src/app.py --server.port=8501 --server.address=0.0.0.0
}

# Ana işlem
main() {
    echo -e "${BLUE}M3U Editör Pro - Kurulum ve Başlatma${NC}"
    echo ""
    
    # Python kontrolü
    check_python
    
    # Sanal ortam kontrolü
    if ! check_venv; then
        read -p "Sanal ortam oluşturmak istiyor musunuz? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_venv
        else
            print_warning "Sanal ortam olmadan devam ediliyor..."
        fi
    fi
    
    # Sanal ortamı aktif et (varsa)
    if [ -d "venv" ] || [ -d ".venv" ]; then
        activate_venv
    fi
    
    # Bağımlılıkları yükle
    install_dependencies
    
    # Uygulamayı başlat
    start_app
}

# Hata yakalama
trap 'print_error "Script durduruldu"; exit 1' INT TERM

# Ana işlemi çalıştır
main "$@"