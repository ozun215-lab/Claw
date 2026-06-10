# -*- coding: utf-8 -*-
"""디버그: 김광규 검색 + 자금 추적 강화"""
import os, sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv(r"D:\Claw\workspace\analysis\all_accounts_combined.csv", dtype=str).fillna("")
print(f"총 {len(df)}건")
print("컬럼:", list(df.columns))

# Search all text columns for 김광규
mask = pd.Series([False]*len(df))
hit_cols = set()
for c in df.columns:
    m = df[c].astype(str).str.contains("김광규", na=False, regex=False)
    if m.any():
        hit_cols.add(c)
        print(f"  '김광규' found in col '{c}': {m.sum()}건")
    mask = mask | m
print(f"\n김광규 총: {mask.sum()}건")
kim = df[mask].copy()
if len(kim) > 0:
    for _, r in kim.iterrows():
        print(f"  [{r['_은행']} {r['_계좌번호']}] {r['거래일시']}  출금 {r['출금_num']:>13}  입금 {r['입금_num']:>13}  ({r['거래내용']})")

# Search agg "박상호" too (big 2021 inflow)
print("\n=== 박상호 검색 ===")
mask2 = pd.Series([False]*len(df))
for c in df.columns:
    m = df[c].astype(str).str.contains("박상호", na=False, regex=False)
    mask2 = mask2 | m
psh = df[mask2].copy()
print(f"박상호 총 {len(psh)}건")
for _, r in psh.iterrows():
    print(f"  [{r['_은행']} {r['_계좌번호']}] {r['거래일시']}  출금 {r['출금_num']:>13}  입금 {r['입금_num']:>13}  ({r['거래내용']}) ← {r.get('상대계좌예금주명','')}")

# 농협 데이터의 컬럼 보기
print("\n=== 농협 row 샘플 ===")
nh_sample = df[df["_은행"] == "농협"].head(3)
for _, r in nh_sample.iterrows():
    print(dict(r))
