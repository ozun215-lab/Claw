# -*- coding: utf-8 -*-
"""IBK 037 계좌 = 상가 임대 운영 계좌
   → 037 입금 전액을 상가 임대 보증금/임대료 수입으로 분류
   → 김연호 배제
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

def fmt(amount):
    return f"{truncate_mil(amount):,}"

# === IBK 037 계좌 전체 입금 (상가 임대 수입) ===
print("="*100)
print("【IBK 037 상가 임대 운영 계좌 — 전체 입금 분석】")
print("="*100)
ibk037 = df[df["_계좌번호"]=="140-090845-01-037"].copy()
print(f"기간: {ibk037['dt'].min()} ~ {ibk037['dt'].max()}")
print(f"총 거래: {len(ibk037)}건")

ibk037_in = ibk037[ibk037["입"]>0].copy()
print(f"\n총 입금: {len(ibk037_in)}건 / {ibk037_in['입'].sum():,}원")
print(f"  ⤷ 백만원 절삭: {truncate_mil(ibk037_in['입'].sum()):,}원")

# 김광규 송금 시점까지만 누적
ibk037_in_cutoff = ibk037_in[ibk037_in["dt"] <= "2022-02-23"]
print(f"\n2022-02-23까지 입금: {len(ibk037_in_cutoff)}건 / {ibk037_in_cutoff['입'].sum():,}원")
print(f"  ⤷ 백만원 절삭: {truncate_mil(ibk037_in_cutoff['입'].sum()):,}원")

# 김연호 제외 (대표님 요청)
khy_mask = ibk037_in_cutoff["거래내용"].str.contains("김연호",na=False) | ibk037_in_cutoff["상대계좌예금주명"].str.contains("김연호",na=False)
khy_total = ibk037_in_cutoff[khy_mask]["입"].sum()
ibk037_in_real = ibk037_in_cutoff[~khy_mask]
print(f"\n김연호 거래 제외 후: {len(ibk037_in_real)}건 / {ibk037_in_real['입'].sum():,}원")
print(f"  ⤷ 백만원 절삭: {truncate_mil(ibk037_in_real['입'].sum()):,}원")

# 본인 다른계좌 이체 제외 (이체는 이미 다른 계좌에서 잡힌 자금이므로 중복)
own_mask = ibk037_in_real["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True) | \
           ibk037_in_real["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)
own_total = ibk037_in_real[own_mask]["입"].sum()
external_in = ibk037_in_real[~own_mask]
print(f"\n본인 다른계좌 이체 제외 후 (외부 자금만): {len(external_in)}건 / {external_in['입'].sum():,}원")
print(f"  ⤷ 백만원 절삭: {truncate_mil(external_in['입'].sum()):,}원")

# === 1천만원 이상 큰 입금 (보증금) ===
print("\n=== 037 계좌 1천만원 이상 외부 입금 (상가 임대 보증금) ===")
big_deposit = external_in[external_in["입"]>=10_000_000].sort_values("dt")
total_big = big_deposit["입"].sum()
print(f"\n{len(big_deposit)}건 / 합계 {total_big:,}원 (절삭: {truncate_mil(total_big):,}원)")
for _, r in big_deposit.iterrows():
    print(f"  {r['dt']:%Y-%m-%d}  +{fmt(r['입']):>13}원  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 100만원~1천만원 (임대료 + 기타) ===
print("\n=== 037 계좌 100만원~1천만원 외부 입금 (월 임대료 + 보증금) ===")
mid = external_in[(external_in["입"]>=1_000_000) & (external_in["입"]<10_000_000)].sort_values("dt")
total_mid = mid["입"].sum()
print(f"\n{len(mid)}건 / 합계 {total_mid:,}원 (절삭: {truncate_mil(total_mid):,}원)")
# 첫 20개만 표시
for _, r in mid.head(30).iterrows():
    print(f"  {r['dt']:%Y-%m-%d}  +{r['입']:>11,}원  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} [{r['거래구분']}]")
if len(mid) > 30:
    print(f"  ... 외 {len(mid)-30}건")

# === 100만원 미만 소액 (월 관리비 등) ===
print("\n=== 037 계좌 100만원 미만 소액 입금 ===")
small = external_in[external_in["입"]<1_000_000]
total_small = small["입"].sum()
print(f"{len(small)}건 / 합계 {total_small:,}원 (절삭: {truncate_mil(total_small):,}원)")

# === 최종 종합 ===
print("\n" + "="*100)
print("【종합: 김광규 송금 5.3억의 자금 출처 (IBK 037 상가임대수입 포함)】")
print("="*100)

# 안경희 보증금 반환 (절삭)
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_total = ahn["입"].sum()
ahn_total_trunc = sum(truncate_mil(x) for x in ahn["입"])

# 빗썸 매도
bit = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] <= "2022-02-23")]
bit_total = bit["입"].sum()
bit_total_trunc = sum(truncate_mil(x) for x in bit["입"])

# 037 상가임대수입 (외부, 김연호 제외)
ibk037_real_total = external_in["입"].sum()
ibk037_real_trunc = sum(truncate_mil(x) for x in external_in["입"])

print(f"""
■ 김광규 전세 보증금 반환:                    -530,000,000원

■ 자금원 (실수령 기준, 백만원 절삭):
  ① 안경희님 전세보증금 반환 수령:           +{ahn_total_trunc:>13,}원
  ② IBK 037 상가 임대 보증금/임대료 수입:    +{ibk037_real_trunc:>13,}원
  ③ 빗썸 가상화폐 매도 회수:                +{bit_total_trunc:>13,}원
  ──────────────────────────────         ─────────────
  소계:                                  +{ahn_total_trunc + ibk037_real_trunc + bit_total_trunc:>13,}원

  잉여:                                  +{ahn_total_trunc + ibk037_real_trunc + bit_total_trunc - 530_000_000:>13,}원

입증 비율: {(ahn_total_trunc + ibk037_real_trunc + bit_total_trunc)/530_000_000*100:.1f}%
""")
