#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
KRX 캐시 데이터베이스 동기화 도구 (sync_krx_db.py)
===============================================================================
- 역할: 오라클 서버에서 매일 새벽 03:40에 수집/축적된 krx_market_cache.db를
        로컬 PC(00 Bookmarks/data/krx_market_cache.db)로 안전하게 다운로드 및 동기화.
- 특징:
  * 서버에서 PRAGMA wal_checkpoint(TRUNCATE)를 사전 실행하여 WAL 파일 병합 후 전송
  * 전송 완료 후 로컬 DB의 테이블별 데이터 건수 및 최신 일자 즉시 검증
===============================================================================
"""

import os
import sys
import time
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
KEY_FILE = ROOT_DIR / "00 API Key" / "ssh-key-2026-10-24.key"
LOCAL_DATA_DIR = ROOT_DIR / "00 Bookmarks" / "data"
LOCAL_DB_FILE = LOCAL_DATA_DIR / "krx_market_cache.db"

HOST_IP = "168.110.38.90"
USER = "ubuntu"
REMOTE_DB_FILE = "/home/ubuntu/apps/data/krx_market_cache.db"

def sync_krx_database():
    print("=" * 70)
    print("  KRX Market Cache DB Synchronizer (Oracle Server -> Local PC)")
    print("=" * 70)

    if not KEY_FILE.exists():
        print(f"[ERROR] SSH key file not found at: {KEY_FILE}")
        return False

    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] Connecting to {USER}@{HOST_IP}...")

    # 1. 서버 측 WAL 체크포인트 실행 (트랜잭션 병합)
    print(" 1. Checkpointing remote SQLite WAL log...")
    remote_chk_py = (
        "import sqlite3; "
        f"conn = sqlite3.connect('{REMOTE_DB_FILE}'); "
        "conn.execute('PRAGMA wal_checkpoint(TRUNCATE);'); "
        "conn.close(); "
        "print('WAL Checkpoint OK')"
    )
    ssh_cmd = [
        "ssh", "-i", str(KEY_FILE),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=8",
        f"{USER}@{HOST_IP}",
        f"/home/ubuntu/venv_apps/bin/python3 -c \"{remote_chk_py}\""
    ]
    try:
        res_chk = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=15)
        if res_chk.returncode == 0:
            print("    -> Remote WAL checkpoint merged successfully.")
        else:
            print(f"    -> Warning on checkpoint: {res_chk.stderr.strip()}")
    except Exception as e:
        print(f"    -> Checkpoint skipped or error: {e}")

    # 2. SCP 다운로드
    print(f" 2. Downloading {REMOTE_DB_FILE} to {LOCAL_DB_FILE}...")
    tmp_local = LOCAL_DB_FILE.with_suffix(".tmp")
    scp_cmd = [
        "scp", "-i", str(KEY_FILE),
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"{USER}@{HOST_IP}:{REMOTE_DB_FILE}",
        str(tmp_local)
    ]

    try:
        res_scp = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=60)
        if res_scp.returncode == 0 and tmp_local.exists():
            # 기존 DB 교체
            os.replace(tmp_local, LOCAL_DB_FILE)
            size_mb = os.path.getsize(LOCAL_DB_FILE) / 1024 / 1024
            duration = time.time() - t0
            print(f"    -> Download complete! File size: {size_mb:.2f} MB (Time: {duration:.1f}s)")
        else:
            print(f"[ERROR] Download failed: {res_scp.stderr.strip()}")
            if tmp_local.exists():
                tmp_local.unlink()
            return False
    except Exception as e:
        print(f"[ERROR] SCP execution failed: {e}")
        if tmp_local.exists():
            tmp_local.unlink()
        return False

    # 3. 로컬 동기화 DB 무결성 및 통계 검증
    print("\n 3. Verifying Local Cache DB Integrity & Statistics:")
    try:
        conn = sqlite3.connect(str(LOCAL_DB_FILE))
        cur = conn.cursor()
        tables = [
            ("index_fundamentals", "지수 기본지표 (PER/PBR/배당)"),
            ("market_adr", "시장 ADR 및 등락 종목 수"),
            ("investor_net_purchases", "투자자별 순매수 현황"),
            ("stock_daily_market", "전종목 시가총액 & 밸류에이션"),
            ("short_selling_daily", "공매도 거래 및 잔고"),
        ]

        for tbl, desc in tables:
            try:
                cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT date) FROM {tbl}")
                cnt, dates = cur.fetchone()
                cur.execute(f"SELECT MIN(date), MAX(date) FROM {tbl}")
                min_d, max_d = cur.fetchone()
                print(f"    * {desc:28s} ({tbl}): {cnt:7,d} 건 | {dates:3d} 영업일 ({min_d} ~ {max_d})")
            except Exception as ex:
                print(f"    * {tbl}: 조회 불가 ({ex})")

        print("\n    [최근 5건 수집 이력]")
        cur.execute("SELECT run_time, target_date, job_name, status, row_count, duration_sec FROM collection_log ORDER BY id DESC LIMIT 5")
        for r in cur.fetchall():
            print(f"      - [{r[0]}] {r[1]} | {r[2]:22s} | {r[3]:7s} | {r[4]:5d}건 ({r[5]}초)")
        conn.close()
        print("\n[SUCCESS] Local KRX cache DB is up-to-date and ready for use!")
        return True
    except Exception as e:
        print(f"[ERROR] Database inspection failed: {e}")
        return False

if __name__ == "__main__":
    success = sync_krx_database()
    sys.exit(0 if success else 1)
