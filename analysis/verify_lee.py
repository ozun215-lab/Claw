# -*- coding: utf-8 -*-
"""이정훈 정체 검증 + 32-00049 대출 추적"""
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

# === 이정훈 모든 거래 ===
print("="*100)
print("【이정훈 관련 모든 거래】")
print("="*100)
lee_mask = (df["거래내용"].str.contains("이정훈",na=False) | 
            df["상대계좌예금주명"].str.contains("이정훈",na=False))
lee = df[lee_mask].copy().sort_values("dt")
print(f"\n이정훈 거래 총 {len(lee)}건")
for _, r in lee.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}] 메모:{r.get('송금메시지','')}")

# === 32-00049 대출 추적 ===
print("\n" + "="*100)
print("【32-00049 대출 계좌 추적】")
print("="*100)
m49 = df[df["상대계좌번호"].astype(str).str.contains("3200049|32.00049", na=False, regex=True) | 
        df["거래내용"].astype(str).str.contains("32-00049|3200049", na=False, regex=True)].copy().sort_values("dt")
print(f"\n32-00049 관련 거래 총 {len(m49)}건")
for _, r in m49.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 32-00033 대출 추적 ===
print("\n" + "="*100)
print("【32-00033 대출 계좌 추적】")
print("="*100)
m33 = df[df["상대계좌번호"].astype(str).str.contains("3200033|32.00033", na=False, regex=True) | 
        df["거래내용"].astype(str).str.contains("32-00033|3200033", na=False, regex=True)].copy().sort_values("dt")
print(f"\n32-00033 관련 거래 총 {len(m33)}건")
for _, r in m33.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")

# === 대출 추정: 큰 금액 입금이 즉시 다른 곳으로 송금되는 패턴 (대출금 실행) ===
print("\n" + "="*100)
print("【대출 실행 패턴: 큰 입금 → 같은 날/다음날 즉시 송금】")
print("="*100)
# 5천만 이상 입금 후 1일 내 거의 같은 금액 송금
big_in = df[df["입"]>=50_000_000].copy().sort_values("dt")
for _, ir in big_in.iterrows():
    amt = ir["입"]
    # 같은 계좌에서 1일 내 동액(±5%) 출금
    after = df[(df["_계좌번호"]==ir["_계좌번호"]) & 
               (df["dt"] >= ir["dt"]) & 
               (df["dt"] <= ir["dt"]+pd.Timedelta(days=2)) & 
               (df["출"]>0)].copy()
    matched = after[(after["출"] >= amt*0.5) & (after["출"] <= amt*1.5)]
    if len(matched)>0:
        for _, mr in matched.head(2).iterrows():
            hours_gap = (mr["dt"] - ir["dt"]).total_seconds() / 3600
            print(f"  +{amt:>12,} ({ir['dt']:%Y-%m-%d %H:%M} {ir['거래내용']:15s} from {ir['상대계좌예금주명']:15s})")
            print(f"     → {hours_gap:>6.1f}h후  -{mr['출']:>12,} ({mr['dt']:%Y-%m-%d %H:%M} → {mr['상대계좌예금주명']:15s})")
            print()
