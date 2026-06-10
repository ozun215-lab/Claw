# -*- coding: utf-8 -*-
"""
김광규 검색 + 자금 출처 추적
"""
import os, sys
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

WORK_DIR = r"D:\Claw\workspace\analysis"
df = pd.read_csv(os.path.join(WORK_DIR, "all_transactions.csv"), dtype=str).fillna("")

print("총 거래 건수:", len(df))
print("컬럼:", list(df.columns))
print()

# 김광규 검색 (모든 텍스트 컬럼)
def find_keyword(df, kw):
    mask = pd.Series([False]*len(df))
    for c in df.columns:
        mask = mask | df[c].astype(str).str.contains(kw, na=False, regex=False)
    return df[mask].copy()

kim = find_keyword(df, "김광규")
print(f"=== '김광규' 검색 결과: {len(kim)}건 ===")
if len(kim) > 0:
    show_cols = ["_계좌번호","거래일시","출금","입금","거래후잔액","거래내용","송금메시지","상대계좌번호","상대예금주명","거래구분","상대고객예금주명"]
    show_cols = [c for c in show_cols if c in kim.columns]
    print(kim[show_cols].to_string(index=False))
    kim.to_csv(os.path.join(WORK_DIR, "kim_gwangkyu_hits.csv"), index=False, encoding="utf-8-sig")
    print("\n파일 저장:", os.path.join(WORK_DIR, "kim_gwangkyu_hits.csv"))

# 김씨 성을 가진 모든 사람 (참고용)
print("\n=== '김' 시작 거래상대 (참고) ===")
kim_all = find_keyword(df, "김")
# 거래내용/상대예금주에서 김으로 시작하는 이름 패턴 추출
import re
names = set()
for col in ["거래내용","상대예금주명","상대고객예금주명"]:
    if col in df.columns:
        for v in df[col].astype(str):
            for m in re.findall(r"김[가-힣]{1,3}", v):
                names.add(m)
print("김씨 후보:", sorted(names))
