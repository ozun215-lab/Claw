# -*- coding: utf-8 -*-
"""
모든 거래내역 통합 + 김광규 자금 출처 완전 추적
- IBK 거래내역 5개 + 과거거래신청 2개 (계좌 012/020/044, 2019~2022)
- 농협 입출금거래내역 4개 (계좌 312-3479-3479-01, 2019~2022)
"""
import os, sys, re, glob
import pandas as pd
import openpyxl
from bs4 import BeautifulSoup
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
WORK = r"D:\Claw\workspace\analysis"

# ===== Parsers =====
def parse_ibk_html(path):
    """IBK 거래내역조회 / 과거거래신청 둘 다 (HTML 형식)"""
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    text_clean = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL|re.IGNORECASE)
    soup = BeautifulSoup(text_clean, "lxml")
    # Meta from type1 table
    meta_text = ""
    tables = soup.find_all("table")
    for tbl in tables:
        if "type1" in (tbl.get("class") or []):
            meta_text = tbl.get_text(" ", strip=True)
            break
    # Find account number
    acct = re.search(r"(\d{3}-\d{6}-\d{2}-\d{3})", meta_text)
    acct_num = acct.group(1) if acct else ""

    # Transactions from type2
    headers = None
    rows = []
    for tbl in tables:
        if "type2" in (tbl.get("class") or []):
            for tr in tbl.find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["th","td"])]
                if not cells: continue
                if headers is None and any("거래일시" in v for v in cells):
                    headers = cells
                    continue
                if headers and len(cells) == len(headers):
                    rows.append(cells)
            break
    df = pd.DataFrame(rows, columns=headers) if headers else pd.DataFrame()
    # Normalize columns
    rename_map = {}
    for c in df.columns:
        if c == "거래후 잔액": rename_map[c] = "잔액"
        elif "수표어음" in c: rename_map[c] = "수표어음금액"
        elif "메모" == c: rename_map[c] = "송금메시지"
    df = df.rename(columns=rename_map)
    # Required cols
    for col in ["출금","입금","잔액","거래일시","거래내용","상대계좌번호","상대은행","거래구분","상대계좌예금주명"]:
        if col not in df.columns:
            df[col] = ""
    df["_은행"] = "IBK기업"
    df["_계좌번호"] = acct_num
    df["_원본파일"] = os.path.basename(path)
    return df

def parse_nh_xlsx(path):
    """농협 입출금거래내역조회결과"""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    # find header row (containing 거래일시)
    header_idx = None
    for i, r in enumerate(all_rows):
        if r and any(v == "거래일시" for v in r if v):
            header_idx = i
            break
    if header_idx is None:
        return pd.DataFrame()
    header = [v if v is not None else f"col{j}" for j, v in enumerate(all_rows[header_idx])]
    data_rows = []
    for r in all_rows[header_idx+1:]:
        if r and any(c is not None for c in r):
            data_rows.append(list(r))
    df = pd.DataFrame(data_rows, columns=header)
    # Drop fully None columns
    df = df.loc[:, [c for c in df.columns if c is not None and c != "" and not str(c).startswith("col")]]
    # Find account number from meta
    acct_num = ""
    for r in all_rows[:12]:
        if r:
            for v in r:
                if v and isinstance(v, str):
                    m = re.search(r"\d{3}-\d{4}-\d{4}-\d{2}", v)
                    if m: acct_num = m.group(0); break
    # Rename cols → standard
    rename = {
        "거래일시":"거래일시","출금금액":"출금","입금금액":"입금","거래후잔액":"잔액",
        "거래내용":"거래구분","거래기록사항":"거래내용","거래점":"거래점","거래메모":"송금메시지",
    }
    df = df.rename(columns=rename)
    for col in ["출금","입금","잔액","거래일시","거래내용","상대계좌번호","상대은행","거래구분","상대계좌예금주명"]:
        if col not in df.columns:
            df[col] = ""
    # In 농협 data, 거래기록사항 has the counterparty name
    df["상대계좌예금주명"] = df["거래내용"].astype(str)  # Counterparty name
    df["_은행"] = "농협"
    df["_계좌번호"] = acct_num
    df["_원본파일"] = os.path.basename(path)
    return df

# ===== Load all =====
all_dfs = []
files = sorted(glob.glob(os.path.join(WORK, "*.xls")) + glob.glob(os.path.join(WORK, "*.xlsx")))
files = [f for f in files if "일관성" not in os.path.basename(f)]
for f in files:
    name = os.path.basename(f)
    if name.startswith("거래내역조회") or name.startswith("과거거래"):
        df = parse_ibk_html(f)
    elif name.startswith("농협"):
        df = parse_nh_xlsx(f)
    else:
        continue
    print(f"  {name}: {len(df)}건 ({df['_계좌번호'].iloc[0] if len(df) else ''})")
    all_dfs.append(df)

# ===== Combine =====
combined = pd.concat(all_dfs, ignore_index=True)
print(f"\n총 거래 건수: {len(combined)}")

