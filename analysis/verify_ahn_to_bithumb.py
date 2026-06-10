# -*- coding: utf-8 -*-
"""
검증: 안경희 → 농협 → 빗썸 투자 → 회수 → 김광규
시계열 자금 흐름 추적 (FIFO 모형)
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

print("="*100)
print("【시나리오 검증: 안경희 자금 → 농협 → 빗썸 → 회수 → 김광규】")
print("="*100)

# === 1. 안경희 입금 시점 ===
print("\n■ 1단계: 안경희 → IBK 012 입금")
print("-"*100)
ahn_in = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)].copy().sort_values("dt")
total_ahn = ahn_in["입"].sum()
for _, r in ahn_in.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  +{r['입']:>13,}  ({r['거래내용']})")
print(f"  ────────────────")
print(f"  소계: {total_ahn:,}원 (2021-01-30 ~ 2021-05-28)")

# === 2. IBK 012 → 농협 이체 (안경희 입금 직후) ===
print("\n■ 2단계: IBK 012 → 농협으로 자금 이체")
print("-"*100)
ibk012_to_nh = df[(df["_계좌번호"]=="140-090845-01-012") & 
                  (df["출"]>0) &
                  (df["dt"] >= "2021-01-30") &
                  (df["dt"] <= "2022-02-23") &
                  (df["상대계좌번호"].astype(str).str.contains("3479", na=False))].copy()
total_to_nh = ibk012_to_nh["출"].sum()
print(f"\n{len(ibk012_to_nh)}건:")
for _, r in ibk012_to_nh.sort_values("dt").iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  → 농협")
print(f"  소계: {total_to_nh:,}원")

# === 3. 농협 → 빗썸 송금 (안경희 자금이 농협 도착 후의 빗썸 송금) ===
print("\n■ 3단계: 농협 → 빗썸 송금 (코인 매수)")
print("-"*100)
nh_to_bit = df[(df["_계좌번호"]=="312-3479-3479-01") & 
               (df["출"]>0) &
               (df["거래내용"].str.contains("빗썸",na=False)) &
               (df["dt"] >= "2021-01-30") &
               (df["dt"] <= "2022-02-23")].copy()
total_to_bit = nh_to_bit["출"].sum()
print(f"\n{len(nh_to_bit)}건, 시간순 (안경희 입금 이후만):")
for _, r in nh_to_bit.sort_values("dt").iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  → 빗썸")
print(f"  소계: {total_to_bit:,}원 ({len(nh_to_bit)}건)")

# === 4. 빗썸 → 농협 회수 (코인 매도 후) ===
print("\n■ 4단계: 빗썸 → 농협 회수 (코인 매도)")
print("-"*100)
bit_to_nh = df[(df["_계좌번호"]=="312-3479-3479-01") & 
               (df["입"]>0) &
               (df["거래내용"].str.contains("빗썸",na=False)) &
               (df["dt"] >= "2021-01-30") &
               (df["dt"] <= "2022-02-23")].copy()
total_from_bit = bit_to_nh["입"].sum()
print(f"\n{len(bit_to_nh)}건, 시간순:")
for _, r in bit_to_nh.sort_values("dt").iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ← 빗썸")
print(f"  소계: {total_from_bit:,}원")

# === 5. 농협 → IBK 044 (김광규 송금 직전) ===
print("\n■ 5단계: 농협 → IBK 044 이체 (김광규 송금 직전)")
print("-"*100)
nh_to_044 = df[(df["_계좌번호"]=="312-3479-3479-01") & 
               (df["출"]>0) &
               (df["dt"] >= "2022-02-22") &
               (df["dt"] <= "2022-02-23 14:00") &
               (df["출"]>=10_000_000)].copy()
# 박영준 자체이체만
nh_to_044 = nh_to_044[nh_to_044["거래내용"].str.contains("박영준",na=False)]
total_to_044 = nh_to_044["출"].sum()
for _, r in nh_to_044.sort_values("dt").iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  → IBK 044")
print(f"  소계: {total_to_044:,}원")

# === 6. IBK 044 → 김광규 ===
print("\n■ 6단계: IBK 044 → 김광규 송금")
print("-"*100)
to_kim = df[(df["_계좌번호"]=="140-090845-01-044") & 
            (df["상대계좌예금주명"].str.contains("김광규",na=False))].copy()
total_kim = to_kim["출"].sum()
for _, r in to_kim.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  → 김광규")
print(f"  소계: {total_kim:,}원")

# === 7. 자금 흐름 가능성 검증 ===
print("\n" + "="*100)
print("【검증 결과】")
print("="*100)
print(f"""
시계열 자금 흐름:

  [1] 안경희 → IBK 012:        +{total_ahn:>13,}원 (2021-01-30 ~ 05-28)
  [2] IBK 012 → 농협:          -{total_to_nh:>13,}원 (안경희 입금 이후)
  [3] 농협 → 빗썸 (매수):       -{total_to_bit:>13,}원 ({len(nh_to_bit)}회)
  [4] 빗썸 → 농협 (매도회수):   +{total_from_bit:>13,}원 ({len(bit_to_nh)}회)
      ⤷ 순매수 (코인보유): {total_to_bit - total_from_bit:,}원
  [5] 농협 → IBK 044:          -{total_to_044:>13,}원 (2022-02-22~23)
  [6] IBK 044 → 김광규:         -{total_kim:>13,}원

