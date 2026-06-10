# -*- coding: utf-8 -*-
"""안경희 입금 → 김광규 송금 자금 흐름 추적 (FIFO 모형)"""
import os, sys
import pandas as pd
from datetime import datetime, timedelta
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

# === 안경희 입금 추적 ===
print("="*100)
print("【안경희 → 박영준 입금: 2021년 1~5월 총 3.74억원】")
print("【김광규 송금: 2021-12 ~ 2022-02 총 5.30억원】")
print("="*100)

# IBK 012 계좌의 안경희 입금 시점부터 2022-02-23까지 자금 흐름
# 핵심: 012 계좌는 안경희 입금 후 매우 빠르게 044/037/농협으로 자금을 분배함

# 안경희 입금 직후 (당일 ~ 2일) 어디로 자금이 흘러갔는지 추적
ahn_in = df[(df["거래내용"].str.contains("안경희",na=False) | df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)].sort_values("dt").reset_index(drop=True)

print("\n=== 각 안경희 입금 직후 1일 이내 IBK 012의 큰 출금 → 어디로 이동? ===")
for _, ar in ahn_in.iterrows():
    print(f"\n▶ {ar['dt']:%Y-%m-%d %H:%M} 안경희 +{ar['입']:,}원 (IBK 012)")
    after = df[(df["_계좌번호"]=="140-090845-01-012") & 
               (df["dt"] > ar["dt"]) & 
               (df["dt"] <= ar["dt"]+timedelta(days=3)) & 
               (df["출"]>=1_000_000)].sort_values("dt")
    moved = 0
    for _, r in after.iterrows():
        # 본인 계좌(044/037/020/농협)로 간 것만 별표
        is_self = ("90845" in str(r["상대계좌번호"]) or 
                   "3479" in str(r["상대계좌번호"]) or
                   "박영준" in str(r["상대계좌예금주명"]))
        marker = " ← 본인 다른계좌" if is_self else ""
        if is_self:
            moved += r["출"]
        print(f"   -{r['출']:>13,} ({r['거래내용']}) → {r['상대계좌예금주명']} {r['상대은행']} {r['상대계좌번호']}{marker}")
    print(f"   * 본인 다른 계좌로 이동: {moved:,}원")

# === 농협 계좌 잔액 추이 (안경희 입금 시점부터 김광규 송금까지) ===
print("\n" + "="*100)
print("【핵심: 안경희 자금이 농협으로 이동 → 농협 잔액이 어떻게 유지됐나?】")
print("="*100)

# 농협 계좌의 큰 입금 (2021년 1월 ~ 2022년 2월)
nh = df[(df["_은행"]=="농협") & (df["dt"] >= "2021-01-01") & (df["dt"] <= "2022-02-24")].copy()
big_in = nh[nh["입"]>=10_000_000].sort_values("dt")
print(f"\n농협 계좌 1천만원 이상 입금 {len(big_in)}건 (2021.01 ~ 2022.02):")
total_nh_in = 0
for _, r in big_in.iterrows():
    src = r["거래내용"] or r["상대계좌예금주명"]
    total_nh_in += r["입"]
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ← {src}  [{r['거래구분']}]  잔액 {n(r['잔액']):>13,}")
print(f"\n농협 큰 입금 합계: {total_nh_in:,}원")

# 농협 큰 출금 (전세자금/김광규 송금 자금 흐름)
print("\n농협 1천만원 이상 출금 (2021.01 ~ 2022.02):")
big_out = nh[nh["출"]>=10_000_000].sort_values("dt")
total_nh_out = 0
for _, r in big_out.iterrows():
    total_nh_out += r["출"]
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  → {r['거래내용']}  [{r['거래구분']}]  잔액 {n(r['잔액']):>13,}")
print(f"\n농협 큰 출금 합계: {total_nh_out:,}원")

# === 자금원 재구성 (FIFO 가정) ===
print("\n" + "="*100)
print("【자금 흐름 재구성: 안경희 → 농협 → IBK 044 → 김광규】")
print("="*100)

# 안경희 자금이 IBK 012로 들어온 후, 본인 다른 계좌로 이체된 금액
ahn_total = ahn_in["입"].sum()
print(f"\n1단계: 안경희 → 박영준 IBK 012 입금 = {ahn_total:,}원")

# 012 → 044 이체 (안경희 입금 직후)
to_044 = df[(df["_계좌번호"]=="140-090845-01-012") & 
            (df["출"]>0) &
            (df["상대계좌번호"].str.contains("090845.*044|01.044",na=False, regex=True))].copy()
to_044 = to_044[(to_044["dt"] >= "2021-01-30") & (to_044["dt"] <= "2022-02-24")]
print(f"\n2단계: IBK 012 → IBK 044 이체 (2021.01.30 ~ 2022.02.23):")
sum_to_044 = 0
for _, r in to_044.iterrows():
    sum_to_044 += r["출"]
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  → {r['상대계좌번호']}")
print(f"   소계: {sum_to_044:,}원")

# 012 → 농협 이체
to_nh = df[(df["_계좌번호"]=="140-090845-01-012") & 
           (df["출"]>0) &
           (df["상대계좌번호"].str.contains("3479",na=False))].copy()
to_nh = to_nh[(to_nh["dt"] >= "2021-01-30") & (to_nh["dt"] <= "2022-02-24")]
print(f"\n3단계: IBK 012 → 농협 이체 (2021.01.30 ~ 2022.02.23):")
sum_to_nh = 0
for _, r in to_nh.iterrows():
    sum_to_nh += r["출"]
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  → {r['상대계좌번호']}")
print(f"   소계: {sum_to_nh:,}원")

# === 결론: 안경희 자금이 김광규에 도달했는지 검증 ===
print("\n" + "="*100)
print("【결론】")
print("="*100)
print(f"""
○ 안경희 → 박영준 입금 시점:  2021-01-30 ~ 2021-05-28 (총 {ahn_total:,}원)
○ 박영준 → 김광규 송금 시점:  2021-12-28 ~ 2022-02-23 (총 530,000,000원)

  → 안경희 자금 도착 후 김광규 송금까지 약 7~13개월 간격.
  → 그 사이 박영준 계좌들(012/044/농협)에서 다수의 거래 발생.
  → "안경희 자금이 김광규 송금에 사용됐다"고 직접 연결되는 거래는 없음.
  → 다만, 안경희 자금이 IBK 012 → IBK 044/농협으로 분산 이체되어
     해당 계좌들의 자금 풀(pool)에 합쳐진 후, 그 풀에서 김광규 송금이 이뤄졌을 가능성은 있음.

  ※ 자금 추적은 FIFO/LIFO/평균 등 회계 가정에 따라 결과가 달라집니다.
""")
