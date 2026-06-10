# -*- coding: utf-8 -*-
"""2019-02-23 전세자금 송금 1.93억 정밀 추적"""
import os, sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv(r"D:\Claw\workspace\analysis\all_accounts_combined.csv", dtype=str).fillna("")
def n(s):
    s = str(s).replace(",","").strip()
    if s in ("","-","None","nan"): return 0
    try: return int(float(s))
    except: return 0
df["출"] = df.apply(lambda r: max(n(r["출금"]), n(r["출금_num"])), axis=1)
df["입"] = df.apply(lambda r: max(n(r["입금"]), n(r["입금_num"])), axis=1)
df["dt"] = pd.to_datetime(df["거래일시_dt"], errors="coerce")
df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

# 2019-02-22~24 모든 거래
print("="*100)
print("【2019-02-22 ~ 2019-02-24 모든 거래】")
print("="*100)
window = df[(df["dt"] >= "2019-02-20") & (df["dt"] <= "2019-02-28")].sort_values("dt")
for _, r in window.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# 전세자금 검색
print("\n" + "="*100)
print("【'전세자금' 키워드 모든 거래】")
print("="*100)
mask = pd.Series([False]*len(df))
for c in df.columns:
    if df[c].dtype == object:
        m = df[c].astype(str).str.contains("전세자금", na=False, regex=False)
        mask = mask | m
hits = df[mask].sort_values("dt")
for _, r in hits.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 1.7억 분할 송금 가능성 — 같은 계좌/같은 날 큰 출금 합계 ===
print("\n" + "="*100)
print("【같은 날 출금 합계 1.5억~2억 (분할 송금 가능성)】")
print("="*100)
df["date"] = df["dt"].dt.date
daily = df[df["출"]>=10_000_000].groupby(["date","_계좌번호"])["출"].sum().reset_index()
candidates = daily[(daily["출"]>=150_000_000) & (daily["출"]<=200_000_000)].sort_values("date")
for _, r in candidates.iterrows():
    print(f"\n  ▶ {r['date']} [{r['_계좌번호']}] 일일 출금 합계: {int(r['출']):,}원")
    # 해당 날짜의 출금 내역 출력
    day_out = df[(df["date"]==r["date"]) & (df["_계좌번호"]==r["_계좌번호"]) & (df["출"]>=1_000_000)].sort_values("dt")
    for _, dr in day_out.iterrows():
        print(f"     {dr['dt']:%H:%M}  -{dr['출']:>13,}  ({dr['거래내용']}) → {dr['상대계좌예금주명']} / {dr['상대은행']} {dr['상대계좌번호']}")