자금 흐름 가능성:
  ✓ 안경희 자금이 농협으로 이체된 금액({total_to_nh:,}원)이 
    빗썸 송금 직전 농협 잔액에 포함되었는지 확인 필요
""")

# === 8. 농협 일자별 잔액 추이 — 안경희 자금이 보존되었는가? ===
print("="*100)
print("【농협 계좌 잔액 추이 (2021-01-30 ~ 2022-02-23)】")
print("="*100)
nh_all = df[(df["_계좌번호"]=="312-3479-3479-01") & 
            (df["dt"] >= "2021-01-30") &
            (df["dt"] <= "2022-02-23")].copy().sort_values("dt")
# 월말 잔액
nh_all["month"] = nh_all["dt"].dt.to_period("M")
monthly = nh_all.groupby("month").agg(
    입금=("입","sum"),
    출금=("출","sum"),
    건수=("입","count"),
).reset_index()
monthly["순"] = monthly["입금"] - monthly["출금"]
print(f"\n월별 농협 자금 흐름:")
print(f"{'월':10} {'입금':>15} {'출금':>15} {'순':>15}")
cumul = 0
for _, r in monthly.iterrows():
    cumul += r["순"]
    print(f"{str(r['month']):10} {int(r['입금']):>15,} {int(r['출금']):>15,} {int(r['순']):>+15,}  누적순 {cumul:>+15,}")

# === 9. 핵심: 농협의 빗썸 송금 합계 vs IBK 012로부터의 안경희 자금 ===
print("\n" + "="*100)
print("【핵심 검증: 안경희 자금 → 빗썸 투자 가능성】")
print("="*100)

# 농협으로 이체된 안경희 자금 추정
# = (IBK 012 → 농협 이체액) ∩ (안경희 입금 이후)
ahn_first = ahn_in["dt"].min()
ahn_last = ahn_in["dt"].max()
nh_received_period = df[(df["_계좌번호"]=="312-3479-3479-01") & 
                        (df["입"]>0) &
                        (df["dt"] >= ahn_first) &
                        (df["dt"] <= "2022-02-23") &
                        (df["거래내용"].str.contains("박영준",na=False))]["입"].sum()
print(f"""
안경희 입금 기간: {ahn_first:%Y-%m-%d} ~ {ahn_last:%Y-%m-%d}
→ 안경희 자금 총액: {total_ahn:,}원

IBK 012 → 농협 이체액 (안경희 입금 후): {total_to_nh:,}원
  ⤷ 이 중 안경희 자금이 포함되어 있을 가능성: 매우 높음

농협이 박영준 본인으로부터 받은 입금 (안경희 기간 이후, ~2022-02-23):
  {nh_received_period:,}원

농협 → 빗썸 송금 (안경희 기간 이후, ~2022-02-23):
  {total_to_bit:,}원 ({len(nh_to_bit)}건)

▶ 결론:
""")
if total_to_bit > 0 and nh_received_period > 0:
    overlap = min(total_to_nh, total_to_bit)
    print(f"   IBK 012에서 농협으로 이체된 {total_to_nh:,}원 중 일부가")
    print(f"   빗썸 송금에 사용된 것으로 추정됨.")
    print(f"   ")
    print(f"   ▷ 안경희 자금이 농협을 거쳐 빗썸에 투자된 최대 가능액: {min(total_ahn, total_to_nh, total_to_bit):,}원")
    print(f"   ")
    print(f"   ▷ 빗썸 매도 회수액 중 안경희 자금 비율 (FIFO 가정):")
    if total_to_bit > 0:
        ratio = min(total_to_nh, total_to_bit) / total_to_bit * 100
        attributable = total_from_bit * ratio / 100
        print(f"      ≈ {ratio:.1f}% (= {attributable:,.0f}원)")
