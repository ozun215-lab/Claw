# -*- coding: utf-8 -*-
"""빗썸 거래 배제 + 자금 출처 재검증"""
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

# === 자금원 재계산 (빗썸 완전 배제) ===

# 안경희
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)]
ahn_trunc = sum(trunc(x) for x in ahn["입"])

# 037 외부 입금 (김연호·빗썸·본인이체 제외)
ibk037_in = df[(df["_계좌번호"]=="140-090845-01-037") & (df["입"]>0) & (df["dt"]<=pd.Timestamp("2022-02-23"))].copy()
ibk037_in = ibk037_in[~ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)]
ibk037_in = ibk037_in[~ibk037_in["상대계좌예금주명"].astype(str).str.contains("김연호", na=False)]
ibk037_in = ibk037_in[~ibk037_in["거래내용"].astype(str).str.contains("김연호", na=False)]
ibk037_in = ibk037_in[~ibk037_in["거래내용"].astype(str).str.contains("빗썸", na=False)]

# 정기 임대료 vs 보증금 분리
grp = ibk037_in.groupby("상대계좌예금주명").agg(건수=("입","count"), 최빈=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0))
rental_names = set(grp[(grp["건수"]>=3) & (grp["최빈"]>=2)].index)

deposit_big = ibk037_in[(~ibk037_in["상대계좌예금주명"].isin(rental_names)) & (ibk037_in["입"]>=5_000_000)]
deposit_trunc = sum(trunc(x) for x in deposit_big["입"])

rental = ibk037_in[ibk037_in["상대계좌예금주명"].isin(rental_names)]
rental_trunc = sum(trunc(x) for x in rental["입"])

print("="*100)
print("【빗썸 거래 완전 배제 후 자금 출처 시나리오】")
print("="*100)

scenarios = [
    ("시나리오 A: 보수적 (보증금만)", ahn_trunc + deposit_trunc),
    ("시나리오 B: 표준 (보증금 + 임대료 50%)", ahn_trunc + deposit_trunc + rental_trunc//2),
    ("시나리오 C: 적극 (보증금 + 임대료 100% / 운영비 대출충당 인정)", ahn_trunc + deposit_trunc + rental_trunc),
]

for name, total in scenarios:
    pct = total / 530_000_000 * 100
    gap = total - 530_000_000
    status = "✅ 입증 가능" if total >= 530_000_000 else "⚠ 부족"
    print(f"\n■ {name}")
    print(f"  자금원 합계: {total:>13,}원")
    print(f"  입증 비율: {pct:>5.1f}%")
    print(f"  {'잉여' if gap>=0 else '부족'}: {gap:>+13,}원  →  {status}")

print(f"""
─── 자금원 상세 ──────────────────
  ① 안경희 전세 보증금 반환 수령:       {ahn_trunc:>13,}원
  ② IBK 037 상가 임대 보증금:           {deposit_trunc:>13,}원
  ③ IBK 037 상가 임대료 (정기 패턴):     {rental_trunc:>13,}원
  ④ IBK 037 소액/기타 (참고):          {sum(trunc(x) for x in ibk037_in['입']) - deposit_trunc - rental_trunc:>13,}원

──────────────────────────────
배제 항목:
  ❌ BNK캐피탈, 이정훈, 이승원, 김수동 (임시자금)
  ❌ 박상호 (임시자금)
  ❌ 김연호 (배제 요청)
  ❌ 빗썸 가상화폐 거래 (배제 요청 — 가상자산 별도 이슈)
  ❌ 급여 (생활비 소진)
""")

# === 부족시 추가 자금원 후보 탐색 ===
print("="*100)
print("【부족시 추가 자금원 후보 — 5백만원 이상 분류되지 않은 입금】")
print("="*100)
EXCLUDE = ["박영준","BNK","이정훈","이승원","김수동","박상호","빗썸","에이엑티브","급여","상여","이자","CC","비바리퍼블리카","SBI","NH카드","안경희","김연호"]
def is_exc(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE)

big_unknown = df[(df["입"]>=5_000_000) & (df["dt"] <= "2022-02-23")].copy()
big_unknown = big_unknown[~big_unknown.apply(is_exc, axis=1)]
big_unknown = big_unknown[~big_unknown["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
print(f"\n총 {len(big_unknown)}건의 미분류 5백만원 이상 입금:")
for _, r in big_unknown.sort_values("dt").iterrows():
    # 임시자금 검증
    after = df[(df["_계좌번호"]==r["_계좌번호"]) & 
               (df["dt"] > r["dt"]) & 
               (df["dt"] <= r["dt"]+pd.Timedelta(days=30)) & 
               (df["출"] > 0)]
    matched = after[(after["출"] >= r["입"]*0.9) & (after["출"] <= r["입"]*1.1)]
    flag = ""
    if len(matched)>0:
        m = matched.iloc[0]
        flag = f" 🔴 임시(d+{(m['dt']-r['dt']).days})"
    else:
        flag = " ✅ 잔존"
    print(f"  {r['dt']:%Y-%m-%d}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]{flag}")
