# -*- coding: utf-8 -*-
"""배우자 1천만원 이상 이체만 자금원으로 포함"""
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

# === 이지영(배우자)로부터의 입금 — 1천만원 이상만 ===
print("="*100)
print("【배우자(이지영)로부터 받은 1천만원 이상 입금】")
print("="*100)
ljy_in = df[(df["거래내용"].str.contains("이지영",na=False) | df["상대계좌예금주명"].str.contains("이지영",na=False)) & (df["입"]>0) & (df["dt"]<=pd.Timestamp("2022-02-23"))].copy()
ljy_in_big = ljy_in[ljy_in["입"]>=10_000_000].sort_values("dt")
print(f"\n1천만원 이상 입금: {len(ljy_in_big)}건")
total_spouse_big = ljy_in_big["입"].sum()
for _, r in ljy_in_big.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")
print(f"\n총 자금원 (배우자 1천만+): {total_spouse_big:,}원 (절삭: {sum(trunc(x) for x in ljy_in_big['입']):,}원)")

# 참고: 500만~1천만원 입금도 표시
print(f"\n--- 참고: 5백만~1천만원 입금 ---")
ljy_in_mid = ljy_in[(ljy_in["입"]>=5_000_000) & (ljy_in["입"]<10_000_000)].sort_values("dt")
for _, r in ljy_in_mid.iterrows():
    print(f"  {r['dt']:%Y-%m-%d}  +{r['입']:>11,}  ({r['거래내용']}) ← {r['상대계좌예금주명']}")

# === 최종 자금 출처 (배우자 1천만+ 포함) ===
print("\n" + "="*100)
print("【최종 자금 출처 (배우자 1천만+ 포함)】")
print("="*100)

# 안경희
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn["입"])

# 037 보증금/임대료
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
ksd_unpaid_trunc = trunc(ksd_in - ksd_out) if (ksd_in - ksd_out) > 0 else 0

# 배우자 1천만 이상
spouse_trunc = sum(trunc(x) for x in ljy_in_big["입"])

scenarios = [
    ("A. 보수적", ahn_trunc + deposit_trunc + ksd_unpaid_trunc + spouse_trunc),
    ("B. 표준 (임대료 50%)", ahn_trunc + deposit_trunc + rental_trunc//2 + ksd_unpaid_trunc + spouse_trunc),
    ("C. 적극 (임대료 100%)", ahn_trunc + deposit_trunc + rental_trunc + ksd_unpaid_trunc + spouse_trunc),
]

for name, total in scenarios:
    pct = total/530_000_000*100
    gap = total - 530_000_000
    print(f"\n■ {name}")
    print(f"  자금원: {total:,}원 → 입증율 {pct:.1f}% / {'잉여' if gap>=0 else '부족'} {gap:+,}원")

print(f"""
─── 자금원 상세 ──────────────────
  ① 안경희 전세 보증금 반환:            {ahn_trunc:>13,}원
  ② IBK 037 상가 임대 보증금:           {deposit_trunc:>13,}원
  ③ IBK 037 상가 임대료 (정기):          {rental_trunc:>13,}원
  ④ 김수동 차용금 미상환:                {ksd_unpaid_trunc:>13,}원
  ⑤ 배우자(이지영) 1천만+ 이체:          {spouse_trunc:>13,}원
""")
