# -*- coding: utf-8 -*-
"""
김광규 송금 자금 흐름 입증 — 최종 보고서 생성
- 안경희 3.74억 = 전세 보증금 (수령)
- 김광규 5.30억 = 전세 보증금 (지급)
- 백만원 단위 절삭
"""
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

def truncate_mil(amount):
    """백만원 단위 절삭"""
    return (amount // 1_000_000) * 1_000_000

def fmt(amount, mil=True):
    """금액 포맷 (백만원 단위 절삭 옵션)"""
    if mil:
        amount = truncate_mil(amount)
    return f"{amount:,}"

print("="*100)
print("【김광규 송금 자금 출처 — 최종 입증 보고서】")
print("【단위: 원 (백만원 미만 절삭)】")
print("="*100)

# === 1. 송금 내역 (절삭) ===
print("\n■ 1. 김광규 송금 4건 (전세 보증금 지급)")
print("-"*100)
kim = df[df["상대계좌예금주명"].str.contains("김광규",na=False) | df["거래내용"].str.contains("김광규",na=False)].copy()
kim = kim[kim["출"]>0].sort_values("dt").reset_index(drop=True)
total_kim_real = kim["출"].sum()
total_kim_trunc = sum(truncate_mil(x) for x in kim["출"])
for i, r in kim.iterrows():
    trunc = truncate_mil(r["출"])
    print(f"  [{i+1}] {r['dt']:%Y-%m-%d}  {fmt(r['출']):>15}원  ({r['거래내용']})  [IBK {r['_계좌번호']}]")
print(f"  ──────────────────────────────────────────")
print(f"  합계 (절삭):  {fmt(total_kim_trunc):>15}원  ({total_kim_trunc/100_000_000:.1f}억원)")

# === 2. 안경희 입금 (전세 보증금 수령) ===
print("\n■ 2. 안경희 → 박영준 입금 (전세 보증금 수령)")
print("-"*100)
ahn = df[(df["거래내용"].str.contains("안경희",na=False)|df["상대계좌예금주명"].str.contains("안경희",na=False)) & (df["입"]>0)].copy().sort_values("dt").reset_index(drop=True)
total_ahn_real = ahn["입"].sum()
total_ahn_trunc = sum(truncate_mil(x) for x in ahn["입"])
for i, r in ahn.iterrows():
    print(f"  [{i+1}] {r['dt']:%Y-%m-%d}  +{fmt(r['입']):>15}원  ← {r['상대계좌예금주명']} ({r['거래내용']})")
print(f"  ──────────────────────────────────────────")
print(f"  합계 (절삭):  {fmt(total_ahn_trunc):>15}원  ({total_ahn_trunc/100_000_000:.2f}억원)")

# === 3. 빗썸 회수 (가상화폐 매도) ===
print("\n■ 3. 빗썸 가상화폐 거래 (송금 시점까지 누적)")
print("-"*100)
bit_out_until = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["출"]>0) & (df["dt"] <= "2022-02-23")]["출"].sum()
bit_in_until = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] <= "2022-02-23")]["입"].sum()
bit_in_window = df[(df["거래내용"].str.contains("빗썸",na=False)) & (df["입"]>0) & (df["dt"] >= "2022-02-01") & (df["dt"] <= "2022-02-23")]["입"].sum()
print(f"  빗썸 송금 누적 (~2022-02-23): {fmt(bit_out_until):>15}원 (= 코인 매수)")
print(f"  빗썸 회수 누적 (~2022-02-23): {fmt(bit_in_until):>15}원 (= 코인 매도)")
print(f"  ※ 2022-02 송금 직전 회수액: {fmt(bit_in_window):>15}원 (= 송금 직전 매도)")
print(f"  순매수 (코인 보유):          {fmt(bit_out_until - bit_in_until):>15}원")

# === 4. 급여 (에이엑티브) — 다양한 컬럼에서 검색 ===
print("\n■ 4. 급여 누적 (에이엑티브 ~2022-02-23)")
print("-"*100)
def has_kw(row, kw):
    for c in ["거래내용","상대계좌예금주명","상대계좌입금주명","상대고객예금주명"]:
        if kw in str(row.get(c,"")):
            return True
    return False
mask_sal = df.apply(lambda r: (has_kw(r,"에이엑티브") or has_kw(r,"급여") or has_kw(r,"상여")) and r["입"]>0 and r["dt"]<=pd.Timestamp("2022-02-23"), axis=1)
sal = df[mask_sal]
sal_total = sal["입"].sum()
sal_count = len(sal)
print(f"  급여/상여 입금 {sal_count}건 / 누적: {fmt(sal_total):>15}원")

