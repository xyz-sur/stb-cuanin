#!/usr/bin/env bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "=== [STB-CUANIN] Memulai Pembaruan Sistem ==="

# Backup konfigurasi pengguna jika ada
if [ -f "config.txt" ]; then
    cp config.txt config.txt.bak
fi

# Tarik perubahan terbaru dari GitHub
if [ -d ".git" ]; then
    echo "[*] Menjalankan git pull..."
    git fetch origin main
    git reset --hard origin/main
    # Restore config pengguna
    if [ -f "config.txt.bak" ]; then
        cp config.txt.bak config.txt
        rm -f config.txt.bak
    fi
fi

chmod +x stb-cuanin.py install.sh update.sh tools/*.py 2>/dev/null || true

# Restart systemd service jika aktif
if systemctl is-active --quiet stb-cuanin.service 2>/dev/null; then
    echo "[*] Merestart service stb-cuanin..."
    systemctl restart stb-cuanin.service
fi

echo "=== [✓] Pembaruan STB-CUANIN Selesai Dilakukan! ==="
