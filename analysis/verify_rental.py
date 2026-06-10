# -*- coding: utf-8 -*-
"""대표님의 임대 수입 / 임대 보증금 정밀 추적"""
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

# === 정기 입금 패턴 = 월세/임대료 후보 (3건 이상 반복) ===
print("="*100)
print("【정기 입금 패턴 — 월세/임대료 후보】")
print("="*100)
# 1만원~500만원 사이 입금만 (월세 수준)
rent_range = df[(df["입"]>=100_000) & (df["입"]<=5_000_000)].copy()
EXCLUDE_NAMES = ["박영준","에이엑티브","CC","비바리퍼블리카","나이스페이","페이팔","쿠팡","우체국이","우편","SBI","NH카드","일성","BC"]
def is_kw(name, kws):
    return any(k in str(name) for k in kws)
rent_clean = rent_range[~rent_range["상대계좌예금주명"].apply(lambda x: is_kw(x, EXCLUDE_NAMES))]

# 상대예금주별 반복 패턴
grp = rent_clean.groupby("상대계좌예금주명").agg(
    건수=("입","count"),
    합계=("입","sum"),
    평균=("입","mean"),
    최초=("dt","min"),
    최종=("dt","max"),
    중복금액=("입", lambda x: x.value_counts().iloc[0] if len(x)>0 else 0)
).sort_values("건수", ascending=False)
# 3건 이상 + 평균이 비슷
recurring = grp[(grp["건수"]>=3)]
print(f"\n3회 이상 반복 입금 거래상대 ({len(recurring)}명):")
print(f"{'이름':25s} {'회수':>5s} {'합계':>15s} {'평균':>13s} {'최초':>12s} {'최종':>12s}")
for name, row in recurring.head(40).iterrows():
    if name and "박영준" not in str(name):
        print(f"{str(name)[:25]:25s} {int(row['건수']):>5}  {int(row['합계']):>15,} {int(row['평균']):>13,}  {row['최초'].strftime('%Y-%m-%d')}  {row['최종'].strftime('%Y-%m-%d')}")

# === 임대료 매출 사업자 패턴 — 같은 사람으로부터 매월 입금 ===
print("\n" + "="*100)
print("【월세/임대료 추정 자금원】")
print("="*100)
# 김연호 - 매월 22.5만원 패턴
khy = df[df["거래내용"].str.contains("김연호",na=False) | df["상대계좌예금주명"].str.contains("김연호",na=False)].copy()
khy = khy[khy["입"]>0].sort_values("dt")
print(f"\n김연호: 입금 {len(khy)}건")
for _, r in khy.iterrows():
    print(f"  {r['dt']:%Y-%m-%d}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 037 계좌의 1천만~5천만원 입금 (자금원 후보) ===
print("\n" + "="*100)
print("【IBK 037 계좌 1천만~5천만원 입금 — 부동산/임대 자금 후보】")
print("="*100)
ibk037 = df[df["_계좌번호"]=="140-090845-01-037"].copy()
mid_in = ibk037[(ibk037["입"]>=10_000_000) & (ibk037["입"]<=50_000_000)].sort_values("dt")
for _, r in mid_in.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 037 계좌의 큰 출금 (부동산 거래/세금) ===
print("\n" + "="*100)
print("【IBK 037 계좌 1천만원 이상 출금 — 부동산 거래 흔적】")
print("="*100)
out_037 = ibk037[ibk037["출"]>=10_000_000].sort_values("dt")
for _, r in out_037.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 김광규 송금 직전 7일 입금 (전체 계좌, BNK·이정훈·이승원·김수동 제외) ===
print("\n" + "="*100)
print("【최종: 김광규 송금 5.3억의 자금원 - IBK 037 통합 + 임시자금 제외】")
print("="*100)

kim = df[df["상대계좌예금주명"].str.contains("김광규",na=False) | df["거래내용"].str.contains("김광규",na=False)].copy()
kim = kim[kim["출"]>0].sort_values("dt").reset_index(drop=True)
total_kim = kim["출"].sum()
print(f"\n김광규 송금 총액: {total_kim:,}원")

# 자금원 항목별 누적
print(f"\n■ 안경희 전세 보증금 반환 (수령): +373,585,220원")
print(f"  - 박영준이 처음 안경희께 지급한 보증금: -37,000,000원 (2019, 본 자료에 포함된 분만)")
print(f"  ⚠ 실제 임차 시 지급한 전체 보증금이 본 자료에 다 잡히지 않음")
print(f"  → 안경희님과의 전세계약서/원본 자료 필요")

# 빗썸
bit_in_all = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] <= "2022-02-23")]["입"].sum()
bit_out_all = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["출"]>0) & (df["dt"] <= "2022-02-23")]["출"].sum()
print(f"\n■ 빗썸 가상화폐 거래:")
print(f"  매도 회수 누적: +{bit_in_all:,}원")
print(f"  매수 송금 누적: -{bit_out_all:,}원")
print(f"  순매수(보유): {bit_out_all-bit_in_all:,}원 (코인 보유)")
