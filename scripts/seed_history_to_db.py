#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Seed 200-day historical data from 01 MarketOverview2 krx_cache.json & adv_dec_history.json
into krx_market_cache.db.
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

def seed():
    base_dir = Path(__file__).resolve().parent.parent
    db_path = base_dir / "data" / "krx_market_cache.db"
    if not db_path.exists():
        print(f"Error: {db_path} does not exist!")
        return

    json_path = base_dir.parent / "01 MarketOverview2" / "krx_cache.json"
    adr_path = base_dir.parent / "01 MarketOverview2" / "data" / "adv_dec_history.json"

    if not json_path.exists():
        print(f"Error: {json_path} does not exist!")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        krx_cache = json.load(f)

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Seed KOSPI (1001) PER / PBR
    per_hist = krx_cache.get("per", {}).get("history", [])
    pbr_hist = krx_cache.get("pbr", {}).get("history", [])

    per_map = {h["date"][:10].replace("-", ""): float(h["value"]) for h in per_hist if "date" in h and "value" in h}
    pbr_map = {h["date"][:10].replace("-", ""): float(h["value"]) for h in pbr_hist if "date" in h and "value" in h}

    all_dates = sorted(set(per_map.keys()) | set(pbr_map.keys()))
    inserted_fund = 0
    for d in all_dates:
        per_v = per_map.get(d, 0.0)
        pbr_v = pbr_map.get(d, 0.0)

        # check if already exists
        cur.execute("SELECT per, pbr FROM index_fundamentals WHERE date = ? AND ticker = '1001'", (d,))
        existing = cur.fetchone()
        if existing:
            # update only if existing has 0.0
            if (existing[0] == 0.0 and per_v > 0) or (existing[1] == 0.0 and pbr_v > 0):
                cur.execute("""
                    UPDATE index_fundamentals 
                    SET per = CASE WHEN per = 0 THEN ? ELSE per END,
                        pbr = CASE WHEN pbr = 0 THEN ? ELSE pbr END
                    WHERE date = ? AND ticker = '1001'
                """, (per_v, pbr_v, d))
        else:
            cur.execute("""
                INSERT INTO index_fundamentals
                (date, ticker, name, close, change, rate, per, fwd_per, pbr, div_yield, updated_at)
                VALUES (?, '1001', '코스피', 0.0, 0.0, 0.0, ?, 0.0, ?, 0.0, ?)
            """, (d, per_v, pbr_v, now_str))
            inserted_fund += 1

    # 2. Seed VKOSPI
    vk_hist = krx_cache.get("vkospi", {}).get("history", [])
    inserted_vk = 0
    for h in vk_hist:
        d = h["date"][:10].replace("-", "")
        val = float(h["value"])
        cur.execute("SELECT close FROM index_fundamentals WHERE date = ? AND ticker = 'VKOSPI'", (d,))
        existing = cur.fetchone()
        if not existing:
            cur.execute("""
                INSERT INTO index_fundamentals
                (date, ticker, name, close, change, rate, per, fwd_per, pbr, div_yield, updated_at)
                VALUES (?, 'VKOSPI', '코스피 200 변동성지수', ?, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ?)
            """, (d, val, now_str))
            inserted_vk += 1

    # 3. Seed market_adr
    inserted_adr = 0
    if adr_path.exists():
        with open(adr_path, "r", encoding="utf-8") as f:
            adr_hist = json.load(f)
        for h in adr_hist:
            d = h["date"].replace("-", "")
            adv = int(h.get("adv", 0))
            dec = int(h.get("dec", 0))
            adr_ratio = round((adv / dec) * 100, 2) if dec > 0 else 0.0
            cur.execute("SELECT advances, declines FROM market_adr WHERE date = ? AND market = 'KOSPI'", (d,))
            existing = cur.fetchone()
            if not existing:
                cur.execute("""
                    INSERT INTO market_adr
                    (date, market, advances, declines, unchanged, upper_limit, lower_limit, total_stocks, adr_ratio, updated_at)
                    VALUES (?, 'KOSPI', ?, ?, 0, 0, 0, ?, ?, ?)
                """, (d, adv, dec, adv + dec, adr_ratio, now_str))
                inserted_adr += 1

    conn.commit()
    conn.close()

    print(f"Seeding completed:")
    print(f"  - KOSPI PER/PBR new dates inserted: {inserted_fund}")
    print(f"  - VKOSPI new dates inserted: {inserted_vk}")
    print(f"  - KOSPI ADR new dates inserted: {inserted_adr}")

if __name__ == "__main__":
    seed()
