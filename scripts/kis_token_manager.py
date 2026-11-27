"""
KIS OpenAPI Central Token Manager (한투 OpenAPI 1일 1회 자동 발급 및 공용 관리자)
- 한투(KIS)의 '1일 1회 발급 원칙'을 엄격히 준수합니다.
- 매일 03:00 KST에 크론(Cron) 또는 스케줄러로 호출되며, 발급 후 20시간 이내에는 중복 발급을 원천 차단합니다.
- 발급된 토큰은 공용 파일(kis_token.json)에 원자적으로 저장되어 모든 앱이 공유합니다.
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    import urllib.request as _urllib_req
    import urllib.error as _urllib_err

# Timezone KST helper
def get_kst_now():
    # 9 hours ahead of UTC
    return datetime.fromtimestamp(time.time())

def get_default_paths():
    if os.name == 'nt':
        base_dir = Path(r"D:\AI Investing")
        token_file = base_dir / "00 API Key" / "kis_token.json"
        env_files = [
            base_dir / "00 API Key" / ".env",
            base_dir / "01 MarketOverview2" / ".env",
            base_dir / "06 MarketWatch" / ".env",
            base_dir / "99 InvestingwithAI" / ".env",
        ]
        log_file = base_dir / "00 Bookmarks" / "scripts" / "kis_token_manager.log"
    else:
        base_dir = Path("/home/ubuntu/apps")
        token_file = base_dir / "kis_token.json"
        env_files = [
            base_dir / ".env",
            base_dir / "01_MarketOverview2" / ".env",
            Path("/home/ubuntu/MarketWatch/.env"),
        ]
        log_file = base_dir / "scripts" / "kis_token_manager.log"
    return token_file, env_files, log_file


def load_credentials(env_files):
    app_key = os.getenv("KIS_APP_KEY", "").strip()
    app_secret = os.getenv("KIS_APP_SECRET", "").strip()

    if app_key and app_secret:
        return app_key, app_secret

    for ef in env_files:
        if ef.exists():
            try:
                with open(ef, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("KIS_APP_KEY="):
                            app_key = line.split("=", 1)[1].strip()
                        elif line.startswith("KIS_APP_SECRET="):
                            app_secret = line.split("=", 1)[1].strip()
                if app_key and app_secret:
                    return app_key, app_secret
            except Exception:
                pass

    return app_key, app_secret


def issue_token(app_key: str, app_secret: str):
    url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    data = resp.json()
    
    if resp.status_code == 200 and "access_token" in data:
        now_ts = time.time()
        expires_in = data.get("expires_in", 86400)
        expires_at = now_ts + expires_in
        
        token_data = {
            "access_token": data["access_token"],
            "token_type": data.get("token_type", "Bearer"),
            "expires_in": expires_in,
            "issued_at": now_ts,
            "expires_at": expires_at,
            "issued_at_kst": datetime.fromtimestamp(now_ts).strftime("%Y-%m-%d %H:%M:%S"),
            "expires_at_kst": datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M:%S")
        }
        return token_data, None
    else:
        err_msg = f"HTTP {resp.status_code}: {data.get('error_description', data.get('msg1', 'Unknown error'))}"
        return None, err_msg


def manage_token(force: bool = False):
    token_file, env_files, log_file = get_default_paths()
    now_ts = time.time()
    now_str = datetime.fromtimestamp(now_ts).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Existing token validation
    if token_file.exists():
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            
            issued_at = cached.get("issued_at", 0)
            expires_at = cached.get("expires_at", 0)
            access_token = cached.get("access_token", "")
            
            # Guard: If token was issued less than 20 hours ago, or has > 4 hours left
            hours_since_issue = (now_ts - issued_at) / 3600.0
            hours_until_expire = (expires_at - now_ts) / 3600.0

            if access_token and not force:
                # If issued less than 20 hours ago AND still valid
                if hours_since_issue < 20.0 and hours_until_expire > 1.0:
                    msg = (
                        f"[{now_str}] [SKIP] Existing token is still valid. "
                        f"Issued: {cached.get('issued_at_kst', 'N/A')} ({hours_since_issue:.1f}h ago), "
                        f"Expires: {cached.get('expires_at_kst', 'N/A')} (in {hours_until_expire:.1f}h). "
                        f"Skipping issuance to strictly honor KIS 1-per-day policy."
                    )
                    print(msg)
                    return True
        except Exception as e:
            print(f"[{now_str}] [WARN] Cache reading error: {e}")

    # 2. Need new token
    print(f"[{now_str}] [REQUEST] Requesting 1-day access token from KIS OpenAPI (force={force})...")
    app_key, app_secret = load_credentials(env_files)
    if not app_key or not app_secret:
        print(f"[{now_str}] [ERROR] KIS_APP_KEY or KIS_APP_SECRET not found in env files!")
        return False

    token_data, err = issue_token(app_key, app_secret)
    if not token_data:
        print(f"[{now_str}] [FAIL] KIS token issuance failed: {err}")
        return False

    # 3. Save atomically
    token_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = token_file.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2, ensure_ascii=False)
    
    os.replace(tmp_file, token_file)
    try:
        os.chmod(token_file, 0o644)
    except Exception:
        pass

    success_msg = (
        f"[{now_str}] [SUCCESS] Successfully issued and saved new KIS access token!\n"
        f"         File: {token_file}\n"
        f"         Issued at:  {token_data['issued_at_kst']}\n"
        f"         Expires at: {token_data['expires_at_kst']}"
    )
    print(success_msg)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KIS OpenAPI Daily 1-time Token Manager")
    parser.add_argument("--force", action="store_true", help="Force new token issuance even if current token is valid")
    args = parser.parse_args()

    success = manage_token(force=args.force)
    sys.exit(0 if success else 1)
