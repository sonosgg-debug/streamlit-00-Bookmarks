"""
Oracle Server Synchronization Tool for AI Investing Apps
Synchronizes local code changes to the Oracle Cloud Server (168.110.38.90) and restarts the apps.
Usage:
    python scripts/sync_to_oracle.py [app_name_or_number]
    python scripts/sync_to_oracle.py 21
    python scripts/sync_to_oracle.py "21 CupWithHandle2"
    python scripts/sync_to_oracle.py all
"""

import os
import sys
import tarfile
import subprocess
import tempfile
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BOOKMARKS_DIR = ROOT_DIR / "00 Bookmarks"
KEY_FILE = ROOT_DIR / "00 API Key" / "ssh-key-2026-10-24.key"
HOST_IP = "168.110.38.90"
USER = "ubuntu"
REMOTE_BASE = "/home/ubuntu/apps"

EXCLUDE_NAMES = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", ".claude", ".agents", ".vscode"}

# All supported applications
APP_MAPPING = [
    ("00 Bookmarks", "00_Bookmarks", 8500),
    ("01 MarketOverview2", "01_MarketOverview2", 8501),
    ("02 MarketBriefing", "02_MarketBriefing", 8502),
    ("03 MarketBalance", "03_MarketBalance", 8503),
    ("04 AfterMarketRally", "04_AfterMarketRally", 8504),
    ("05 MonthlyReview", "05_MonthlyReview", 8505),
    ("06 MarketWatch", "06_MarketWatch", 8506),
    ("07 BeforeSunrise", "07_BeforeSunrise", 8507),
    ("11 MagicS-RIM2", "11_MagicS-RIM2", 8511),
    ("21 CupWithHandle2", "21_CupWithHandle2", 8521),
    ("22 JustDrawtheLine", "22_JustDrawtheLine", 8522),
    ("25 MarkMinerviniMTT2", "25_MarkMinerviniMTT2", 8525),
    ("27 MajorsNetBuy", "27_MajorsNetBuy", 8527),
    ("28 TradingStrategy", "28_TradingStrategy", 8528),
    ("29 MultiIndicatorEnsemble", "29_MultiIndicatorEnsemble", 8529),
    ("31 WinnersChart", "31_WinnersChart", 8531),
    ("32 FundamentalAnalysis", "32_FundamentalAnalysis", 8532),
    ("33 NetBuyerChart", "33_NetBuyerChart", 8533),
    ("35 ShortSellingChart", "35_ShortSellingChart", 8535),
    ("36 TechnicalAnalysis", "36_TechnicalAnalysis", 8536),
    ("37 PERcomparison", "37_PERcomparison", 8537),
    ("38 PreferredStock", "38_PreferredStock", 8538),
    ("39 DividendStock", "39_DividendStock", 8539),
    ("40 ETFscreener", "40_ETFscreener", 8540),
    ("41 SKHYadrP", "41_SKHYadrP", 8541),
    ("45 RealEstate", "45_RealEstate", 8545),
]


def tar_filter(tarinfo):
    parts = Path(tarinfo.name).parts
    if any(x in EXCLUDE_NAMES for x in parts):
        return None
    if tarinfo.issym():
        return None
    return tarinfo


def run_ssh(cmd_str):
    ssh_cmd = [
        "ssh", "-i", str(KEY_FILE),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"{USER}@{HOST_IP}",
        cmd_str
    ]
    return subprocess.run(ssh_cmd, text=True, capture_output=True)


def run_scp(local_file, remote_dest):
    scp_cmd = [
        "scp", "-i", str(KEY_FILE),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        str(local_file),
        f"{USER}@{HOST_IP}:{remote_dest}"
    ]
    return subprocess.run(scp_cmd, text=True, capture_output=True)


def sync_single_app(src_folder, dst_folder, port):
    local_path = ROOT_DIR / src_folder
    if not local_path.exists():
        print(f"[ERROR] Local directory {local_path} does not exist!")
        return False

    print(f"\n[SYNC] Packaging '{src_folder}' -> '{dst_folder}' (Port {port})...")
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_tar = Path(tmp.name)

    try:
        with tarfile.open(tmp_tar, "w:gz") as tar:
            tar.add(local_path, arcname=dst_folder, filter=tar_filter)

        sz_kb = tmp_tar.stat().st_size / 1024
        print(f"       Archive size: {sz_kb:.1f} KB. Uploading to Oracle server...")

        # Upload
        res = run_scp(tmp_tar, f"{REMOTE_BASE}/tmp_sync.tar.gz")
        if res.returncode != 0:
            print(f"[FAIL] Upload failed: {res.stderr}")
            return False

        # Extract & Restart
        remote_cmds = (
            f"tar -xzf {REMOTE_BASE}/tmp_sync.tar.gz -C {REMOTE_BASE}/ && "
            f"rm -f {REMOTE_BASE}/tmp_sync.tar.gz && "
            f"python3 {REMOTE_BASE}/manager.py restart {dst_folder}"
        )
        if dst_folder == "06_MarketWatch":
            remote_cmds += (
                f" && cp -f {REMOTE_BASE}/06_MarketWatch/*.py /home/ubuntu/MarketWatch/ 2>/dev/null || true && "
                f"sudo systemctl restart marketwatch.service"
            )
        res_ssh = run_ssh(remote_cmds)
        if res_ssh.returncode == 0:
            print(f"[OK]   Successfully synced & restarted on Port {port}!")
            if res_ssh.stdout.strip():
                print(res_ssh.stdout.strip())
            return True
        else:
            print(f"[FAIL] Remote extract/restart error: {res_ssh.stderr}")
            return False

    finally:
        if tmp_tar.exists():
            tmp_tar.unlink()


def main():
    if not KEY_FILE.exists():
        print(f"[ERROR] SSH key not found at {KEY_FILE}")
        sys.exit(1)

    target_arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""

    if not target_arg:
        print("=" * 60)
        print("  Oracle Server Synchronization Tool (168.110.38.90)")
        print("=" * 60)
        print("Usage:")
        print("  python scripts/sync_to_oracle.py <app_name_or_number>")
        print("  python scripts/sync_to_oracle.py all")
        print("\nExamples:")
        print("  python scripts/sync_to_oracle.py 06")
        print("  python scripts/sync_to_oracle.py 21")
        print("  python scripts/sync_to_oracle.py 39")
        print("  python scripts/sync_to_oracle.py '00 Bookmarks'")
        print("=" * 60)
        sys.exit(0)

    if target_arg.lower() == "all":
        print(f"=== Syncing ALL {len(APP_MAPPING)} applications to Oracle Server ===")
        success_count = 0
        for src, dst, port in APP_MAPPING:
            if sync_single_app(src, dst, port):
                success_count += 1
        print(f"\n[SUMMARY] {success_count}/{len(APP_MAPPING)} applications synced successfully!")
    else:
        # Match target
        matched = []
        for src, dst, port in APP_MAPPING:
            if target_arg.lower() in src.lower() or target_arg.lower() == src.split()[0] or target_arg == str(port):
                matched.append((src, dst, port))

        if not matched:
            print(f"[ERROR] Could not find any app matching '{target_arg}'.")
            print("Available apps:")
            for src, _, port in APP_MAPPING:
                print(f"  - {src} (Port {port})")
            sys.exit(1)

        for src, dst, port in matched:
            sync_single_app(src, dst, port)


if __name__ == "__main__":
    main()
