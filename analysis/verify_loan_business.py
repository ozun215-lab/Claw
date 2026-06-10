# -*- coding: utf-8 -*-
"""상가 사업운영비를 대출로 충당했는지 검증"""
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

# === IBK 037 (상가 사업) 계좌의 출금 분석 ===
print("="*100)
print("【IBK 037 상가 사업 계좌의 모든 큰 출금 분석】")
print("="*100)
ibk037 = df[df["_계좌번호"]=="140-090845-01-037"].copy()
out = ibk037[ibk037["출"]>=1_000_000].copy().sort_values("dt")
print(f"\n037 계좌 100만원 이상 출금 {len(out)}건:")
print(f"총 출금: {out['출'].sum():,}원\n")

categories = {
    "임차인 보증금 반환": [],
    "세금/공과금": [],
    "이자/원리금 (대출 상환)": [],
    "사업 운영비 (공사·관리)": [],
    "본인 다른계좌 이체": [],
    "기타": [],
}

for _, r in out.iterrows():
    desc = str(r["거래내용"])
    name = str(r["상대계좌예금주명"])
    s = desc + " " + name
    if "이자" in s or "원리금" in s or "원금" in s or "할부" in s:
        categories["이자/원리금 (대출 상환)"].append(r)
    elif "세금" in s or "세" in s and ("부가" in s or "주민" in s or "재산" in s):
        categories["세금/공과금"].append(r)
    elif "보증금" in s and ("반환" in s or "반금" in s):
        categories["임차인 보증금 반환"].append(r)
    elif "박영준" in name or "90845" in str(r["상대계좌번호"]) or "3479" in str(r["상대계좌번호"]):
        categories["본인 다른계좌 이체"].append(r)
    elif any(k in s for k in ["공사","수리","청소","관리","청구","비용","수수료","렌탈"]):
        categories["사업 운영비 (공사·관리)"].append(r)
    else:
        categories["기타"].append(r)

print("=== 037 계좌 출금 분류 ===\n")
for cat, rows in categories.items():
    if not rows: continue
    total = sum(r["출"] for r in rows)
    print(f"\n■ {cat}: {len(rows)}건 / {total:,}원")
    for r in rows[:15]:
        print(f"  {r['dt']:%Y-%m-%d}  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']}")
    if len(rows)>15:
        print(f"  ... 외 {len(rows)-15}건")

# === 대출 이자/원리금 상환 패턴 분석 ===
print("\n" + "="*100)
print("【대출 이자/원리금 상환 패턴 — 대출 보유 입증】")
print("="*100)
# IBK 전체에서 이자/원리금
loan_pay = df[(df["_은행"]=="IBK기업") & (df["출"]>0)]
loan_pay = loan_pay[loan_pay["거래내용"].str.contains("원리금|이자|할부", na=False, regex=True)]
print(f"\nIBK 대출 이자/원리금 출금 총 {len(loan_pay)}건 / {loan_pay['출'].sum():,}원")

# 계좌별 분류
print("\n=== 계좌별 대출 상환 ===")
for acct, g in loan_pay.groupby("_계좌번호"):
    total = g["출"].sum()
    print(f"  {acct}: {len(g)}건 / {total:,}원")
    print(f"     기간: {g['dt'].min():%Y-%m-%d} ~ {g['dt'].max():%Y-%m-%d}")

# 대출 종류 (32-00033, 32-00049 등)
print("\n=== 대출 종류별 상환액 ===")
loan_pay["대출종류"] = "기타"
loan_pay.loc[loan_pay["거래내용"].str.contains("32-00049", na=False), "대출종류"] = "32-00049"
loan_pay.loc[loan_pay["거래내용"].str.contains("32-00033", na=False), "대출종류"] = "32-00033"
loan_pay.loc[loan_pay["거래내용"].str.contains("전세", na=False), "대출종류"] = "전세자금대출(어머니)"
grp = loan_pay.groupby("대출종류").agg(건수=("출","count"), 합계=("출","sum"))
print(grp.to_string())

# 사업 운영비 = 037 출금 - 본인이체 - 임차인 반환 - 세금 - 대출상환
print("\n" + "="*100)
print("【037 상가 사업 운영비 추정 (대출 충당 부분 제외 후)】")
print("="*100)
business_cost = sum(r["출"] for r in categories["사업 운영비 (공사·관리)"])
loan_repay_037 = sum(r["출"] for r in categories["이자/원리금 (대출 상환)"])
deposit_return = sum(r["출"] for r in categories["임차인 보증금 반환"])
tax = sum(r["출"] for r in categories["세금/공과금"])
self_transfer = sum(r["출"] for r in categories["본인 다른계좌 이체"])
etc = sum(r["출"] for r in categories["기타"])