# ===== Normalize numeric =====
def to_num(s):
    if pd.isna(s): return 0
    s = str(s).replace(",", "").strip()
    if s in ("", "-", "None"): return 0
    try: return int(float(s))
    except: return 0

combined["출금_num"] = combined["출금"].apply(to_num)
combined["입금_num"] = combined["입금"].apply(to_num)
combined["잔액_num"] = combined["잔액"].apply(to_num)

# Parse datetime - handle both formats
def parse_dt(s):
    if pd.isna(s): return pd.NaT
    s = str(s).strip().replace("/", "-")
    # multiple spaces
    s = re.sub(r"\s+", " ", s)
    for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M"):
        try: return datetime.strptime(s, fmt)
        except: pass
    return pd.to_datetime(s, errors="coerce")
combined["거래일시_dt"] = combined["거래일시"].apply(parse_dt)
combined = combined.dropna(subset=["거래일시_dt"])
combined = combined.sort_values("거래일시_dt").reset_index(drop=True)

# Save combined
combined.to_csv(os.path.join(WORK, "all_accounts_combined.csv"), index=False, encoding="utf-8-sig")
print(f"저장: all_accounts_combined.csv ({len(combined)}건)")

# Account summary
print("\n=== 계좌별 거래수 ===")
print(combined.groupby(["_은행","_계좌번호"]).size())

# ===== 김광규 검색 (모든 계좌) =====
print("\n" + "="*100)
print("【김광규 관련 거래 — 모든 계좌】")
print("="*100)
mask = pd.Series([False]*len(combined))
for c in combined.columns:
    if combined[c].dtype == object:
        mask = mask | combined[c].astype(str).str.contains("김광규", na=False, regex=False)
kim = combined[mask].copy()
print(f"총 {len(kim)}건")
for _, r in kim.iterrows():
    print(f"  [{r['_은행']} {r['_계좌번호']}] {r['거래일시']}  출금 {r['출금_num']:>13,}  입금 {r['입금_num']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']}")
kim.to_csv(os.path.join(WORK, "kim_all_accounts.csv"), index=False, encoding="utf-8-sig")

# ===== 자금 추적: 김광규 송금건 4개의 자금 출처를 모든 계좌에 걸쳐 추적 =====
print("\n" + "="*100)
print("【자금 출처 추적 — 모든 계좌 통합】")
print("="*100)

# 김광규로 보낸 4건의 송금 시점
kim_outflows = kim[kim["출금_num"] > 0].sort_values("거래일시_dt").reset_index(drop=True)

# 농협 계좌의 동기 입금 (송금일 ±3일)
nh = combined[combined["_은행"] == "농협"].copy()
print(f"\n농협 계좌 312-3479-3479-01: 총 {len(nh)}건")
print(f"기간: {nh['거래일시_dt'].min()} ~ {nh['거래일시_dt'].max()}")

# 농협 → IBK 044 송금 (자금 흐름 연결)
print("\n=== 농협에서 IBK로 이체 (김광규 송금 자금 흐름) ===")
# 농협에서 출금 + 거래내용에 박영준 또는 IBK계좌번호
nh_to_ibk = nh[(nh["출금_num"] >= 5_000_000)].copy()
# IBK 044에서 받은 입금 (큰 금액 - 자금 모음)
ibk_044 = combined[(combined["_계좌번호"].astype(str).str.contains("044", na=False))].copy()
ibk_044_inflows = ibk_044[ibk_044["입금_num"] >= 5_000_000].copy()
print(f"\nIBK 044계좌 5백만원 이상 입금 {len(ibk_044_inflows)}건:")
for _, r in ibk_044_inflows.head(30).iterrows():
    print(f"  {r['거래일시']}  +{r['입금_num']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}")

# 농협 큰 출금
print(f"\n농협 5백만원 이상 출금 {len(nh_to_ibk)}건:")
for _, r in nh_to_ibk.head(30).iterrows():
    print(f"  {r['거래일시']}  -{r['출금_num']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']}")

# ===== 송금 4건별 자금 추적 (전체 계좌) =====
print("\n" + "="*100)
print("【김광규 송금 4건의 직전 7일 자금 흐름 (전체 계좌)】")
print("="*100)
for idx, row in kim_outflows.iterrows():
    sdt = row["거래일시_dt"]
    samt = row["출금_num"]
    print(f"\n▶ 송금 [{idx+1}] {sdt.strftime('%Y-%m-%d %H:%M')}  {samt:,}원  ({row['거래내용']})")
    print(f"   from: {row['_은행']} {row['_계좌번호']}")
    window_start = sdt - pd.Timedelta(days=7)
    window_end = sdt
    nearby_in = combined[(combined["거래일시_dt"] >= window_start) &
                          (combined["거래일시_dt"] <= window_end) &
                          (combined["입금_num"] >= 1_000_000)].sort_values("거래일시_dt")
    print(f"   직전 7일간 100만원 이상 입금 ({len(nearby_in)}건):")
    for _, r in nearby_in.iterrows():
        print(f"      {r['거래일시']}  [{r['_은행']} {r['_계좌번호']}]  +{r['입금_num']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']}")

print("\n[완료]")
