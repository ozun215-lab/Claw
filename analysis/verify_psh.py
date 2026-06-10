# -*- coding: utf-8 -*-
"""박상호 8.18억 입금 검증 — 임대 보증금 가능성 확인"""
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

# === 1. 박상호 거래 전체 ===
print("="*100)
print("【박상호 관련 거래 전체】")
print("="*100)
psh = df[df["거래내용"].str.contains("박상호",na=False) | df["상대계좌예금주명"].str.contains("박상호",na=False)].copy().sort_values("dt")
print(f"총 {len(psh)}건")
for _, r in psh.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}] 메모:{r.get('송금메시지','')}")

# === 2. 2021-01-26 박상호 입금 직후 044 계좌의 흐름 ===
print("\n" + "="*100)
print("【2021-01-26 박상호 8.18억 입금 직후 IBK 044 자금 흐름】")
print("="*100)
ibk044 = df[df["_계좌번호"]=="140-090845-01-044"].copy().sort_values("dt").reset_index(drop=True)
# 입금 전후 30일
window = ibk044[(ibk044["dt"] >= "2021-01-25") & (ibk044["dt"] <= "2021-02-28")]
for _, r in window.iterrows():
    sign = "+" if r["입"]>0 else "-"
    amt = r["입"] if r["입"]>0 else r["출"]
    desc = r["거래내용"]
    name = r["상대계좌예금주명"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  {sign}{amt:>13,}  잔액 {n(r['잔액']):>13,}  ({desc}) → {name} {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 3. 박상호 입금이 임대 보증금인지 판단 — 입금 후 출금 패턴 확인 ===
print("\n" + "="*100)
print("【박상호 8.18억 → 어떻게 사용되었나? IBK 044 → 다른 곳으로 출금 추적】")
print("="*100)
# 2021-01-26 입금부터 1년 내 출금
window_out = ibk044[(ibk044["dt"] >= "2021-01-26") & (ibk044["dt"] <= "2022-02-28") & (ibk044["출"]>0)].copy()
print(f"\n2021-01-26 ~ 2022-02-28 IBK 044 출금 ({len(window_out)}건):")
total_out_044 = window_out["출"].sum()
for _, r in window_out.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")
print(f"\n총 출금: {total_out_044:,}원")

# === 4. 김연호 1.93억도 확인 ===
print("\n" + "="*100)
print("【김연호 관련 거래 (2019년 1.93억 입금)】")
print("="*100)
khy = df[df["거래내용"].str.contains("김연호",na=False) | df["상대계좌예금주명"].str.contains("김연호",na=False)].copy().sort_values("dt")
for _, r in khy.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")

# === 5. 박상호 자금이 김광규 송금까지 추적 (1년 이상 잔존 가능성) ===
print("\n" + "="*100)
print("【핵심: 박상호 8.18억 → 안경희 3.73억 → 김광규 5.30억 통합 자금풀 분석】")
print("="*100)

# 박상호 입금 8.18억 이후 044 계좌의 모든 출금 분류
out_summary = {}
for _, r in window_out.iterrows():
    s = str(r["거래내용"]) + " " + str(r["상대계좌예금주명"])
    if "김광규" in s: c = "김광규 송금"
    elif "박영준" in s: c = "본인 다른계좌"
    elif "이정훈" in s: c = "이정훈 (임시자금 상환)"
    elif "BNK" in s or "캐피" in s: c = "BNK 상환"
    elif "이자" in s: c = "이자"
    else: c = "기타: " + (r["상대계좌예금주명"] or r["거래내용"])[:20]
    out_summary[c] = out_summary.get(c, 0) + r["출"]

print("\n=== 박상호 입금 후 IBK 044 출금 분류 ===")
for c, v in sorted(out_summary.items(), key=lambda x: -x[1]):
    print(f"   {c:30s}  {v:>15,}원")
