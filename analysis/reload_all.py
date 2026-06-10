# -*- coding: utf-8 -*-
"""IBK 037 추가 후 전체 데이터 재구성 + 김광규 송금 자금 출처 종합 재검증"""
import os, sys, re, glob
import pandas as pd
import openpyxl
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')
WORK = r"D:\Claw\workspace\analysis"

# === Parsers ===
def parse_ibk_html(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="replace")
    text_clean = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL|re.IGNORECASE)
    soup = BeautifulSoup(text_clean, "lxml")
    meta_text = ""
    tables = soup.find_all("table")
    for tbl in tables:
        if "type1" in (tbl.get("class") or []):
            meta_text = tbl.get_text(" ", strip=True)
            break
    acct = re.search(r"(\d{3}-\d{6}-\d{2}-\d{3})", meta_text)
    acct_num = acct.group(1) if acct else ""
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
    rename_map = {}
    for c in df.columns:
        if c == "거래후 잔액": rename_map[c] = "잔액"
        elif "수표어음" in c: rename_map[c] = "수표어음금액"
        elif c == "메모": rename_map[c] = "송금메시지"
    df = df.rename(columns=rename_map)
    for col in ["출금","입금","잔액","거래일시","거래내용","상대계좌번호","상대은행","거래구분","상대계좌예금주명"]:
        if col not in df.columns:
            df[col] = ""
    df["_은행"] = "IBK기업"
    df["_계좌번호"] = acct_num
    df["_원본파일"] = os.path.basename(path)
    return df

def parse_nh_xlsx(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
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
    df = df.loc[:, [c for c in df.columns if c is not None and c != "" and not str(c).startswith("col")]]
    acct_num = ""
    for r in all_rows[:12]:
        if r:
            for v in r:
                if v and isinstance(v, str):
                    m = re.search(r"\d{3}-\d{4}-\d{4}-\d{2}", v)
                    if m: acct_num = m.group(0); break
    rename = {
        "거래일시":"거래일시","출금금액":"출금","입금금액":"입금","거래후잔액":"잔액",
        "거래내용":"거래구분","거래기록사항":"거래내용","거래점":"거래점","거래메모":"송금메시지",
    }
    df = df.rename(columns=rename)
    for col in ["출금","입금","잔액","거래일시","거래내용","상대계좌번호","상대은행","거래구분","상대계좌예금주명"]:
        if col not in df.columns:
            df[col] = ""
    df["상대계좌예금주명"] = df["거래내용"].astype(str)
    df["_은행"] = "농협"
    df["_계좌번호"] = acct_num
    df["_원본파일"] = os.path.basename(path)
    return df

# === Load all ===
all_dfs = []
files = sorted(glob.glob(os.path.join(WORK, "*.xls")) + glob.glob(os.path.join(WORK, "*.xlsx")))
files = [f for f in files if "일관성" not in os.path.basename(f)]
print(f"총 {len(files)}개 파일 로드:")
for f in files:
    name = os.path.basename(f)
    if name.startswith("거래내역조회") or name.startswith("과거거래"):
        df = parse_ibk_html(f)
    elif name.startswith("농협"):
        df = parse_nh_xlsx(f)
    else:
        continue
    acct = df['_계좌번호'].iloc[0] if len(df)>0 else ''
    print(f"  {name[:50]:55s}  {len(df):>4}건  ({acct})")
    all_dfs.append(df)

combined = pd.concat(all_dfs, ignore_index=True)
print(f"\n총 거래: {len(combined)}건")

# === Normalize ===
def to_num(s):
    if pd.isna(s): return 0
    s = str(s).replace(",", "").strip()
    if s in ("", "-", "None"): return 0
    try: return int(float(s))
    except: return 0
combined["출"] = combined["출금"].apply(to_num)
combined["입"] = combined["입금"].apply(to_num)
combined["잔액_num"] = combined["잔액"].apply(to_num)

def parse_dt(s):
    if pd.isna(s): return pd.NaT
    s = str(s).strip().replace("/", "-")
    s = re.sub(r"\s+", " ", s)
    for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M"):
        try: return datetime.strptime(s, fmt)
        except: pass
    return pd.to_datetime(s, errors="coerce")
combined["dt"] = combined["거래일시"].apply(parse_dt)
combined = combined.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

# Save
combined.to_csv(os.path.join(WORK, "all_v2.csv"), index=False, encoding="utf-8-sig")
print(f"\n저장: all_v2.csv")

# === 계좌별 통계 ===
print("\n=== 계좌별 거래 ===")
acct_summary = combined.groupby(["_은행","_계좌번호"]).agg(
    건수=("dt","count"),
    최초=("dt","min"),
    최종=("dt","max"),
    입금합=("입","sum"),
    출금합=("출","sum")
).sort_values("건수", ascending=False)
print(acct_summary.to_string())

# === IBK 037 계좌의 주요 거래 (큰 입금 + 큰 출금) ===
print("\n" + "="*100)
print("【IBK 037 계좌 주요 거래 분석】")
print("="*100)
ibk037 = combined[combined["_계좌번호"].astype(str).str.contains("037", na=False)].copy()
print(f"\n037 계좌 총 {len(ibk037)}건")
print(f"기간: {ibk037['dt'].min()} ~ {ibk037['dt'].max()}")

# 1천만원 이상 입금/출금
big_in = ibk037[ibk037["입"]>=10_000_000].sort_values("dt")
big_out = ibk037[ibk037["출"]>=10_000_000].sort_values("dt")
print(f"\n=== 037 계좌 1천만원 이상 입금 ({len(big_in)}건) ===")
for _, r in big_in.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  +{r['입']:>13,}  ({r['거래내용']}) ← {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

print(f"\n=== 037 계좌 1천만원 이상 출금 ({len(big_out)}건) ===")
for _, r in big_out.iterrows():
    print(f"  {r['dt']:%Y-%m-%d %H:%M}  -{r['출']:>13,}  ({r['거래내용']}) → {r['상대계좌예금주명']} / {r['상대은행']} {r['상대계좌번호']} [{r['거래구분']}]")

# === 김광규 송금 직전 7일 입금 (전체 계좌 재추적) ===
print("\n" + "="*100)
print("【김광규 송금 4건 직전 7일 입금 — IBK 037 추가 후 재추적】")
print("="*100)
kim = combined[combined["상대계좌예금주명"].str.contains("김광규",na=False) | combined["거래내용"].str.contains("김광규",na=False)].copy()
kim = kim[kim["출"]>0].sort_values("dt").reset_index(drop=True)

EXCLUDE = ["BNK","이정훈","이승원","김수동"]
def is_exc(row):
    s = str(row["거래내용"]) + " " + str(row["상대계좌예금주명"])
    return any(k in s for k in EXCLUDE)

for i, kr in kim.iterrows():
    sdt = kr["dt"]
    samt = kr["출"]
    print(f"\n▶ [{i+1}] {sdt:%Y-%m-%d %H:%M} 김광규 {samt:,}원")
    win = combined[(combined["dt"] >= sdt-timedelta(days=7)) & (combined["dt"] <= sdt) & (combined["입"]>=1_000_000)].copy()
    win_clean = win[~win.apply(is_exc, axis=1)]
    for _, r in win_clean.sort_values("dt").iterrows():
        s_acct = r["_계좌번호"]
        src = r["상대계좌예금주명"] or r["거래내용"]
        print(f"     {r['dt']:%m-%d %H:%M}  [{r['_은행']:5}{str(s_acct)[-3:]}]  +{r['입']:>13,}  ({r['거래내용']}) ← {src}")
