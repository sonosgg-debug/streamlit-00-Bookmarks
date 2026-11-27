#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
KRX 일일 일괄 수집 & 캐시 DB 관리자 (krx_daily_collector.py)
===============================================================================
- 역할: KRX 고유 데이터(지수 PER/PBR, ADR, 전종목 시총/밸류에이션, 투자자별 매매, 공매도)를
        1일 1회 안전하게 일괄 수집하여 SQLite DB(krx_market_cache.db)에 저장.
- 실행 주기: 매일 새벽 03:40 KST (crontab 자동 실행)
  * 이유 1: KRX 지수 기본지표(PER/PBR/배당)가 야간 23:00경 최종 반영 완료됨.
  * 이유 2: 심야 KRX 시스템 백업/점검 시간(00:00 ~ 02:30)을 완전히 통과한 안정적 시간대.
  * 이유 3: 한투 토큰 발급(03:00) 후 실행되며, 사용자 앱 이용(05:00~) 이전에 수집 완료.
- 안전 장치:
  * 요청 간격 2.5초 지연(Throttling)으로 KRX 웹 방화벽 차단 원천 방지
  * CD010(비밀번호 연기) 및 CD011(중복 세션) 자동 처리
  * 테이블별 예외 격리(하나가 실패해도 다른 데이터 수집 지속)
  * SQLite WAL 모드 적용으로 다중 Streamlit 앱의 동시 읽기 지원
