# -*- coding: utf-8 -*-
"""임대료 완전 배제 + 김수동 차용증 유무 시나리오"""
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

def trunc(amount):
    return (amount // 1_000_000) * 1_000_000

# 자금원 계산
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn["입"])

ibk037_in = df[(df["_계좌번호"]=="140-090845-01-037") & (df["입"]>0) & (df["dt"]<=pd.Timestamp("2022-02-23"))].copy()
ibk037_in = ibk037_in[~ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준|김연호", na=False)]
ibk037_in = ibk037_in[~ibk037_in["거래내용"].astype(str).str.contains("김연호|빗썸", na=False, regex=True)]
grp = ibk037_in.groupby("상대계좌예금주명").agg(건수=("입","count"), 최빈=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0))
rental_names = set(grp[(grp["건수"]>=3) & (grp["최빈"]>=2)].index)
deposit_big = ibk037_in[(~ibk037_in["상대계좌예금주명"].isin(rental_names)) & (ibk037_in["입"]>=5_000_000)]
deposit_trunc = sum(trunc(x) for x in deposit_big["입"])

# 김수동
ksd_in = df[(df["거래내용"].str.contains("김수동",na=False)|df["상대계좌예금주명"].str.contains("김수동",na=False)) & (df["입"]>0)]["입"].sum()
ksd_out = df[(df["거래내용"].str.contains("김수동",na=False)|df["상대계좌예금주명"].str.contains("김수동",na=False)) & (df["출"]>0)]["출"].sum()
ksd_unpaid_trunc = trunc(ksd_in - ksd_out) if (ksd_in - ksd_out) > 0 else 0

# 배우자 500만+
ljy_big = df[(df["거래내용"].str.contains("이지영",na=False) | df["상대계좌예금주명"].str.contains("이지영",na=False)) & (df["입"]>=5_000_000) & (df["dt"]<=pd.Timestamp("2022-02-23"))]
spouse_trunc = sum(trunc(x) for x in ljy_big["입"])

print("="*100)
print("【시나리오 1: 임대료 배제 + 김수동 차용증 보유】")
print("="*100)
total_1 = ahn_trunc + deposit_trunc + ksd_unpaid_trunc + spouse_trunc
print(f"""
┌──────────────────────────────────────────────────────────────────┐
│ 김광규 전세 보증금 반환:                  530,000,000원           │
├──────────────────────────────────────────────────────────────────┤
│ ① 안경희 전세 보증금 반환:                {ahn_trunc:>13,}원         │
│ ② IBK 037 상가 임대 보증금:                {deposit_trunc:>13,}원         │
│ ③ 김수동 차용금 (미상환):                  {ksd_unpaid_trunc:>13,}원         │
│ ④ 배우자(이지영) 500만+ 이체:              {spouse_trunc:>13,}원         │
│                                       ─────────────             │
│ 자금원 합계:                            {total_1:>13,}원         │
│                                                                  │
│ 입증 비율: {total_1/530_000_000*100:.1f}%   {'잉여' if total_1-530_000_000>=0 else '부족'} {total_1-530_000_000:+,}원        │
└──────────────────────────────────────────────────────────────────┘
""")

print("="*100)
print("【시나리오 2: 임대료 배제 + 김수동 차용증 없음 (배제)】")
print("="*100)
total_2 = ahn_trunc + deposit_trunc + spouse_trunc
print(f"""
┌──────────────────────────────────────────────────────────────────┐
│ 김광규 전세 보증금 반환:                  530,000,000원           │
├──────────────────────────────────────────────────────────────────┤
│ ① 안경희 전세 보증금 반환:                {ahn_trunc:>13,}원         │
│ ② IBK 037 상가 임대 보증금:                {deposit_trunc:>13,}원         │
│ ③ 배우자(이지영) 500만+ 이체:              {spouse_trunc:>13,}원         │
│                                       ─────────────             │
│ 자금원 합계:                            {total_2:>13,}원         │
│                                                                  │
│ 입증 비율: {total_2/530_000_000*100:.1f}%   {'잉여' if total_2-530_000_000>=0 else '부족'} {total_2-530_000_000:+,}원        │
└──────────────────────────────────────────────────────────────────┘
""")

# 김수동 차용증 없을 시 대응 방안
print("="*100)
print("【시나리오 2의 부족분(-43백만) 보완 대안 — 김수동 차용증 없을 시】")
print("="*100)
shortage = 530_000_000 - total_2
print(f"\n부족 금액: {shortage:,}원\n")

# 대안 자금원 후보 추출
print("=== 대안 자금원 후보 ===\n")

# 대안 1: 037 임대료 일부 인정 (가장 자연스러움)
rental = df[(df["_계좌번호"]=="140-090845-01-037") & (df["입"]>0) & (df["dt"]<=pd.Timestamp("2022-02-23"))].copy()
rental = rental[rental["상대계좌예금주명"].isin(rental_names)]
rental_trunc = sum(trunc(x) for x in rental["입"])
print(f"대안 A. IBK 037 상가 임대료 일부 인정")
print(f"   - 전체 임대료: {rental_trunc:,}원")
print(f"   - 부족액 {shortage:,}원 / 전체 {rental_trunc:,}원 = {shortage/rental_trunc*100:.1f}%만 인정해도 충당")
print(f"   - 입증 비율: {(total_2 + shortage)/530_000_000*100:.1f}% (정확히 100%)")
print()

# 대안 2: 다른 부동산 거래 (037 외)
# 2019-02-22 농협 김연호 1.93억 입금이 다음날 전세자금1,2로 출금
print(f"대안 B. 2019년 농협 1.93억 (김연호) 거래 재검토")
print(f"   - 2019-02-22 농협 +1.93억 (김연호, 수표)")
print(f"   - 2019-02-23 농협 -1.93억 (전세자금1, 전세자금2)")
print(f"   - 김연호 = 임차인이면 1.93억은 사업 보증금")
print(f"   - 단, 다음날 전세자금으로 출금되어 자금풀에 잔존하지 않음")
print(f"   - 회계적으로는 추적 불가")
print()

# 대안 3: 부족분 = 김수동 자금 = 자기자금
print(f"대안 C. 김수동 차용증 없을 시 → 자기자금으로 충당")
print(f"   - 자기자금 입증 방법:")
print(f"     1) 본인 다른 보유 자산 (예금, 주식, 펀드) 매도/인출")
print(f"     2) 추가 가족 자금 차용 (배우자/부모/형제)")
print(f"     3) IBK 사업 운영 대출 → 자기자금으로 사용")
print()

# 대안 4: 김수동을 "증여" 또는 "기타소득"으로 신고
print(f"대안 D. 김수동 자금을 증여 또는 기타 자금으로 처리")
print(f"   - 증여로 인정: 증여세 신고 필요 (6,500만 ⇒ 약 650만 세금)")
print(f"   - 단순 입금으로 인정: 차용 입증 부담 회피")
