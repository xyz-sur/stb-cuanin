# 🚀 STB-CUANIN (1 STB 1 IP Passive Income Node Manager)

Platform otomasi dan dashboard monitoring *passive income node* (sharing bandwidth residensial & DePIN) yang dioptimasi khusus untuk perangkat **STB Android / Armbian (seperti ZTE HG680P, Fiberhome HG680-FJ, B860H) dan Single Board Computer (Raspberry Pi, Orange Pi)** dengan RAM 2 GB.

Didesain dengan arsitektur **1 STB 1 IP Murni (Tanpa Proxy Internal)**, alokasi memori ketat yang menyisakan cadangan RAM aman minimal **30% – 60%**, serta Web Dashboard interaktif di port **12345**.

---

## 🌟 Fitur Utama

1. **1 STB 1 IP Direct Connection (No Proxy)**  
   Semua container berjalan langsung memanfaatkan IP publik utama perangkat tanpa overhead proxy lokal (menghilangkan bottleneck dan halaman proxy internal bawaan port 8081).
2. **Dashboard Monitoring Real-Time Terproteksi (Port 12345)**  
   Antarmuka web bertema *Cyberpunk Dark Theme* yang ringan (~15 MB RAM overhead) dan terproteksi autentikasi password (**default: `12345`**) untuk mencegah akses lokal yang tidak diinginkan:
   * Memantau CPU, RAM, Uptime, dan status operasional setiap container node.
   * Tabel Link Referral interaktif untuk memudahkan pendaftaran akun baru.
   * Form pengaturan akun terpusat dengan tombol *Apply & Restart*.
   * Tombol *Log Realtime* dan *Restart Container* individual.
3. **Alokasi RAM Aman & Hemat Daya**  
   Setiap container dipasangi *Hard Resource Limit* (`mem_limit`). Total pemakaian RAM seluruh container sangat hemat (~200 – 300 MB), menyisakan lebih dari **1.600 MB (~80%+) RAM bebas** di STB 2 GB untuk menjaga suhu adem dan mencegah *OOM Killer*.
4. **Auto-Provisioning & Self-Healing**  
   Stack container siap jalan dengan konfigurasi otomatis dan *restart policy* andal jika terjadi gangguan koneksi atau reboot perangkat.
5. **Menu Update 1-Klik**  
   Tersedia tombol pembaruan sistem di Web UI dan skrip `update.sh` yang menarik pembaruan terbaru dari repositori tanpa menghapus atau mereset file `config.txt` pengguna.

---

## 📋 Daftar 7 Layanan Legit Terintegrasi (Docker ARM64 & AMD64)

| No | Layanan | Docker Image | Min. Payout | Metode Payout | Status Arsitektur |
| :---: | :--- | :--- | :---: | :--- | :---: |
| 1 | **Pawns.app** | `iproyal/pawns-cli:latest` | **$5** | PayPal, BTC, Visa | ARM64 / AMD64 |
| 2 | **PacketStream** | `packetstream/psclient:latest` | **$5** | PayPal | ARM64 / AMD64 |
| 3 | **EarnApp** | `fazalfarhan01/earnapp:lite` | **$10** | PayPal, Wise (Auto) | ARM64 / AMD64 |
| 4 | **Honeygain** | `honeygain/honeygain:latest` | **$0** (JMPT) / $20 | JumpTask (Crypto) / PayPal | ARM64 / AMD64 |
| 5 | **TraffMonetizer**| `traffmonetizer/cli:arm64v8` | **$10** | USDT (TRC-20), BTC | Multi-tag Otomatis |
| 6 | **EarnFM** | `earnfm/earnfm-client:latest`| **$15** | PayPal, USDT, Crypto | ARM64 / AMD64 |
| 7 | **Repocket** | `repocket/repocket:latest` | **$20** | PayPal, Wise | ARM64 / AMD64 |

---

## ⚡ Cara Instalasi 1-Klik

Jalankan perintah ini di terminal STB / Linux Armbian Anda sebagai **root**:

```bash
curl -fsSL https://raw.githubusercontent.com/xyz-sur/stb-cuanin/main/install.sh | bash
```

Setelah instalasi selesai, buka browser Anda ke:
```text
http://<IP_STB_ANDA>:12345
```
*Gunakan password bawaan: `12345` (Dapat langsung diganti melalui tombol **🔑 Ganti Password** di dashboard atau melalui file `config.txt`).*

---

## 🛠️ Format File `config.txt`

File konfigurasi terletak di `/opt/stb-cuanin/config.txt`. Anda dapat mengeditnya langsung lewat terminal atau melalui form di Web Dashboard:

```text
# 1. Pawns.app (IPRoyal)
# DAFTAR: https://pawns.app/?r=16604653
PAWNS_EMAIL=
PAWNS_PASSWORD=

# 2. PacketStream
# DAFTAR: https://packetstream.io/share-bandwidth/?psr=15mskkd307
PACKETSTREAM_CID=

# 3. Honeygain
# DAFTAR: https://join.honeygain.com/T3RNA0D471
HONEYGAIN_EMAIL=
HONEYGAIN_PASSWORD=

# 4. TraffMonetizer
# DAFTAR: https://traffmonetizer.com/?aff=2128139
TRAFFMONETIZER_TOKEN=

# 5. EarnFM
# DAFTAR: https://earn.fm/ref/TERNKIO4
EARNFM_TOKEN=

# 6. Repocket
# DAFTAR: https://repocket.com/
REPOCKET_EMAIL=
REPOCKET_API_KEY=

# 7. Keamanan Web Dashboard Monitoring (Port 12345)
# Password default: 12345 (Dapat diubah untuk mengamankan akses dari jaringan lokal)
DASHBOARD_PASSWORD=12345
```

---

## 🔄 Pembaruan Sistem

Pembaruan dapat dilakukan dengan menekan tombol **"Cek Update Git"** di Web Dashboard atau via CLI:

```bash
/opt/stb-cuanin/update.sh
```

---
*Dibuat & Dikelola untuk Komunitas Passive Income STB / Armbian Indonesia.*
