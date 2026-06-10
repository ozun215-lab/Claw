# -*- coding: utf-8 -*-
"""기업은행(IBK) 대출 거래 추적 — 대출 실행, 이자, 원금 상환"""
import os, sys
import pandas as pd
from datetime import timedelta
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv(r"D:\Claw\workspace\analysis\all_accounts_combined.csv", dtype=str).fillna("")
def n(s):
    s = str(s).replace(",","").strip()
    if s in ("","-","None","nan"): return 0
    try: return int(float(s))
    except: return 0
df["출"] = df.apply(lambda r: max(n(r["출금"]), n(r["출금_num"])), axis=1)
df["입"] = df.apply(lambda r: max(n(r["입금"]), n(r["입금_num"])), axis=1)
df["dt"] = pd.to_datetime(df["거래일시_dt"], errors="coerce")
df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

# === 1. 대출 관련 키워드 검색 ===
print("="*100)
print("【1단계: 대출 관련 키워드 입금 검색】")
print("="*100)
loan_keywords = ["대출", "차입", "loan", "기업은행"]
print("\n=== 거래내용/상대예금주명 키워드 매칭 입금 거래 ===")
for kw in loan_keywords:
    mask = pd.Series([False]*len(df))
    for c in ["거래내용","상대계좌예금주명","송금메시지","거래구분"]:
        if c in df.columns:
            mask = mask | df[c].astype(str).str.contains(kw, na=False, regex=False)
    hits = df[mask & (df["입"]>0) & (df["입"]>=1_000_000)]
    if len(hits)>0:
        print(f"\n--- '{kw}' 키워드 입금 {len(hits)}건 ---")
        for _, r in hits.iterrows():
            print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")

# === 2. 이자 출금 추적 (대출 이자는 정기적 출금) ===
print("\n" + "="*100)
print("【2단계: 정기 이자 출금 패턴 — 대출 보유 증거】")
print("="*100)
mask = pd.Series([False]*len(df))
for c in ["거래내용","상대계좌예금주명"]:
    mask = mask | df[c].astype(str).str.contains("이자", na=False, regex=False)
interest = df[mask & (df["출"]>0)].copy()
print(f"\n이자 출금 총 {len(interest)}건")
# 거래내용/상대로 그룹화
grp = interest.groupby("거래내용").agg(
    건수=("출","count"),
    합계=("출","sum"),
    평균=("출","mean"),
    최초=("dt","min"),
    최종=("dt","max")
).sort_values("건수", ascending=False)
print("\n=== 이자 출금 패턴 ===")
for desc, row in grp.iterrows():
    if row["건수"]>=1:
        print(f"  {desc:30s}  {int(row['건수']):>3}회  합 {int(row['합계']):>13,}  평균 {int(row['평균']):>10,}  {row['최초'].strftime('%Y-%m-%d')} ~ {row['최종'].strftime('%Y-%m-%d')}")

# === 3. IBK 자체 출금 거래 (대출 실행 시 IBK는 자체 송금자) ===
print("\n" + "="*100)
print("【3단계: IBK 기업은행 본점 또는 자체 입금 (대출 실행 후보)】")
print("="*100)
# 상대은행이 "기업은행"이고 상대예금주가 박영준이 아닌 경우 → 대출 가능성
ibk_loan = df[(df["상대은행"].astype(str).str.contains("기업|IBK", na=False, regex=True)) & 
              (df["입"]>0) & 
              (df["입"]>=10_000_000)].copy()
# 박영준 본인 이체는 제외
ibk_loan = ibk_loan[~ibk_loan["상대계좌예금주명"].str.contains("박영준", na=False)]
print(f"\n기업은행으로부터의 1천만원 이상 입금 (본인 이체 제외) {len(ibk_loan)}건:")
for _, r in ibk_loan.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]  메모:{r.get('송금메시지','')}")

# === 4. "원리금균등", "원리금", "대환", "상환" 출금 (대출 상환 흔적) ===
print("\n" + "="*100)
print("【4단계: 대출 상환/대환 거래 추적】")
print("="*100)
repay_kws = ["원리금","대환","상환","원금","월부금"]
for kw in repay_kws:
    mask = pd.Series([False]*len(df))
    for c in ["거래내용","상대계좌예금주명","거래구분"]:
        mask = mask | df[c].astype(str).str.contains(kw, na=False, regex=False)
    hits = df[mask & ((df["출"]>0)|(df["입"]>0))]
    if len(hits)>0:
        print(f"\n--- '{kw}' 매칭 거래 {len(hits)}건 ---")
        for _, r in hits.head(20).iterrows():
            sign = "+입금" if r["입"]>0 else "-출금"
            amt = r["입"] if r["입"]>0 else r["출"]
            print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")

# === 5. IBK 044 계좌 = 대출 또는 부동산 전용 계좌? ===
print("\n" + "="*100)
print("【5단계: IBK 044 계좌 성격 분석】")
print("="*100)
ibk044 = df[df["_계좌번호"]=="140-090845-01-044"].copy()
print(f"\nIBK 044 계좌 전체 거래: {len(ibk044)}건")
print(f"기간: {ibk044['dt'].min()} ~ {ibk044['dt'].max()}")
print(f"입금 합계: {ibk044['입'].sum():,}원")
print(f"출금 합계: {ibk044['출'].sum():,}원")

# === 6. 자기앞수표 발행/거래 (대출금 실행 시 자기앞수표로 받는 경우 多) ===
print("\n" + "="*100)
print("【6단계: 자기앞수표·CD 거래】")
print("="*100)
check_kws = ["수표","자기앞","CD","당좌","어음"]
for kw in check_kws:
    mask = pd.Series([False]*len(df))
    for c in ["거래내용","거래구분","상대계좌예금주명"]:
        mask = mask | df[c].astype(str).str.contains(kw, na=False, regex=False)
    hits = df[mask & ((df["출"]>=10_000_000)|(df["입"]>=10_000_000))]
    if len(hits)>0:
        print(f"\n--- '{kw}' 1천만원 이상 거래 {len(hits)}건 ---")
        for _, r in hits.head(20).iterrows():
            sign = "+입금" if r["입"]>0 else "-출금"
            amt = r["입"] if r["입"]>0 else r["출"]
            print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")
