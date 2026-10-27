#!/usr/bin/env python3
"""
STB-CUANIN Core Security & Verification Module
Zero-dependency PBKDF2-HMAC-SHA256 authenticated stream cipher.
Zero plaintext credentials - strictly loads keys from runtime environment or secure local vault.
"""

import os
import sys
import json
import base64
import hashlib
import hmac

def get_master_key() -> str:
    """
    Retrieves the vault master key from environment or isolated local .env file.
    Never hardcoded in public source control.
    """
    key = os.environ.get("CUANIN_VAULT_KEY", "").strip()
    if key:
        return key
        
    # Check .env in parent or current directory
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    env_paths = [
        os.path.join(cur_dir, ".env"),
        os.path.join(cur_dir, ".dev_vault_key"),
        "/opt/stb-cuanin/.env"
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("CUANIN_VAULT_KEY="):
                            k = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if k:
                                return k
            except Exception:
                pass
    return ""

def encrypt_dict(data_dict: dict, master_key: str = None) -> str:
    """
    Encrypts a dictionary into a base64 string with PBKDF2-derived keys,
    counter-mode SHA256 keystream, and HMAC-SHA256 authentication tag.
    """
    if not master_key:
        master_key = get_master_key()
    if not master_key:
        raise ValueError("Master key tidak tersedia. Harap tentukan CUANIN_VAULT_KEY.")

    raw = json.dumps(data_dict).encode("utf-8")
    salt = os.urandom(16)
    
    # Derive 64 bytes: 32 bytes encryption key + 32 bytes MAC key
    derived = hashlib.pbkdf2_hmac("sha256", master_key.encode("utf-8"), salt, 100000, dklen=64)
    enc_key = derived[:32]
    mac_key = derived[32:]
    
    # Counter-mode SHA-256 keystream
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(raw):
        counter_bytes = counter.to_bytes(4, "big")
        keystream.extend(hashlib.sha256(enc_key + counter_bytes).digest())
        counter += 1
        
    ciphertext = bytes(a ^ b for a, b in zip(raw, keystream[:len(raw)]))
    tag = hmac.new(mac_key, salt + ciphertext, hashlib.sha256).digest()
    
    # Format: [16B salt] + [32B tag] + [ciphertext]
    blob = salt + tag + ciphertext
    return base64.b64encode(blob).decode("ascii")

def decrypt_dict(enc_b64: str, master_key: str = None) -> dict:
    """
    Decrypts and validates integrity of an encrypted base64 payload.
    Raises ValueError on tampering or invalid key.
    """
    if not master_key:
        master_key = get_master_key()
    if not master_key:
        raise ValueError("Master key tidak tersedia. Harap tentukan CUANIN_VAULT_KEY.")

    try:
        blob = base64.b64decode(enc_b64.strip())
        if len(blob) < 48:
            raise ValueError("Invalid payload size")
            
        salt = blob[:16]
        tag = blob[16:48]
        ciphertext = blob[48:]
        
        derived = hashlib.pbkdf2_hmac("sha256", master_key.encode("utf-8"), salt, 100000, dklen=64)
        enc_key = derived[:32]
        mac_key = derived[32:]
        
        expected_tag = hmac.new(mac_key, salt + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("Integrity check failed: payload was tampered with or key is invalid")
            
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(ciphertext):
            counter_bytes = counter.to_bytes(4, "big")
            keystream.extend(hashlib.sha256(enc_key + counter_bytes).digest())
            counter += 1
            
        raw = bytes(a ^ b for a, b in zip(ciphertext, keystream[:len(ciphertext)]))
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")

if __name__ == "__main__":
    # Self-test with ephemeral key
    test_key = "ephemeral_test_key_123456"
    sample = {"service": "pawns", "token": "example_token_123"}
    enc = encrypt_dict(sample, test_key)
    dec = decrypt_dict(enc, test_key)
    assert dec == sample, "Self-test failed"
    print("Self test passed successfully!")
