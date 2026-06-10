# -*- coding: utf-8 -*-
"""김수동(매제) 차용 + 부분 상환 확인"""
import os, sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv(r"D:\Claw\workspace\analysis\all_v2.csv", dtype=str).fillna("")
def n(s):
    s = str(s).replace(",","").strip()
    if s in ("","-","None","nan"): return 0
    try: return int(float(s))
    except: return 0
df["출"] = df.apply(lambda r: max(n(r["출금"]), n(r["출"])), axis=1)
df["입"] = df.apply(lambda r: max(n(r["입금"]), n(r["입"])), axis=1)
df["dt"] = pd.to_datetime(df["dt"], errors="coerce")
df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

# === 김수동 전체 거래 (시점 제한 없이) ===
print("="*100)
print("【김수동(매제) 관련 모든 거래 — 전체 기간】")
print("="*100)
ksd = df[df["거래내용"].str.contains("김수동",na=False) | df["상대계좌예금주명"].str.contains("김수동",na=False)].copy().sort_values("dt")
print(f"\n총 {len(ksd)}건")
print(f"기간: {ksd['dt'].min() if len(ksd)>0 else 'N/A'} ~ {ksd['dt'].max() if len(ksd)>0 else 'N/A'}")

in_t = ksd[ksd["입"]>0]["입"].sum()
out_t = ksd[ksd["출"]>0]["출"].sum()
print(f"\n입금(차용): {len(ksd[ksd['입']>0])}건 / {in_t:,}원")
print(f"출금(상환): {len(ksd[ksd['출']>0])}건 / {out_t:,}원")
print(f"미상환 잔액: {in_t - out_t:,}원")

print(f"\n=== 전체 거래 내역 ===")
for _, r in ksd.iterrows():
    sign = "+차용" if r["입"]>0 else "-상환"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# 가장 최근의 1,500만원 상환을 확인
print("\n" + "="*100)
print("【최근 1,500만원 상환 거래 확인 — 모든 1,500만원 출금】")
print("="*100)
out_1500 = df[(df["출"]>=14_000_000) & (df["출"]<=16_000_000)].sort_values("dt", ascending=False)
print(f"\n1,500만원 ± 100만원 범위 출금 (최근순):")
for _, r in out_1500.head(20).iterrows():
    is_ksd = "김수동" in str(r["상대계좌예금주명"]) or "김수동" in str(r["거래내용"])
    marker = " ⭐김수동" if is_ksd else ""
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}{marker}")
