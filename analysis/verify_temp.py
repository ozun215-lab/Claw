# -*- coding: utf-8 -*-
"""
임시자금 검증 + 김광규 5.3억 자금원 입증 가능성 분석
배제 자금원: BNK캐피탈, 이정훈, 이승원, 김수동 (모두 임시자금 가정)
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

# === 1단계: 임시자금 검증 (들어온 후 빠르게 나갔는지) ===
print("="*100)
print("【1단계: 임시자금 검증 — 들어온 후 짧은 시간 내 동일/유사액이 출금됐는가?】")
print("="*100)

def check_temporary(keyword, days=14):
    """keyword로 입금 검색 후, 입금 직후 days일 내에 유사 금액이 출금됐는지 확인"""
    print(f"\n=== {keyword} 임시자금 검증 ===")
    mask = (df["거래내용"].str.contains(keyword, na=False, regex=False) | 
            df["상대계좌예금주명"].str.contains(keyword, na=False, regex=False))
    hits = df[mask].copy()
    inflows = hits[hits["입"]>0].sort_values("dt")
    if len(inflows)==0:
        print(f"   {keyword} 입금 없음")
        return 0, 0
    total_in = inflows["입"].sum()
    print(f"   {keyword} 총 입금: {len(inflows)}건 / {total_in:,}원")
    
    # 각 입금 후 days일 내 큰 출금 확인
    repaid = 0
    for _, ir in inflows.iterrows():
        amt = ir["입"]
        # 동일 계좌에서 입금 후 14일 내 출금
        after = df[(df["_계좌번호"]==ir["_계좌번호"]) & 
                   (df["dt"] > ir["dt"]) & 
                   (df["dt"] <= ir["dt"]+timedelta(days=days)) & 
                   (df["출"] > 0)].copy()
        # 유사 금액 (±5%)
        threshold_lo = amt * 0.95
        threshold_hi = amt * 1.05
        matched = after[(after["출"] >= threshold_lo) & (after["출"] <= threshold_hi)]
        if len(matched)>0:
            m = matched.iloc[0]
            days_gap = (m["dt"] - ir["dt"]).days
            hours_gap = (m["dt"] - ir["dt"]).total_seconds()/3600
            print(f"   ✅ {ir['dt']:%Y-%m-%d %H:%M} +{amt:,} → {m['dt']:%Y-%m-%d %H:%M} -{m['출']:,} ({hours_gap:.1f}시간 후) → {m['상대계좌예금주명']}")
            repaid += amt
        else:
            print(f"   ⚠ {ir['dt']:%Y-%m-%d %H:%M} +{amt:,} → 14일내 유사출금 없음 (계좌에 잔존 가능)")
    if total_in > 0:
        print(f"   → 임시자금 확률: {repaid:,} / {total_in:,} = {100*repaid/total_in:.0f}%")
    return total_in, repaid

bnk_in, bnk_out = check_temporary("BNK")
lj_in, lj_out = check_temporary("이정훈")
ls_in, ls_out = check_temporary("이승원")
ks_in, ks_out = check_temporary("김수동")

# === 2단계: 5.3억 송금에 가용한 "확정 자금원" 계산 ===
print("\n" + "="*100)
print("【2단계: 5.3억 송금에 가용한 확정 자금원 — 임시자금 제외】")
print("="*100)

# 김광규 송금 시점
kim_total = 530_000_000
print(f"\n김광규 송금 총액: {kim_total:,}원")
print(f"송금 시점: 2021-12-28 ~ 2022-02-23")

# 자금원 분류 (송금 시점까지 누적 가능한 자금)
# 안경희 입금 (2021년)
ahn_in_total = df[(df["거래내용"].str.contains("안경희",na=False)|
                   df["상대계좌예금주명"].str.contains("안경희",na=False)) & 
                  (df["입"]>0)]["입"].sum()
print(f"\n■ 안경희 → 박영준 입금 (2021년 누적): {ahn_in_total:,}원")

# 빗썸 회수 (2022-02 김광규 송금 전후, 농협)
bit_in_2022 = df[(df["거래내용"].str.contains("빗썸",na=False)) & 
                 (df["입"]>0) &
                 (df["dt"] >= "2022-01-01") &
                 (df["dt"] <= "2022-02-23")]["입"].sum()
bit_in_total = df[(df["거래내용"].str.contains("빗썸",na=False)) & 
                  (df["입"]>0)]["입"].sum()
print(f"■ 빗썸 회수 (2022-01~02): {bit_in_2022:,}원")
print(f"■ 빗썸 회수 (전체 누적):  {bit_in_total:,}원")

# 급여 (에이엑티브)
salary_total = df[(df["상대계좌예금주명"].str.contains("에이엑티브",na=False)|
                   df["거래내용"].str.contains("급여",na=False)) & 
                  (df["입"]>0) &
                  (df["dt"] <= "2022-02-23")]["입"].sum()
print(f"■ 급여(에이엑티브) 누적: {salary_total:,}원")

# 빗썸 순매수액 (즉 코인 보유로 전환된 본인 자금) — 이게 사실상 본인이 모은 자금의 한 형태
bit_out_total = df[(df["거래내용"].str.contains("빗썸",na=False)) & 
                   (df["출"]>0) &
                   (df["dt"] <= "2022-02-23")]["출"].sum()
bit_in_until = df[(df["거래내용"].str.contains("빗썸",na=False)) & 
                  (df["입"]>0) &
                  (df["dt"] <= "2022-02-23")]["입"].sum()
print(f"■ 빗썸 송금(매수) 누적: {bit_out_total:,}원")
print(f"  → 순매수 (보유): {bit_out_total - bit_in_until:,}원 (= 코인으로 보유 중)")

# 송금 시점 IBK 044 계좌 잔액 변화
print("\n■ IBK 044 계좌 (전세 송금 계좌) 자금 흐름:")
ibk044 = df[df["_계좌번호"]=="140-090845-01-044"].sort_values("dt")
ibk044_in = ibk044[ibk044["입"]>0]["입"].sum()
ibk044_out = ibk044[ibk044["출"]>0]["출"].sum()
print(f"   입금 누적: {ibk044_in:,}원 / 출금 누적: {ibk044_out:,}원")

# === 3단계: 시간 가중 자금 출처 추정 (FIFO) ===
print("\n" + "="*100)
print("【3단계: 시간 가중 자금 흐름 — 2022-02-23 송금 4.8억의 직접 출처】")
print("="*100)

# IBK 044로 들어온 자금 (송금 직전)
print("\n=== IBK 044 (전세 송금계좌) 2022-02-22~23 입금 출처 ===")
ibk044_in_2022 = df[(df["_계좌번호"]=="140-090845-01-044") & 
                    (df["dt"] >= "2022-02-22") &
                    (df["dt"] <= "2022-02-23 14:00") &
                    (df["입"]>0)].copy()
for _, r in ibk044_in_2022.iterrows():
    src = r["상대계좌예금주명"]
    src_acct = r["상대계좌번호"]
    print(f"   {r['dt']:%m-%d %H:%M}  +{r['입']:>13,}  ← {src} / {r['상대은행']} {src_acct} [{r['거래구분']}]")
total_044_in = ibk044_in_2022["입"].sum()
print(f"   소계: {total_044_in:,}원 (= 김광규 송금 4.8억의 직접 원천)")

# 농협 → IBK 044 이체분
nh_to_044 = df[(df["_계좌번호"]=="312-3479-3479-01") & 
               (df["dt"] >= "2022-02-22") &
               (df["dt"] <= "2022-02-23 14:00") &
               (df["출"]>=10_000_000)].copy()
print(f"\n=== 농협 → IBK 044 송금 (2022-02-22~23) ===")
total_nh_out_to_044 = 0
for _, r in nh_to_044.iterrows():
    if "박영준" in str(r["거래내용"]):
        total_nh_out_to_044 += r["출"]
        print(f"   {r['dt']:%m-%d %H:%M}  -{r['출']:>13,}  → 박영준 IBK")
print(f"   농협→IBK 이체: {total_nh_out_to_044:,}원")

# 농협의 이 시점 직전 자금 출처
print(f"\n=== 농협이 이 자금을 마련하기 위해 직전 받은 입금 (2022-02-19 ~ 2022-02-23 13:13) ===")
nh_pre = df[(df["_계좌번호"]=="312-3479-3479-01") & 
            (df["dt"] >= "2022-02-19") &
            (df["dt"] <= "2022-02-23 13:13") &
            (df["입"]>=1_000_000)].copy()
nh_pre_by_src = {}
for _, r in nh_pre.iterrows():
    src = r["거래내용"]
    if "이승원" in src: cat = "이승원(임시)"
    elif "김수동" in src: cat = "김수동(임시)"
    elif "빗썸" in src: cat = "빗썸(코인매도)"
    elif "박영준" in src: cat = "본인 다른계좌"
    else: cat = src
    nh_pre_by_src[cat] = nh_pre_by_src.get(cat, 0) + r["입"]
for k, v in sorted(nh_pre_by_src.items(), key=lambda x: -x[1]):
    print(f"   {k:25s}  {v:>13,}원")

# === 4단계: 임시자금 제외 후 실제 가용 자금 계산 ===
print("\n" + "="*100)
print("【4단계: 임시자금(이승원·김수동·이정훈·BNK) 제외 시 남는 자금원】")
print("="*100)

# 김광규 4건 송금
print(f"\n김광규 송금 총액: {kim_total:,}원\n")

# 임시자금 (송금 직전 7일 내 입금)
temp_funds = ls_in + ks_in + lj_in + bnk_in  
print(f"임시자금 추정 (배제):")
print(f"  • BNK캐피탈: {bnk_in:,}원")
print(f"  • 이정훈:    {lj_in:,}원")
print(f"  • 이승원:    {ls_in:,}원")
print(f"  • 김수동:    {ks_in:,}원")
print(f"  소계: {temp_funds:,}원")

# 자금원으로 인정되는 항목
print(f"\n자금원으로 인정되는 항목 (송금 시점까지 누적):")
print(f"  • 안경희 입금:           {ahn_in_total:,}원")
print(f"  • 급여(에이엑티브) 누적: {salary_total:,}원")
print(f"  • 빗썸 회수액 누적:      {bit_in_until:,}원 (= 가상화폐 매도)")
real_sources = ahn_in_total + salary_total + bit_in_until
print(f"  소계: {real_sources:,}원")

# 검증
print(f"\n┌{'─'*60}")
print(f"│ 검증: {real_sources:,}원 vs 김광규 송금 {kim_total:,}원")
print(f"│")
if real_sources >= kim_total:
    print(f"│ ✅ 입증 가능: 자금원이 송금액보다 {real_sources - kim_total:,}원 많음")
else:
    print(f"│ ⚠ 부족: {kim_total - real_sources:,}원 부족")
print(f"└{'─'*60}")

# 더 정밀: 송금 직전 7일내 직접 입금 (분류별)
print("\n" + "="*100)
print("【5단계: 4건 송금 직전 7일 입금 — 임시자금 제외 후 직접 입증 가능액】")
print("="*100)

kim = df[df["상대계좌예금주명"].str.contains("김광규",na=False) | df["거래내용"].str.contains("김광규",na=False)].copy()
kim = kim[kim["출"]>0].sort_values("dt").reset_index(drop=True)

EXCLUDE_KEYWORDS = ["BNK", "이정훈", "이승원", "김수동"]
def is_excluded(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE_KEYWORDS)

total_direct_evidence = 0
for i, kr in kim.iterrows():
    sdt = kr["dt"]
    samt = kr["출"]
    print(f"\n▶ 송금 [{i+1}] {sdt:%Y-%m-%d %H:%M} {samt:,}원")
    win = df[(df["dt"] >= sdt-timedelta(days=7)) & 
             (df["dt"] <= sdt) & 
             (df["입"] >= 100_000)].copy()
    win_clean = win[~win.apply(is_excluded, axis=1)]
    # 본인 다른계좌 이체는 중복방지 (042/044/농협 사이 이체)
    # 카테고리화
    cat_sum = {}
    for _, r in win_clean.iterrows():
        s = str(r["거래내용"]) + " " + str(r["상대계좌예금주명"])
        if "빗썸" in s: c = "빗썸(가상화폐 매도)"
        elif "안경희" in s: c = "안경희"
        elif "박영준" in s and ("90845" in str(r["상대계좌번호"]) or "3479" in str(r["상대계좌번호"])): 
            c = "본인 다른계좌(중복 집계 주의)"
        elif "에이엑티브" in s: c = "급여"
        else: c = f"기타: {r['상대계좌예금주명'] or r['거래내용']}"
        cat_sum[c] = cat_sum.get(c, 0) + r["입"]
    for c, v in sorted(cat_sum.items(), key=lambda x: -x[1]):
        print(f"     {c:35s} +{v:>13,}원")
    # 본인 다른계좌 중복 제외한 외부 자금만
    external = sum(v for c, v in cat_sum.items() if "본인 다른계좌" not in c)
    print(f"     ── 외부 자금 (중복제외):    +{external:,}원")
