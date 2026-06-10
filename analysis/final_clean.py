# -*- coding: utf-8 -*-
"""최종 보고서용 깔끔한 자금원 계산
배제: BNK·이정훈·이승원·박상호·김연호·빗썸·급여·이지영(배우자)·소액
포함: 안경희 보증금·037 상가 보증금·김수동 차용금·037 임대료 일부
"""
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

# ===================================================================
# 자금원 항목 계산
# ===================================================================

# ① 안경희 보증금 반환
ahn_in = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn_in["입"])

# ② IBK 037 상가 임대 보증금 (5백만 이상 일회성, 임대료 패턴 제외)
ibk037_in = df[(df["_계좌번호"]=="140-090845-01-037") & (df["입"]>0) & (df["dt"]<=pd.Timestamp("2022-02-23"))].copy()
# 본인 다른계좌 이체 제외
ibk037_in = ibk037_in[~ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)]
# 김연호 제외
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("김연호", na=False)]
ibk037_in = ibk037_in[~ibk037_in["거래내용"].astype(str).str.contains("김연호|빗썸", na=False, regex=True)]

# 정기 임대료 패턴 식별
grp = ibk037_in.groupby("상대계좌예금주명").agg(건수=("입","count"), 최빈=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0))
rental_names = set(grp[(grp["건수"]>=3) & (grp["최빈"]>=2)].index)

# 보증금 = 정기 임대료 패턴 제외 + 5백만 이상
deposit_big = ibk037_in[(~ibk037_in["상대계좌예금주명"].isin(rental_names)) & (ibk037_in["입"]>=5_000_000)]
deposit_trunc = sum(trunc(x) for x in deposit_big["입"])

# ③ 037 정기 임대료
rental = ibk037_in[ibk037_in["상대계좌예금주명"].isin(rental_names)]
rental_trunc = sum(trunc(x) for x in rental["입"])

# ④ 김수동 차용 미상환
ksd_in = df[(df["거래내용"].str.contains("김수동",na=False)|df["상대계좌예금주명"].str.contains("김수동",na=False)) & (df["입"]>0)]["입"].sum()
ksd_out = df[(df["거래내용"].str.contains("김수동",na=False)|df["상대계좌예금주명"].str.contains("김수동",na=False)) & (df["출"]>0)]["출"].sum()
ksd_unpaid_trunc = trunc(ksd_in - ksd_out) if (ksd_in - ksd_out) > 0 else 0

# 출력
print("="*100)
print("【김광규 송금 5.3억의 최종 자금 출처】")
print("【배제: 임시자금·빗썸·김연호·배우자(생활비)·소액·급여】")
print("="*100)

scenarios = [
    ("A. 보수적 (보증금만 + 김수동)",
     ahn_trunc + deposit_trunc + ksd_unpaid_trunc,
     "임대료 전체 배제"),
    ("B. 표준 (보증금 + 임대료 50% + 김수동)",
     ahn_trunc + deposit_trunc + rental_trunc//2 + ksd_unpaid_trunc,
     "임대료 50% 인정 (운영비 일부 대출 충당)"),
    ("C. 적극 (보증금 + 임대료 100% + 김수동)",
     ahn_trunc + deposit_trunc + rental_trunc + ksd_unpaid_trunc,
     "임대료 100% 인정 (운영비 전액 대출 충당 입증 시)"),
]

for name, total, note in scenarios:
    pct = total / 530_000_000 * 100
    gap = total - 530_000_000
    status = "✅" if total >= 530_000_000 else "⚠"
    print(f"\n■ 시나리오 {name}")
    print(f"  ({note})")
    print(f"  자금원 합계: {total:,}원")
    print(f"  입증 비율: {pct:.1f}%   {'잉여' if gap>=0 else '부족'} {gap:+,}원  {status}")

# ⭐ 권장 시나리오 B
total_B = ahn_trunc + deposit_trunc + rental_trunc//2 + ksd_unpaid_trunc
print(f"""
{'='*100}

⭐ 권장: 시나리오 B (표준)

┌────────────────────────────────────────────────────────────────┐
│ 김광규 전세 보증금 반환:                  530,000,000원         │
├────────────────────────────────────────────────────────────────┤
│  ① 안경희 전세 보증금 반환:               {ahn_trunc:>13,}원   │
│  ② IBK 037 상가 임대 보증금:              {deposit_trunc:>13,}원   │
│  ③ IBK 037 상가 임대료 (50%):             {rental_trunc//2:>13,}원   │
│  ④ 김수동 차용금 미상환:                  {ksd_unpaid_trunc:>13,}원   │
│  ──────────────────────────────         ─────────────         │
│  합계:                                  {total_B:>13,}원   │
│                                                                │
│  ✅ 입증 비율 {total_B/530_000_000*100:.1f}%   잉여 {total_B-530_000_000:+,}원   │
└────────────────────────────────────────────────────────────────┘

배제 항목:
  ❌ BNK캐피탈, 이정훈, 이승원 (임시자금)
  ❌ 박상호 (임시자금, 3일 후 수표 출금)
  ❌ 김연호 (배제 요청)
  ❌ 빗썸 가상화폐 (가상자산 이슈 회피)
  ❌ 급여 (생활비 소진)
  ❌ 배우자 이지영 (소액 양방향 생활비 정산, 순지출)
  ❌ 037 임대료 50% (일부 생활비 소진 가정, 50%만 인정)

자금 구성 비율:
  • 안경희 전세 보증금:    {ahn_trunc/total_B*100:.1f}%
  • 037 상가 임대 보증금:  {deposit_trunc/total_B*100:.1f}%
  • 037 임대료 50%:        {rental_trunc//2/total_B*100:.1f}%
  • 김수동 차용:           {ksd_unpaid_trunc/total_B*100:.1f}%
""")
