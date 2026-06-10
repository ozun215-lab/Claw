# -*- coding: utf-8 -*-
"""김수동 차용금 분석 - 입금/상환 흐름 추적"""
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

def trunc(amount):
    return (amount // 1_000_000) * 1_000_000

# === 김수동 거래 전체 ===
print("="*100)
print("【김수동 관련 모든 거래 (전체 계좌)】")
print("="*100)
ksd = df[df["거래내용"].str.contains("김수동",na=False) | df["상대계좌예금주명"].str.contains("김수동",na=False)].copy().sort_values("dt")
print(f"\n총 {len(ksd)}건")
in_total = ksd[ksd["입"]>0]["입"].sum()
out_total = ksd[ksd["출"]>0]["출"].sum()
print(f"입금(김수동 → 박영준): {len(ksd[ksd['입']>0])}건 / {in_total:,}원")
print(f"출금(박영준 → 김수동): {len(ksd[ksd['출']>0])}건 / {out_total:,}원")
print(f"순잔존 (입금-출금):    {in_total - out_total:+,}원")
print()
for _, r in ksd.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 김수동 명의가 정확히 일치하지 않을 수 있어 확장 검색 ===
print("\n" + "="*100)
print("【'김수동' 외 유사 거래 확장 검색 (수동, 수돵 등)】")
print("="*100)
extended = df[df["거래내용"].str.contains("수동|수돵",na=False) | df["상대계좌예금주명"].str.contains("수동|수돵",na=False)].copy()
extended = extended[~extended.index.isin(ksd.index)]
print(f"\n추가 발견: {len(extended)}건")
for _, r in extended.head(20).iterrows():
    sign = "+" if r["입"]>0 else "-"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d}  {sign}{amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']}")

# === 김수동 자금이 어느 계좌로 들어왔는지 + 김광규 송금까지 흐름 ===
print("\n" + "="*100)
print("【김수동 자금 흐름 추적】")
print("="*100)
ksd_in = ksd[ksd["입"]>0].sort_values("dt")
ksd_out = ksd[ksd["출"]>0].sort_values("dt")

if len(ksd_in)>0:
    for _, kr in ksd_in.iterrows():
        print(f"\n▶ {kr['dt']:%Y-%m-%d %H:%M} [{kr['_은행']}{kr['_계좌번호'][-3:]}]")
        print(f"  김수동 입금: +{kr['입']:,}원")
        # 입금 후 동일 계좌의 큰 출금 (30일)
        after = df[(df["_계좌번호"]==kr["_계좌번호"]) & 
                   (df["dt"] > kr["dt"]) & 
                   (df["dt"] <= kr["dt"]+timedelta(days=30)) & 
                   (df["출"]>=1_000_000)].sort_values("dt")
        print(f"  입금 후 30일 내 100만원 이상 출금:")
        for _, ar in after.head(15).iterrows():
            hours = (ar["dt"]-kr["dt"]).total_seconds()/3600
            print(f"    +{hours:>6.1f}h  -{ar['출']:>13,}  ({ar['거래내용']}) → {ar['상대계좌예금주명']} / {ar['상대은행']} {ar['상대계좌번호']}")

# === 김수동에게 환급/상환된 흔적 ===
print("\n" + "="*100)
print("【김수동에게 환급/상환 흔적】")
print("="*100)
if len(ksd_out)>0:
    print(f"\n{len(ksd_out)}건의 김수동 환급/상환:")
    for _, r in ksd_out.iterrows():
        print(f"  {r['dt']:%Y-%m-%d}  -{r['출']:>13,}  → 김수동 / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 최종 자금 출처 (김수동 미상환분 포함) ===
print("\n" + "="*100)
print("【김수동 미상환 잔존액 추정】")
print("="*100)
unpaid = in_total - out_total
unpaid_trunc = trunc(unpaid) if unpaid > 0 else 0
print(f"""
김수동 차용:    +{in_total:,}원
김수동 상환:    -{out_total:,}원
미상환 잔존:    {unpaid:+,}원
백만원 절삭:    {unpaid_trunc:,}원

→ 이 미상환 차용금이 김광규 송금에 사용된 자금으로 인정 가능
""")

# === 최종 자금 출처 시나리오 (빗썸 배제 + 김수동 미상환 포함) ===
print("="*100)
print("【최종 자금 출처: 빗썸 배제 + 김수동 미상환 잔존 포함】")
print("="*100)

# 안경희
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn["입"])

# 037 보증금 (5백만 이상)
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

scenarios = [
    ("A. 보수적 (보증금만 + 김수동 미상환)", ahn_trunc + deposit_trunc + unpaid_trunc),
    ("B. 표준 (보증금 + 임대료 50% + 김수동 미상환)", ahn_trunc + deposit_trunc + rental_trunc//2 + unpaid_trunc),
    ("C. 적극 (보증금 + 임대료 100% + 김수동 미상환)", ahn_trunc + deposit_trunc + rental_trunc + unpaid_trunc),
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
  ③ IBK 037 상가 임대료 (정기):           {rental_trunc:>13,}원
  ④ 김수동 차용금 미상환 잔존:            {unpaid_trunc:>13,}원
""")
