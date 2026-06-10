# -*- coding: utf-8 -*-
"""이지영 송금 추적 (1.7억 정황)"""
import os, sys
import pandas as pd
from datetime import timedelta
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

# === 이지영 전체 거래 ===
print("="*100)
print("【이지영 관련 모든 거래】")
print("="*100)
mask = (df["거래내용"].str.contains("이지영",na=False) | 
        df["상대계좌예금주명"].str.contains("이지영",na=False))
ljy = df[mask].copy().sort_values("dt")
print(f"\n총 {len(ljy)}건")
total_out = ljy[ljy["출"]>0]["출"].sum()
total_in = ljy[ljy["입"]>0]["입"].sum()
print(f"출금(이지영에게): {ljy[ljy['출']>0].shape[0]}건 / 총 {total_out:,}원")
print(f"입금(이지영으로부터): {ljy[ljy['입']>0].shape[0]}건 / 총 {total_in:,}원")
print()
for _, r in ljy.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}] 메모:{r.get('송금메시지','')}")

# === 1.7억 정황 ===
print("\n" + "="*100)
print("【1.7억 관련 큰 송금 검색 (모든 거래에서)】")
print("="*100)
# 1.5억 ~ 2억 출금
big_out = df[(df["출"]>=150_000_000) & (df["출"]<=200_000_000)].sort_values("dt")
print(f"\n1.5억~2억 출금 거래 총 {len(big_out)}건:")
for _, r in big_out.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# 1.7억 정확히 일치
print(f"\n1.7억 정확 일치 거래:")
exact = df[(df["출"]==170_000_000) | (df["입"]==170_000_000)]
for _, r in exact.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}")

# 합계로 1.7억 = 100M + 70M, 50M*3 + 20M 등 가능한 조합 출금
print(f"\n1.7억 = 분할 송금 가능성 검색 (이지영 또는 다른 인물)")
# 모든 큰 출금에서 인물별 합계
big_out_all = df[df["출"]>=10_000_000].copy()
grp = big_out_all.groupby("상대계좌예금주명").agg(
    건수=("출","count"),
    합계=("출","sum"),
    최초=("dt","min"),
    최종=("dt","max")
).sort_values("합계", ascending=False).head(30)
print(f"\n수취인별 출금 누적 (1천만원 이상 거래, 큰순):")
for name, row in grp.iterrows():
    if name and name.strip():
        print(f"  {name:30s}  {int(row['건수']):>3}회  합 {int(row['합계']):>15,}  {row['최초'].strftime('%Y-%m-%d')} ~ {row['최종'].strftime('%Y-%m-%d')}")