===============================================================================
"""

import os
import sys
import time
import argparse
import sqlite3
import datetime
from pathlib import Path

# -----------------------------------------------------------------------------
# 1. 환경 및 인증 정보 로드 (pykrx import 전에 수행)
# -----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
IS_SERVER = "/home/ubuntu" in str(SCRIPT_DIR) or os.path.exists("/home/ubuntu/apps")

if IS_SERVER:
    BASE_DIR = Path("/home/ubuntu/apps")
    DATA_DIR = BASE_DIR / "data"
    DB_PATH = DATA_DIR / "krx_market_cache.db"
    LOG_FILE = SCRIPT_DIR / "krx_collector.log"
    ENV_PATH = BASE_DIR / ".env"
else:
    BASE_DIR = Path(r"D:\AI Investing\00 Bookmarks")
    DATA_DIR = BASE_DIR / "data"
    DB_PATH = DATA_DIR / "krx_market_cache.db"
    LOG_FILE = SCRIPT_DIR / "krx_collector.log"
    ENV_PATH = Path(r"D:\AI Investing\01 MarketOverview2\.env")
    ALT_KEY_PATH = Path(r"D:\AI Investing\00 API Key\KRX ID&PW.txt")

DATA_DIR.mkdir(parents=True, exist_ok=True)

# KRX 자격 증명 주입
def load_credentials():
    if os.environ.get("KRX_ID") and os.environ.get("KRX_PW"):
        return

    # 1) .env 파일 시도
    if 'ENV_PATH' in globals() and ENV_PATH.exists():
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("KRX_ID="):
                        os.environ["KRX_ID"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif line.startswith("KRX_PW="):
                        os.environ["KRX_PW"] = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception as e:
            print(f"[Auth] Error loading .env: {e}")

    # 2) 로컬 텍스트 파일 시도
    if (not os.environ.get("KRX_ID") or not os.environ.get("KRX_PW")) and not IS_SERVER:
        if 'ALT_KEY_PATH' in globals() and ALT_KEY_PATH.exists():
            try:
                with open(ALT_KEY_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ID :") or line.startswith("ID:"):
                            os.environ["KRX_ID"] = line.split(":", 1)[1].strip()
                        elif line.startswith("PW :") or line.startswith("PW:"):
                            os.environ["KRX_PW"] = line.split(":", 1)[1].strip()
            except Exception as e:
                print(f"[Auth] Error loading alt key file: {e}")

load_credentials()

# PyKRX 인증 패치 (CD010 비밀번호 변경 연기 및 세션 안정화)
def patch_pykrx():
    try:
        import pykrx.website.comm.auth as krx_auth
        import requests

        orig_login = getattr(krx_auth, "login_krx", None)
        if not orig_login:
            return

        def robust_login_krx(login_id: str, login_pw: str, session=None) -> bool:
            if session is None:
                session = requests.Session()

            krx_auth.warmup_krx_session(session)
            payload = {
                "mbrNm": "",
                "telNo": "",
                "di": "",
                "certType": "",
                "mbrId": login_id,
                "pw": login_pw,
            }
            headers = {"User-Agent": krx_auth.USER_AGENT, "Referer": krx_auth.LOGIN_PAGE}

            try:
                resp = session.post(krx_auth.LOGIN_URL, data=payload, headers=headers, timeout=15)
                data = resp.json()
            except Exception as e:
                print(f"[KRX Auth] Login request failed: {e}")
                return False

            err_code = data.get("_error_code", "")
            err_msg = data.get("_error_message", "")

            # CD010: 비밀번호 변경 연기
            if err_code == "CD010":
                try:
                    postpone_url = "https://data.krx.co.kr/contents/MDC/COMS/client/postponePasswordChange.cmd"
                    session.post(postpone_url, headers=headers, timeout=15)
                    payload["skipDup"] = "Y"
                    resp = session.post(krx_auth.LOGIN_URL, data=payload, headers=headers, timeout=15)
                    data = resp.json()
                    err_code = data.get("_error_code", "")
                except Exception:
                    pass

            # CD011: 중복 로그인 방어 (skipDup)
            if err_code == "CD011":
                payload["skipDup"] = "Y"
                try:
                    resp = session.post(krx_auth.LOGIN_URL, data=payload, headers=headers, timeout=15)
                    data = resp.json()
                    err_code = data.get("_error_code", "")
                except Exception:
                    pass

            return err_code == "CD001"

        krx_auth.login_krx = robust_login_krx
    except Exception:
        pass

patch_pykrx()

# 이제 pykrx 임포트
import pykrx.stock as stock

# -----------------------------------------------------------------------------
# 2. 휴장일 및 거래일 헬퍼
# -----------------------------------------------------------------------------
KRX_HOLIDAYS = {
    # 2024
    '20240101', '20240209', '20240212', '20240301', '20240410', '20240501', '20240506',
    '20240515', '20240606', '20240815', '20240916', '20240917', '20240918', '20241001',
    '20241003', '20241009', '20241225', '20241231',
    # 2025
    '20250101', '20250128', '20250129', '20250130', '20250303', '20250501', '20250505',
    '20250506', '20250606', '20250815', '20251003', '20251006', '20251007', '20251008',
    '20251009', '20251225', '20251231',
    # 2026
    '20260101', '20260216', '20260217', '20260218', '20260302', '20260501', '20260505',
    '20260525', '20260603', '20260606', '20260817', '20260924', '20260925', '20261005',
    '20261009', '20261225', '20261231',
    # 2027
    '20270101', '20270208', '20270209', '20270210', '20270301', '20270503', '20270505',
    '20270513', '20270607', '20270816', '20270914', '20270915', '20270916', '20271004',
    '20271011', '20271225', '20271231'
}

def get_now_kst():
    """현재 한국 표준시 (KST) 반환"""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return now_utc + datetime.timedelta(hours=9)

def is_business_day(date_str):
    """주말 및 법정 공휴일 여부 체크 (YYYYMMDD)"""
    clean_date = date_str.replace("-", "")
    if clean_date in KRX_HOLIDAYS:
        return False
    try:
        dt = datetime.datetime.strptime(clean_date, "%Y%m%d")
        return dt.weekday() < 5
    except Exception:
        return False

def get_recent_trading_days(count=5, ref_date=None):
    """
    기준일 이전의 최근 거래일 목록을 내림차순(최신순)으로 반환합니다.
    새벽 03:40 실행 시 기준일은 오늘이므로, 어제(D-1)부터 과거로 거슬러 올라갑니다.
    """
    if ref_date is None:
        ref_dt = get_now_kst().date()
    elif isinstance(ref_date, str):
        ref_dt = datetime.datetime.strptime(ref_date.replace("-", ""), "%Y%m%d").date()
    else:
        ref_dt = ref_date

    trading_days = []
    curr = ref_dt - datetime.timedelta(days=1)
    while len(trading_days) < count:
        d_str = curr.strftime("%Y%m%d")
        if is_business_day(d_str):
            trading_days.append(d_str)
        curr -= datetime.timedelta(days=1)
    return trading_days

# -----------------------------------------------------------------------------
# 3. SQLite 데이터베이스 초기화 (WAL 모드 & 스키마 생성)
# -----------------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=10000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db_connection()
    with conn:
        # 1) 지수 기본지표 (PER, PBR, 배당수익률, 종가)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS index_fundamentals (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT NOT NULL,
            close REAL,
            change REAL,
            rate REAL,
            per REAL,
            fwd_per REAL,
            pbr REAL,
            div_yield REAL,
            updated_at TEXT,
            PRIMARY KEY (date, ticker)
        );
        """)

        # 2) 시장 ADR / 등락 종목 수
        conn.execute("""
        CREATE TABLE IF NOT EXISTS market_adr (
            date TEXT NOT NULL,
            market TEXT NOT NULL,
            advances INTEGER,
            declines INTEGER,
            unchanged INTEGER,
            upper_limit INTEGER,
            lower_limit INTEGER,
            total_stocks INTEGER,
            adr_ratio REAL,
            updated_at TEXT,
            PRIMARY KEY (date, market)
        );
        """)

        # 3) 시장 전체 투자자별 순매수 대금/거래량
        conn.execute("""
        CREATE TABLE IF NOT EXISTS investor_net_purchases (
            date TEXT NOT NULL,
            market TEXT NOT NULL,
            investor TEXT NOT NULL,
            net_buy_amt REAL,
            buy_amt REAL,
            sell_amt REAL,
            updated_at TEXT,
            PRIMARY KEY (date, market, investor)
        );
        """)

        # 4) 전종목 시가총액 및 개별 밸류에이션
        conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_daily_market (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            market TEXT NOT NULL,
            close REAL,
            change REAL,
            rate REAL,
            market_cap REAL,
            shares REAL,
            trading_value REAL,
            trading_volume REAL,
            per REAL,
            pbr REAL,
            div_yield REAL,
            eps REAL,
            bps REAL,
            dps REAL,
            updated_at TEXT,
            PRIMARY KEY (date, ticker)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_cap ON stock_daily_market(date, market_cap DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stock_mkt ON stock_daily_market(date, market);")

        # 5) 공매도 거래 및 잔고
        conn.execute("""
        CREATE TABLE IF NOT EXISTS short_selling_daily (
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            market TEXT NOT NULL,
            short_vol REAL,
            short_val REAL,
            short_ratio REAL,
            balance_shares REAL,
            balance_amt REAL,
            updated_at TEXT,
            PRIMARY KEY (date, ticker)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_short_date ON short_selling_daily(date, market);")

        # 6) 수집 이력 로그
        conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_time TEXT NOT NULL,
            target_date TEXT NOT NULL,
            job_name TEXT NOT NULL,
            status TEXT NOT NULL,
            row_count INTEGER DEFAULT 0,
            duration_sec REAL DEFAULT 0,
            message TEXT
        );
        """)
    conn.close()

def log_job(target_date, job_name, status, row_count, duration, message=""):
    try:
        conn = get_db_connection()
        now_str = get_now_kst().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.execute("""
            INSERT INTO collection_log (run_time, target_date, job_name, status, row_count, duration_sec, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now_str, target_date, job_name, status, row_count, round(duration, 2), message))
        conn.close()
    except Exception as e:
        print(f"[Log Error] {e}")

# -----------------------------------------------------------------------------
# 4. 개별 데이터 수집 함수 (안전 지연 2.5초 & 예외 격리)
# -----------------------------------------------------------------------------
DELAY_SEC = 2.5

def collect_index_fundamentals(target_date, force=False):
    """
    KOSPI(1001), KOSDAQ(2001), KOSPI200(1028) 지수 기본지표 수집
    """
    job = "index_fundamentals"
    t0 = time.time()
    conn = get_db_connection()

    # 이미 수집되어 있고 유효한지(PER > 0) 확인
    if not force:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM index_fundamentals WHERE date = ? AND per > 0", (target_date,))
        if cur.fetchone()[0] >= 2:
            conn.close()
            return True, "Already exists with valid PER"

    indices = [
        ("1001", "코스피"),
        ("2001", "코스닥"),
        ("1028", "코스피 200"),
    ]

    now_str = get_now_kst().strftime("%Y-%m-%d %H:%M:%S")
    collected_rows = 0

    try:
        for code, name in indices:
            time.sleep(DELAY_SEC)
            try:
                df = stock.get_index_fundamental(target_date, target_date, code)
                if df is not None and not df.empty:
                    row = df.iloc[-1]
                    close_p = float(row.get("종가", 0.0))
                    rate = float(row.get("등락률", 0.0))
                    per = float(row.get("PER", 0.0))
                    fwd_per = float(row.get("선행PER", 0.0)) if "선행PER" in row else 0.0
                    pbr = float(row.get("PBR", 0.0))
                    div_y = float(row.get("배당수익률", 0.0))

                    with conn:
                        conn.execute("""
                        INSERT OR REPLACE INTO index_fundamentals 
                        (date, ticker, name, close, change, rate, per, fwd_per, pbr, div_yield, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (target_date, code, name, close_p, 0.0, rate, per, fwd_per, pbr, div_y, now_str))
                    collected_rows += 1
            except Exception as e:
                print(f"[{job}] Error fetching {name}({code}): {e}")

        # VKOSPI (코스피 200 변동성지수) 수집
        time.sleep(DELAY_SEC)
        try:
            from pykrx.website.krx.krxio import KrxWebIo
            class VkMdc(KrxWebIo):
                @property
                def bld(self):
                    return 'dbms/MDC/STAT/standard/MDCSTAT01201'
            vk = VkMdc()
            res = vk.read(locale='ko_KR', indTpCd='1', idxIndCd='300', strtDd=target_date, endDd=target_date, share='1', money='1')
            if res and isinstance(res, dict) and res.get('output'):
                vk_rows = res['output']
                if len(vk_rows) > 0:
                    row = vk_rows[0]
                    close_p = float(str(row.get('CLSPRC_IDX', 0)).replace(',', ''))
                    rate = float(str(row.get('FLUC_RT', 0)).replace(',', ''))
                    with conn:
                        conn.execute("""
                        INSERT OR REPLACE INTO index_fundamentals
                        (date, ticker, name, close, change, rate, per, fwd_per, pbr, div_yield, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (target_date, "VKOSPI", "코스피 200 변동성지수", close_p, 0.0, rate, 0.0, 0.0, 0.0, 0.0, now_str))
                    collected_rows += 1
        except Exception as e:
            print(f"[{job}] VKOSPI query notice: {e}")

        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "SUCCESS" if collected_rows > 0 else "EMPTY", collected_rows, duration)
        return True, f"Collected {collected_rows} index records"
    except Exception as e:
        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "FAILED", collected_rows, duration, str(e))
        return False, str(e)


def collect_market_adr(target_date, force=False):
    """
    KOSPI / KOSDAQ 일일 등락 종목 수 (상승, 하락, 보합, 상한, 하한) 및 ADR 수집
    """
    job = "market_adr"
    t0 = time.time()
    conn = get_db_connection()

    if not force:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM market_adr WHERE date = ?", (target_date,))
        if cur.fetchone()[0] >= 2:
            conn.close()
            return True, "Already exists"

    now_str = get_now_kst().strftime("%Y-%m-%d %H:%M:%S")
    collected_rows = 0

    try:
        for market in ["KOSPI", "KOSDAQ"]:
            time.sleep(DELAY_SEC)
            try:
                df = stock.get_market_price_change_by_ticker(target_date, target_date, market=market)
                if df is not None and not df.empty:
                    adv = int((df["등락률"] > 0).sum())
                    dec = int((df["등락률"] < 0).sum())
                    unc = int((df["등락률"] == 0).sum())
                    up_lim = int((df["등락률"] >= 29.5).sum())
                    low_lim = int((df["등락률"] <= -29.5).sum())
                    total = len(df)
                    adr_ratio = round((adv / dec * 100.0), 2) if dec > 0 else 100.0

                    with conn:
                        conn.execute("""
                        INSERT OR REPLACE INTO market_adr
                        (date, market, advances, declines, unchanged, upper_limit, lower_limit, total_stocks, adr_ratio, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (target_date, market, adv, dec, unc, up_lim, low_lim, total, adr_ratio, now_str))
                    collected_rows += 1
            except Exception as e:
                print(f"[{job}] Error fetching {market}: {e}")

        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "SUCCESS" if collected_rows > 0 else "EMPTY", collected_rows, duration)
        return True, f"Collected {collected_rows} market ADR records"
    except Exception as e:
        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "FAILED", collected_rows, duration, str(e))
        return False, str(e)


def collect_investor_net_purchases(target_date, force=False):
    """
    시장 전체 투자자별 순매수 대금 (외국인, 기관합계, 개인, 연기금 등)
    """
    job = "investor_net_purchases"
    t0 = time.time()
    conn = get_db_connection()

    if not force:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM investor_net_purchases WHERE date = ?", (target_date,))
        if cur.fetchone()[0] >= 10:
            conn.close()
            return True, "Already exists"

    now_str = get_now_kst().strftime("%Y-%m-%d %H:%M:%S")
    collected_rows = 0

    try:
        for market in ["KOSPI", "KOSDAQ"]:
            time.sleep(DELAY_SEC)
            try:
                df = stock.get_market_trading_value_by_investor(target_date, target_date, market)
                if df is not None and not df.empty:
                    with conn:
                        for investor_name, row in df.iterrows():
                            buy_amt = float(row.get("매수", 0.0))
                            sell_amt = float(row.get("매도", 0.0))
                            net_amt = float(row.get("순매수", 0.0))

                            conn.execute("""
                            INSERT OR REPLACE INTO investor_net_purchases
                            (date, market, investor, net_buy_amt, buy_amt, sell_amt, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (target_date, market, str(investor_name), net_amt, buy_amt, sell_amt, now_str))
                            collected_rows += 1
            except Exception as e:
                print(f"[{job}] Error fetching {market}: {e}")

        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "SUCCESS" if collected_rows > 0 else "EMPTY", collected_rows, duration)
        return True, f"Collected {collected_rows} investor purchase records"
    except Exception as e:
        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "FAILED", collected_rows, duration, str(e))
        return False, str(e)


def collect_stock_daily_market(target_date, force=False):
    """
    전종목 시가총액, 거래대금, 상장주식수, PER, PBR, 배당수익률 수집
    (21, 22, 25, 27, 29, 32, 37, 38, 39, 40 앱 공통 기반 데이터)
    """
    job = "stock_daily_market"
    t0 = time.time()
    conn = get_db_connection()

    if not force:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM stock_daily_market WHERE date = ?", (target_date,))
        if cur.fetchone()[0] >= 1500:
            conn.close()
            return True, "Already exists with >=1500 stocks"

    now_str = get_now_kst().strftime("%Y-%m-%d %H:%M:%S")
    collected_rows = 0

    try:
        # 시장별로 분할 수집 (KOSPI, KOSDAQ)
        for market in ["KOSPI", "KOSDAQ"]:
            time.sleep(DELAY_SEC)
            print(f"[{job}] Fetching {market} market cap...")
            df_cap = stock.get_market_cap_by_ticker(target_date, market=market)

            time.sleep(DELAY_SEC)
            print(f"[{job}] Fetching {market} fundamentals...")
            df_fund = stock.get_market_fundamental_by_ticker(target_date, market=market)

            if df_cap is None or df_cap.empty:
                continue

            # 기본 정보 병합
            merged = df_cap.copy()
            if df_fund is not None and not df_fund.empty:
                merged = merged.join(df_fund, how="left")

            # 1회 조회로 종목명 맵핑 가져오기 (초고속 일괄 맵핑)
            ticker_names = {}
            try:
                df_names = stock.get_market_price_change_by_ticker(target_date, target_date, market=market)
                if df_names is not None and not df_names.empty and "종목명" in df_names.columns:
                    for t, name in df_names["종목명"].items():
                        ticker_names[str(t)] = str(name)
            except Exception as e:
                print(f"[{job}] Warning: bulk ticker names fetch failed: {e}")

            records = []
            for t, row in merged.iterrows():
                t_str = str(t)
                name = ticker_names.get(t_str)
                if not name:
                    try:
                        name = stock.get_market_ticker_name(t_str)
                    except Exception:
                        name = t_str

                close_p = float(row.get("종가", 0.0))
                mkt_cap = float(row.get("시가총액", 0.0))
                shares = float(row.get("상장주식수", 0.0))
                val = float(row.get("거래대금", 0.0))
                vol = float(row.get("거래량", 0.0))

                per = float(row.get("PER", 0.0)) if "PER" in row and not pd_isna(row.get("PER")) else 0.0
                pbr = float(row.get("PBR", 0.0)) if "PBR" in row and not pd_isna(row.get("PBR")) else 0.0
                div_y = float(row.get("DIV", 0.0)) if "DIV" in row and not pd_isna(row.get("DIV")) else 0.0
                eps = float(row.get("EPS", 0.0)) if "EPS" in row and not pd_isna(row.get("EPS")) else 0.0
                bps = float(row.get("BPS", 0.0)) if "BPS" in row and not pd_isna(row.get("BPS")) else 0.0
                dps = float(row.get("DPS", 0.0)) if "DPS" in row and not pd_isna(row.get("DPS")) else 0.0

                records.append((
                    target_date, str(t), name, market, close_p, 0.0, 0.0,
                    mkt_cap, shares, val, vol, per, pbr, div_y, eps, bps, dps, now_str
                ))

            with conn:
                conn.executemany("""
                INSERT OR REPLACE INTO stock_daily_market
                (date, ticker, name, market, close, change, rate, market_cap, shares, 
                 trading_value, trading_volume, per, pbr, div_yield, eps, bps, dps, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records)
            collected_rows += len(records)
            print(f"[{job}] Saved {len(records)} stocks for {market}")

        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "SUCCESS" if collected_rows > 0 else "EMPTY", collected_rows, duration)
        return True, f"Collected {collected_rows} stocks"
    except Exception as e:
        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "FAILED", collected_rows, duration, str(e))
        return False, str(e)


def collect_short_selling_daily(target_date, force=False):
    """
    공매도 거래량 및 2일 전 잔고 수집 (35 ShortSellingChart 지원)
    """
    job = "short_selling_daily"
    t0 = time.time()
    conn = get_db_connection()

    if not force:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM short_selling_daily WHERE date = ?", (target_date,))
        if cur.fetchone()[0] >= 500:
            conn.close()
            return True, "Already exists"

    now_str = get_now_kst().strftime("%Y-%m-%d %H:%M:%S")
    collected_rows = 0

    try:
        # 공매도 거래대금/거래량
        for market in ["KOSPI", "KOSDAQ"]:
            time.sleep(DELAY_SEC)
            try:
                df_vol = stock.get_shorting_volume_by_ticker(target_date, market)
                if df_vol is not None and not df_vol.empty:
                    records = []
                    for t, row in df_vol.iterrows():
                        short_vol = float(row.get("공매도", 0.0))
                        short_ratio = float(row.get("비중", 0.0))
                        records.append((target_date, str(t), market, short_vol, 0.0, short_ratio, 0.0, 0.0, now_str))

                    with conn:
                        conn.executemany("""
                        INSERT OR REPLACE INTO short_selling_daily
                        (date, ticker, market, short_vol, short_val, short_ratio, balance_shares, balance_amt, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, records)
                    collected_rows += len(records)
            except Exception as e:
                print(f"[{job}] Error fetching shorting volume {market}: {e}")

        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "SUCCESS" if collected_rows > 0 else "EMPTY", collected_rows, duration)
        return True, f"Collected {collected_rows} short selling records"
    except Exception as e:
        conn.close()
        duration = time.time() - t0
        log_job(target_date, job, "FAILED", collected_rows, duration, str(e))
        return False, str(e)


def pd_isna(val):
    if val is None:
        return True
    try:
        import math
        return math.isnan(float(val))
    except Exception:
        return False

# -----------------------------------------------------------------------------
# 5. 메인 일괄 수집 오케스트레이터 (2단계 분할 수집 지원)
# -----------------------------------------------------------------------------
def run_collection_by_mode(mode="all", target_date=None, force=False):
    """
    모드별 수집 오케스트레이터:
    - evening: 저녁 20:30 KST 실행
        * 대상일: 오늘(D) (평일 거래일인 경우)
        * 수집 데이터:
          1) market_adr (상승, 하락, 보합, 상한, 하한 종목 수)
          2) investor_net_purchases (외국인, 기관, 연기금 등 13개 주체 확정치)
          3) stock_daily_market (전종목 시가총액, 종가, 거래대금, 상장주식수, 개별 밸류에이션)
          4) short_selling_daily (전종목 공매도 거래량 및 비중)
        * (지수 PER/PBR은 23:00경 산출되므로 저녁엔 스킵)
    - dawn: 새벽 03:40 KST 실행
        * 대상일: 어제 이전 마감 거래일(D-1 이하)
        * 수집 데이터:
          1) index_fundamentals (코스피, 코스닥, 코스피200, VKOSPI: 최종 PER/PBR/배당)
          2) 누락 검사: 저녁 수집에서 누락된 테이블이 있다면 자동 보완 수집(Self-Healing)
    - all: 지정된 날짜의 전체 데이터 일괄 수집
    """
    init_database()
    now_kst = get_now_kst()
    today_str = now_kst.strftime("%Y%m%d")

    if target_date is not None:
        clean_date = target_date.replace("-", "")
    else:
        if mode == "evening":
            if is_business_day(today_str):
                clean_date = today_str
            else:
                print(f"[Evening Mode] Today ({today_str}) is a holiday/weekend. Skipping evening collection.")
                return {}
        elif mode == "dawn":
            clean_date = get_recent_trading_days(count=1)[0]
        else: # all / auto
            if now_kst.hour >= 16 and is_business_day(today_str):
                clean_date = today_str
            else:
                clean_date = get_recent_trading_days(count=1)[0]

    print(f"\n{'='*70}")
    print(f" KRX Market Cache Collector [Mode: {mode.upper()}]")
    print(f" - Target Date: {clean_date}")
    print(f" - Database: {DB_PATH}")
    print(f" - Server Mode: {IS_SERVER}")
    print(f" - Current Time (KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    summary = {}

    # 저녁 모드 (20:30): 시총, ADR, 투자자별 매매, 공매도 수집
    if mode in ["evening", "all"]:
        # 1. 시장 ADR
        print("▶ [1/4] Collecting Market ADR & Advances/Declines...")
        ok, msg = collect_market_adr(clean_date, force=force)
        summary["market_adr"] = msg
        print(f"   -> Result: {msg}")

        # 2. 투자자별 순매수 확정치
        print("\n▶ [2/4] Collecting Investor Net Purchases...")
        ok, msg = collect_investor_net_purchases(clean_date, force=force)
        summary["investor_net_purchases"] = msg
        print(f"   -> Result: {msg}")

        # 3. 전종목 시총 & 밸류에이션
        print("\n▶ [3/4] Collecting Stock Daily Market Cap & Valuation...")
        ok, msg = collect_stock_daily_market(clean_date, force=force)
        summary["stock_daily_market"] = msg
        print(f"   -> Result: {msg}")

        # 4. 공매도 거래량
        print("\n▶ [4/4] Collecting Short Selling Volume...")
        ok, msg = collect_short_selling_daily(clean_date, force=force)
        summary["short_selling_daily"] = msg
        print(f"   -> Result: {msg}")

    # 새벽 모드 (03:40): 지수 PER/PBR 최종치 + 저녁 데이터 누락 보완
    if mode in ["dawn", "all"]:
        # 1. 지수 기본지표 최종치 (야간 23:00 산출분)
        print("▶ [Dawn 1] Collecting Finalized Index Fundamentals (PER/PBR/DIV)...")
        ok, msg = collect_index_fundamentals(clean_date, force=force)
        summary["index_fundamentals"] = msg
        print(f"   -> Result: {msg}")

        # 2. 저녁 수집 데이터 누락 자동 보완 (Self-Healing)
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM market_adr WHERE date = ?", (clean_date,))
        if cur.fetchone()[0] == 0:
            print("\n▶ [Self-Healing] Backfilling missing Market ADR...")
            collect_market_adr(clean_date, force=True)

        cur.execute("SELECT COUNT(*) FROM investor_net_purchases WHERE date = ?", (clean_date,))
        if cur.fetchone()[0] == 0:
            print("\n▶ [Self-Healing] Backfilling missing Investor Net Purchases...")
            collect_investor_net_purchases(clean_date, force=True)

        cur.execute("SELECT COUNT(*) FROM stock_daily_market WHERE date = ?", (clean_date,))
        if cur.fetchone()[0] < 1500:
            print("\n▶ [Self-Healing] Backfilling missing Stock Daily Market...")
            collect_stock_daily_market(clean_date, force=True)

        cur.execute("SELECT COUNT(*) FROM short_selling_daily WHERE date = ?", (clean_date,))
        if cur.fetchone()[0] == 0:
            print("\n▶ [Self-Healing] Backfilling missing Short Selling...")
            collect_short_selling_daily(clean_date, force=True)
        conn.close()

    print(f"\n{'='*70}")
    print(f" [{mode.upper()} Mode] Collection Completed for Date: {clean_date}")
    print(f"{'='*70}\n")
    return summary


def run_daily_collection(target_date=None, force=False):
    """하위 호환용 래퍼: 전체 수집 실행"""
    return run_collection_by_mode(mode="all", target_date=target_date, force=force)


def run_multi_day_check(days=3, force=False):
    """최근 N개 거래일을 점검하여 누락된 날짜를 순차적으로 보완 수집"""
    init_database()
    trading_days = get_recent_trading_days(count=days)
    print(f"[Multi-Day Check] Target dates to verify: {trading_days}")

    for d in reversed(trading_days):  # 과거순으로 수집
        print(f"\n>>> Checking Date: {d} <<<")
        run_collection_by_mode(mode="all", target_date=d, force=force)
        time.sleep(3.0)


def show_status():
    """현재 SQLite DB 상태 및 최근 수집 로그 출력"""
    init_database()
    conn = get_db_connection()
    cur = conn.cursor()

    print("\n================== KRX Cache DB Status ==================")
    print(f"DB Location: {DB_PATH}")
    print(f"File Size: {round(os.path.getsize(DB_PATH) / 1024 / 1024, 2)} MB" if DB_PATH.exists() else "DB not found")

    tables = ["index_fundamentals", "market_adr", "investor_net_purchases", "stock_daily_market", "short_selling_daily"]
    for tbl in tables:
        try:
            cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT date) FROM {tbl}")
            cnt, dates = cur.fetchone()
            cur.execute(f"SELECT MIN(date), MAX(date) FROM {tbl}")
            min_d, max_d = cur.fetchone()
            print(f" - {tbl:24s}: {cnt:7,d} rows | {dates:3d} dates ({min_d} ~ {max_d})")
        except Exception as e:
            print(f" - {tbl:24s}: Error {e}")

    print("\n---------------- Recent Collection Logs ----------------")
    try:
        cur.execute("SELECT run_time, target_date, job_name, status, row_count, duration_sec FROM collection_log ORDER BY id DESC LIMIT 10")
        logs = cur.fetchall()
        for l in logs:
            print(f" [{l['run_time']}] Date:{l['target_date']} | {l['job_name']:22s} | {l['status']:7s} | {l['row_count']:5d} rows | {l['duration_sec']}s")
    except Exception as e:
        print(f" Log read error: {e}")
    print("=========================================================\n")
    conn.close()

# -----------------------------------------------------------------------------
# 6. 진입점 CLI
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="KRX Daily Batch Collector and SQLite Cache DB")
    parser.add_argument("--mode", choices=["all", "evening", "dawn"], default="all",
                        help="Collection mode: 'evening' (20:30), 'dawn' (03:40), or 'all' (default)")
    parser.add_argument("--date", type=str, help="Target date to collect (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=1, help="Check and backfill last N business days (default: 1)")
    parser.add_argument("--force", action="store_true", help="Force recollected data even if already exists")
    parser.add_argument("--status", action="store_true", help="Display DB status and recent logs")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.date:
        run_collection_by_mode(mode=args.mode, target_date=args.date, force=args.force)
    elif args.days > 1:
        run_multi_day_check(days=args.days, force=args.force)
    else:
        run_collection_by_mode(mode=args.mode, force=args.force)

if __name__ == "__main__":
    main()
