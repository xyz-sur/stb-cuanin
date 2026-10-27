#!/usr/bin/env python3
"""
STB-CUANIN - Automated Passive Income Node Stack & Management Dashboard
Designed for TV Box / STB / SBC (HG680P, Armbian, Raspberry Pi)
Port: 12345
"""

import os
import sys
import json
import time
import socket
import shutil
import secrets
import hmac
import hashlib
import platform
import subprocess
import urllib.request
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Import our zero-dependency Crypto Vault
from crypto_vault import decrypt_dict, get_master_key

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(APP_DIR, "config.txt")
VAULT_FILE = os.path.join(APP_DIR, "dev_vault.enc")
REMOTE_VAULT_URLS = [
    "https://stbcuanin.89id.eu.org/api/v1/vault",
    "https://vault-cuanin.msr.my.id/api/v1/vault",
    "https://stb-cuanin-vault.mansyurj168.workers.dev/api/v1/vault"
]
COMPOSE_FILE = os.path.join(APP_DIR, "docker-compose.generated.yml")
DATA_DIR = os.path.join(APP_DIR, ".data")
PORT = int(os.environ.get("DASHBOARD_PORT", 12345))

SERVICES_META = {
    "pawns": {
        "name": "Pawns.app (IPRoyal)",
        "min_payout": "$5",
        "methods": "PayPal, BTC, Visa",
        "ref_url": "https://pawns.app/?r=16604653",
        "description": "Bandwidth sharing P2P, pembayaran cepat & stabil."
    },
    "packetstream": {
        "name": "PacketStream",
        "min_payout": "$5",
        "methods": "PayPal",
        "ref_url": "https://packetstream.io/share-bandwidth/?psr=15mskkd307",
        "description": "Jaringan proxy residensial global, sangat ringan."
    },
    "earnapp": {
        "name": "EarnApp",
        "min_payout": "$10",
        "methods": "PayPal, Wise (Auto-Redeem)",
        "ref_url": "https://earnapp.com/i/3zulx7k",
        "description": "Trafik tinggi di Indonesia, payout otomatis ke PayPal."
    },
    "honeygain": {
        "name": "Honeygain",
        "min_payout": "$0 (JMPT) / $20",
        "methods": "JumpTask Crypto / PayPal",
        "ref_url": "https://join.honeygain.com/T3RNA0D471",
        "description": "Bonus pendaftaran $3, tanpa batas minimal via JumpTask."
    },
    "traffmonetizer": {
        "name": "TraffMonetizer",
        "min_payout": "$10",
        "methods": "USDT (TRC-20), BTC",
        "ref_url": "https://traffmonetizer.com/?aff=2128139",
        "description": "Payout langsung crypto USDT ke Indodax/Tokocrypto."
    },
    "earnfm": {
        "name": "EarnFM",
        "min_payout": "$15",
        "methods": "PayPal, USDT, Crypto",
        "ref_url": "https://earn.fm/ref/TERNKIO4",
        "description": "Proyek bandwidth sharing terpercaya & stabil."
    },
    "repocket": {
        "name": "Repocket",
        "min_payout": "$20",
        "methods": "PayPal, Wise",
        "ref_url": "https://repocket.com/",
        "description": "Bonus pendaftaran $5, pelengkap diversifikasi node."
    }
}

def get_hostname():
    try:
        return socket.gethostname().strip() or "stb-cuanin"
    except Exception:
        return "stb-cuanin"

def get_host_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def get_architecture():
    m = platform.machine().lower()
    if m in ["aarch64", "arm64", "armv8l"]:
        return "arm64"
    return "amd64"

def get_or_create_earnapp_uuid():
    os.makedirs(DATA_DIR, exist_ok=True)
    uuid_file = os.path.join(DATA_DIR, "earnapp_uuid")
    uuid_val = None
    if os.path.exists(uuid_file):
        try:
            with open(uuid_file, "r") as f:
                val = f.read().strip()
                if val.startswith("sdk-node-") and len(val) >= 41:
                    uuid_val = val
        except Exception:
            pass
    if not uuid_val:
        # Generate static 32-character hex node UUID
        uuid_val = f"sdk-node-{secrets.token_hex(16)}"
        with open(uuid_file, "w") as f:
            f.write(uuid_val)

    # Simpan link binding mandiri ke file link_earnapps.txt
    try:
        link_file = os.path.join(APP_DIR, "link_earnapps.txt")
        claim_url = f"https://earnapp.com/r/{uuid_val}"
        with open(link_file, "w") as f:
            f.write(f"{claim_url}\n")
    except Exception:
        pass

    return uuid_val

def load_user_config():
    cfg = {}
    if not os.path.exists(CONFIG_FILE):
        return cfg
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg

def save_user_config(new_vals: dict):
    lines = []
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = [
            "# ==============================================================================\n",
            "#                      STB-CUANIN CONFIGURATION FILE\n",
            "# ==============================================================================\n"
        ]

    keys_written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in new_vals:
                new_lines.append(f"{k}={new_vals[k]}\n")
                keys_written.add(k)
                continue
        new_lines.append(line)

    for k, v in new_vals.items():
        if k not in keys_written:
            new_lines.append(f"{k}={v}\n")

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def load_dev_vault():
    master_key = get_master_key()
    if not master_key:
        return {}

    # 1. Dynamically auto-fetch latest encrypted payload from Cloudflare Worker
    for url in REMOTE_VAULT_URLS:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Linux; STB-Cuanin-Node)",
                    "X-Fleet-Key": master_key
                }
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    remote_blob = resp.read().decode("utf-8").strip()
                    dec = decrypt_dict(remote_blob, master_key)
                    if dec and isinstance(dec, dict):
                        # Cache to local dev_vault.enc for offline resilience (mode 600)
                        try:
                            with open(VAULT_FILE, "w", encoding="utf-8") as f:
                                f.write(remote_blob)
                            os.chmod(VAULT_FILE, 0o600)
                        except Exception:
                            pass
                        return dec
        except Exception:
            continue

    # 2. Offline fallback to local cached dev_vault.enc
    if os.path.exists(VAULT_FILE):
        try:
            with open(VAULT_FILE, "r", encoding="utf-8") as f:
                enc_data = f.read()
            return decrypt_dict(enc_data, master_key)
        except Exception as e:
            return {}
    return {}

