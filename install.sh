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
apt-get install -y curl git python3 python3-pip ca-certificates cron

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
echo -e "${BLUE}[3/5] Mengunduh / Memperbarui Repository STB-CUANIN...${NC}"
if [ -d "$INSTALL_DIR/.git" ]; then
  echo -e "${YELLOW}[*] Direktori lama ditemukan. Memperbarui ke versi terbaru...${NC}"
  cd "$INSTALL_DIR"

  # Backup parameter aktif user sebelum update
  python3 - << 'EOF' 2>/dev/null || true
import os, json
app_dir = "/opt/stb-cuanin"
cfg_file = os.path.join(app_dir, "config.txt")
data_dir = os.path.join(app_dir, ".data")
os.makedirs(data_dir, exist_ok=True)
bak_file = os.path.join(data_dir, "user_config_backup.json")
user_cfg = {}
if os.path.exists(cfg_file):
    with open(cfg_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if v:
                    user_cfg[k] = v
with open(bak_file, "w", encoding="utf-8") as f:
    json.dump(user_cfg, f, indent=2)
EOF

  git fetch origin main
  git checkout -- .
  git reset --hard origin/main

  # Pulihkan parameter user
  python3 - << 'EOF' 2>/dev/null || true
import os, json
app_dir = "/opt/stb-cuanin"
cfg_file = os.path.join(app_dir, "config.txt")
bak_file = os.path.join(app_dir, ".data", "user_config_backup.json")
if os.path.exists(bak_file) and os.path.exists(cfg_file):
    try:
        with open(bak_file, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
    except Exception:
        user_cfg = {}
    if user_cfg:
        with open(cfg_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        written = set()
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k = s.split("=", 1)[0].strip()
                if k in user_cfg and user_cfg[k]:
                    new_lines.append(f"{k}={user_cfg[k]}\n")
                    written.add(k)
                    continue
            new_lines.append(line)
        for k, v in user_cfg.items():
            if k not in written and v:
                new_lines.append(f"{k}={v}\n")
        with open(cfg_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
EOF

else
  echo -e "${YELLOW}[*] Melakukan clone repository ke $INSTALL_DIR...${NC}"
  rm -rf "$INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
  cd "$INSTALL_DIR"
fi

# Set permission ketat (Zero-Trust Security)
chmod +x stb-cuanin.py install.sh update.sh 2>/dev/null || true
mkdir -p "$INSTALL_DIR/.data/earnapp"
chmod 700 "$INSTALL_DIR/.data"
[ -f "$INSTALL_DIR/docker-compose.generated.yml" ] && chmod 600 "$INSTALL_DIR/docker-compose.generated.yml"

if [ -n "$DEV_KEY" ]; then
  echo -e "${YELLOW}[*] Menyimpan Fleet Key ke $INSTALL_DIR/.env (chmod 600)...${NC}"
  echo "CUANIN_VAULT_KEY=${DEV_KEY}" > "$INSTALL_DIR/.env"
  chmod 600 "$INSTALL_DIR/.env"
fi

# 5. Pasang Systemd Service & Cron Maintenance Harian 00:00
echo -e "${BLUE}[4/5] Memasang Systemd Service & Cron Maintenance 00:00...${NC}"
cp "$INSTALL_DIR/systemd/stb-cuanin.service" /etc/systemd/system/stb-cuanin.service
systemctl daemon-reload
systemctl enable stb-cuanin.service

# Setup cron maintenance harian pukul 00:00 (Cek update, pertahankan config, restart stack)
CRON_FILE="/etc/cron.d/stb-cuanin"
cat << 'CRON_EOF' > "$CRON_FILE"
# STB-CUANIN: Maintenance harian pukul 00:00 (Cek update GitHub, pertahankan setting user, restart)
0 0 * * * root /opt/stb-cuanin/update.sh >> /var/log/stb-cuanin-update.log 2>&1
CRON_EOF
chmod 644 "$CRON_FILE"
systemctl enable cron 2>/dev/null || systemctl enable crond 2>/dev/null || true
systemctl restart cron 2>/dev/null || systemctl restart crond 2>/dev/null || true

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
echo -e "Password Bawaan     : ${CYAN}12345${NC} (Dapat diubah via web)"
echo -e "File Konfigurasi     : ${YELLOW}${INSTALL_DIR}/config.txt${NC}"
echo -e "Maintenance Otomatis : ${GREEN}Setiap Pukul 00:00 (Auto-Update & Restart Bersih)${NC}"
echo -e "Perintah Cek Log    : ${YELLOW}journalctl -u stb-cuanin -f${NC}"
echo -e "Perintah Update     : ${YELLOW}${INSTALL_DIR}/update.sh${NC}"
echo -e "----------------------------------------------------------------------"
echo -e "${YELLOW}CATATAN PENTING:${NC}"
echo -e "1. Buka browser: ${CYAN}http://${HOST_IP}:12345${NC} (Login: 12345)"
echo -e "2. Jika belum diisi user, sistem otomatis menggunakan konfigurasi server API."
echo -e "3. Konfigurasi Anda aman dan tidak akan tertimpa saat update harian pukul 00:00."
echo -e "4. Cadangan RAM 30%+ dipertahankan otomatis agar STB tetap stabil & adem."
echo -e "======================================================================\n"
