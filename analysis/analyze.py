# -*- coding: utf-8 -*-
"""
김광규 입금 자금 출처 추적 분석
거래내역 .xls 파일 (실제로는 HTML) 파싱
"""
import os
import sys
import io
import pandas as pd
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

WORK_DIR = r"D:\Claw\workspace\analysis"

files = [
    "거래내역조회_입출식_출력용_20260609-21-012.xls",
    "거래내역조회_입출식_출력용_20260609-21-022.xls",
    "거래내역조회_입출식_출력용_20260609-21-044.xls",
    "거래내역조회_입출식_출력용_20260609-22-022.xls",
    "거래내역조회_입출식_출력용_20260609-22-044.xls",
]

def detect_encoding(raw_bytes):
    for enc in ("utf-8", "euc-kr", "cp949", "utf-16"):
        try:
            raw_bytes.decode(enc)
            return enc
        except Exception:
            pass
    return "utf-8"

for fname in files:
    path = os.path.join(WORK_DIR, fname)
    print("=" * 100)
    print("FILE:", fname)
    print("SIZE:", os.path.getsize(path), "bytes")
    with open(path, "rb") as f:
        raw = f.read()
    enc = detect_encoding(raw)
    print("DETECTED ENCODING:", enc)
    text = raw.decode(enc, errors="replace")
    # Print first 600 chars to inspect
    print("--- HTML head preview ---")
    print(text[:600])
    print("--- end preview ---")

    # Parse with BeautifulSoup
    soup = BeautifulSoup(text, "lxml")

    # Find any contextual info before the table (account holder name, account number)
    body_text_lines = []
    for el in soup.find_all(text=True):
        s = str(el).strip()
        if s:
            body_text_lines.append(s)

    # Print metadata (first ~30 non-empty lines outside table)
    print("\n--- top text lines ---")
    for line in body_text_lines[:40]:
        print(line)

    # Extract tables
    try:
        tables = pd.read_html(io.StringIO(text))
    except Exception as e:
        print("read_html error:", e)
        tables = []
    print(f"\nFound {len(tables)} tables")
    for i, t in enumerate(tables):
        print(f"-- table {i}: shape {t.shape} --")
        print(t.head(3).to_string())
    print()