def get_fleet_active_services(dev_vault=None):
    if dev_vault is None:
        dev_vault = load_dev_vault()
    active = dev_vault.get("active_services")
    if isinstance(active, list) and len(active) > 0:
        return active
    try:
        req = urllib.request.Request(
            "https://stbcuanin.89id.eu.org/api/v1/rules",
            headers={"User-Agent": "Mozilla/5.0 (Linux; STB-Cuanin-Node)"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                rules_active = data.get("active_services")
                if isinstance(rules_active, list) and len(rules_active) > 0:
                    return rules_active
    except Exception:
        pass
    return [
        "pawns", "packetstream", "earnapp", "honeygain",
        "traffmonetizer", "earnfm", "repocket"
    ]

def resolve_credentials():
    user_cfg = load_user_config()
    dev_vault = load_dev_vault()
    resolved = {
        "_active_services": get_fleet_active_services(dev_vault)
    }

    def get_val(user_key, dev_key):
        u_val = user_cfg.get(user_key, "").strip()
        if u_val:
            return u_val, "user"
        d_val = dev_vault.get(dev_key, "").strip()
        if d_val:
            return d_val, "default"
        return "", "empty"

    # Pawns
    p_email, p_em_m = get_val("PAWNS_EMAIL", "pawns_email")
    p_pass, p_pa_m = get_val("PAWNS_PASSWORD", "pawns_password")
    resolved["pawns"] = {
        "email": p_email,
        "password": p_pass,
        "mode": "user" if p_em_m == "user" else ("default" if p_email and p_pass else "empty")
    }

    # PacketStream
    ps_cid, ps_m = get_val("PACKETSTREAM_CID", "packetstream_cid")
    resolved["packetstream"] = {
        "cid": ps_cid,
        "mode": ps_m if ps_cid else "empty"
    }

    # EarnApp
    resolved["earnapp"] = {
        "uuid": get_or_create_earnapp_uuid(),
        "mode": "user"
    }

    # Honeygain
    hg_email, hg_em_m = get_val("HONEYGAIN_EMAIL", "honeygain_email")
    hg_pass, hg_pa_m = get_val("HONEYGAIN_PASSWORD", "honeygain_password")
    resolved["honeygain"] = {
        "email": hg_email,
        "password": hg_pass,
        "mode": "user" if hg_em_m == "user" else ("default" if hg_email and hg_pass else "empty")
    }

    # TraffMonetizer
    tm_token, tm_m = get_val("TRAFFMONETIZER_TOKEN", "traffmonetizer_token")
    resolved["traffmonetizer"] = {
        "token": tm_token,
        "mode": tm_m if tm_token else "empty"
    }

    # EarnFM
    efm_token, efm_m = get_val("EARNFM_TOKEN", "earnfm_token")
    resolved["earnfm"] = {
        "token": efm_token,
        "mode": efm_m if efm_token else "empty"
    }

    # Repocket
    rp_email, rp_em_m = get_val("REPOCKET_EMAIL", "repocket_email")
    rp_key, rp_k_m = get_val("REPOCKET_API_KEY", "repocket_api_key")
    resolved["repocket"] = {
        "email": rp_email,
        "api_key": rp_key,
        "mode": "user" if rp_em_m == "user" else ("default" if rp_email and rp_key else "empty")
    }

    return resolved

def generate_docker_compose():
    creds = resolve_credentials()
    active_services = creds.get("_active_services", list(SERVICES_META.keys()))
    hostname = get_hostname()
    arch = get_architecture()
    earnapp_dir = os.path.join(DATA_DIR, "earnapp")
    os.makedirs(earnapp_dir, exist_ok=True)

    services = {}

    # 1. Pawns
    if "pawns" in active_services and creds["pawns"]["email"] and creds["pawns"]["password"]:
        services["pawns"] = {
            "container_name": f"{hostname}_pawns",
            "image": "iproyal/pawns-cli:latest",
            "restart": "always",
            "command": f"-email={creds['pawns']['email']} -password={creds['pawns']['password']} -device-name={hostname} -accept-tos",
            "mem_limit": "80m",
            "cpus": 0.5
        }

    # 2. PacketStream
    if "packetstream" in active_services and creds["packetstream"]["cid"]:
        services["packetstream"] = {
            "container_name": f"{hostname}_packetstream",
            "image": "packetstream/psclient:latest",
            "restart": "always",
            "environment": [f"CID={creds['packetstream']['cid']}"],
            "mem_limit": "80m",
            "cpus": 0.5
        }

    # 3. EarnApp (Uses persistent EARNAPP_UUID)
    if "earnapp" in active_services:
        earn_uuid = creds["earnapp"]["uuid"]
        services["earnapp"] = {
            "container_name": f"{hostname}_earnapp",
            "image": "fazalfarhan01/earnapp:lite",
            "restart": "always",
            "volumes": [f"{earnapp_dir}:/etc/earnapp"],
            "environment": [
                f"EARNAPP_UUID={earn_uuid}",
                "EARNAPP_TERM=yes"
            ],
            "mem_limit": "120m",
            "cpus": 0.6
        }

    # 4. Honeygain
    if "honeygain" in active_services and creds["honeygain"]["email"] and creds["honeygain"]["password"]:
        services["honeygain"] = {
            "container_name": f"{hostname}_honeygain",
            "image": "honeygain/honeygain:latest",
            "restart": "always",
            "command": f"-tou-accept -email {creds['honeygain']['email']} -pass {creds['honeygain']['password']} -device {hostname}",
            "mem_limit": "80m",
            "cpus": 0.5
        }

    # 5. TraffMonetizer
    if "traffmonetizer" in active_services and creds["traffmonetizer"]["token"]:
        tm_image = "traffmonetizer/cli:arm64v8" if arch == "arm64" else "traffmonetizer/cli_v2:latest"
        services["traffmonetizer"] = {
            "container_name": f"{hostname}_traffmonetizer",
            "image": tm_image,
            "restart": "always",
            "command": f"start accept --token {creds['traffmonetizer']['token']} --device-name {hostname}",
            "mem_limit": "80m",
            "cpus": 0.5
        }

    # 6. EarnFM
    if "earnfm" in active_services and creds["earnfm"]["token"]:
        services["earnfm"] = {
            "container_name": f"{hostname}_earnfm",
            "image": "earnfm/earnfm-client:latest",
            "restart": "always",
            "environment": [f"EARNFM_TOKEN={creds['earnfm']['token']}"],
            "mem_limit": "80m",
            "cpus": 0.5
        }

    # 7. Repocket
    if "repocket" in active_services and creds["repocket"]["email"] and creds["repocket"]["api_key"]:
        services["repocket"] = {
            "container_name": f"{hostname}_repocket",
            "image": "repocket/repocket:latest",
            "restart": "always",
            "environment": [
                f"RP_EMAIL={creds['repocket']['email']}",
                f"RP_API_KEY={creds['repocket']['api_key']}"
            ],
            "mem_limit": "80m",
            "cpus": 0.5
        }

    yaml_lines = ["version: '3.8'", "services:"]
    for name, s_cfg in services.items():
        yaml_lines.append(f"  {name}:")
        yaml_lines.append(f"    container_name: {s_cfg['container_name']}")
        yaml_lines.append(f"    image: {s_cfg['image']}")
        yaml_lines.append(f"    restart: {s_cfg['restart']}")
        if "command" in s_cfg:
            yaml_lines.append(f"    command: {s_cfg['command']}")
        if "environment" in s_cfg:
            yaml_lines.append("    environment:")
            for env_item in s_cfg["environment"]:
                yaml_lines.append(f"      - {env_item}")
        if "volumes" in s_cfg:
            yaml_lines.append("    volumes:")
            for vol_item in s_cfg["volumes"]:
                yaml_lines.append(f"      - {vol_item}")
        yaml_lines.append(f"    mem_limit: {s_cfg['mem_limit']}")
        yaml_lines.append(f"    cpus: {s_cfg['cpus']}")

    with open(COMPOSE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines) + "\n")

    return list(services.keys())

def run_compose_command(action):
    generate_docker_compose()
    cmd = ["docker", "compose", "-f", COMPOSE_FILE]
    if action == "up":
        cmd.extend(["up", "-d", "--remove-orphans"])
    elif action == "down":
        cmd.extend(["down"])
    elif action == "restart":
        cmd.extend(["restart"])
    
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode == 0, res.stdout + res.stderr

def get_system_stats():
    hostname = get_hostname()
    ip = get_host_ip()
    arch = get_architecture()
    
    total_ram_mb = 2048
    free_ram_mb = 1024
    try:
        with open("/proc/meminfo", "r") as f:
            mem_data = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    mem_data[key] = int(val)
            total_ram_mb = round(mem_data.get("MemTotal", 2048 * 1024) / 1024)
            avail_ram_mb = round(mem_data.get("MemAvailable", mem_data.get("MemFree", 1024 * 1024)) / 1024)
            free_ram_mb = avail_ram_mb
    except Exception:
        pass

    used_ram_mb = max(0, total_ram_mb - free_ram_mb)
    ram_free_percent = round((free_ram_mb / total_ram_mb) * 100, 1) if total_ram_mb else 0
    ram_used_percent = round((used_ram_mb / total_ram_mb) * 100, 1) if total_ram_mb else 0

    cpu_cores = os.cpu_count() or 4
    load_avg = [0.0, 0.0, 0.0]
    try:
        load_avg = [round(x, 2) for x in os.getloadavg()]
    except Exception:
        pass

    return {
        "hostname": hostname,
        "ip": ip,
        "arch": arch,
        "cpu_cores": cpu_cores,
        "load_avg": load_avg,
        "total_ram_mb": total_ram_mb,
        "used_ram_mb": used_ram_mb,
        "free_ram_mb": free_ram_mb,
        "ram_used_percent": ram_used_percent,
        "ram_free_percent": ram_free_percent
    }

def get_containers_status():
    hostname = get_hostname()
    creds = resolve_credentials()
    earn_uuid = creds["earnapp"]["uuid"]

    ps_cmd = ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.State}}"]
    res = subprocess.run(ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    running_map = {}
    if res.returncode == 0:
        for line in res.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                name, status_str, state = parts[0], parts[1], parts[2]
                running_map[name] = {"status_text": status_str, "state": state.lower()}

    stats_map = {}
    try:
        st_cmd = ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"]
        st_res = subprocess.run(st_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if st_res.returncode == 0:
            for line in st_res.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 3:
                    cname, cpu_p, mem_u = parts[0], parts[1], parts[2]
                    stats_map[cname] = {"cpu": cpu_p, "mem": mem_u}
    except Exception:
        pass

    nodes = []
    active_services = creds.get("_active_services", list(SERVICES_META.keys()))
    for svc_key, meta in SERVICES_META.items():
        c_name = f"{hostname}_{svc_key}"
        c_info = running_map.get(c_name, None)
        c_stats = stats_map.get(c_name, {"cpu": "0%", "mem": "0B"})
        cred_info = creds.get(svc_key, {})
        mode = cred_info.get("mode", "empty")
        is_fleet_active = svc_key in active_services

        status = "stopped"
        if not is_fleet_active:
            status = "disabled_by_fleet"
        elif c_info:
            if c_info["state"] == "running":
                status = "running"
            elif c_info["state"] == "restarting":
                status = "restarting"
            else:
                status = "stopped"
        else:
            status = "not_created"

        node_data = {
            "id": svc_key,
            "name": meta["name"],
            "container_name": c_name,
            "status": status,
            "mode": mode,
            "fleet_active": is_fleet_active,
            "min_payout": meta["min_payout"],
            "methods": meta["methods"],
            "ref_url": meta["ref_url"],
            "description": meta["description"],
            "cpu": c_stats["cpu"],
            "mem": c_stats["mem"]
        }

        if svc_key == "earnapp":
            node_data["claim_url"] = f"https://earnapp.com/r/{earn_uuid}"
            node_data["node_id"] = earn_uuid

        nodes.append(node_data)

    return nodes

HTML_PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>STB-CUANIN | Dashboard Monitoring</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #151d2f;
      --border: #232f48;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --accent: #10b981;
      --accent-purple: #8b5cf6;
      --danger: #ef4444;
      --warning: #f59e0b;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); padding-bottom: 60px; }
    .header { background: linear-gradient(180deg, #182238 0%, #111827 100%); border-bottom: 1px solid var(--border); padding: 18px 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px; }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand-logo { background: linear-gradient(135deg, #3b82f6, #10b981); color: white; width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 20px; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4); }
    .brand-title { font-size: 1.25rem; font-weight: 700; letter-spacing: -0.5px; }
    .brand-sub { font-size: 0.8rem; color: var(--text-muted); }
    .host-badge { background: var(--card-bg); border: 1px solid var(--border); padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; font-family: monospace; display: flex; align-items: center; gap: 8px; }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 8px var(--accent); }
    .container { max-width: 1200px; margin: 24px auto; padding: 0 16px; }
    
    /* Stats Bar */
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .stat-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 6px; }
    .stat-label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-value { font-size: 1.35rem; font-weight: 700; color: #fff; }
    .progress-bar { width: 100%; height: 6px; background: #232f48; border-radius: 3px; overflow: hidden; margin-top: 4px; }
    .progress-fill { height: 100%; background: var(--accent); border-radius: 3px; transition: width 0.3s; }

    /* Actions Bar */
    .actions-bar { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
    .btn-group { display: flex; gap: 10px; flex-wrap: wrap; }
    .btn { padding: 9px 16px; border-radius: 8px; font-weight: 600; font-size: 0.85rem; cursor: pointer; border: none; transition: 0.2s; display: inline-flex; align-items: center; gap: 6px; text-decoration: none; }
    .btn-primary { background: var(--primary); color: white; }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-success { background: var(--accent); color: #064e3b; }
    .btn-success:hover { background: #059669; color: white; }
    .btn-danger { background: #7f1d1d; color: #fecaca; }
    .btn-danger:hover { background: var(--danger); color: white; }
    .btn-dark { background: #1e293b; color: var(--text); border: 1px solid var(--border); }
    .btn-dark:hover { background: #334155; }

    /* Tabs */
    .tabs { display: flex; gap: 8px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
    .tab-btn { padding: 10px 18px; background: transparent; border: none; color: var(--text-muted); font-weight: 600; cursor: pointer; border-bottom: 2px solid transparent; font-size: 0.95rem; }
    .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }

    /* Node Cards */
    .nodes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 18px; margin-bottom: 30px; }
    .node-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 18px; display: flex; flex-direction: column; justify-content: space-between; transition: 0.2s; position: relative; overflow: hidden; }
    .node-card:hover { border-color: #3b82f6; transform: translateY(-2px); }
    .node-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
    .node-title { font-size: 1.05rem; font-weight: 700; color: #fff; }
    .badge { font-size: 0.72rem; font-weight: 700; padding: 3px 8px; border-radius: 12px; text-transform: uppercase; }
    .badge-running { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-stopped { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-mode-user { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-mode-dev { background: rgba(139, 92, 246, 0.2); color: #a78bfa; border: 1px solid rgba(139, 92, 246, 0.3); }
    
    .node-body { font-size: 0.85rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
    .node-metric { display: flex; justify-content: space-between; padding-bottom: 4px; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .node-metric span:last-child { color: var(--text); font-family: monospace; font-weight: 600; }
    .node-actions { display: flex; gap: 8px; }

    /* Referral Table */
    .table-container { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 30px; }
    .ref-table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.88rem; }
    .ref-table th { background: #1e293b; padding: 12px 16px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }
    .ref-table td { padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .ref-table tr:last-child td { border-bottom: none; }
    .ref-table tr:hover td { background: rgba(255,255,255,0.02); }

    /* Config Form */
    .form-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 30px; }
    .form-section { margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .form-section:last-child { border-bottom: none; }
    .form-section-title { font-size: 1rem; font-weight: 700; color: #fff; margin-bottom: 6px; display: flex; align-items: center; justify-content: space-between; }
    .form-section-desc { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 14px; }
    .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
    .form-group { display: flex; flex-direction: column; gap: 6px; }
    .form-group label { font-size: 0.82rem; font-weight: 600; color: var(--text-muted); }
    .form-input { background: #0f172a; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; color: #fff; font-size: 0.9rem; transition: 0.2s; }
    .form-input:focus { border-color: var(--primary); outline: none; }

    /* Lock Overlay */
    .lock-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(11, 15, 25, 0.94); backdrop-filter: blur(8px); z-index: 9999; align-items: center; justify-content: center; }
    .lock-card { background: #151d2f; border: 1px solid #232f48; border-radius: 16px; padding: 32px 28px; width: 90%; max-width: 400px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.6); }
    .lock-icon { background: linear-gradient(135deg, #3b82f6, #10b981); color: #fff; width: 56px; height: 56px; border-radius: 14px; margin: 0 auto 16px; display: flex; align-items: center; justify-content: center; font-size: 26px; box-shadow: 0 8px 20px rgba(59,130,246,0.4); }
    .lock-title { font-size: 1.35rem; font-weight: 700; color: #fff; margin-bottom: 6px; }
    .lock-desc { font-size: 0.85rem; color: #9ca3af; margin-bottom: 22px; }

    /* Modal */
    .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); backdrop-filter: blur(4px); z-index: 999; align-items: center; justify-content: center; }
    .modal-content { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; width: 90%; max-width: 800px; max-height: 85vh; display: flex; flex-direction: column; overflow: hidden; }
    .modal-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
    .modal-body { padding: 16px; overflow-y: auto; background: #0b0f19; font-family: monospace; font-size: 0.82rem; color: #38bdf8; white-space: pre-wrap; flex-grow: 1; }
    .modal-footer { padding: 12px 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; }
  </style>
</head>
<body>

  <header class="header">
    <div class="brand">
      <div class="brand-logo">C</div>
      <div>
        <div class="brand-title">STB-CUANIN</div>
        <div class="brand-sub">1 STB 1 IP Passive Income Node Manager</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
      <div class="host-badge">
        <div class="status-dot"></div>
        <span id="txt-hostname">STB</span> (<span id="txt-ip">0.0.0.0</span>) | <span id="txt-arch">arm64</span>
      </div>
      <button class="btn btn-dark" onclick="openPasswordModal()" style="font-size: 0.8rem; padding: 6px 12px;">🔑 Ganti Password</button>
      <button class="btn btn-dark" onclick="handleLogout()" style="font-size: 0.8rem; padding: 6px 12px; color: #f87171;">🚪 Logout</button>
    </div>
  </header>

  <div class="container">
    <!-- Top Stats -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Sisa Cadangan RAM (30% Buffer)</div>
        <div class="stat-value" id="val-free-ram">-- MB (64%)</div>
        <div class="progress-bar"><div class="progress-fill" id="bar-ram" style="width: 64%;"></div></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total RAM Terpakai</div>
        <div class="stat-value" id="val-used-ram">-- MB</div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;">Dari total <span id="val-total-ram">2048</span> MB</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Beban CPU (Load Avg)</div>
        <div class="stat-value" id="val-cpu-load">0.12, 0.15</div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;"><span id="val-cpu-cores">4</span> Cores S905X</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Node Aktif Berjalan</div>
        <div class="stat-value" id="val-active-nodes" style="color: var(--accent);">-- / 8</div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;">Langsung ke IP Publik (No Proxy)</div>
      </div>
    </div>

    <!-- Quick Actions Bar -->
    <div class="actions-bar">
      <div style="font-size: 0.9rem; font-weight: 600;">Status Kontrol Node</div>
      <div class="btn-group">
        <button class="btn btn-success" onclick="actionAll('start')">🚀 Start Semua</button>
        <button class="btn btn-dark" onclick="actionAll('restart')">🔄 Restart Semua</button>
        <button class="btn btn-danger" onclick="actionAll('stop')">⏹️ Stop Semua</button>
        <button class="btn btn-primary" onclick="triggerUpdate()">⚡ Cek Update Git</button>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('tab-nodes', this)">🖥️ Monitor Node</button>
      <button class="tab-btn" onclick="switchTab('tab-config', this)">⚙️ Konfigurasi Akun</button>
      <button class="tab-btn" onclick="switchTab('tab-referrals', this)">🎁 Daftar Link Referral</button>
    </div>

    <!-- TAB 1: NODES -->
    <div id="tab-nodes" class="tab-content">
      <div class="nodes-grid" id="nodes-container">
        <!-- Rendered by Javascript -->
      </div>
    </div>

    <!-- TAB 2: CONFIGURATION -->
    <div id="tab-config" class="tab-content" style="display: none;">
      <div class="form-card">
        <div style="margin-bottom: 20px;">
          <h2 style="font-size: 1.2rem; margin-bottom: 6px;">Pengaturan Akun Node</h2>
          <p style="font-size: 0.85rem; color: var(--text-muted);">
            Masukkan credential akun Anda di bawah ini agar penghasilan masuk ke akun Anda sendiri. Anda dapat mendaftar melalui tautan pada masing-masing layanan.
          </p>
        </div>

        <form id="cfg-form" onsubmit="saveConfig(event)">
          <!-- Pawns -->
          <div class="form-section">
            <div class="form-section-title">
              <span>1. Pawns.app (IPRoyal)</span>
              <a href="https://pawns.app/?r=16604653" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:4px 10px;">Daftar Akun</a>
            </div>
            <div class="form-section-desc">Min Payout $5 (PayPal, Crypto)</div>
            <div class="form-row">
              <div class="form-group"><label>Email</label><input type="email" id="cfg_PAWNS_EMAIL" class="form-input" placeholder="contoh@gmail.com"></div>
              <div class="form-group"><label>Password</label><input type="password" id="cfg_PAWNS_PASSWORD" class="form-input" placeholder="Password Pawns"></div>
            </div>
          </div>

          <!-- PacketStream -->
          <div class="form-section">
            <div class="form-section-title">
              <span>2. PacketStream</span>
              <a href="https://packetstream.io/share-bandwidth/?psr=15mskkd307" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:4px 10px;">Daftar Akun</a>
            </div>
            <div class="form-section-desc">Min Payout $5 (PayPal). Masukkan CID (ID Numerik dari script install PacketStream).</div>
            <div class="form-row">
              <div class="form-group"><label>CID (Client ID)</label><input type="text" id="cfg_PACKETSTREAM_CID" class="form-input" placeholder="Contoh: 7RmD atau 12345"></div>
            </div>
          </div>

          <!-- Honeygain -->
          <div class="form-section">
            <div class="form-section-title">
              <span>3. Honeygain</span>
              <a href="https://join.honeygain.com/T3RNA0D471" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:4px 10px;">Daftar Akun (Bonus $3)</a>
            </div>
            <div class="form-section-desc">Min Payout $0 via JumpTask. Wajib akun mandiri (bukan Google SSO).</div>
            <div class="form-row">
              <div class="form-group"><label>Email</label><input type="email" id="cfg_HONEYGAIN_EMAIL" class="form-input" placeholder="email@gmail.com"></div>
              <div class="form-group"><label>Password</label><input type="password" id="cfg_HONEYGAIN_PASSWORD" class="form-input" placeholder="Password Honeygain"></div>
            </div>
          </div>

          <!-- TraffMonetizer -->
          <div class="form-section">
            <div class="form-section-title">
              <span>4. TraffMonetizer</span>
              <a href="https://traffmonetizer.com/?aff=2128139" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:4px 10px;">Daftar Akun</a>
            </div>
            <div class="form-section-desc">Min Payout $10 USDT TRC-20 ke Indodax/Tokocrypto. Ambil token dari dashboard TraffMonetizer.</div>
            <div class="form-row">
              <div class="form-group"><label>Application Token</label><input type="text" id="cfg_TRAFFMONETIZER_TOKEN" class="form-input" placeholder="Token TraffMonetizer"></div>
            </div>
          </div>

          <!-- EarnFM -->
          <div class="form-section">
            <div class="form-section-title">
              <span>5. EarnFM</span>
              <a href="https://earn.fm/ref/TERNKIO4" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:4px 10px;">Daftar Akun</a>
            </div>
            <div class="form-section-desc">Min Payout $15 (USDT/Crypto). Masukkan API Key dari dashboard EarnFM.</div>
            <div class="form-row">
              <div class="form-group"><label>API Token</label><input type="text" id="cfg_EARNFM_TOKEN" class="form-input" placeholder="Token EarnFM"></div>
            </div>
          </div>

          <!-- Repocket -->
          <div class="form-section">
            <div class="form-section-title">
              <span>6. Repocket</span>
              <a href="https://repocket.com/" target="_blank" class="btn btn-dark" style="font-size:0.75rem; padding:4px 10px;">Daftar Akun (Bonus $5)</a>
            </div>
            <div class="form-section-desc">Min Payout $20 (PayPal). Masukkan Email dan API Key dari tab SDK dashboard Repocket.</div>
            <div class="form-row">
              <div class="form-group"><label>Email</label><input type="email" id="cfg_REPOCKET_EMAIL" class="form-input" placeholder="email@gmail.com"></div>
              <div class="form-group"><label>API Key</label><input type="text" id="cfg_REPOCKET_API_KEY" class="form-input" placeholder="API Key Repocket"></div>
            </div>
          </div>

          <!-- Keamanan Dashboard -->
          <div class="form-section">
            <div class="form-section-title">
              <span>7. Keamanan Web Dashboard (Port 12345)</span>
            </div>
            <div class="form-section-desc">Lindungi dashboard dari user jail di WiFi/LAN lokal Anda. Password default: <code>12345</code>.</div>
            <div class="form-row">
              <div class="form-group"><label>Password Dashboard Monitoring</label><input type="password" id="cfg_DASHBOARD_PASSWORD" class="form-input" placeholder="Default: 12345"></div>
            </div>
          </div>

          <div style="margin-top: 30px; display: flex; justify-content: flex-end;">
            <button type="submit" class="btn btn-success" style="font-size: 1rem; padding: 12px 28px;">💾 Simpan & Terapkan Perubahan</button>
          </div>
        </form>
      </div>
    </div>

    <!-- TAB 3: REFERRALS -->
    <div id="tab-referrals" class="tab-content" style="display: none;">
      <div class="table-container">
        <table class="ref-table">
          <thead>
            <tr>
              <th>Layanan</th>
              <th>Metode & Min. Payout</th>
              <th>Kelebihan / Karakteristik</th>
              <th>Aksi Pendaftaran</th>
            </tr>
          </thead>
          <tbody id="ref-table-body">
            <!-- Rendered by JS -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Lock Screen Overlay -->
  <div id="lock-overlay" class="lock-overlay">
    <div class="lock-card">
      <div class="lock-icon">🔒</div>
      <div class="lock-title">STB-CUANIN</div>
      <div class="lock-desc">Dashboard Terproteksi &bull; Masukkan Password</div>
      <form onsubmit="handleLogin(event)">
        <div style="margin-bottom: 16px; text-align: left;">
          <label style="display: block; font-size: 0.75rem; font-weight: 600; color: #9ca3af; margin-bottom: 6px; text-transform: uppercase;">Password Dashboard</label>
          <input type="password" id="login-pwd" class="form-input" placeholder="Default: 12345" style="width: 100%; font-size: 1rem; padding: 12px; text-align: center;" required autofocus>
        </div>
        <div id="login-err" style="color: #ef4444; font-size: 0.82rem; margin-bottom: 14px; display: none; background: rgba(239,68,68,0.1); padding: 8px 12px; border-radius: 6px; border: 1px solid rgba(239,68,68,0.2);"></div>
        <button type="submit" id="btn-login-submit" class="btn btn-primary" style="width: 100%; padding: 12px; font-size: 0.95rem; justify-content: center;">🔓 Buka Dashboard</button>
      </form>
      <div style="margin-top: 20px; font-size: 0.78rem; color: #64748b;">
        Password default: <code style="color: #34d399; background: rgba(52,211,153,0.1); padding: 2px 6px; border-radius: 4px;">12345</code>
      </div>
    </div>
  </div>

  <!-- Modal Ganti Password -->
  <div id="pwd-modal" class="modal">
    <div class="modal-content" style="max-width: 440px;">
      <div class="modal-header">
        <h3>🔑 Ubah Password Dashboard</h3>
        <button class="btn btn-dark" onclick="closePasswordModal()" style="padding: 4px 10px;">✕ Tutup</button>
      </div>
      <form onsubmit="handleChangePassword(event)" style="padding: 20px;">
        <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 16px;">
          Ganti password default (12345) untuk mengamankan STB dari akses tak dikenal di WiFi/LAN lokal Anda.
        </div>
        <div class="form-group" style="margin-bottom: 14px;">
          <label>Password Saat Ini</label>
          <input type="password" id="pwd-current" class="form-input" placeholder="Masukkan password sekarang" required>
        </div>
        <div class="form-group" style="margin-bottom: 16px;">
          <label>Password Baru</label>
          <input type="password" id="pwd-new" class="form-input" placeholder="Minimal 3 karakter" required minlength="3">
        </div>
        <div id="pwd-change-msg" style="font-size: 0.82rem; margin-bottom: 14px; display: none;"></div>
        <button type="submit" id="btn-save-pwd" class="btn btn-primary" style="width: 100%; justify-content: center; padding: 10px;">Simpan Password Baru</button>
      </form>
    </div>
  </div>

  <!-- Modal Log -->
  <div id="log-modal" class="modal">
    <div class="modal-content">
      <div class="modal-header">
        <h3 id="modal-title">Live Log Container</h3>
        <button class="btn btn-dark" onclick="closeLogModal()" style="padding: 4px 10px;">✕ Tutup</button>
      </div>
      <div id="modal-log-text" class="modal-body">Memuat log...</div>
      <div class="modal-footer">
        <button class="btn btn-primary" onclick="refreshCurrentLog()">Segarkan Log</button>
      </div>
    </div>
  </div>

  <script>
    let activeLogNode = "";

    function getStoredToken() {
      return sessionStorage.getItem('stb_token') || '';
    }

    function setStoredToken(token) {
      if (token) sessionStorage.setItem('stb_token', token);
      else sessionStorage.removeItem('stb_token');
    }

    function authHeaders(extra = {}) {
      const headers = { ...extra };
      const token = getStoredToken();
      if (token) {
        headers['Authorization'] = 'Bearer ' + token;
        headers['X-Dashboard-Token'] = token;
      }
      return headers;
    }

    function showLockScreen() {
      const overlay = document.getElementById('lock-overlay');
      if (overlay) {
        overlay.style.display = 'flex';
        document.getElementById('login-pwd').focus();
      }
    }

    function hideLockScreen() {
      const overlay = document.getElementById('lock-overlay');
      if (overlay) overlay.style.display = 'none';
      const err = document.getElementById('login-err');
      if (err) err.style.display = 'none';
    }

    async function handleLogin(e) {
      e.preventDefault();
      const pwd = document.getElementById('login-pwd').value;
      const errEl = document.getElementById('login-err');
      const btn = document.getElementById('btn-login-submit');
      errEl.style.display = 'none';
      btn.textContent = 'Memverifikasi...';
      btn.disabled = true;

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: pwd })
        });
        const out = await res.json();
        if (out.success) {
          setStoredToken(out.token);
          hideLockScreen();
          document.getElementById('login-pwd').value = '';
          fetchStatus();
        } else {
          errEl.textContent = out.message || 'Password salah!';
          errEl.style.display = 'block';
        }
      } catch (err) {
        errEl.textContent = 'Gagal menghubungi server: ' + err;
        errEl.style.display = 'block';
      } finally {
        btn.textContent = '🔓 Buka Dashboard';
        btn.disabled = false;
      }
    }

    async function handleLogout() {
      if (!confirm("Logout dari dashboard?")) return;
      try {
        await fetch('/api/auth/logout', { method: 'POST', headers: authHeaders() });
      } catch (e) {}
      setStoredToken('');
      showLockScreen();
    }

    function openPasswordModal() {
      document.getElementById('pwd-current').value = '';
      document.getElementById('pwd-new').value = '';
      const msg = document.getElementById('pwd-change-msg');
      msg.style.display = 'none';
      document.getElementById('pwd-modal').style.display = 'flex';
      document.getElementById('pwd-current').focus();
    }

    function closePasswordModal() {
      document.getElementById('pwd-modal').style.display = 'none';
    }

    async function handleChangePassword(e) {
      e.preventDefault();
      const current_password = document.getElementById('pwd-current').value;
      const new_password = document.getElementById('pwd-new').value;
      const msgEl = document.getElementById('pwd-change-msg');
      const btn = document.getElementById('btn-save-pwd');
      msgEl.style.display = 'none';
      btn.textContent = 'Menyimpan...';
      btn.disabled = true;

      try {
        const res = await fetch('/api/auth/change_password', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ current_password, new_password })
        });
        const out = await res.json();
        if (out.success) {
          if (out.token) setStoredToken(out.token);
          msgEl.style.color = '#34d399';
          msgEl.textContent = '✅ ' + (out.message || 'Password berhasil diperbarui!');
          msgEl.style.display = 'block';
          setTimeout(() => {
            closePasswordModal();
          }, 1500);
        } else {
          msgEl.style.color = '#ef4444';
          msgEl.textContent = '❌ ' + (out.message || 'Gagal mengubah password!');
          msgEl.style.display = 'block';
        }
      } catch (err) {
        msgEl.style.color = '#ef4444';
        msgEl.textContent = 'Error: ' + err;
        msgEl.style.display = 'block';
      } finally {
        btn.textContent = 'Simpan Password Baru';
        btn.disabled = false;
      }
    }

    function switchTab(tabId, btn) {
      document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).style.display = 'block';
      btn.classList.add('active');
      if (tabId === 'tab-config') loadConfigValues();
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status', { headers: authHeaders() });
        if (res.status === 401) {
          showLockScreen();
          return;
        }
        hideLockScreen();
        const data = await res.json();
        
        // Update header & sys stats
        document.getElementById('txt-hostname').textContent = data.system.hostname;
        document.getElementById('txt-ip').textContent = data.system.ip;
        document.getElementById('txt-arch').textContent = data.system.arch;
        document.getElementById('val-free-ram').textContent = `${data.system.free_ram_mb} MB (${data.system.ram_free_percent}%)`;
        document.getElementById('val-used-ram').textContent = `${data.system.used_ram_mb} MB`;
        document.getElementById('val-total-ram').textContent = data.system.total_ram_mb;
        document.getElementById('bar-ram').style.width = `${data.system.ram_free_percent}%`;
        document.getElementById('val-cpu-load').textContent = data.system.load_avg.slice(0, 2).join(', ');
        document.getElementById('val-cpu-cores').textContent = data.system.cpu_cores;

        let runningCount = 0;
        const container = document.getElementById('nodes-container');
        container.innerHTML = '';

        const refTbody = document.getElementById('ref-table-body');
        refTbody.innerHTML = '';

        data.nodes.forEach(node => {
          if (node.status === 'running') runningCount++;

          const isRunning = node.status === 'running';
          const badgeClass = isRunning ? 'badge-running' : 'badge-stopped';
          let modeBadge = '';
          if (!node.fleet_active) {
            modeBadge = '<span class="badge" style="background:#374151; color:#9ca3af;">Nonaktif Fleet</span>';
          } else if (node.mode === 'user') {
            modeBadge = '<span class="badge badge-mode-user">Akun Mandiri</span>';
          } else {
            modeBadge = '<span class="badge badge-mode-dev">Fleet Default</span>';
          }

          let claimBtn = '';
          if (node.id === 'earnapp' && node.claim_url) {
            claimBtn = `<a href="${node.claim_url}" target="_blank" class="btn btn-success" style="font-size:0.75rem; width:100%; justify-content:center; margin-bottom:8px;">🔗 Tautkan Node ke Akun EarnApp</a>`;
          }

          const card = document.createElement('div');
          card.className = 'node-card';
          card.innerHTML = `
            <div>
              <div class="node-header">
                <div>
                  <div class="node-title">${node.name}</div>
                  <div style="margin-top:4px;">${modeBadge}</div>
                </div>
                <span class="badge ${badgeClass}">${node.status}</span>
              </div>
              <div class="node-body">
                <div class="node-metric"><span>CPU:</span> <span>${node.cpu}</span></div>
                <div class="node-metric"><span>RAM:</span> <span>${node.mem}</span></div>
                <div class="node-metric"><span>Min Payout:</span> <span>${node.min_payout}</span></div>
                <div class="node-metric"><span>Metode:</span> <span style="font-size:0.75rem;">${node.methods}</span></div>
              </div>
            </div>
            <div>
              ${claimBtn}
              <div class="node-actions">
                <button class="btn btn-dark" style="flex:1; font-size:0.78rem;" onclick="viewLog('${node.id}')">📜 Log</button>
                <button class="btn btn-dark" style="flex:1; font-size:0.78rem;" onclick="actionSingle('${node.id}', 'restart')">🔄 Restart</button>
              </div>
            </div>
          `;
          container.appendChild(card);

          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td><strong>${node.name}</strong></td>
            <td><span style="color:var(--accent); font-weight:600;">${node.min_payout}</span><br><span style="font-size:0.75rem; color:var(--text-muted);">${node.methods}</span></td>
            <td>${node.description}</td>
            <td><a href="${node.ref_url}" target="_blank" class="btn btn-primary" style="font-size:0.78rem; padding:6px 12px;">Daftar Akun ↗</a></td>
          `;
          refTbody.appendChild(tr);
        });

        document.getElementById('val-active-nodes').textContent = `${runningCount} / ${data.nodes.length}`;

      } catch (err) {
        console.error("Gagal refresh status:", err);
      }
    }

    async function loadConfigValues() {
      try {
        const res = await fetch('/api/config', { headers: authHeaders() });
        if (res.status === 401) {
          showLockScreen();
          return;
        }
        const cfg = await res.json();
        for (const [k, v] of Object.entries(cfg)) {
          const el = document.getElementById(`cfg_${k}`);
          if (el) el.value = v;
        }
      } catch (e) {
        console.error("Gagal load config:", e);
      }
    }

    async function saveConfig(e) {
      e.preventDefault();
      const keys = [
        "PAWNS_EMAIL", "PAWNS_PASSWORD", "PACKETSTREAM_CID",
        "HONEYGAIN_EMAIL", "HONEYGAIN_PASSWORD", "TRAFFMONETIZER_TOKEN",
        "EARNFM_TOKEN",
        "REPOCKET_EMAIL", "REPOCKET_API_KEY",
        "DASHBOARD_PASSWORD"
      ];
      const payload = {};
      keys.forEach(k => {
        const el = document.getElementById(`cfg_${k}`);
        if (el) payload[k] = el.value.trim();
      });

      if (!confirm("Simpan konfigurasi dan restart node dengan pengaturan baru?")) return;

      try {
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(payload)
        });
        if (res.status === 401) {
          showLockScreen();
          return;
        }
        const out = await res.json();
        alert(out.message || "Konfigurasi berhasil disimpan!");
        switchTab('tab-nodes', document.querySelectorAll('.tab-btn')[0]);
        fetchStatus();
      } catch (err) {
        alert("Gagal menyimpan konfigurasi: " + err);
      }
    }

    async function actionAll(action) {
      if (!confirm(`Apakah Anda yakin ingin mengeksekusi '${action}' untuk semua node?`)) return;
      try {
        const res = await fetch(`/api/nodes/${action}`, { method: 'POST', headers: authHeaders() });
        if (res.status === 401) {
          showLockScreen();
          return;
        }
        const out = await res.json();
        alert(out.message);
        setTimeout(fetchStatus, 2000);
      } catch (e) {
        alert("Error: " + e);
      }
    }

    async function actionSingle(node, action) {
      try {
        const res = await fetch('/api/nodes/action', {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ node, action })
        });
        if (res.status === 401) {
          showLockScreen();
          return;
        }
        const out = await res.json();
        alert(out.message);
        setTimeout(fetchStatus, 2000);
      } catch (e) {
        alert("Error: " + e);
      }
    }

    async function viewLog(node) {
      activeLogNode = node;
      document.getElementById('modal-title').textContent = `Live Log: ${node}`;
      document.getElementById('modal-log-text').textContent = "Memuat log...";
      document.getElementById('log-modal').style.display = 'flex';
      refreshCurrentLog();
    }

    async function refreshCurrentLog() {
      if (!activeLogNode) return;
      try {
        const res = await fetch(`/api/logs?node=${activeLogNode}`, { headers: authHeaders() });
        if (res.status === 401) {
          closeLogModal();
          showLockScreen();
          return;
        }
        const data = await res.json();
        document.getElementById('modal-log-text').textContent = data.logs || "(Log kosong / node belum menghasilkan log)";
      } catch (e) {
        document.getElementById('modal-log-text').textContent = "Gagal mengambil log: " + e;
      }
    }

    function closeLogModal() {
      document.getElementById('log-modal').style.display = 'none';
      activeLogNode = "";
    }

    async function triggerUpdate() {
      if (!confirm("Cek dan tarik pembaruan terbaru dari GitHub repo?")) return;
      try {
        const res = await fetch('/api/update', { method: 'POST', headers: authHeaders() });
        if (res.status === 401) {
          showLockScreen();
          return;
        }
        const out = await res.json();
        alert(out.message + "\n\nLog:\n" + (out.output || ''));
        setTimeout(fetchStatus, 2000);
      } catch (e) {
        alert("Gagal update: " + e);
      }
    }

    fetchStatus();
    setInterval(fetchStatus, 5000);
  </script>
</body>
</html>
"""


def get_dashboard_password():
    cfg = load_user_config()
    pwd = cfg.get("DASHBOARD_PASSWORD", "").strip()
    if not pwd:
        pwd = os.environ.get("DASHBOARD_PASSWORD", "").strip()
    if not pwd:
        pwd = "12345"
    return pwd

def get_auth_secret():
    pwd = get_dashboard_password()
    return hashlib.sha256(f"stb_cuanin_auth_{pwd}".encode()).digest()

def generate_session_token():
    ts = str(int(time.time()))
    sig = hmac.new(get_auth_secret(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"

def verify_session_token(token):
    if not token or "." not in token:
        return False
    parts = token.split(".", 1)
    if len(parts) != 2:
        return False
    ts, sig = parts
    try:
        ts_int = int(ts)
    except ValueError:
        return False
    # Max age: 30 days (2592000s)
    if time.time() - ts_int > 2592000 or ts_int > time.time() + 3600:
        return False
    expected_sig = hmac.new(get_auth_secret(), ts.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected_sig)

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def get_token_from_request(self):
        cookie_hdr = self.headers.get("Cookie", "")
        if "stb_session=" in cookie_hdr:
            for part in cookie_hdr.split(";"):
                part = part.strip()
                if part.startswith("stb_session="):
                    return part.split("=", 1)[1].strip()
        auth_hdr = self.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            return auth_hdr.split(" ", 1)[1].strip()
        custom_hdr = self.headers.get("X-Dashboard-Token", "")
        if custom_hdr:
            return custom_hdr.strip()
        return ""

    def is_authenticated(self):
        token = self.get_token_from_request()
        return verify_session_token(token)

    def send_unauthorized(self):
        self.send_json(
            {"error": "Unauthorized", "locked": True, "message": "Password dashboard diperlukan."},
            status=401
        )

    def send_json(self, data, status=200, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        elif path == "/api/auth/status":
            self.send_json({"authenticated": self.is_authenticated()})
            return

        # Protected endpoints below require authentication
        if not self.is_authenticated():
            return self.send_unauthorized()

        if path == "/api/status":
            sys_stats = get_system_stats()
            nodes_stats = get_containers_status()
            data = {
                "system": sys_stats,
                "nodes": nodes_stats
            }
            self.send_json(data)
            return

        elif path == "/api/config":
            user_cfg = load_user_config()
            self.send_json(user_cfg)
            return

        elif path == "/api/logs":
            qs = parse_qs(parsed.query)
            node = qs.get("node", [""])[0]
            hostname = get_hostname()
            c_name = f"{hostname}_{node}"
            logs = ""
            try:
                res = subprocess.run(["docker", "logs", "--tail", "100", c_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                logs = res.stdout + res.stderr
            except Exception as e:
                logs = f"Error reading logs: {e}"
            self.send_json({"node": node, "logs": logs})
            return

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else ""
        payload = {}
        if body:
            try:
                payload = json.loads(body)
            except Exception:
                pass

        if path == "/api/auth/login":
            entered_pwd = payload.get("password", "")
            if entered_pwd == get_dashboard_password():
                token = generate_session_token()
                self.send_json(
                    {"success": True, "token": token, "message": "Login berhasil!"},
                    extra_headers={"Set-Cookie": f"stb_session={token}; Path=/; Max-Age=2592000; SameSite=Lax"}
                )
            else:
                self.send_json({"success": False, "message": "Password salah!"}, status=401)
            return

        elif path == "/api/auth/logout":
            self.send_json(
                {"success": True, "message": "Logout berhasil."},
                extra_headers={"Set-Cookie": "stb_session=; Path=/; Max-Age=0; SameSite=Lax"}
            )
            return

        # Protected endpoints below require authentication
        if not self.is_authenticated():
            return self.send_unauthorized()

        if path == "/api/auth/change_password":
            curr_pwd = payload.get("current_password", "").strip()
            new_pwd = payload.get("new_password", "").strip()
            if curr_pwd != get_dashboard_password():
                self.send_json({"success": False, "message": "Password lama tidak sesuai!"})
                return
            if len(new_pwd) < 3:
                self.send_json({"success": False, "message": "Password baru minimal 3 karakter!"})
                return
            save_user_config({"DASHBOARD_PASSWORD": new_pwd})
            new_token = generate_session_token()
            self.send_json(
                {"success": True, "token": new_token, "message": "Password dashboard berhasil diubah!"},
                extra_headers={"Set-Cookie": f"stb_session={new_token}; Path=/; Max-Age=2592000; SameSite=Lax"}
            )
            return

        elif path == "/api/config":
            pwd_changed = False
            if "DASHBOARD_PASSWORD" in payload and payload["DASHBOARD_PASSWORD"].strip():
                new_p = payload["DASHBOARD_PASSWORD"].strip()
                if new_p != get_dashboard_password():
                    pwd_changed = True
            save_user_config(payload)
            ok, out = run_compose_command("up")
            extra_h = {}
            if pwd_changed:
                new_token = generate_session_token()
                extra_h["Set-Cookie"] = f"stb_session={new_token}; Path=/; Max-Age=2592000; SameSite=Lax"
            self.send_json({
                "success": ok,
                "message": "Konfigurasi tersimpan dan node berhasil diterapkan!",
                "output": out
            }, extra_headers=extra_h)
            return

        elif path == "/api/nodes/start":
            ok, out = run_compose_command("up")
            self.send_json({"success": ok, "message": "Semua node telah dijalankan!", "output": out})
            return

        elif path == "/api/nodes/stop":
            ok, out = run_compose_command("down")
            self.send_json({"success": ok, "message": "Semua node telah dihentikan!", "output": out})
            return

        elif path == "/api/nodes/restart":
            ok, out = run_compose_command("restart")
            self.send_json({"success": ok, "message": "Semua node telah direstart!", "output": out})
            return

        elif path == "/api/nodes/action":
            node = payload.get("node", "")
            action = payload.get("action", "restart")
            hostname = get_hostname()
            c_name = f"{hostname}_{node}"
            cmd = ["docker", action, c_name]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.send_json({
                "success": res.returncode == 0,
                "message": f"Aksi '{action}' pada {node} selesai.",
                "output": res.stdout + res.stderr
            })
            return

        elif path == "/api/update":
            update_script = os.path.join(APP_DIR, "update.sh")
            if os.path.exists(update_script):
                res = subprocess.run(["bash", update_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.send_json({"success": res.returncode == 0, "message": "Pembaruan selesai dieksekusi!", "output": res.stdout + res.stderr})
            else:
                res = subprocess.run(["git", "-C", APP_DIR, "pull"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.send_json({"success": res.returncode == 0, "message": "Git pull selesai!", "output": res.stdout + res.stderr})
            return

        else:
            self.send_response(404)
            self.end_headers()

def backup_user_config_dict():
    """
    Ekstrak konfigurasi yang telah diisi oleh pengguna (non-empty)
    dan simpan ke cache aman .data/user_config_backup.json
    """
    user_settings = {}
    user_cfg_path = os.path.join(APP_DIR, "config.txt")
    if os.path.exists(user_cfg_path):
        raw_cfg = load_user_config()
        for k, v in raw_cfg.items():
            if v and v.strip():
                user_settings[k] = v.strip()

    backup_cache = os.path.join(DATA_DIR, "user_config_backup.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(backup_cache, "w", encoding="utf-8") as f:
            json.dump(user_settings, f, indent=2)
    except Exception:
        pass
    return user_settings

def restore_user_config_dict(user_settings=None):
    """
    Kembalikan konfigurasi user ke config.txt setelah update dari GitHub,
    memastikan pengaturan pengguna tidak pernah terhapus atau tertimpa template kosong.
    """
    if not user_settings:
        backup_cache = os.path.join(DATA_DIR, "user_config_backup.json")
        if os.path.exists(backup_cache):
            try:
                with open(backup_cache, "r", encoding="utf-8") as f:
                    user_settings = json.load(f)
            except Exception:
                user_settings = {}

    if not user_settings:
        return

    save_user_config(user_settings)
    print(f"[✓] Berhasil memulihkan {len(user_settings)} parameter konfigurasi user ke config.txt!")

def auto_update_repo():
    """
    Autonomous Git Auto-Update:
    Memeriksa commit baru di origin/main, mengamankan konfigurasi user,
    menarik kode terbaru dari GitHub, lalu memulihkan konfigurasi pengguna.
    """
    try:
        git_dir = os.path.join(APP_DIR, ".git")
        if not os.path.isdir(git_dir):
            return False

        print("[*] Memeriksa pembaruan skrip dari GitHub...")
        fetch_res = subprocess.run(
            ["git", "-C", APP_DIR, "fetch", "origin", "main"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
        )
        if fetch_res.returncode != 0:
            return False

        diff_res = subprocess.run(
            ["git", "-C", APP_DIR, "rev-list", "HEAD..origin/main", "--count"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
        )
        count = int(diff_res.stdout.strip() or "0")
        if count > 0:
            print(f"[!] Ditemukan {count} pembaruan baru dari GitHub! Mengamankan konfigurasi user...")
            
            # Step A: Amankan konfigurasi user
            saved_cfg = backup_user_config_dict()

            # Step B: Reset working tree & tarik update terbaru dari GitHub
            subprocess.run(["git", "-C", APP_DIR, "checkout", "--", "."], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pull_res = subprocess.run(
                ["git", "-C", APP_DIR, "reset", "--hard", "origin/main"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
            )

            # Step C: Pulihkan kembali konfigurasi user ke template baru
            restore_user_config_dict(saved_cfg)

            if pull_res.returncode == 0:
                print("[✓] Repository berhasil diperbarui ke versi terbaru dari GitHub tanpa menghapus setting user!")
                return True
        else:
            print("[✓] Skrip STB-CUANIN sudah dalam versi terbaru dari GitHub.")
    except Exception as e:
        print(f"[!] Warning auto-update repo: {e}")
    return False

def start_autonomous_worker():
    """
    Autonomous Background Worker:
    1. Berjalan di background thread setiap 300 detik.
    2. Maintenance harian pukul 00:00: Cek update GitHub, pertahankan setting user, restart stack/daemon.
    3. Pengecekan sinkronisasi otonom dari Developer Web Portal (stbcuanin.89id.eu.org).
    """
    import threading

    def sync_loop():
        time.sleep(30)
        last_sync_key = ""
        last_midnight_date = ""
        while True:
            try:
                now_hm = time.strftime("%H:%M")
                today_date = time.strftime("%Y-%m-%d")

                # 1. Maintenance Harian Pukul 00:00
                if now_hm == "00:00" and last_midnight_date != today_date:
                    last_midnight_date = today_date
                    print("\n" + "=" * 60)
                    print(f"[*] [00:00] Memulai maintenance harian STB-CUANIN ({today_date})...")
                    print("=" * 60)
                    updated = auto_update_repo()
                    if updated:
                        print("[*] Update terbaru diterapkan. Merestart daemon STB-CUANIN...")
                        time.sleep(2)
                        os.execv(sys.executable, [sys.executable] + sys.argv)
                    else:
                        print("[*] Merestart container stack untuk penyegaran memori harian...")
                        run_compose_command("restart")
                        print("[✓] Restart harian selesai. Menunggu hari berikutnya.\n")
                    time.sleep(65)
                    continue

                # 2. Check Git Update di interval berkala
                if auto_update_repo():
                    print("[*] Pembaruan skrip terdeteksi di background. Merestart daemon...")
                    time.sleep(2)
                    os.execv(sys.executable, [sys.executable] + sys.argv)

                # 3. Check Remote Developer Web Portal
                dev_vault = load_dev_vault()
                active_list = get_fleet_active_services(dev_vault)
                creds = resolve_credentials()
                
                # Fingerprint state
                sync_key = f"{','.join(sorted(active_list))}|" + ",".join(
                    f"{k}:{creds[k].get('mode')}" for k in sorted(creds.keys()) if k != "_active_services"
                )

                if last_sync_key and sync_key != last_sync_key:
                    print(f"[*] Perubahan otonom dari Developer Web Portal terdeteksi ({len(active_list)} layanan aktif)! Memperbarui stack container...")
                    run_compose_command("up")
                last_sync_key = sync_key
            except Exception as e:
                pass
            time.sleep(300)

    t = threading.Thread(target=sync_loop, daemon=True, name="AutonomousFleetWorker")
    t.start()

def main():
    print("=" * 60)
    print("           STB-CUANIN NODE ENGINE & DASHBOARD")
    print("=" * 60)

    # 1. Autonomous Pre-Flight Git Update
    if auto_update_repo():
        print("[*] Merestart skrip dengan kode versi terbaru...")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    # 2. Start Autonomous Fleet Worker
    start_autonomous_worker()

    hostname = get_hostname()
    ip = get_host_ip()
    print(f"[*] Hostname : {hostname}")
    print(f"[*] IP Node  : {ip}")
    print(f"[*] Port Web : {PORT}")
    print(f"[*] Arch     : {get_architecture()}")
    
    print("[*] Mengompilasi konfigurasi dan menaikkan container...")
    ok, out = run_compose_command("up")
    if ok:
        print("[✓] Node stack siap dan berjalan!")
    else:
        print(f"[!] Warning: docker compose up output: {out}")

    server = ThreadingHTTPServer(("0.0.0.0", PORT), DashboardHandler)
    print(f"\n[✓] Dashboard aktif pada: http://{ip}:{PORT}")
    print("Tekan Ctrl+C untuk berhenti.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Mematikan server dashboard...")
        server.server_close()

if __name__ == "__main__":
    main()
