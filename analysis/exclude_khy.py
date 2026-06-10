# -*- coding: utf-8 -*-
"""김연호 거래 전면 배제 + 최종 보고"""
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

# === 김연호 거래 전체 확인 ===
print("="*100)
print("【전체 계좌의 김연호 거래 (배제 대상)】")
print("="*100)
khy_mask = (df["거래내용"].str.contains("김연호",na=False) | 
            df["상대계좌예금주명"].str.contains("김연호",na=False))
khy = df[khy_mask].copy().sort_values("dt")
print(f"\n총 {len(khy)}건")
khy_in = khy[khy["입"]>0]["입"].sum()
khy_out = khy[khy["출"]>0]["출"].sum()
print(f"입금(김연호로부터): {len(khy[khy['입']>0])}건 / {khy_in:,}원")
print(f"출금(김연호에게):  {len(khy[khy['출']>0])}건 / {khy_out:,}원")
print()
for _, r in khy.iterrows():
    sign = "+" if r["입"]>0 else "-"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign}{amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']}")

# === 김연호 배제 후 037 보증금 재계산 ===
print("\n" + "="*100)
print("【김연호 완전 배제 후 IBK 037 상가 임대 보증금 재계산】")
print("="*100)

ibk037 = df[df["_계좌번호"]=="140-090845-01-037"].copy()
# 김연호 + 김연호 관련 자금(농협 → 037 이체 중 김연호 추정분) 제외
ibk037_in = ibk037[ibk037["입"]>0].copy()
# 외부 자금만 (본인 이체 제외)
ibk037_in = ibk037_in[~ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)]
# 김연호 제외
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("김연호", na=False)]
ibk037_in = ibk037_in[~ibk037_in["거래내용"].astype(str).str.contains("김연호", na=False)]

# 임대료 패턴 (정기) 제외
grp = ibk037_in.groupby("상대계좌예금주명").agg(
    건수=("입","count"),
    최빈빈도=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0),
).reset_index()
rental_names = set(grp[(grp["건수"]>=3) & (grp["최빈빈도"]>=2)]["상대계좌예금주명"])
print(f"\n정기 임대료 패턴 거래자 (제외): {len(rental_names)}명")
for nm in sorted(rental_names):
    if nm: print(f"  - {nm}")

# 일회성 5백만원 이상 (보증금)
ibk037_in_deposit = ibk037_in[~ibk037_in["상대계좌예금주명"].isin(rental_names)]
ibk037_in_deposit = ibk037_in_deposit[ibk037_in_deposit["입"] >= 5_000_000]
# 김광규 송금 시점까지만
ibk037_in_deposit = ibk037_in_deposit[ibk037_in_deposit["dt"] <= "2022-02-23"]

print(f"\n5백만원 이상 일회성 입금 (보증금 후보, 김연호 제외):")
total_deposit = 0
for _, r in ibk037_in_deposit.sort_values("dt").iterrows():
    total_deposit += r["입"]
    print(f"  {r['dt']:%Y-%m-%d}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']}")
print(f"\n총 보증금 후보: {total_deposit:,}원 (절삭: {sum(trunc(r['입']) for _, r in ibk037_in_deposit.iterrows()):,}원)")

# === 최종 자금 출처 (보수적, 김연호 제외) ===
print("\n" + "="*100)
print("【김광규 송금 5.3억의 최종 자금 출처 (김연호 완전 배제)】")
print("="*100)

# 안경희 (확정)
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn["입"])

# 빗썸
bit = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] <= "2022-02-23")]
bit_trunc = sum(trunc(x) for x in bit["입"])

# 037 보증금 (김연호 제외, 임대료 제외, 5백만 이상)
deposit_trunc = sum(trunc(r["입"]) for _, r in ibk037_in_deposit.iterrows())

total = ahn_trunc + deposit_trunc + bit_trunc
gap = total - 530_000_000

print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ 김광규 전세 보증금 반환:                          530,000,000원       │
├──────────────────────────────────────────────────────────────────────┤
│ 자금원 (보수적 기준, 김연호 완전 배제):                                │
│                                                                      │
│  ① 안경희 전세 보증금 반환 수령:               {ahn_trunc:>13,}원        │
│  ② IBK 037 상가 임대 보증금 (임대료·김연호 제외): {deposit_trunc:>13,}원        │
│  ③ 빗썸 가상화폐 매도 회수:                    {bit_trunc:>13,}원        │
│  ──────────────────────────────────         ─────────────           │
│  소계:                                       {total:>13,}원        │
│                                                                      │
│  {'잉여' if gap>=0 else '부족'}:                                       {gap:>+13,}원        │
│                                                                      │
│  입증 비율: {total/530_000_000*100:.1f}%                                                │
└──────────────────────────────────────────────────────────────────────┘
""")
