"""
KIS Token Synchronizer for Local PC (오라클 서버 -> 로컬 PC 토큰 동기화 도구)
- 오라클 서버에서 매일 03:00에 발급/갱신된 공용 kis_token.json을 로컬 PC(00 API Key)로 가져옵니다.
- KIS API 서버로의 중복 발급 요청을 원천적으로 0건으로 유지합니다.
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
KEY_FILE = ROOT_DIR / "00 API Key" / "ssh-key-2026-10-24.key"
LOCAL_TOKEN_FILE = ROOT_DIR / "00 API Key" / "kis_token.json"
HOST_IP = "168.110.38.90"
USER = "ubuntu"
REMOTE_TOKEN_FILE = "/home/ubuntu/apps/kis_token.json"

def sync_from_oracle():
    print("=" * 65)
    print("  KIS OpenAPI Token Synchronization (Oracle Server -> Local PC)")
    print("=" * 65)
    
    if not KEY_FILE.exists():
        print(f"[ERROR] SSH key not found at {KEY_FILE}")
        return False

    now_ts = time.time()
    now_str = datetime.fromtimestamp(now_ts).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Download token from Oracle server
    print(f"[{now_str}] Downloading latest token from {USER}@{HOST_IP}:{REMOTE_TOKEN_FILE}...")
    
    LOCAL_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_local = LOCAL_TOKEN_FILE.with_suffix(".tmp")

    scp_cmd = [
        "scp", "-i", str(KEY_FILE),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=8",
        f"{USER}@{HOST_IP}:{REMOTE_TOKEN_FILE}",
        str(tmp_local)
    ]

    res = subprocess.run(scp_cmd, capture_output=True, text=True)
    if res.returncode == 0 and tmp_local.exists():
        try:
            with open(tmp_local, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            
            if "access_token" in token_data and "expires_at" in token_data:
                os.replace(tmp_local, LOCAL_TOKEN_FILE)
                exp_kst = token_data.get("expires_at_kst", "N/A")
                iss_kst = token_data.get("issued_at_kst", "N/A")
                rem_hours = (token_data["expires_at"] - now_ts) / 3600.0
                
                print(f"[OK] Token synced successfully to: {LOCAL_TOKEN_FILE}")
                print(f"     - Issued at:  {iss_kst}")
                print(f"     - Expires at: {exp_kst} (Remaining: {rem_hours:.1f} hours)")
                print(f"     - Token head: {token_data['access_token'][:18]}...")
                return True
            else:
                print("[ERROR] Remote token file has invalid format!")
        except Exception as e:
            print(f"[ERROR] Failed to parse downloaded token: {e}")
        finally:
            if tmp_local.exists():
                tmp_local.unlink()
    else:
        print(f"[WARN] Failed to fetch from Oracle server: {res.stderr.strip()}")
        # Check if local token is still valid
        if LOCAL_TOKEN_FILE.exists():
            try:
                with open(LOCAL_TOKEN_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("expires_at", 0) > now_ts:
                    rem_h = (cached["expires_at"] - now_ts) / 3600.0
                    print(f"[INFO] Using existing local token (still valid for {rem_h:.1f} hours).")
                    return True
            except Exception:
                pass

        # Fallback to local issuance if server is down and local is missing/expired
        print("[FALLBACK] Attempting local token issuance...")
        manager_script = ROOT_DIR / "00 Bookmarks" / "scripts" / "kis_token_manager.py"
        res_mgr = subprocess.run([sys.executable, str(manager_script)])
        return res_mgr.returncode == 0

    return False


if __name__ == "__main__":
    success = sync_from_oracle()
    sys.exit(0 if success else 1)
