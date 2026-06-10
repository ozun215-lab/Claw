# -*- coding: utf-8 -*-
"""이지영(배우자) 송금 자금원 포함 최종 재계산"""
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

# === 이지영 거래 전체 (배우자) ===
print("="*100)
print("【이지영(배우자) 관련 모든 거래】")
print("="*100)
ljy = df[df["거래내용"].str.contains("이지영",na=False) | df["상대계좌예금주명"].str.contains("이지영",na=False)].copy().sort_values("dt")
ljy_cutoff = ljy[ljy["dt"] <= "2022-02-23"]

in_total = ljy_cutoff[ljy_cutoff["입"]>0]["입"].sum()
out_total = ljy_cutoff[ljy_cutoff["출"]>0]["출"].sum()
in_count = len(ljy_cutoff[ljy_cutoff["입"]>0])
out_count = len(ljy_cutoff[ljy_cutoff["출"]>0])

print(f"\n김광규 송금 시점(2022-02-23)까지 거래 통계:")
print(f"  배우자 → 박영준: {in_count}건 / +{in_total:,}원")
print(f"  박영준 → 배우자: {out_count}건 / -{out_total:,}원")
print(f"  순흐름 (박영준 입장): {in_total - out_total:+,}원")

# 배우자 간 자금 흐름 - 송금 시점까지 순잔존
spouse_net = in_total - out_total
spouse_net_trunc = trunc(spouse_net) if spouse_net > 0 else 0

# 입금건만 (자금원 후보)
print(f"\n=== 배우자로부터의 입금 ({in_count}건) ===")
for _, r in ljy_cutoff[ljy_cutoff["입"]>0].iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>11,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")

print(f"\n=== 배우자에게 송금 ({out_count}건, 큰순) ===")
for _, r in ljy_cutoff[ljy_cutoff["출"]>0].sort_values("출", ascending=False).head(10).iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  -{r['출']:>11,}  ({r['거래내용']}) → {r['상대계좌예금주명']}")

# === 최종 자금 출처 (빗썸 배제 + 김수동 미상환 + 배우자 순흐름) ===
print("\n" + "="*100)
print("【최종 자금 출처: 배우자 자금 포함 (빗썸 배제, 김수동 미상환 포함)】")
print("="*100)

# 안경희
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn["입"])

# 037 보증금
ibk037_in = df[(df["_계좌번호"]=="140-090845-01-037") & (df["입"]>0) & (df["dt"]<=pd.Timestamp("2022-02-23"))].copy()
ibk037_in = ibk037_in[~ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("김연호", na=False)]
ibk037_in = ibk037_in[~ibk037_in["거래내용"].astype(str).str.contains("김연호|빗썸", na=False, regex=True)]

grp = ibk037_in.groupby("상대계좌예금주명").agg(건수=("입","count"), 최빈=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0))
rental_names = set(grp[(grp["건수"]>=3) & (grp["최빈"]>=2)].index)

deposit_big = ibk037_in[(~ibk037_in["상대계좌예금주명"].isin(rental_names)) & (ibk037_in["입"]>=5_000_000)]
deposit_trunc = sum(trunc(x) for x in deposit_big["입"])

rental = ibk037_in[ibk037_in["상대계좌예금주명"].isin(rental_names)]
rental_trunc = sum(trunc(x) for x in rental["입"])

# 김수동
ksd_in = df[(df["거래내용"].str.contains("김수동",na=False)|df["상대계좌예금주명"].str.contains("김수동",na=False)) & (df["입"]>0)]["입"].sum()
ksd_out = df[(df["거래내용"].str.contains("김수동",na=False)|df["상대계좌예금주명"].str.contains("김수동",na=False)) & (df["출"]>0)]["출"].sum()
ksd_unpaid = trunc(ksd_in - ksd_out) if (ksd_in - ksd_out) > 0 else 0

scenarios = [
    ("A. 보수적 (보증금만 + 김수동 + 배우자)", ahn_trunc + deposit_trunc + ksd_unpaid + spouse_net_trunc),
    ("B. 표준 (보증금 + 임대료 50% + 김수동 + 배우자)", ahn_trunc + deposit_trunc + rental_trunc//2 + ksd_unpaid + spouse_net_trunc),
    ("C. 적극 (보증금 + 임대료 100% + 김수동 + 배우자)", ahn_trunc + deposit_trunc + rental_trunc + ksd_unpaid + spouse_net_trunc),
]

for name, total in scenarios:
    pct = total / 530_000_000 * 100
    gap = total - 530_000_000
    print(f"\n■ 시나리오 {name}")
    print(f"  자금원: {total:,}원   →   입증율 {pct:.1f}%, {'잉여' if gap>=0 else '부족'} {gap:+,}원")

print(f"""
─── 자금원 상세 ──────────────────
  ① 안경희 전세 보증금 반환 수령:        {ahn_trunc:>13,}원
  ② IBK 037 상가 임대 보증금:            {deposit_trunc:>13,}원
  ③ IBK 037 상가 임대료 (정기 패턴):      {rental_trunc:>13,}원
  ④ 김수동 차용금 미상환 잔존:            {ksd_unpaid:>13,}원
  ⑤ 배우자(이지영) 순송금:                {spouse_net_trunc:>13,}원

────────────────────────
배우자 자금 세부:
  배우자로부터 받은 입금:  +{in_total:,}원 ({in_count}건)
  배우자에게 송금:        -{out_total:,}원 ({out_count}건)
  순잔존:                  +{spouse_net:,}원
""")
