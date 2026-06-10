# -*- coding: utf-8 -*-
"""IBK 037 계좌 입금을 보증금 vs 임대료로 구분
   - 임대료: 정기적 매월 비슷한 금액 반복 입금
   - 보증금: 일회성 큰 금액 입금
"""
import os, sys
import pandas as pd
from datetime import timedelta
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

def truncate_mil(amount):
    return (amount // 1_000_000) * 1_000_000

# IBK 037 외부 입금 (김연호·본인이체 제외)
ibk037_in = df[(df["_계좌번호"]=="140-090845-01-037") & 
               (df["입"]>0) &
               (df["dt"] <= "2022-02-23")].copy()
ibk037_in = ibk037_in[~ibk037_in["거래내용"].str.contains("김연호",na=False)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].str.contains("김연호",na=False)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)]

print("="*100)
print("【IBK 037 계좌 외부 입금 — 보증금 vs 임대료 구분】")
print("="*100)
print(f"\n총 외부 입금: {len(ibk037_in)}건 / {ibk037_in['입'].sum():,}원")

# === 분류 1: 정기 임대료 (같은 사람이 매월/유사 금액 반복) ===
# 그룹화: 상대예금주별
grp = ibk037_in.groupby("상대계좌예금주명").agg(
    건수=("입","count"),
    합계=("입","sum"),
    최빈금액=("입", lambda x: x.value_counts().index[0] if len(x)>0 else 0),
    최빈빈도=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0),
    최초=("dt","min"),
    최종=("dt","max"),
).reset_index()
grp["기간_월"] = ((grp["최종"] - grp["최초"]).dt.days / 30).round(1)

# 임대료 패턴: 3건 이상 + 동일 금액 2회 이상
rental_pattern = grp[(grp["건수"]>=3) & (grp["최빈빈도"]>=2)]
print(f"\n=== 정기 임대료 패턴 (3건 이상 + 동일금액 2회 이상): {len(rental_pattern)}명 ===")
print(f"{'임차인':25s} {'건수':>5} {'합계':>13} {'월세':>11} {'반복':>4} {'기간':>5}월")
total_rental = 0
rental_names = set()
for _, r in rental_pattern.iterrows():
    name = r["상대계좌예금주명"]
    if not name: continue
    print(f"{str(name)[:25]:25s} {int(r['건수']):>5} {int(r['합계']):>13,} {int(r['최빈금액']):>11,} {int(r['최빈빈도']):>4} {r['기간_월']:>5}")
    total_rental += r["합계"]
    rental_names.add(name)

print(f"\n정기 임대료 추정 총액: {total_rental:,}원")

# === 분류 2: 일회성 큰 보증금 (1천만원 이상, 한 사람당 1~2회만) ===
deposit_pattern = grp[grp["건수"]<=2]
print(f"\n=== 일회성/단기 입금 (1~2회): {len(deposit_pattern)}명 ===")

big_deposits = ibk037_in[(ibk037_in["입"]>=5_000_000) & 
                         (~ibk037_in["상대계좌예금주명"].isin(rental_names))].sort_values("dt")
total_deposit = big_deposits["입"].sum()
print(f"\n=== 5백만원 이상 일회성 입금 (보증금 후보): {len(big_deposits)}건 ===")
for _, r in big_deposits.iterrows():
    print(f"  {r['dt']:%Y-%m-%d}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")
print(f"\n보증금 후보 총액: {total_deposit:,}원")

# === 임대료 vs 보증금 명확 구분 시도 ===
# 임대료 = 정기 패턴에 속한 거래
# 보증금 = 그 외 큰 일회성 거래 (3백만원 이상)
print("\n" + "="*100)
print("【분류 결과 (절삭, 백만원 단위)】")
print("="*100)

rental_mask = ibk037_in["상대계좌예금주명"].isin(rental_names)
rental_tx = ibk037_in[rental_mask]
non_rental_tx = ibk037_in[~rental_mask]

rental_sum = sum(truncate_mil(x) for x in rental_tx["입"])
non_rental_sum = sum(truncate_mil(x) for x in non_rental_tx["입"])
print(f"\n① 정기 임대료 추정:        {rental_sum:>13,}원 ({len(rental_tx)}건)")
print(f"② 일회성 입금 (보증금 추정): {non_rental_sum:>13,}원 ({len(non_rental_tx)}건)")
print(f"  ─────────────────────")
print(f"  외부 입금 합계:          {rental_sum + non_rental_sum:>13,}원")

# 일회성 입금 중 5백만원 이상만 (보증금 추정)
non_rental_big = non_rental_tx[non_rental_tx["입"]>=5_000_000]
non_rental_big_sum = sum(truncate_mil(x) for x in non_rental_big["입"])
print(f"\n  ⤷ 일회성 중 5백만원 이상: {non_rental_big_sum:>13,}원 ({len(non_rental_big)}건) — 명확한 보증금")
non_rental_small = non_rental_tx[non_rental_tx["입"]<5_000_000]
non_rental_small_sum = sum(truncate_mil(x) for x in non_rental_small["입"])
print(f"  ⤷ 일회성 중 5백만 미만:  {non_rental_small_sum:>13,}원 ({len(non_rental_small)}건) — 불명확")

# === 최종 보고서 갱신 ===
print("\n" + "="*100)
print("【최종: 임대료 제외, 보증금만 자금원으로 인정 (백만원 절삭)】")
print("="*100)

# 안경희
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(truncate_mil(x) for x in ahn["입"])

# 빗썸
bit = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] <= "2022-02-23")]
bit_trunc = sum(truncate_mil(x) for x in bit["입"])

# 037 보증금만 (5백만 이상 일회성)
deposit_only = non_rental_big_sum

print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ 김광규 전세 보증금 반환:                          530,000,000원       │
├──────────────────────────────────────────────────────────────────────┤
│  ① 안경희 전세 보증금 반환 수령:               {ahn_trunc:>13,}원        │
│  ② IBK 037 상가 임대 보증금 (임대료 제외):    {deposit_only:>13,}원        │
│  ③ 빗썸 가상화폐 매도 회수:                  {bit_trunc:>13,}원        │
│  ──────────────────────────────────         ─────────────           │
│  소계:                                       {ahn_trunc + deposit_only + bit_trunc:>13,}원        │
│                                                                      │
│  잉여:                                       {ahn_trunc + deposit_only + bit_trunc - 530_000_000:>+13,}원        │
└──────────────────────────────────────────────────────────────────────┘

입증 비율: {(ahn_trunc + deposit_only + bit_trunc)/530_000_000*100:.1f}%
""")
