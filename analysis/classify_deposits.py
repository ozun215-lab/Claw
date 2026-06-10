# -*- coding: utf-8 -*-
"""IBK 전체 계좌에서 임대차 보증금 자금 분류
   - 일회성 큰 금액 (1천만원 이상)
   - 반복 패턴이 아닌 거래 (월세 제외)
   - 거래 적요/패턴 분석
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

# IBK 모든 계좌 데이터
ibk = df[df["_은행"]=="IBK기업"].copy()
print(f"IBK 전체: {len(ibk)}건 (4개 계좌)")
print(f"  012(주거래): {len(ibk[ibk['_계좌번호']=='140-090845-01-012'])}건")
print(f"  020:        {len(ibk[ibk['_계좌번호']=='140-090845-01-020'])}건")
print(f"  037(상가):   {len(ibk[ibk['_계좌번호']=='140-090845-01-037'])}건")
print(f"  044(전세):   {len(ibk[ibk['_계좌번호']=='140-090845-01-044'])}건")

# === 정기 임대료 패턴 식별 (제외용) ===
# 같은 사람으로부터 3건 이상 + 동일 금액 2회 이상 = 임대료
def get_rental_names(df_acct):
    grp = df_acct.groupby("상대계좌예금주명").agg(
        건수=("입","count"),
        최빈빈도=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0),
    ).reset_index()
    return set(grp[(grp["건수"]>=3) & (grp["최빈빈도"]>=2)]["상대계좌예금주명"])

ibk_in_all = ibk[ibk["입"]>0]
rental_names = get_rental_names(ibk_in_all)
print(f"\n임대료 패턴 거래자 (제외 대상): {len(rental_names)}명")
for n in sorted(rental_names): print(f"  - {n}")

# === 1. 1천만원 이상 일회성 입금 (수령 보증금 후보) ===
print("\n" + "="*100)
print("【수령 보증금 후보 — 1천만원 이상 일회성 입금】")
print("="*100)
EXCLUDE_KW = ["박영준","BNK","이정훈","이승원","김수동","박상호","빗썸","에이엑티브","급여","상여","이자","CC","비바리퍼블리카","SBI","NH카드"]
def is_exc(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE_KW)

# 김연호 / 안경희도 별도 표시 후 분류
# 임대료 패턴 거래자 제외
big_in = ibk[(ibk["입"]>=10_000_000)].copy()
big_in_clean = big_in[~big_in.apply(is_exc, axis=1)]
big_in_clean = big_in_clean[~big_in_clean["상대계좌예금주명"].isin(rental_names)]

# 본인 이체 제외
big_in_clean = big_in_clean[~big_in_clean["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]

print(f"\n계좌별 1천만원 이상 일회성 입금 (임시자금/임대료/본인이체 제외):")
total_deposit_in = 0
deposits_in = []
for acct in ["140-090845-01-012","140-090845-01-020","140-090845-01-037","140-090845-01-044"]:
    sub = big_in_clean[big_in_clean["_계좌번호"]==acct].sort_values("dt")
    if len(sub)==0: continue
    print(f"\n--- IBK {acct} ({len(sub)}건) ---")
    for _, r in sub.iterrows():
        is_ahn = "안경희" in str(r["상대계좌예금주명"]) or "안경희" in str(r["거래내용"])
        is_khy = "김연호" in str(r["상대계좌예금주명"]) or "김연호" in str(r["거래내용"])
        marker = ""
        if is_ahn: marker = " ★안경희(임대인→대표님)"
        elif is_khy: marker = " ⚠김연호(배제)"
        print(f"  {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]{marker}")
        if not is_khy:
            total_deposit_in += r["입"]
            deposits_in.append(r)

print(f"\n총 수령 보증금 후보 (김연호 제외): {total_deposit_in:,}원")

# === 2. 1천만원 이상 큰 출금 — 반환 보증금 / 지급 보증금 ===
print("\n" + "="*100)
print("【보증금 지급/반환 후보 — 1천만원 이상 큰 출금】")
print("="*100)
big_out = ibk[(ibk["출"]>=10_000_000)].copy()
big_out_clean = big_out[~big_out.apply(is_exc, axis=1)]
big_out_clean = big_out_clean[~big_out_clean["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
# 김광규 송금 제외
big_out_clean = big_out_clean[~big_out_clean["상대계좌예금주명"].str.contains("김광규",na=False)]

print(f"\n계좌별 1천만원 이상 큰 출금 (김광규/김연호/임시자금/본인이체 제외):")
for acct in ["140-090845-01-012","140-090845-01-020","140-090845-01-037","140-090845-01-044"]:
    sub = big_out_clean[big_out_clean["_계좌번호"]==acct].sort_values("dt")
    if len(sub)==0: continue
    print(f"\n--- IBK {acct} ({len(sub)}건) ---")
    for _, r in sub.iterrows():
        is_ahn = "안경희" in str(r["상대계좌예금주명"]) or "안경희" in str(r["거래내용"])
        marker = ""
        if is_ahn: marker = " ★안경희(대표님→임대인 보증금 지급)"
        print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]{marker}")

# === 3. 보증금 키워드 거래 (적요에 "보증금","계약금","임대" 포함) ===
print("\n" + "="*100)
print("【적요 키워드 매칭: '보증금', '계약금', '임대', '잔금' 거래】")
print("="*100)
kws = ["보증금","계약금","임대","잔금","임차"]
mask = pd.Series([False]*len(ibk))
for kw in kws:
    for c in ["거래내용","상대계좌예금주명","송금메시지"]:
        if c in ibk.columns:
            mask = mask | ibk[c].astype(str).str.contains(kw, na=False, regex=False)
hits = ibk[mask].sort_values("dt")
print(f"\n총 {len(hits)}건:")
for _, r in hits.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}")

# === 4. 종합: 임대차 보증금 분류표 ===
print("\n" + "="*100)
print("【종합: IBK 계좌의 임대차 보증금 분류】")
print("="*100)

# 카테고리별 합산 (백만원 절삭)
categories = {
    "① 안경희 → 박영준 (이전 임대인의 보증금 반환)": [],
    "② 박영준 → 안경희 (본인 임차 시 보증금 지급)": [],
    "③ 037 상가 임차인 → 박영준 (상가 임대 보증금 수령)": [],
    "④ 박영준 → 상가 보증금 반환 또는 기타 지급": [],
}

# ① 안경희로부터 받은 입금
ahn_in = ibk[(ibk["거래내용"].str.contains("안경희",na=False) | ibk["상대계좌예금주명"].str.contains("안경희",na=False)) & (ibk["입"]>0)]
for _, r in ahn_in.iterrows():
    categories["① 안경희 → 박영준 (이전 임대인의 보증금 반환)"].append(r)

# ② 안경희에게 송금
ahn_out = ibk[(ibk["거래내용"].str.contains("안경희",na=False) | ibk["상대계좌예금주명"].str.contains("안경희",na=False)) & (ibk["출"]>0)]
for _, r in ahn_out.iterrows():
    categories["② 박영준 → 안경희 (본인 임차 시 보증금 지급)"].append(r)

# ③ 037 계좌 입금 중 보증금으로 추정 (1천만원 이상 일회성, 임대료 패턴 제외)
ibk037_in_big = ibk[(ibk["_계좌번호"]=="140-090845-01-037") & (ibk["입"]>=5_000_000)].copy()
ibk037_in_big = ibk037_in_big[~ibk037_in_big["상대계좌예금주명"].isin(rental_names)]
ibk037_in_big = ibk037_in_big[~ibk037_in_big["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_in_big = ibk037_in_big[~ibk037_in_big["상대계좌예금주명"].str.contains("박영준|김연호", na=False)]
for _, r in ibk037_in_big.iterrows():
    categories["③ 037 상가 임차인 → 박영준 (상가 임대 보증금 수령)"].append(r)

# ④ 037 계좌 큰 출금 (반환 또는 지급)
ibk037_out_big = ibk[(ibk["_계좌번호"]=="140-090845-01-037") & (ibk["출"]>=5_000_000)].copy()
ibk037_out_big = ibk037_out_big[~ibk037_out_big["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
ibk037_out_big = ibk037_out_big[~ibk037_out_big["상대계좌예금주명"].str.contains("박영준|안경희", na=False)]
for _, r in ibk037_out_big.iterrows():
    categories["④ 박영준 → 상가 보증금 반환 또는 기타 지급"].append(r)

# 출력
for cat, rows in categories.items():
    if not rows: continue
    print(f"\n{cat}:")
    total = 0
    total_trunc = 0
    for r in rows:
        amt = r["입"] if r["입"]>0 else r["출"]
        sign = "+" if r["입"]>0 else "-"
        print(f"  {r['dt']:%Y-%m-%d}  {sign}{amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['_계좌번호'][-3:]}]")
        total += amt
        total_trunc += truncate_mil(amt)
    print(f"  소계: {total:,}원 (절삭: {total_trunc:,}원)")

# === 최종 요약 ===
print("\n" + "="*100)
print("【최종 요약: 임대차 보증금 분류 (백만원 절삭)】")
print("="*100)

ahn_in_trunc = sum(truncate_mil(r["입"]) for r in categories["① 안경희 → 박영준 (이전 임대인의 보증금 반환)"])
ahn_out_trunc = sum(truncate_mil(r["출"]) for r in categories["② 박영준 → 안경희 (본인 임차 시 보증금 지급)"])
shop_in_trunc = sum(truncate_mil(r["입"]) for r in categories["③ 037 상가 임차인 → 박영준 (상가 임대 보증금 수령)"])
shop_out_trunc = sum(truncate_mil(r["출"]) for r in categories["④ 박영준 → 상가 보증금 반환 또는 기타 지급"])

print(f"""
[A] 박영준 대표님 거주 관련 (안경희 임대차):
   ① 안경희로부터 보증금 반환 수령:    +{ahn_in_trunc:>13,}원
   ② 안경희께 보증금 지급 (2019):     -{ahn_out_trunc:>13,}원
   순수익(반환-지급):                  {ahn_in_trunc-ahn_out_trunc:>+13,}원
   ⚠ 지급액({ahn_out_trunc:,})이 반환액({ahn_in_trunc:,})보다 작음
     → 지급 시 본 자료에 없는 다른 계좌나 시점에서 추가 지급 가능성 있음

[B] 상가 임대 사업 (IBK 037):
   ③ 상가 임차인으로부터 보증금 수령:   +{shop_in_trunc:>13,}원
   ④ 상가 보증금 반환/기타 지급:       -{shop_out_trunc:>13,}원
   순수익:                            {shop_in_trunc-shop_out_trunc:>+13,}원

[C] 김광규 거래 (별도 - 매입 아파트):
   김광규께 보증금 반환:               -530,000,000원

총 임대차 보증금 순흐름:
   = (A순수익) + (B순수익) - (김광규 반환)
   = {(ahn_in_trunc-ahn_out_trunc) + (shop_in_trunc-shop_out_trunc) - 530_000_000:+,}원
""")
