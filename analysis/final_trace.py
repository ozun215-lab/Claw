# -*- coding: utf-8 -*-
"""김광규 송금 자금 출처 정밀 추적 (농협 + IBK 통합)"""
import os, sys
import pandas as pd
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')

WORK = r"D:\Claw\workspace\analysis"
df = pd.read_csv(os.path.join(WORK, "all_accounts_combined.csv"), dtype=str).fillna("")

# Normalize numeric
def n(s):
    s = str(s).replace(",", "").strip()
    if s in ("","-","None","nan"): return 0
    try: return int(float(s))
    except: return 0
df["출"] = df["출금"].apply(n) + df["출금_num"].apply(n)
df["입"] = df["입금"].apply(n) + df["입금_num"].apply(n)
df["출"] = df.apply(lambda r: max(n(r["출금"]), n(r["출금_num"])), axis=1)
df["입"] = df.apply(lambda r: max(n(r["입금"]), n(r["입금_num"])), axis=1)
df["dt"] = pd.to_datetime(df["거래일시_dt"], errors="coerce")
df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

# 김광규 송금건 (IBK)
kim = df[df["상대계좌예금주명"].str.contains("김광규", na=False) | df["거래내용"].str.contains("김광규", na=False)].copy()
kim = kim[kim["출"] > 0].sort_values("dt").reset_index(drop=True)
print("="*100)
print(f"【김광규 송금 {len(kim)}건】 총 {kim['출'].sum():,}원")
for i, r in kim.iterrows():
    print(f"  [{i+1}] {r['dt']:%Y-%m-%d %H:%M}  {r['출']:>13,}원  ({r['거래내용']})  [{r['_은행']} {r['_계좌번호']}]")

# === 송금 직전 7일간 모든 계좌 100만원 이상 입금 ===
print("\n" + "="*100)
print("【송금 직전 7일간 100만원 이상 입금 (전체 계좌 통합)】")
print("="*100)
for i, srow in kim.iterrows():
    sdt = srow["dt"]
    samt = srow["출"]
    print(f"\n▶ [{i+1}] {sdt:%Y-%m-%d %H:%M} 김광규 {samt:,}원 송금")
    w_start = sdt - timedelta(days=7)
    win = df[(df["dt"] >= w_start) & (df["dt"] <= sdt) & (df["입"] >= 1_000_000)].sort_values("dt")
    total_in = win["입"].sum()
    print(f"   직전 7일 입금 {len(win)}건 / 총 {total_in:,}원")
    for _, r in win.iterrows():
        print(f"     {r['dt']:%m-%d %H:%M}  [{r['_은행']:5}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}")

# === 농협 → IBK 044 송금 매칭 (자금 흐름 연결) ===
print("\n" + "="*100)
print("【2022-02-22~23 송금일 농협의 큰 출금 (IBK로 이체된 자금)】")
print("="*100)
nh = df[(df["_은행"]=="농협") & (df["dt"] >= "2022-02-18") & (df["dt"] <= "2022-02-24") & (df["출"]>=1_000_000)].sort_values("dt")
for _, r in nh.iterrows():
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} [{r['거래구분']}]  잔액 {n(r['잔액']):>13,}")

# 농협 직전 큰 입금 (자금 모음)
print("\n" + "="*100)
print("【농협 계좌 2022년 1~2월 큰 입금 (1천만원 이상)】")
print("="*100)
nh_in = df[(df["_은행"]=="농협") & (df["dt"] >= "2022-01-01") & (df["dt"] <= "2022-02-24") & (df["입"]>=10_000_000)].sort_values("dt")
for _, r in nh_in.iterrows():
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ({r['거래내용']}) ← from {r['거래구분']} [{r['거래']}]")

# 농협 전체 큰 자금 흐름 (5천만 이상 입금)
print("\n" + "="*100)
print("【농협 계좌 전체기간(2019~2022) 5천만원 이상 입금 — 큰 자금 유입】")
print("="*100)
big_in = df[(df["_은행"]=="농협") & (df["입"]>=50_000_000)].sort_values("dt")
for _, r in big_in.iterrows():
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ({r['거래내용']}) [{r['거래구분']}] {r['거래']}")

# IBK 5천만 이상 입금
print("\n" + "="*100)
print("【IBK 전체기간 5천만원 이상 입금 — 큰 자금 유입】")
print("="*100)
big_in2 = df[(df["_은행"]=="IBK기업") & (df["입"]>=50_000_000)].sort_values("dt")
for _, r in big_in2.iterrows():
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  [{r['_계좌번호']}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 자금원 인물별 집계 (큰 외부 송금자) ===
print("\n" + "="*100)
print("【주요 외부 자금원 — 1천만원 이상 입금 인물별 집계 (IBK)】")
print("="*100)
ibk_in = df[(df["_은행"]=="IBK기업") & (df["입"]>=10_000_000)].copy()
agg = ibk_in.groupby("상대계좌예금주명").agg(건수=("입","count"), 총입금=("입","sum")).sort_values("총입금", ascending=False)
print(agg.to_string())

print("\n=== 농협 큰 입금 (거래내용=상대인) 인물별 ===")
nh_in_all = df[(df["_은행"]=="농협") & (df["입"]>=10_000_000)].copy()
agg2 = nh_in_all.groupby("거래내용").agg(건수=("입","count"), 총입금=("입","sum")).sort_values("총입금", ascending=False)
print(agg2.to_string())
