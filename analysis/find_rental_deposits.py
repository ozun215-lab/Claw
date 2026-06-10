# -*- coding: utf-8 -*-
"""건물 임대 보증금으로 추정되는 입금 거래 탐색"""
import os, sys
import pandas as pd
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

# === 1. "보증금", "임대", "전세" 키워드 검색 ===
print("="*100)
print("【1단계: '보증금', '임대', '전세' 등 키워드 입금 거래】")
print("="*100)
keywords = ["보증금", "임대", "전세", "월세", "임차", "잔금"]
for kw in keywords:
    print(f"\n=== '{kw}' 검색 ===")
    mask = pd.Series([False]*len(df))
    for c in df.columns:
        if df[c].dtype == object:
            m = df[c].astype(str).str.contains(kw, na=False, regex=False)
            mask = mask | m
    hits = df[mask & (df["입"]>0)].copy()
    print(f"   입금 {len(hits)}건")
    for _, r in hits.iterrows():
        print(f"     {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")

# === 2. 안경희 외 큰 입금 (5천만원 이상, 김광규 송금 전까지) ===
print("\n" + "="*100)
print("【2단계: 5천만원 이상 큰 입금 (~ 2022-02-23, 안경희·BNK·이정훈·이승원·김수동 제외)】")
print("="*100)
big = df[(df["입"]>=50_000_000) & (df["dt"] <= "2022-02-23")].copy()
EXCLUDE = ["안경희","BNK","이정훈","이승원","김수동","빗썸","박영준"]
def is_exc(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE)
big_clean = big[~big.apply(is_exc, axis=1)]
print(f"\n{len(big_clean)}건:")
for _, r in big_clean.iterrows():
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]")

# === 3. 1천만원 이상 입금 — 미분류 (자금원 후보) ===
print("\n" + "="*100)
print("【3단계: 1천만원 이상 미분류 입금 — 자금원 후보】")
print("="*100)
mid = df[(df["입"]>=10_000_000) & (df["dt"] <= "2022-02-23")].copy()
mid_clean = mid[~mid.apply(is_exc, axis=1)]
# 추가 제외: 일상적 패턴
EXCLUDE2 = ["에이엑티브","급여","에이액티브","주식회사 에이","CC", "이자"]
def is_exc2(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE2)
mid_clean = mid_clean[~mid_clean.apply(is_exc2, axis=1)]
print(f"\n{len(mid_clean)}건 (큰순):")
mid_sorted = mid_clean.sort_values("입", ascending=False).head(30)
for _, r in mid_sorted.iterrows():
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} [{r['거래구분']}]  메모:{r.get('송금메시지','')}")

# === 4. 상대계좌번호별 큰 입금 패턴 (반복 입금 = 임대료 가능성) ===
print("\n" + "="*100)
print("【4단계: 동일 상대로부터의 반복 입금 패턴 (월세/임대료 후보)】")
print("="*100)
recur = df[(df["입"]>=500_000) & (df["입"]<10_000_000) & (df["dt"] <= "2022-02-23")].copy()
recur_clean = recur[~recur.apply(is_exc2, axis=1)]
# 상대계좌예금주명 또는 거래내용별 집계
grp = recur_clean.groupby("상대계좌예금주명").agg(
    건수=("입","count"),
    합계=("입","sum"),
    평균=("입","mean"),
    최초=("dt","min"),
    최종=("dt","max")
).sort_values("건수", ascending=False)
grp_filter = grp[(grp["건수"]>=3)]
print(f"\n3건 이상 반복 입금된 상대 {len(grp_filter)}명:")
for name, row in grp_filter.head(30).iterrows():
    if name and name != "" and "박영준" not in name:
        print(f"   {name:20s}  {row['건수']:>3}회  합 {int(row['합계']):>13,}  평균 {int(row['평균']):>10,}  {row['최초'].strftime('%Y-%m-%d')} ~ {row['최종'].strftime('%Y-%m-%d')}")

# === 5. 거래내용으로도 반복 패턴 ===
print("\n=== 거래내용 기준 반복 입금 패턴 ===")
grp2 = recur_clean.groupby("거래내용").agg(
    건수=("입","count"),
    합계=("입","sum"),
    평균=("입","mean")
).sort_values("건수", ascending=False)
for desc, row in grp2.head(20).iterrows():
    if desc and "박영준" not in str(desc) and "안경희" not in str(desc):
        print(f"   {desc:30s}  {row['건수']:>3}회  합 {int(row['합계']):>13,}  평균 {int(row['평균']):>10,}")