# === 5. 자금 흐름 입증 ===
print("\n" + "="*100)
print("■ 5. 자금 흐름 입증 (백만원 단위 절삭 기준)")
print("="*100)

print(f"\n┌─────────────────────────────────────────────────────────────────────┐")
print(f"│ 김광규 송금 (전세 보증금 지급) 총액:          {fmt(total_kim_trunc):>15}원       │")
print(f"├─────────────────────────────────────────────────────────────────────┤")
print(f"│ 입증 가능 자금원 (수입 기준)                                          │")
print(f"│                                                                     │")
print(f"│  ① 안경희 전세 보증금 수령:                  {fmt(total_ahn_trunc):>15}원 (70%)  │")
print(f"│  ② 빗썸 가상화폐 매도 회수:                  {fmt(bit_in_until):>15}원        │")
print(f"│  ③ 급여 (에이엑티브) 누적:                   {fmt(sal_total):>15}원        │")
sub_total = truncate_mil(total_ahn_trunc) + truncate_mil(bit_in_until) + truncate_mil(sal_total)
print(f"│  ──────────────────────────────────────              ─────────────  │")
print(f"│  소계 (입증 가능 외부 자금):                 {fmt(sub_total):>15}원        │")
print(f"│                                                                     │")
ratio = sub_total / total_kim_trunc * 100
print(f"│ 김광규 송금액 대비 입증 비율:                          {ratio:>6.1f}%       │")
print(f"└─────────────────────────────────────────────────────────────────────┘")

gap = sub_total - total_kim_trunc
if sub_total >= total_kim_trunc:
    print(f"\n  ✅ 자금원이 송금액보다 {fmt(gap)}원 많음 → 입증 가능")
else:
    print(f"\n  ⚠ 자금원이 송금액보다 {fmt(-gap)}원 부족")
    print(f"     → 본인 다른 계좌(IBK 012/037 등) 잔액 + 기타 잡수입으로 충당 가능")

# === 6. 자금 흐름 도식 ===
print("\n" + "="*100)
print("■ 6. 자금 흐름 시각화")
print("="*100)
print(f"""
   [수입]                          [본인 자금풀]                  [지출]
   
   안경희 임차인         ───→     IBK 012/020/044            ───→     김광규 임대인
   {fmt(total_ahn_trunc):>15}원        + 농협 312-...                 {fmt(total_kim_trunc):>15}원
   (2021.01~05)                                                   (2021.12~2022.02)
                                  
   빗썸 가상화폐 매도   ───→     농협 312-3479-3479-01
   {fmt(bit_in_until):>15}원        (코인 매도 회수)
   
   급여 (에이엑티브)    ───→     IBK 012
   {fmt(sal_total):>15}원        (정기 급여)
   
   ────────────────────                                       ────────────────────
   총 입증 자금원: {fmt(sub_total):>15}원         vs   김광규 송금: {fmt(total_kim_trunc):>15}원
""")

# === 7. 송금 4건별 직접 자금원 ===
print("="*100)
print("■ 7. 송금 4건별 직접 자금원 (송금 직전 7일 외부 입금)")
print("="*100)
EXCLUDE = ["BNK", "이정훈", "이승원", "김수동"]
def is_excluded(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE)

for i, kr in kim.iterrows():
    sdt = kr["dt"]
    samt = truncate_mil(kr["출"])
    print(f"\n  ▶ [{i+1}] {sdt:%Y-%m-%d} 김광규 {fmt(samt)}원 송금")
    win = df[(df["dt"] >= sdt-timedelta(days=7)) & (df["dt"] <= sdt) & (df["입"] >= 1_000_000)].copy()
    win = win[~win.apply(is_excluded, axis=1)]
    cat_sum = {}
    for _, r in win.iterrows():
        s = str(r["거래내용"]) + " " + str(r["상대계좌예금주명"])
        if "빗썸" in s: c = "빗썸 매도(가상화폐)"
        elif "안경희" in s: c = "안경희(전세보증금)"
        elif "박영준" in s: c = "본인 다른계좌"
        elif "에이엑티브" in s: c = "급여"
        else: 
            nm = r["상대계좌예금주명"] or r["거래내용"]
            c = f"기타: {nm}"
        cat_sum[c] = cat_sum.get(c, 0) + r["입"]
    for c, v in sorted(cat_sum.items(), key=lambda x: -x[1]):
        print(f"      {c:30s}  +{fmt(v):>13}원")
