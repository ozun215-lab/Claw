# -*- coding: utf-8 -*-
"""빗썸코리아 거래 흐름 + 김광규 송금 자금 출처 재구성"""
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

# === 빗썸 거래 모두 ===
bithumb_mask = (df["거래내용"].str.contains("빗썸", na=False, regex=False) | 
                df["상대계좌예금주명"].str.contains("빗썸", na=False, regex=False))
bit = df[bithumb_mask].copy().sort_values("dt").reset_index(drop=True)

print("="*100)
print(f"【빗썸코리아 거래 전체 {len(bit)}건】")
print("="*100)
print(f"기간: {bit['dt'].min()} ~ {bit['dt'].max()}")
total_out = bit["출"].sum()
total_in = bit["입"].sum()
print(f"빗썸으로 송금(매수용): {bit[bit['출']>0].shape[0]}건 / 총 {total_out:,}원")
print(f"빗썸에서 회수(매도후): {bit[bit['입']>0].shape[0]}건 / 총 {total_in:,}원")
print(f"순흐름 (회수 - 송금): {total_in - total_out:,}원")

# 계좌별 통계
print("\n=== 계좌별 빗썸 거래 ===")
for acct, g in bit.groupby("_계좌번호"):
    out_sum = g[g["출"]>0]["출"].sum()
    in_sum = g[g["입"]>0]["입"].sum()
    print(f"  {acct}: 송금 {out_sum:,} / 회수 {in_sum:,} / 순 {in_sum-out_sum:+,}")

# 연도별
print("\n=== 연도별 빗썸 거래 ===")
bit["year"] = bit["dt"].dt.year
for yr, g in bit.groupby("year"):
    out_sum = g[g["출"]>0]["출"].sum()
    in_sum = g[g["입"]>0]["입"].sum()
    print(f"  {yr}: 송금 {out_sum:>15,}  /  회수 {in_sum:>15,}  /  순 {in_sum-out_sum:>+15,}")

# === 2022년 김광규 송금 직전 빗썸 회수 ===
print("\n" + "="*100)
print("【2022-02-23 김광규 송금 직전 빗썸코리아 회수 (=가상화폐 매도 자금)】")
print("="*100)
bit_2022 = bit[(bit["dt"] >= "2022-02-15") & (bit["dt"] <= "2022-02-24")].sort_values("dt")
for _, r in bit_2022.iterrows():
    sign = "+회수" if r["입"]>0 else "-송금"
    amt = r["입"] if r["입"]>0 else r["출"]
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  [{r['_은행']}{r['_계좌번호'][-3:]}]  {sign} {amt:>13,}  ({r['거래내용']}) [{r['거래구분']}]")

# === 전체 김광규 송금 직전 자금 출처 재정리 (안경희·이승원·김수동·빗썸 매도) ===
print("\n" + "="*100)
print("【최종 자금 출처: BNK/이정훈 제외, 실제 자금원 분류】")
print("="*100)

kim = df[df["상대계좌예금주명"].str.contains("김광규",na=False) | df["거래내용"].str.contains("김광규",na=False)].copy()
kim = kim[kim["출"]>0].sort_values("dt").reset_index(drop=True)

# 자금원 카테고리화
def categorize(row):
    desc = str(row.get("거래내용",""))
    name = str(row.get("상대계좌예금주명",""))
    bank = str(row.get("상대은행",""))
    acct = str(row.get("상대계좌번호",""))
    
    if "빗썸" in desc or "빗썸" in name:
        return "빗썸(가상화폐 매도)"
    if "안경희" in desc or "안경희" in name:
        return "안경희"
    if "이승원" in desc or "이승원" in name:
        return "이승원"
    if "김수동" in desc or "김수동" in name:
        return "김수동"
    if "이정훈" in desc or "이정훈" in name:
        return "이정훈(임시·배제)"
    if "BNK" in desc or "BNK" in name or "캐피" in desc:
        return "BNK캐피탈(배제)"
    if "박영준" in name or "박영준" in desc:
        # 본인 다른 계좌
        if "90845" in acct or "3479" in acct:
            return "본인 다른계좌 이체"
        return "본인 명의 자금"
    if "에이엑티브" in name or "에이엑티브" in desc:
        return "급여(에이엑티브)"
    return f"기타: {name or desc}"

print("\n=== 김광규 송금 4건의 직전 7일 입금 분류 ===")
all_sources = {}
for _, kr in kim.iterrows():
    sdt = kr["dt"]
    samt = kr["출"]
    win = df[(df["dt"] >= sdt-timedelta(days=7)) & (df["dt"] <= sdt) & (df["입"] >= 100_000)].copy()
    win["분류"] = win.apply(categorize, axis=1)
    print(f"\n▶ 송금 {sdt:%Y-%m-%d %H:%M} {samt:,}원")
    grp = win.groupby("분류")["입"].sum().sort_values(ascending=False)
    for cat, total in grp.items():
        print(f"    {cat:30s}  {total:>13,}원")
        all_sources[cat] = all_sources.get(cat, 0) + total

print("\n=== 전체 합계 (송금별 합산 - 중복 가능) ===")
for cat, total in sorted(all_sources.items(), key=lambda x: -x[1]):
    print(f"  {cat:30s}  {total:>13,}원")

# 빗썸 회수가 김광규 송금에 사용된 양 검증
# 2022-02-23 농협의 빗썸코리아 회수
print("\n" + "="*100)
print("【2022-02-23 농협 계좌의 빗썸 자금 흐름 - 시간순】")
print("="*100)
nh_223 = df[(df["_은행"]=="농협") & (df["dt"] >= "2022-02-19") & (df["dt"] <= "2022-02-24")].sort_values("dt")
for _, r in nh_223.iterrows():
    sign = "+" if r["입"]>0 else "-"
    amt = r["입"] if r["입"]>0 else r["출"]
    desc = r["거래내용"]
    bal = n(r["잔액"])
    flag = ""
    if "빗썸" in str(desc): flag = " ★빗썸"
    if "이승원" in str(desc): flag = " ★이승원"
    if "김수동" in str(desc): flag = " ★김수동"
    print(f"   {r['dt']:%Y-%m-%d %H:%M}  {sign}{amt:>13,}  잔액 {bal:>13,}  ({desc}) [{r['거래구분']}]{flag}")
