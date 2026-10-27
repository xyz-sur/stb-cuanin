#!/usr/bin/env bash
set -e

# ==============================================================================
#                      STB-CUANIN 1-KLIK INSTALLER
#           Otomasi Node Pasif Berpenghasilan Khusus STB / Armbian
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "======================================================================"
echo "          🚀 STB-CUANIN - 1 STB 1 IP AUTOMATED NODE STACK             "
echo "        Optimal untuk STB HG680P / B860H / Armbian / SBC 2GB          "
echo "======================================================================"
echo -e "${NC}"

# 1. Validasi Root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[!] Harap jalankan script ini sebagai root (sudo su).${NC}"
  exit 1
fi

INSTALL_DIR="/opt/stb-cuanin"
REPO_URL="https://github.com/xyz-sur/stb-cuanin.git"

# Parse CLI flags
DEV_KEY="${CUANIN_VAULT_KEY:-}"
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dev-key|--fleet-key) DEV_KEY="$2"; shift ;;
    esac
    shift
done

# 2. Update package index & install prerequisite
echo -e "${BLUE}[1/5] Memeriksa & Menginstal Paket Esensial...${NC}"
apt-get update -y
apt-get install -y curl git python3 python3-pip ca-certificates

# 3. Validasi / Instalasi Docker & Compose
echo -e "${BLUE}[2/5] Memeriksa Instalasi Docker Engine...${NC}"
if ! command -v docker &> /dev/null; then
  echo -e "${YELLOW}[*] Docker belum terpasang. Memasang Docker Engine resmi...${NC}"
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
else
  echo -e "${GREEN}[✓] Docker Engine sudah terpasang.${NC}"
fi

# Pastikan docker compose plugin tersedia
if ! docker compose version &> /dev/null; then
  echo -e "${YELLOW}[*] Memasang plugin Docker Compose...${NC}"
  apt-get install -y docker-compose-plugin || true
fi

# 4. Clone atau Update Repo ke /opt/stb-cuanin
echo -e "${BLUE}[3/5] Mengunduh Repository STB-CUANIN...${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
  echo -e "${YELLOW}[*] Direktori lama ditemukan. Memperbarui ke versi terbaru...${NC}"
  cd "$INSTALL_DIR"
  [ -f "config.txt" ] && cp config.txt config.txt.bak
  git fetch origin main
  git reset --hard origin/main
  [ -f "config.txt.bak" ] && cp config.txt.bak config.txt && rm -f config.txt.bak
else
  echo -e "${YELLOW}[*] Melakukan clone repository ke $INSTALL_DIR...${NC}"
  rm -rf "$INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

# Set permission
chmod +x stb-cuanin.py install.sh update.sh tools/*.py 2>/dev/null || true
mkdir -p "$INSTALL_DIR/.data/earnapp"

if [ -n "$DEV_KEY" ]; then
  echo -e "${YELLOW}[*] Menyimpan Fleet Key ke $INSTALL_DIR/.env (chmod 600)...${NC}"
  echo "CUANIN_VAULT_KEY=${DEV_KEY}" > "$INSTALL_DIR/.env"
  chmod 600 "$INSTALL_DIR/.env"
fi

# 5. Pasang Systemd Service
echo -e "${BLUE}[4/5] Memasang Systemd Service (Auto-Start Boot)...${NC}"
cp "$INSTALL_DIR/systemd/stb-cuanin.service" /etc/systemd/system/stb-cuanin.service
systemctl daemon-reload
systemctl enable stb-cuanin.service
systemctl restart stb-cuanin.service

# 6. Dapatkan IP Host
HOST_IP=$(hostname -I | awk '{print $1}')
[ -z "$HOST_IP" ] && HOST_IP="127.0.0.1"
HOSTNAME=$(hostname)

echo -e "\n${GREEN}======================================================================${NC}"
echo -e "${GREEN}   🎉 INSTALASI SELESAI & SISTEM STB-CUANIN TELAH BERJALAN AKTIF!     ${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo -e "Hostname STB        : ${YELLOW}${HOSTNAME}${NC}"
echo -e "Web Dashboard Monitor: ${CYAN}http://${HOST_IP}:12345${NC}"
echo -e "File Konfigurasi     : ${YELLOW}${INSTALL_DIR}/config.txt${NC}"
echo -e "Perintah Cek Log    : ${YELLOW}journalctl -u stb-cuanin -f${NC}"
echo -e "Perintah Update     : ${YELLOW}${INSTALL_DIR}/update.sh${NC}"
echo -e "----------------------------------------------------------------------"
echo -e "${YELLOW}CATATAN PENTING:${NC}"
echo -e "1. Buka browser ke URL: ${CYAN}http://${HOST_IP}:12345${NC}"
echo -e "2. Masukkan akun Anda pada tab 'Konfigurasi Akun' di Web Dashboard."
echo -e "3. Cadangan RAM 30%+ dipertahankan otomatis agar STB tetap stabil & adem."
echo -e "======================================================================\n"
