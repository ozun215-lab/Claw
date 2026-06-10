# -*- coding: utf-8 -*-
"""IBK 037 계좌 추가 후 자금 출처 종합 재분석"""
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

# === 안경희 관련 거래 (037 추가 후) ===
print("="*100)
print("【안경희 관련 모든 거래 (IBK 037 포함, 양방향)】")
print("="*100)
ahn = df[df["거래내용"].str.contains("안경희",na=False) | df["상대계좌예금주명"].str.contains("안경희",na=False)].copy().sort_values("dt")
for _, r in ahn.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

ahn_out = ahn[ahn["출"]>0]["출"].sum()
ahn_in = ahn[ahn["입"]>0]["입"].sum()
print(f"\n안경희에게 출금(보증금 지급): {ahn_out:,}원")
print(f"안경희로부터 입금(보증금 반환): {ahn_in:,}원")
print(f"순(반환-지급): {ahn_in - ahn_out:+,}원")

# === 김연호 관련 거래 (037 추가 후) ===
print("\n" + "="*100)
print("【김연호 관련 모든 거래】")
print("="*100)
khy = df[df["거래내용"].str.contains("김연호",na=False) | df["상대계좌예금주명"].str.contains("김연호",na=False)].copy().sort_values("dt")
for _, r in khy.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 037 계좌 큰 입금 (5천만원 이상) ===
print("\n" + "="*100)
print("【IBK 037 계좌 + 다른 계좌, 5천만원 이상 입금 — 자금원 후보】")
print("="*100)
big = df[(df["입"]>=50_000_000) & (df["dt"] <= "2022-02-23")].sort_values("dt")
EXCLUDE = ["BNK","이정훈","이승원","김수동","빗썸","박영준","박상호","에이엑티브","급여","상여","이자"]
def is_exc(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE)
big_clean = big[~big.apply(is_exc, axis=1)]
print(f"\n총 {len(big_clean)}건 (5천만원 이상, 임시자금/빗썸/본인 제외):")
for _, r in big_clean.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 임대 보증금 패턴: 부동산 거래 키워드 ===
print("\n" + "="*100)
print("【부동산 거래 키워드 (보증금, 계약금, 잔금, 임대료) 거래 — 양방향】")
print("="*100)
re_kws = ["계약금","잔금","보증금","임대료","임차","월세","전세","오연부가","부가가치"]
hits_all = pd.DataFrame()
for kw in re_kws:
    mask = pd.Series([False]*len(df))
    for c in df.columns:
        if df[c].dtype == object:
            mask = mask | df[c].astype(str).str.contains(kw, na=False, regex=False)
    sub = df[mask].copy()
    if len(sub)>0:
        sub["키워드"] = kw
        hits_all = pd.concat([hits_all, sub])
hits_all = hits_all.drop_duplicates(subset=["dt","_계좌번호","출","입","거래내용"]).sort_values("dt")
print(f"\n총 {len(hits_all)}건:")
for _, r in hits_all.iterrows():
    sign = "+입금" if r["입"]>0 else "-출금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}] [{r.get('키워드','')}]")

# === 037 계좌의 자금 흐름 요약 ===
print("\n" + "="*100)
print("【IBK 037 계좌 → 다른 계좌(012/044/농협) 이체 (자금 모음)】")
print("="*100)
ibk037_out = df[(df["_계좌번호"]=="140-090845-01-037") & (df["출"]>=1_000_000)].copy()
to_self = ibk037_out[ibk037_out["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True)]
print(f"\n037 → 본인 다른 계좌 이체 {len(to_self)}건:")
for _, r in to_self.sort_values("dt").iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌번호']}")
print(f"\n037 → 본인계좌 이체 누계: {to_self['출'].sum():,}원")

ibk037_in = df[(df["_계좌번호"]=="140-090845-01-037") & (df["입"]>=1_000_000)].copy()
from_self = ibk037_in[ibk037_in["상대계좌번호"].astype(str).str.contains("90845|3479", na=False, regex=True) | 
                     ibk037_in["상대계좌예금주명"].astype(str).str.contains("박영준", na=False)]
print(f"\n037 ← 본인 다른 계좌 입금 {len(from_self)}건:")
for _, r in from_self.sort_values("dt").iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌번호']} / {r['상대계좌예금주명']}")
print(f"\n037 ← 본인계좌 입금 누계: {from_self['입'].sum():,}원")

# === 김광규 송금에 사용된 자금원 종합 (037 포함) ===
print("\n" + "="*100)
print("【최종 자금원 종합 — IBK 037 포함】")
print("="*100)

# 1. 안경희 전세보증금 (반환받음)
ahn_in_total = ahn[ahn["입"]>0]["입"].sum()
# 2. 안경희에게 보증금 지급 (당시 임차하면서)
ahn_out_total = ahn[ahn["출"]>0]["출"].sum()
# 3. 빗썸 회수
bit_in = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] <= "2022-02-23")]["입"].sum()
# 4. 김연호 (부동산 관련 가능성)
khy_in = khy[khy["입"]>0]["입"].sum()
khy_out = khy[khy["출"]>0]["출"].sum()

print(f"\n■ 안경희님 (이전 임대인) 거래:")
print(f"  안경희께 보증금 지급:    -{ahn_out_total:,}원 (2019, 임차 시작)")
print(f"  안경희로부터 반환받음:   +{ahn_in_total:,}원 (2021, 임차 종료)")
print(f"  순수익 (반환-지급):       {ahn_in_total-ahn_out_total:+,}원")
print(f"\n■ 김연호님 거래:")
print(f"  김연호로부터 입금:       +{khy_in:,}원")
print(f"  김연호께 출금:           -{khy_out:,}원")
print(f"\n■ 빗썸 가상화폐 회수 (~2022-02-23): +{bit_in:,}원")
