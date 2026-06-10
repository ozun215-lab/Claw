# -*- coding: utf-8 -*-
"""
김광규 송금 4건의 자금 출처 추적
각 송금일 직전의 입금 거래를 추적하여 자금이 어디서 왔는지 확인
"""
import os, sys
import pandas as pd
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

WORK_DIR = r"D:\Claw\workspace\analysis"
df = pd.read_csv(os.path.join(WORK_DIR, "all_transactions.csv"), dtype=str).fillna("")

# 숫자 컬럼 변환
def to_num(s):
    s = str(s).replace(",", "").strip()
    if s in ("", "-"): return 0
    try: return int(float(s))
    except: return 0

df["출금_num"] = df["출금"].apply(to_num)
df["입금_num"] = df["입금"].apply(to_num)
df["잔액_num"] = df["거래후 잔액"].apply(to_num)
df["거래일시_dt"] = pd.to_datetime(df["거래일시"], errors="coerce")

# 김광규 송금 건
kim_tx = df[df["상대계좌예금주명"].astype(str).str.contains("김광규", na=False)].copy()
kim_tx = kim_tx.sort_values("거래일시_dt").reset_index(drop=True)

print("="*100)
print("【김광규 송금 4건 요약】")
print("="*100)
total_to_kim = kim_tx["출금_num"].sum()
print(f"총 송금액: {total_to_kim:,}원 ({total_to_kim/100000000:.2f}억원)")
for i, r in kim_tx.iterrows():
    print(f"  [{i+1}] {r['거래일시']}  출금 {r['출금_num']:>13,}원  잔액 {r['잔액_num']:>13,}원  ({r['거래내용']})")
    print(f"      → 신한은행 110406712671 김광규  /  파일: {r['_파일'][-7:-4]} 계좌")

print()
print("="*100)
print("【자금 출처 추적: 각 송금 직전 30일 이내의 입금 거래】")
print("="*100)

# 각 송금일 기준으로 직전 30일 이내 입금건 추출
for idx, row in kim_tx.iterrows():
    send_dt = row["거래일시_dt"]
    send_amt = row["출금_num"]
    # 같은 파일(=같은 계좌, 같은 조회기간) 내에서 이전 거래
    same_acct = df[df["_파일"] == row["_파일"]].copy()
    same_acct = same_acct.sort_values("거래일시_dt")
    # 직전 60일 입금건
    window_start = send_dt - pd.Timedelta(days=60)
    inflows = same_acct[(same_acct["거래일시_dt"] >= window_start) &
                        (same_acct["거래일시_dt"] < send_dt) &
                        (same_acct["입금_num"] > 0)].copy()
    print(f"\n▶ 송금 [{send_dt.strftime('%Y-%m-%d %H:%M')}] {send_amt:,}원 ({row['거래내용']})")
    print(f"  직전 60일 입금 {len(inflows)}건, 총 {inflows['입금_num'].sum():,}원")
    # 상위 큰 입금건
    top = inflows.sort_values("입금_num", ascending=False).head(15)
    for _, r in top.iterrows():
        print(f"   • {r['거래일시']}  입금 {r['입금_num']:>13,}원  ({r['거래내용']})  ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}")

# 두 번째 분석: 김광규 송금 직전의 큰 입금건 매칭 (당일~3일 이내)
print()
print("="*100)
print("【자금 출처 정밀 매칭: 송금 당일/직전 1-3일 큰 입금건】")
print("="*100)
for idx, row in kim_tx.iterrows():
    send_dt = row["거래일시_dt"]
    send_amt = row["출금_num"]
    same_acct = df[df["_파일"] == row["_파일"]].copy()
    same_acct["거래일시_dt"] = pd.to_datetime(same_acct["거래일시"], errors="coerce")
    same_acct = same_acct.sort_values("거래일시_dt")
    # 같은 날 또는 직전 3일
    window_start = send_dt - pd.Timedelta(days=3)
    close = same_acct[(same_acct["거래일시_dt"] >= window_start) &
                      (same_acct["거래일시_dt"] <= send_dt + pd.Timedelta(hours=1)) &
                      (same_acct["입금_num"] >= 1_000_000)].copy()
    print(f"\n▶ 송금 [{send_dt.strftime('%Y-%m-%d %H:%M')}] {send_amt:,}원")
    if len(close) == 0:
        print("   직전 3일 이내 100만원 이상 입금건 없음 → 기존 잔액에서 송금했을 가능성")
    else:
        for _, r in close.iterrows():
            print(f"   • {r['거래일시']}  입금 {r['입금_num']:>13,}원  ({r['거래내용']})  ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# 결과 저장
kim_tx[["거래일시","출금","입금","거래후 잔액","거래내용","상대계좌번호","상대은행","상대계좌예금주명","_파일"]].to_csv(
    os.path.join(WORK_DIR, "kim_outflows.csv"), index=False, encoding="utf-8-sig"
)
print("\n저장:", os.path.join(WORK_DIR, "kim_outflows.csv"))
