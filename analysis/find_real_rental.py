# -*- coding: utf-8 -*-
"""진짜 임대 보증금 후보 발굴 + 임시자금 배제"""
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

# 임시자금 검증 함수: 입금 후 N일 내 동일 ±10% 금액 출금?
def is_temp(row, days=30):
    """이 입금이 임시자금인지 확인"""
    amt = row["입"]
    if amt <= 0: return False, None
    after = df[(df["_계좌번호"]==row["_계좌번호"]) & 
               (df["dt"] > row["dt"]) & 
               (df["dt"] <= row["dt"]+timedelta(days=days)) & 
               (df["출"] > 0)]
    matched = after[(after["출"] >= amt*0.9) & (after["출"] <= amt*1.1)]
    if len(matched)>0:
        m = matched.iloc[0]
        gap = (m["dt"] - row["dt"]).days
        return True, f"{gap}일 후 -{m['출']:,}원 출금"
    return False, None

# 김광규 송금 전까지 1천만원 이상 입금 (안경희·박영준 본인 이체·빗썸·이정훈·이승원·김수동·BNK 제외)
print("="*100)
print("【진짜 자금원 후보 발굴 — 1천만원 이상 입금 (~2022-02-23)】")
print("="*100)
EXCLUDE = ["안경희","BNK","이정훈","이승원","김수동","빗썸","박영준","박상호","에이엑티브","에이액티브","급여","상여","이자","CC","주식회사 에이"]
def is_excluded(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE)

mid = df[(df["입"]>=10_000_000) & (df["dt"] <= "2022-02-23")].copy()
mid_clean = mid[~mid.apply(is_excluded, axis=1)].copy()

print(f"\n총 {len(mid_clean)}건의 분류되지 않은 큰 입금:")
results = []
for _, r in mid_clean.sort_values("dt").iterrows():
    is_t, detail = is_temp(r, days=30)
    flag = " 🔴 임시자금" if is_t else " ✅ 잔존가능"
    results.append({"row": r, "temp": is_t, "detail": detail})
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]{flag} {detail or ''}")

# === 잔존 가능한 자금만 합산 ===
print("\n" + "="*100)
print("【잔존 가능 자금원 (30일 내 동액 출금 없음) — 진짜 자금원】")
print("="*100)
real_sources = [r for r in results if not r["temp"]]
total = sum(r["row"]["입"] for r in real_sources)
print(f"\n총 {len(real_sources)}건 / {total:,}원")
for r in real_sources:
    row = r["row"]
    print(f"  {row['dt']:%Y-%m-%d}  +{row['입']:>13,}  ({row['거래내용']}) ← {row['상대계좌예금주명']}")

# === 5천만원 이상 큰 입금만 (임대 보증금 후보) ===
print("\n" + "="*100)
print("【5천만원 이상 큰 입금 — 임대 보증금 후보 (잔존 가능)】")
print("="*100)
big_real = [r for r in results if not r["temp"] and r["row"]["입"]>=50_000_000]
total_big = sum(r["row"]["입"] for r in big_real)
print(f"\n총 {len(big_real)}건 / {total_big:,}원")
for r in big_real:
    row = r["row"]
    print(f"  {row['dt']:%Y-%m-%d}  +{row['입']:>13,}  ({row['거래내용']}) ← {row['상대계좌예금주명']} [{row['거래구분']}]  [{row['_은행']}{row['_계좌번호'][-3:]}]")

# === 추가: 김광규 입금 직전 IBK 044의 직접 입금 출처 ===
print("\n" + "="*100)
print("【최종 검증: 김광규 송금 직전 IBK 044 계좌의 직접 입금 출처】")
print("="*100)
ibk044_in = df[(df["_계좌번호"]=="140-090845-01-044") & (df["입"]>0)].sort_values("dt")
print(f"\nIBK 044 계좌 전체 입금 {len(ibk044_in)}건:")
for _, r in ibk044_in.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")