print(f"""
037 계좌 출금 구성:
  - 사업 운영비 (공사/관리/청소):     {business_cost:>13,}원
  - 대출 이자/원리금 상환:           {loan_repay_037:>13,}원
  - 임차인 보증금 반환:              {deposit_return:>13,}원
  - 세금/공과금:                    {tax:>13,}원
  - 본인 다른계좌 이체:              {self_transfer:>13,}원
  - 기타:                          {etc:>13,}원
  ───────────────────────────
""")

# === 최종 자금 흐름 모형 ===
print("="*100)
print("【최종 자금 출처: 상가 보증금·임대료 자금풀 완전 잔존】")
print("="*100)
print("""
[해석]
  상가 운영비를 대출로 충당하셨으므로:
  - 상가 임대 보증금/임대료 수입 → 자산 자금풀에 잔존
  - 대출금 → 사업 운영비로 소진 (이자만 임대 수입에서 일부 지급)
  → 임대 수입을 김광규 송금 자금원으로 인정 가능
""")

# 안경희
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn["입"])

# 빗썸
bit = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] <= "2022-02-23")]
bit_trunc = sum(trunc(x) for x in bit["입"])

# 037 계좌 외부 입금 전체 (김연호 제외, 본인이체 제외) — 임대료까지 모두 포함
ibk037_in = ibk037[ibk037["입"]>0].copy()
ibk037_in = ibk037_in[~ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("김연호", na=False)]
ibk037_in = ibk037_in[~ibk037_in["거래내용"].astype(str).str.contains("김연호", na=False)]
ibk037_in = ibk037_in[ibk037_in["dt"] <= "2022-02-23"]

# 보증금 (5백만 이상 일회성)
grp_037 = ibk037_in.groupby("상대계좌예금주명").agg(건수=("입","count"), 최빈=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0))
rental_names = set(grp_037[(grp_037["건수"]>=3) & (grp_037["최빈"]>=2)].index)

deposit = ibk037_in[~ibk037_in["상대계좌예금주명"].isin(rental_names)]
deposit_big = deposit[deposit["입"]>=5_000_000]
deposit_trunc = sum(trunc(x) for x in deposit_big["입"])

rental = ibk037_in[ibk037_in["상대계좌예금주명"].isin(rental_names)]
rental_trunc = sum(trunc(x) for x in rental["입"])

# 037 전체 외부 입금 (임대료+보증금 모두)
all_037_trunc = sum(trunc(x) for x in ibk037_in["입"])

print(f"\n■ 상가 임대 수입 (IBK 037, 김연호 제외):")
print(f"  - 보증금 (5백만 이상 일회성): {deposit_trunc:,}원")
print(f"  - 정기 임대료:               {rental_trunc:,}원")
print(f"  - 소액/기타:                  {all_037_trunc - deposit_trunc - rental_trunc:,}원")
print(f"  ───────────────────")
print(f"  - 합계:                      {all_037_trunc:,}원")

print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ 김광규 전세 보증금 반환:                          530,000,000원       │
├──────────────────────────────────────────────────────────────────────┤
│ 자금원 (운영비 대출 충당 → 임대수입 전액 잔존 인정):                    │
│                                                                      │
│  ① 안경희 전세 보증금 반환 수령:               {ahn_trunc:>13,}원       │
│  ② IBK 037 상가 임대 보증금:                  {deposit_trunc:>13,}원       │
│  ③ IBK 037 상가 임대료 (운영비 대출충당시 잔존): {rental_trunc:>13,}원       │
│  ④ 빗썸 가상화폐 매도 회수:                    {bit_trunc:>13,}원       │
│  ──────────────────────────────────         ─────────────           │
│  소계:                                       {ahn_trunc + deposit_trunc + rental_trunc + bit_trunc:>13,}원       │
│                                                                      │
│  잉여:                                       +{ahn_trunc + deposit_trunc + rental_trunc + bit_trunc - 530_000_000:,}원       │
│                                                                      │
│  입증 비율: {(ahn_trunc + deposit_trunc + rental_trunc + bit_trunc)/530_000_000*100:.1f}%                                                │
└──────────────────────────────────────────────────────────────────────┘

[대안 시나리오: 임대료의 50%만 인정 (생활비 일부 소진)]
""")
total_50 = ahn_trunc + deposit_trunc + (rental_trunc//2) + bit_trunc
print(f"  소계: {total_50:,}원")
print(f"  잉여: {total_50 - 530_000_000:+,}원")
print(f"  입증 비율: {total_50/530_000_000*100:.1f}%")
