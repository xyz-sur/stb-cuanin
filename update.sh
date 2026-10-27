#!/usr/bin/env bash
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "=== [STB-CUANIN] Memulai Pembaruan & Maintenance Harian ==="

# 1. Simpan konfigurasi pengguna yang sudah disetting (jangan sampai tertimpa)
python3 - << 'EOF'
import os, json

app_dir = os.path.abspath(os.getcwd())
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

print(f"[*] Berhasil membackup {len(user_cfg)} pengaturan aktif user.")
EOF

# 2. Periksa update dari GitHub
HAS_UPDATE=0
if [ -d ".git" ]; then
    echo "[*] Memeriksa repository GitHub..."
    git fetch origin main 2>/dev/null || true
    BEHIND_COUNT=$(git rev-list HEAD..origin/main --count 2>/dev/null || echo "0")
    if [ "$BEHIND_COUNT" -gt 0 ]; then
        echo "[!] Ditemukan $BEHIND_COUNT pembaruan baru dari GitHub! Mengunduh update..."
        git checkout -- .
        git reset --hard origin/main
        HAS_UPDATE=1
    else
        echo "[✓] Kode STB-CUANIN sudah dalam versi terbaru."
    fi
fi

# 3. Pulihkan kembali konfigurasi pengguna ke config.txt
python3 - << 'EOF'
import os, json

app_dir = os.path.abspath(os.getcwd())
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
        written_keys = set()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in user_cfg and user_cfg[k]:
                    new_lines.append(f"{k}={user_cfg[k]}\n")
                    written_keys.add(k)
                    continue
            new_lines.append(line)

        for k, v in user_cfg.items():
            if k not in written_keys and v:
                new_lines.append(f"{k}={v}\n")

        with open(cfg_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"[✓] Berhasil memulihkan {len(user_cfg)} pengaturan user ke config.txt!")
EOF

chmod +x stb-cuanin.py install.sh update.sh 2>/dev/null || true

# 4. Restart service untuk maintenance harian
if systemctl is-active --quiet stb-cuanin.service 2>/dev/null; then
    echo "[*] Merestart service stb-cuanin (maintenance harian)..."
    touch "$APP_DIR/.data/.maintenance_restarted" 2>/dev/null || true
    systemctl restart stb-cuanin.service
    echo "[✓] Service stb-cuanin berhasil direstart."
fi

echo "=== [✓] Pembaruan & Maintenance Harian Selesai Dilakukan! ==="
