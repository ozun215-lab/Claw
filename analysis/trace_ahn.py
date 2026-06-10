# -*- coding: utf-8 -*-
"""안경희 입금 추적 + 김광규 자금 연결 (BNK·이정훈 제외)"""
import os, sys, pandas as pd
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

# === 안경희 검색 (모든 컬럼) ===
print("="*100)
print("【안경희 검색】")
print("="*100)
mask = pd.Series([False]*len(df))
hit_cols = []
for c in df.columns:
    m = df[c].astype(str).str.contains("안경희", na=False, regex=False)
    if m.any():
        hit_cols.append((c, m.sum()))
    mask = mask | m
print(f"hit columns: {hit_cols}")
ahn = df[mask].copy().sort_values("dt").reset_index(drop=True)
print(f"\n안경희 관련 거래 총 {len(ahn)}건\n")
for _, r in ahn.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']:5}{r['_계좌번호'][-3:]}]  출 {r['출']:>13,}  입 {r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}  [{r['거래구분']}]")

# 통계
in_ahn = ahn[ahn["입"]>0]
out_ahn = ahn[ahn["출"]>0]
print(f"\n안경희로부터 입금: {len(in_ahn)}건 / 총 {in_ahn['입'].sum():,}원")
print(f"안경희에게 출금: {len(out_ahn)}건 / 총 {out_ahn['출'].sum():,}원")

# 김광규 송금 시점
kim = df[df["상대계좌예금주명"].str.contains("김광규",na=False) | df["거래내용"].str.contains("김광규",na=False)].copy()
kim = kim[kim["출"]>0].sort_values("dt").reset_index(drop=True)

# === 안경희 입금과 김광규 송금의 시간차 ===
print("\n" + "="*100)
print("【안경희 입금 ↔ 김광규 송금 시간 차이】")
print("="*100)
for _, kr in kim.iterrows():
    print(f"\n▶ 김광규 송금 {kr['dt']:%Y-%m-%d %H:%M}  {kr['출']:,}원  [{kr['_계좌번호']}]")
    # 안경희로부터 송금 시점 직전 60일 이내 입금
    win = in_ahn[(in_ahn["dt"] <= kr["dt"]) & (in_ahn["dt"] >= kr["dt"] - timedelta(days=180))]
    if len(win) == 0:
        print("   직전 180일 이내 안경희 입금 없음")
    else:
        for _, ar in win.iterrows():
            delta = kr["dt"] - ar["dt"]
            print(f"   ← 안경희 {ar['dt']:%Y-%m-%d %H:%M}  +{ar['입']:>13,}원 ({delta.days}일 전, {ar['_은행']} {ar['_계좌번호']}) [{ar['거래구분']}]")

# === 안경희 입금 전후 자금 흐름 ===
print("\n" + "="*100)
print("【각 안경희 입금 직후 큰 출금 (자금 사용처 추적)】")
print("="*100)
for _, ar in in_ahn.iterrows():
    print(f"\n▶ 안경희 입금 {ar['dt']:%Y-%m-%d %H:%M}  +{ar['입']:,}원  [{ar['_은행']} {ar['_계좌번호']}]")
    # 입금 후 30일 이내, 같은 계좌의 100만원 이상 출금
    after = df[(df["_계좌번호"]==ar["_계좌번호"]) & 
               (df["dt"] >= ar["dt"]) & 
               (df["dt"] <= ar["dt"]+timedelta(days=30)) & 
               (df["출"]>=1_000_000)].sort_values("dt")
    print(f"   직후 30일 100만원 이상 출금 {len(after)}건:")
    for _, r in after.iterrows():
        days = (r["dt"] - ar["dt"]).days
        print(f"     {r['dt']:%m-%d %H:%M} ({days}일후)  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === BNK·이정훈 제외한 자금원 재집계 (2022-02-23 송금 4.8억 직전 7일) ===
print("\n" + "="*100)
print("【BNK·이정훈 제외한 자금원 — 2022년 송금 직전 7일 외부 입금】")
print("="*100)
exclude = ["BNK", "이정훈"]
for _, kr in kim.iterrows():
    sdt = kr["dt"]
    samt = kr["출"]
    print(f"\n▶ 송금 {sdt:%Y-%m-%d %H:%M} {samt:,}원")
    w = df[(df["dt"] >= sdt-timedelta(days=7)) & (df["dt"] <= sdt) & (df["입"] >= 1_000_000)].copy()
    # exclude 키워드 검사 (거래내용, 상대예금주명)
    for ex in exclude:
        w = w[~w["거래내용"].str.contains(ex, na=False, regex=False)]
        w = w[~w["상대계좌예금주명"].str.contains(ex, na=False, regex=False)]
    # 추가로 본인이체(박영준/빛없박영준)는 자금 흐름 합치므로 표시는 하되 별표
    print(f"   외부 자금 후보 ({len(w)}건):")
    for _, r in w.sort_values("dt").iterrows():
        owner = r["상대계좌예금주명"] or r["거래내용"]
        own_flag = "*본인이체" if "박영준" in owner or "빛없" in owner else ""
        print(f"     {r['dt']:%m-%d %H:%M} [{r['_은행']:5}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {owner} {own_flag}")
