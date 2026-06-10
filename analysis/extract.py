# -*- coding: utf-8 -*-
"""
거래내역 HTML(.xls) 파싱하여 통합 CSV 생성 + 김광규 입금 추적
"""
import os, sys, re
from bs4 import BeautifulSoup
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

WORK_DIR = r"D:\Claw\workspace\analysis"
files = [
    "거래내역조회_입출식_출력용_20260609-21-012.xls",
    "거래내역조회_입출식_출력용_20260609-21-022.xls",
    "거래내역조회_입출식_출력용_20260609-21-044.xls",
    "거래내역조회_입출식_출력용_20260609-22-022.xls",
    "거래내역조회_입출식_출력용_20260609-22-044.xls",
]

def parse_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    # Remove the <style> block so pd.read_html doesn't choke
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    soup = BeautifulSoup(text, "lxml")

    # Account info (table.type1) usually has metadata
    meta = {}
    tables = soup.find_all("table")

    # First pass: scan for account info – look at all <td> inside type1
    for tbl in tables:
        cls = tbl.get("class") or []
        if "type1" in cls:
            ths = [th.get_text(strip=True) for th in tbl.find_all("th")]
            tds = [td.get_text(strip=True) for td in tbl.find_all("td")]
            for h, d in zip(ths, tds):
                meta[h] = d
            break

    # Transactions: table.type2
    trans_rows = []
    headers = None
    for tbl in tables:
        cls = tbl.get("class") or []
        if "type2" in cls:
            rows = tbl.find_all("tr")
            for tr in rows:
                cells = tr.find_all(["th", "td"])
                vals = [c.get_text(strip=True) for c in cells]
                if not vals:
                    continue
                if headers is None and any("거래일시" in v for v in vals):
                    headers = vals
                    continue
                if headers and len(vals) == len(headers):
                    trans_rows.append(vals)
            break

    df = pd.DataFrame(trans_rows, columns=headers) if headers else pd.DataFrame()
    return meta, df

all_dfs = []
for fname in files:
    path = os.path.join(WORK_DIR, fname)
    meta, df = parse_file(path)
    print("="*100)
    print("FILE:", fname)
    print("META:", meta)
    print("Rows:", len(df))
    if not df.empty:
        print("Columns:", list(df.columns))
        print(df.head(5).to_string())
        df["_파일"] = fname
        df["_계좌번호"] = meta.get("계좌번호", "")
        df["_예금주명"] = meta.get("예금주명", "")
        df["_조회기간"] = meta.get("조회시작일자", "") + "~" + meta.get("조회종료일자", "")
        all_dfs.append(df)
    print()

if all_dfs:
    combined = pd.concat(all_dfs, ignore_index=True)
    out_csv = os.path.join(WORK_DIR, "all_transactions.csv")
    combined.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print("Saved:", out_csv, "Total rows:", len(combined))

    # ===== 김광규 검색 =====
    print("\n" + "="*100)
    print("[김광규 입금 건 검색]")
    print("="*100)
    # Search all text columns for "김광규"
    text_cols = [c for c in combined.columns if combined[c].dtype == object]
    mask = pd.Series([False]*len(combined))
    for c in text_cols:
        mask = mask | combined[c].astype(str).str.contains("김광규", na=False)
    kim_rows = combined[mask].copy()
    print("총", len(kim_rows), "건 발견")
    if not kim_rows.empty:
        # Show with key columns
        cols_to_show = [c for c in ["_계좌번호","거래일시","출금","입금","거래후잔액","거래내용","송금메시지","상대계좌번호","상대예금주명","거래구분"] if c in kim_rows.columns]
        print(kim_rows[cols_to_show].to_string())
        kim_rows.to_csv(os.path.join(WORK_DIR, "kim_gwangkyu.csv"), index=False, encoding="utf-8-sig")
