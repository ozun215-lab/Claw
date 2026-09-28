#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit 알트 숏 스캐너 (Bybit Alt Short Scanner)
================================================

USDT 무기한(perp) 전 종목을 훑어 **숏 진입 후보**를 점수화하는 스캐너.
4시간봉으로 추세/구조를 판단하고 1시간봉으로 타이밍을 정하며 0~100 점수로 순위를 매긴다.

점수 항목 (합계 100)
  · 4H 하락 추세    : 종가 < EMA200, EMA20 < EMA50 < EMA200, EMA50 기울기 하락
  · 4H 모멘텀      : RSI(14) 30~48 구간(과매도 직전, 반등 전)
  · 거래량 확장     : 최근 3봉 거래량 / 직전 20봉 평균
  · 구조            : 직전 20봉 저점 이탈 또는 근접
  · 진입 품질      : EMA20 대비 ATR 이격 (너무 멀리 가면 감점)
  · 1H 타이밍      : RSI(14) 32~50 구간
  · 펀딩비          : 플러스(롱 쏠림) 만점, 마이너스이면 0점

단락 조건
  · 4H RSI 20↓ (과매도 반등 위험)
  · 1H RSI 22↓
  · 24h -25%↓ (급락 추격 금지)
  · ATR 12%↑ (변동성 과다)
  · 거래대금 $10M 미만

숏 게이트 (short_regime_gate.py 연동)
  · BTC 4H < EMA200 → BLOCK (숏에 불리한 구간)
  · 브레드스 < 50% → 포지션 축소
  · 선호 조건(거래량 ≥1.5× 또는 ATR ≥3%) 미충족 → 경고

출력물
  · 콘솔 순위표
  · CSV  (--csv)
  · HTML 리포트 (--html)

사용법
  python3 bybit_alt_short_scanner.py
  python3 bybit_alt_short_scanner.py --exchange okx --top 200 --html short.html
  python3 bybit_alt_short_scanner.py --edge --min-score 65
  python3 bybit_alt_short_scanner.py --no-gate   # 숏 게이트 비활성화

주의: 이 스크립트는 정보 제공이며 투자 자문이 아닙니다.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    print("requests 가 필요합니다:  pip install requests", file=sys.stderr)
    raise

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AltShortScanner/1.0)"}
_tl = threading.local()

EQUITY_TICKERS = {
    "AAPL","MSFT","NVDA","GOOGL","GOOG","AMZN","META","TSLA","MSTR","COIN",
    "HOOD","CRCL","SPY","QQQ","TQQQ","SQQQ","SOXL","SOXS","AMD","NFLX",
    "PLTR","BRK.B","JPM","V","MA","DIS","INTC","MU","ORCL","CRM","UBER",
    "ABNB","SBUX","NKE","BA","SKHYNIX","SKHY","SAMSUNG","HYNIX","AVGO","LLY","UNH","XOM",
}
INCLUDE_EQUITIES = False

# edge 필터
EDGE = {"min_vol_ratio": 0.0, "min_atr_pct": 0.0, "exclude_setup": set()}

# 숏 게이트 상태 (short_regime_gate 연동)
GATE_RESULT = {"action": "ALLOW", "size": 1.0, "reasons": [], "warnings": [], "checked": False}

# ────────────────────────── 공통 HTTP ──────────────────────────

def _sess():
    if not hasattr(_tl, "s"):
        s = requests.Session()
        s.headers.update(UA)
        _tl.s = s
    return _tl.s

def _get(url, params=None, timeout=20):
    for attempt in range(3):
        try:
            r = _sess().get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(1.0 * (attempt + 1))

# ────────────────────────── 지표 계산 ──────────────────────────

def ema(vals, n):
    if len(vals) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(vals[:n]) / n
    for v in vals[n:]:
        e = v * k + e * (1 - k)
    return e

def rsi(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n-1) + gains[i]) / n
        al = (al * (n-1) + losses[i]) / n
    return 100 - 100 / (1 + ag / al) if al else 100.0

def atr(candles, n=14):
    if len(candles) < n + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i][2], candles[i][3], candles[i-1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:n]) / n
    for t in trs[n:]:
        a = (a * (n-1) + t) / n
    return a

# ────────────────────────── 거래소 API ──────────────────────────

def bybit_symbols(top_n, min_turnover_usd):
    data = _get("https://api.bybit.com/v5/market/tickers", params={"category":"linear"})
    rows = data["result"]["list"]
    out = []
    for r in rows:
        s = r["symbol"]
        if not s.endswith("USDT"):
            continue
        base = s[:-4]
        if not INCLUDE_EQUITIES and base in EQUITY_TICKERS:
            continue
        try:
            tv = float(r.get("turnover24h") or 0)
            lp = float(r.get("lastPrice") or 0)
            chg = float(r.get("price24hPcnt") or 0) * 100
            fund = float(r.get("fundingRate") or 0)
        except:
            continue
        if tv < min_turnover_usd or lp <= 0:
            continue
        out.append({"symbol": s, "base": base, "turnover": tv, "last": lp, "chg24": chg, "funding": fund})
    out.sort(key=lambda x: -x["turnover"])
    return out[:top_n]

def okx_symbols(top_n, min_turnover_usd):
    data = _get("https://www.okx.com/api/v5/market/tickers", params={"instType":"SWAP"})
    rows = data.get("data", [])
    out = []
    for r in rows:
        inst = r.get("instId","")
        if not inst.endswith("-USDT-SWAP"):
            continue
        base = inst.replace("-USDT-SWAP","")
        if not INCLUDE_EQUITIES and base in EQUITY_TICKERS:
            continue
        try:
            tv = float(r.get("volCcy24h") or 0) * float(r.get("last") or 0)
            lp = float(r.get("last") or 0)
            op = float(r.get("open24h") or lp)
            chg = (lp - op) / op * 100 if op else 0
        except:
            continue
        if tv < min_turnover_usd or lp <= 0:
            continue
        fund_data = _get("https://www.okx.com/api/v5/public/funding-rate", params={"instId": inst})
        fund = float(fund_data["data"][0].get("fundingRate", 0)) if fund_data.get("data") else 0
        out.append({"symbol": inst, "base": base, "turnover": tv, "last": lp, "chg24": chg, "funding": fund})
    out.sort(key=lambda x: -x["turnover"])
    return out[:top_n]

def fetch_candles_bybit(symbol, interval, limit=250):
    data = _get("https://api.bybit.com/v5/market/kline",
                params={"category":"linear","symbol":symbol,"interval":interval,"limit":limit})
    raw = data["result"]["list"]
    # [time, open, high, low, close, volume, turnover] 내림차순 → 오름차순
    candles = []
    for r in reversed(raw):
        candles.append([float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
    return candles

def fetch_candles_okx(symbol, bar, limit=250):
    data = _get("https://www.okx.com/api/v5/market/candles",
                params={"instId":symbol,"bar":bar,"limit":limit})
    raw = data.get("data",[])
    candles = []
    for r in reversed(raw):
        candles.append([float(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
    return candles

# ────────────────────────── 숏 점수화 ──────────────────────────

def score_short(sym_info, exchange="bybit"):
    sym = sym_info["symbol"]
    chg24 = sym_info["chg24"]
    fund = sym_info["funding"]

    try:
        if exchange == "bybit":
            c4 = fetch_candles_bybit(sym, "240", 250)
            c1 = fetch_candles_bybit(sym, "60", 100)
        else:
            c4 = fetch_candles_okx(sym, "4H", 250)
            c1 = fetch_candles_okx(sym, "1H", 100)
    except Exception as e:
        return None

    if len(c4) < 210 or len(c1) < 20:
        return None

    closes4 = [c[4] for c in c4]
    vols4   = [c[5] for c in c4]
    closes1 = [c[4] for c in c1]

    last = closes4[-1]
    e200 = ema(closes4, 200)
    e50  = ema(closes4, 50)
    e20  = ema(closes4, 20)
    if not all([e200, e50, e20]):
        return None

    atr4 = atr(c4, 14)
    if not atr4 or last <= 0:
        return None
    atr_pct_val = atr4 / last * 100

    rsi4 = rsi(closes4, 14)
    rsi1 = rsi(closes1, 14)
    if rsi4 is None or rsi1 is None:
        return None

    # ── 단락 조건 ──
    if rsi4 < 20:       return None   # 과매도 반등 위험
    if rsi1 < 22:       return None
    if abs(chg24) > 25: return None   # 급변동
    if atr_pct_val > 12: return None  # 변동성 과다

    # edge 필터
    vol3  = sum(vols4[-3:]) / 3
    vol20 = sum(vols4[-23:-3]) / 20 if len(vols4) >= 23 else sum(vols4[:-3]) / max(len(vols4)-3,1)
    vol_ratio = vol3 / vol20 if vol20 else 0

    if EDGE["min_vol_ratio"] and vol_ratio < EDGE["min_vol_ratio"]: return None
    if EDGE["min_atr_pct"]   and atr_pct_val < EDGE["min_atr_pct"]: return None

    # ── 점수 계산 ──
    score = 0

    # 4H 하락 추세 (16점)
    trend_pts = 0
    if last < e200: trend_pts += 8
    if e20 < e50:   trend_pts += 4
    if e50 < e200:  trend_pts += 4
    score += trend_pts

    # EMA50 기울기 하락 (8점) — 10봉 전 EMA50 대비
    if len(closes4) >= 210:
        e50_prev = ema(closes4[:-10], 50)
        if e50_prev and e50 < e50_prev * 0.98:
            score += 8
        elif e50_prev and e50 < e50_prev:
            score += 4

    # 4H 모멘텀 (14점) — RSI 30~48 구간
    if 30 <= rsi4 <= 48:
        score += 14
    elif 48 < rsi4 <= 55:
        score += 7
    elif rsi4 < 30:
        score += 3  # 과매도 — 부분 점수만

    # 거래량 확장 (14점)
    if vol_ratio >= 2.0:   score += 14
    elif vol_ratio >= 1.5: score += 10
    elif vol_ratio >= 1.2: score += 6
    elif vol_ratio >= 1.0: score += 3

    # 구조 — 직전 20봉 저점 이탈/근접 (16점)
    low20 = min(c[3] for c in c4[-21:-1])
    dist_low20 = (last - low20) / low20 * 100  # 음수면 이탈
    if dist_low20 <= 0:       score += 16   # 저점 이탈
    elif dist_low20 <= 1.0:   score += 12   # 저점 근접
    elif dist_low20 <= 2.5:   score += 6
    elif dist_low20 <= 4.0:   score += 2

    # 진입 품질 (14점) — EMA20 대비 이격
    dist_ema20 = (e20 - last) / atr4  # 양수 = EMA20 아래 (숏 유리)
    if dist_ema20 >= 0 and dist_ema20 <= 1.0:
        score += 14
    elif dist_ema20 >= 0 and dist_ema20 <= 2.0:
        score += 8
    elif dist_ema20 < 0 and abs(dist_ema20) <= 1.0:
        score += 6   # EMA20 위에 있지만 근접
    elif dist_ema20 < 0 and abs(dist_ema20) > 3.0:
        score -= 6   # 너무 멀리 올라감

    # 1H 타이밍 (8점)
    if 32 <= rsi1 <= 50:   score += 8
    elif 50 < rsi1 <= 58:  score += 4

    # 펀딩비 (10점) — 플러스(롱 쏠림)이면 숏에 유리
    if fund >= 0.0008:    score += 10
    elif fund >= 0.0004:  score += 6
    elif fund >= 0.0001:  score += 3
    elif fund < 0:        score += 0   # 숏 쏠림 — 불리

    # ── 4H RSI 과열 감점 ──
    if rsi4 > 75: score -= 12
    if rsi1 > 73: score -= 8

    score = max(0, min(100, score))

    # ── 셋업 분류 ──
    if dist_low20 <= 0:
        setup = "저점이탈"
    elif dist_low20 <= 1.5 and vol_ratio >= 1.2:
        setup = "돌파숏"
    elif dist_ema20 >= 0 and dist_ema20 <= 1.5:
        setup = "눌림숏"
    else:
        setup = "관찰"

    if "관찰" in EDGE.get("exclude_setup", set()) and setup == "관찰":
        return None
    if setup in EDGE.get("exclude_setup", set()):
        return None

    # ── 손절 / TP ──
    high10 = max(c[2] for c in c4[-10:])
    stop = max(last + 1.5 * atr4, high10 + 0.25 * atr4)
    risk = stop - last
    tp1  = last - 2.0 * risk
    tp2  = last - 3.2 * risk
    risk_pct = risk / last * 100

    return {
        "symbol":    sym_info["base"],
        "score":     round(score, 1),
        "setup":     setup,
        "last":      last,
        "chg24":     round(chg24, 2),
        "rsi_4h":    round(rsi4, 1),
        "rsi_1h":    round(rsi1, 1),
        "vol_ratio": round(vol_ratio, 2),
        "funding":   round(fund, 4),
        "atr_pct":   round(atr_pct_val, 2),
        "dist_low20":round(dist_low20, 2),
        "stop":      round(stop, 6),
        "tp1":       round(tp1, 6),
        "tp2":       round(tp2, 6),
        "risk_pct":  round(risk_pct, 2),
        "turnover":  sym_info["turnover"],
        "gate_size": GATE_RESULT["size"],
    }

# ────────────────────────── 숏 게이트 연동 ──────────────────────

def run_short_gate(exchange, top_n, min_turnover):
    global GATE_RESULT
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import short_regime_gate as G
        state = G.market_state(exchange, top_n, min_turnover)
        v = G.verdict(state)
        GATE_RESULT = v
        GATE_RESULT["checked"] = True
    except Exception as e:
        GATE_RESULT = {"action": "ALLOW", "size": 1.0, "reasons": [f"게이트 오류: {e}"],
                       "warnings": [], "checked": False}

# ────────────────────────── 스캔 실행 ──────────────────────────

def run_scan(args):
    exchange    = args.exchange
    top_n       = args.top
    min_turn    = args.min_turnover * 1_000_000
    min_score   = args.min_score
    workers     = args.workers
    print_n     = getattr(args, "print_n", 15)
    no_gate     = getattr(args, "no_gate", False)

    # edge 설정
    if getattr(args, "edge", False):
        EDGE["min_vol_ratio"]  = 1.5
        EDGE["min_atr_pct"]    = 3.0
        EDGE["exclude_setup"]  = set()

    now_kst = datetime.now(KST)
    stamp   = now_kst.strftime("%Y%m%d_%H%M")
    ts_str  = now_kst.strftime("%Y-%m-%d %H:%M:%S KST")

    edge_rule = ""
    if EDGE["min_vol_ratio"] or EDGE["min_atr_pct"]:
        parts = []
        if EDGE["min_vol_ratio"]: parts.append(f"거래량 ≥ {EDGE['min_vol_ratio']}배")
        if EDGE["min_atr_pct"]:   parts.append(f"ATR ≥ {EDGE['min_atr_pct']}%")
        if EDGE["exclude_setup"]: parts.append(f"셋업 제외 {'/'.join(EDGE['exclude_setup'])}")
        edge_rule = " · ".join(parts)
        print(f"[숏run] {ts_str} — edge 필터: {edge_rule}")
    else:
        print(f"[숏run] {ts_str}")

    # 숏 게이트 체크
    if not no_gate:
        run_short_gate(exchange, top_n, min_turn)
        g = GATE_RESULT
        gate_line = f"SHORT_GATE|{g['action']}|size={g['size']}"
        if g["reasons"]:    gate_line += "|" + "|".join(g["reasons"])
        if g["warnings"]:   gate_line += "|WARN:" + "|".join(g["warnings"])
        print(gate_line)
        if g["action"] == "BLOCK":
            print("[숏ok] 게이트 BLOCK — 숏 신호 발송 중단")
            return [], 0, ts_str, stamp, edge_rule

    # 종목 조회
    try:
        if exchange == "bybit":
            symbols = bybit_symbols(top_n, min_turn)
        else:
            symbols = okx_symbols(top_n, min_turn)
    except Exception as e:
        print(f"[숏오류] 종목 조회 실패: {e}", file=sys.stderr)
        return [], 0, ts_str, stamp, edge_rule

    total = len(symbols)
    results = []
    errors  = 0

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(score_short, s, exchange): s for s in symbols}
        for fut in as_completed(futs):
            try:
                r = fut.result()
                if r and r["score"] >= min_score:
                    results.append(r)
            except Exception:
                errors += 1

    results.sort(key=lambda x: -x["score"])

    # 콘솔 출력
    hdr = f"  {'#':>3} {'심볼':<12} {'점수':>6} {'셋업':<10} {'가격':>16} {'24h%':>7} {'RSI4h':>6} {'RSI1h':>6} {'거래량':>8} {'펀딩%':>8} {'손절':>12} {'TP1':>12} {'손절폭':>7}"
    print()
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(results[:print_n], 1):
        fund_str = f"{r['funding']*100:+.4f}"
        print(f"  {i:>3} {r['symbol']:<12} {r['score']:>6.1f} {r['setup']:<10} "
              f"{r['last']:>16.6g} {r['chg24']:>6.2f}% {r['rsi_4h']:>6.1f} {r['rsi_1h']:>6.1f} "
              f"{r['vol_ratio']:>7.2f}x {fund_str:>8} {r['stop']:>12.6g} {r['tp1']:>12.6g} {r['risk_pct']:>6.2f}%")

    print(f"\n[숏ok] 후보 {len(results)}개 / 분석 {total}개 — 오류 {errors}개")
    return results, total, ts_str, stamp, edge_rule


# ────────────────────────── CSV / HTML ──────────────────────────

def write_csv(results, path):
    if not results:
        return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)

def write_html(results, path, ts_str, total, exchange, edge_rule, gate_result):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    gate_action  = gate_result.get("action", "N/A")
    gate_size    = gate_result.get("size", 1.0)
    gate_reasons = " / ".join(gate_result.get("reasons", []))
    gate_warns   = " / ".join(gate_result.get("warnings", []))
    gate_color   = {"ALLOW":"#3fc7a4","CAUTION":"#e8b45c","BLOCK":"#e0655f"}.get(gate_action,"#8ea3bf")

    rows_html = ""
    for i, r in enumerate(results, 1):
        chg_cls  = "pos" if r["chg24"] >= 0 else "neg"
        fund_str = f"{r['funding']*100:+.4f}%"
        badge_cls = {"저점이탈":"b-이탈","돌파숏":"b-돌파","눌림숏":"b-눌림","관찰":"b-관찰"}.get(r["setup"],"b-관찰")
        rows_html += f"""
        <tr data-sym="{r['symbol']}" data-setup="{r['setup']}">
          <td class="l rk">{i}</td>
          <td class="l"><span class="sym">{r['symbol']}</span></td>
          <td class="l"><span class="badge {badge_cls}">{r['setup']}</span></td>
          <td class="l"><span style="font-size:11px;color:var(--dim2)">{int(r['score'])}</span>
            <span style="display:inline-block;margin-left:4px;width:{int(r['score'])}px;height:6px;background:var(--rose);border-radius:3px;vertical-align:middle;opacity:.7"></span>
          </td>
          <td style="font-family:var(--mono)">{r['last']:.6g}</td>
          <td class="{chg_cls}">{r['chg24']:+.2f}%</td>
          <td>{r['rsi_4h']:.1f}</td>
          <td>{r['rsi_1h']:.1f}</td>
          <td>{r['vol_ratio']:.2f}x</td>
          <td style="color:{'#3fc7a4' if r['funding']>0 else '#e0655f'}">{fund_str}</td>
          <td>{r['atr_pct']:.2f}%</td>
          <td class="neg">{r['stop']:.6g}</td>
          <td class="pos">{r['tp1']:.6g}</td>
          <td>{r['risk_pct']:.2f}%</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALT SHORT RADAR — {ts_str}</title>
<style>
:root{{
  --ink:#0b1220;--ink2:#0f1929;--panel:#121e30;--panel2:#16243a;
  --line:#20304a;--line2:#2a3d5c;
  --txt:#e6edf7;--dim:#8ea3bf;--dim2:#63799a;
  --amber:#e8b45c;--azure:#5fa8f5;--teal:#3fc7a4;--rose:#e0655f;--violet:#9d8bf0;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}}
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0}}
body{{background:radial-gradient(1100px 620px at 12% -12%,#16263f 0%,transparent 60%),radial-gradient(900px 520px at 96% 4%,#1a2033 0%,transparent 55%),var(--ink);color:var(--txt);font-family:"IBM Plex Sans KR",-apple-system,"Malgun Gothic",sans-serif;font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1400px;margin:0 auto;padding:34px 22px 80px}}
.top{{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-end;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:20px}}
h1{{margin:0;font-size:26px;font-weight:700;letter-spacing:.14em}}
h1 small{{display:block;font-size:11px;font-weight:500;letter-spacing:.34em;color:var(--dim2);margin-top:3px}}
.meta{{font-family:var(--mono);font-size:12px;color:var(--dim);text-align:right;line-height:1.85}}
.meta b{{color:var(--txt);font-weight:500}}
.strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0 8px}}
.stat{{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:12px;padding:16px 18px}}
.stat .k{{font-size:11px;letter-spacing:.18em;color:var(--dim2);text-transform:uppercase}}
.stat .v{{font-family:var(--mono);font-size:30px;font-weight:600;margin-top:6px}}
.stat .s{{font-size:12px;color:var(--dim);margin-top:2px}}
.gate-bar{{margin:16px 0;padding:14px 18px;border:1px solid var(--line);border-radius:12px;background:var(--panel);display:flex;flex-wrap:wrap;gap:12px;align-items:center}}
.gate-badge{{font-size:13px;font-weight:700;padding:4px 14px;border-radius:8px;border:1.5px solid {gate_color};color:{gate_color}}}
.gate-reason{{font-size:12px;color:var(--dim)}}
.sec{{margin-top:38px}}
.sech{{display:flex;align-items:baseline;gap:12px;border-bottom:1px solid var(--line);padding-bottom:9px;margin-bottom:16px}}
.sech h2{{margin:0;font-size:13px;letter-spacing:.22em;font-weight:600}}
.ctl{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:4px 0 14px}}
.ctl input[type=search]{{background:var(--ink2);border:1px solid var(--line2);border-radius:9px;padding:9px 13px;color:var(--txt);font-family:var(--mono);font-size:13px;min-width:210px}}
.chip{{background:var(--ink2);border:1px solid var(--line2);color:var(--dim);border-radius:9px;padding:8px 13px;font-size:12.5px;cursor:pointer;font-family:inherit}}
.chip[aria-pressed=true]{{background:rgba(224,101,95,.14);border-color:var(--rose);color:var(--rose)}}
.cnt{{font-family:var(--mono);font-size:12px;color:var(--dim2);margin-left:auto}}
.tblwrap{{border:1px solid var(--line);border-radius:13px;overflow:auto;background:var(--panel)}}
table{{width:100%;border-collapse:collapse;min-width:1000px}}
thead th{{position:sticky;top:0;background:var(--panel2);z-index:2;text-align:right;font-size:11px;letter-spacing:.1em;color:var(--dim2);font-weight:600;padding:11px 12px;border-bottom:1px solid var(--line2);white-space:nowrap}}
thead th.l{{text-align:left}}
tbody td{{padding:11px 12px;border-bottom:1px solid rgba(32,48,74,.6);text-align:right;font-family:var(--mono);font-size:13px;white-space:nowrap}}
tbody td.l{{text-align:left;font-family:inherit}}
tbody tr:hover{{background:rgba(224,101,95,.055)}}
tbody tr:last-child td{{border-bottom:none}}
.rk{{color:var(--dim2);font-size:12px}} .sym{{font-weight:600;font-size:14px}}
.pos{{color:var(--teal)}} .neg{{color:var(--rose)}} .mut{{color:var(--dim2)}}
.badge{{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11.5px;border:1px solid transparent}}
.b-이탈{{background:rgba(224,101,95,.15);color:var(--rose);border-color:rgba(224,101,95,.4)}}
.b-돌파{{background:rgba(232,180,92,.14);color:var(--amber);border-color:rgba(232,180,92,.35)}}
.b-눌림{{background:rgba(95,168,245,.14);color:var(--azure);border-color:rgba(95,168,245,.35)}}
.b-관찰{{background:rgba(142,163,191,.1);color:var(--dim);border-color:var(--line2)}}
.note{{margin-top:40px;border-top:1px solid var(--line);padding-top:20px;display:grid;grid-template-columns:1.4fr 1fr;gap:26px;font-size:13px;color:var(--dim)}}
.note h3{{font-size:11.5px;letter-spacing:.2em;color:var(--dim2);margin:0 0 9px}}
.note ul{{margin:0;padding-left:17px}} .note li{{margin-bottom:5px}}
.warn{{color:var(--rose);font-size:12.5px}}
@media(max-width:860px){{.strip{{grid-template-columns:repeat(2,1fr)}}.note{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <h1>ALT SHORT RADAR<small>USDT PERPETUAL · SHORT-ONLY SCANNER</small></h1>
    </div>
    <div class="meta">
      스캔 시각 <b>{ts_str}</b><br>
      거래소 <b>{exchange.upper()} USDT 무기한</b> · 분석 <b>{total}</b>종목<br>
      {'edge 필터: <b>' + edge_rule + '</b>' if edge_rule else ''}
    </div>
  </header>

  <section class="strip">
    <div class="stat"><div class="k">Scanned</div><div class="v">{total}</div><div class="s">분석 완료 종목</div></div>
    <div class="stat"><div class="k">Candidates</div><div class="v" style="color:var(--rose)">{len(results)}</div><div class="s">기준점 이상 · 게이트 통과</div></div>
    <div class="stat"><div class="k">Top score</div><div class="v" style="color:var(--amber)">{int(results[0]['score']) if results else 0}</div><div class="s">{'#1 ' + results[0]['symbol'] if results else '—'}</div></div>
    <div class="stat"><div class="k">Gate</div><div class="v" style="font-size:18px;color:{gate_color}">{gate_action}</div><div class="s">size × {gate_size:.1f}</div></div>
  </section>

  <div class="gate-bar">
    <span class="gate-badge">{gate_action}</span>
    <span class="gate-reason">{gate_reasons}</span>
    {f'<span style="color:var(--amber);font-size:12px">⚠ {gate_warns}</span>' if gate_warns else ''}
  </div>

  <section class="sec">
    <div class="sech"><h2>SHORT SIGNAL BOARD</h2><span>점수 = 추세16 · 기울기8 · 모멘텀14 · 거래량14 · 구조16 · 진입14 · 타이밍8 · 펀딩10</span></div>
    <div class="ctl">
      <input id="q" type="search" placeholder="심볼 검색 (예: XRP)" autocomplete="off">
      <button class="chip" data-setup="전체" aria-pressed="true">전체</button>
      <button class="chip" data-setup="저점이탈" aria-pressed="false">저점이탈</button>
      <button class="chip" data-setup="돌파숏" aria-pressed="false">돌파숏</button>
      <button class="chip" data-setup="눌림숏" aria-pressed="false">눌림숏</button>
      <span class="cnt" id="cnt">0 / 0 종목</span>
    </div>
    <div class="tblwrap">
      <table>
        <thead><tr>
          <th class="l">#</th><th class="l">심볼</th><th class="l">셋업</th><th class="l">점수</th>
          <th>가격</th><th>24h%</th><th>RSI 4H</th><th>RSI 1H</th><th>거래량배수</th>
          <th>펀딩 8h</th><th>ATR%</th><th>손절</th><th>TP1</th><th>손절폭</th>
        </tr></thead>
        <tbody id="tb">{rows_html}</tbody>
      </table>
    </div>
  </section>

  <footer class="note">
    <div>
      <h3>숏 판정 규칙</h3>
      <ul>
        <li><b>저점이탈</b> — 4H 직전 20봉 저점을 종가로 하향 이탈</li>
        <li><b>돌파숏</b> — 저점 1.5% 이내 + 거래량 1.2배 이상</li>
        <li><b>눌림숏</b> — EMA20 이격 ≤ 1.5 ATR (반등 후 재하락)</li>
        <li>손절 = max(진입 + 1.5×ATR, 최근 10봉 고점 + 0.25×ATR)</li>
        <li>TP1 = 2.0R / TP2 = 3.2R</li>
      </ul>
      <h3 style="margin-top:14px">숏 게이트 (short_regime_gate)</h3>
      <ul>
        <li>BTC 4H &lt; EMA200 → BLOCK (숏에 불리한 구간)</li>
        <li>브레드스 &lt; 50% → 포지션 축소 (size × 0.6)</li>
        <li>선호: 거래량 ≥1.5× 또는 ATR ≥3%</li>
      </ul>
    </div>
    <div>
      <h3>재현</h3>
      <ul>
        <li><code>python3 bybit_alt_short_scanner.py --edge --html short.html</code></li>
        <li><code>python3 alt_short_runner.py --edge --alert-min-score 65</code></li>
      </ul>
      <p class="warn">⚠ 본 리포트는 정보 제공용이며 투자 자문이 아닙니다. 레버리지 상품은 원금 전액 손실이 가능합니다.</p>
    </div>
  </footer>
</div>
<script>
(function(){{
  var rows=Array.prototype.slice.call(document.querySelectorAll('#tb tr'));
  var cnt=document.getElementById('cnt');
  var q=document.getElementById('q');
  var mode='전체';
  function apply(){{
    var needle=(q&&q.value||'').trim().toUpperCase();
    var shown=0;
    rows.forEach(function(tr){{
      var ok=(mode==='전체'||tr.getAttribute('data-setup')===mode)&&(!needle||(tr.getAttribute('data-sym')||'').indexOf(needle)>=0);
      tr.style.display=ok?'':'none';
      if(ok){{shown++;var rk=tr.querySelector('.rk');if(rk)rk.textContent=shown;}}
    }});
    if(cnt)cnt.textContent=shown+' / '+rows.length+' 종목';
  }}
  document.querySelectorAll('.chip').forEach(function(b){{
    b.addEventListener('click',function(){{
      document.querySelectorAll('.chip').forEach(function(o){{o.setAttribute('aria-pressed','false');}});
      b.setAttribute('aria-pressed','true');mode=b.getAttribute('data-setup');apply();
    }});
  }});
  if(q)q.addEventListener('input',apply);
  apply();
}})();
</script>
</body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ────────────────────────── CLI ──────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Bybit 알트 숏 스캐너")
    ap.add_argument("--exchange",   default="bybit", choices=["bybit","okx"])
    ap.add_argument("--top",        type=int,   default=200)
    ap.add_argument("--min-turnover", dest="min_turnover", type=float, default=5.0, help="최소 24h 거래대금 (백만 USD)")
    ap.add_argument("--min-score",  dest="min_score", type=int, default=55)
    ap.add_argument("--workers",    type=int,   default=8)
    ap.add_argument("--print-n",    dest="print_n", type=int, default=15)
    ap.add_argument("--edge",       action="store_true", help="edge 필터 (거래량≥1.5× · ATR≥3%)")
    ap.add_argument("--no-gate",    dest="no_gate", action="store_true", help="숏 게이트 비활성화")
    ap.add_argument("--html",       default="", help="HTML 리포트 저장 경로")
    ap.add_argument("--csv",        default="", help="CSV 저장 경로")
    args = ap.parse_args()

    results, total, ts_str, stamp, edge_rule = run_scan(args)

    if args.csv and results:
        write_csv(results, args.csv)
        print(f"     CSV    {args.csv}")
    if args.html:
        write_html(results, args.html, ts_str, total, args.exchange, edge_rule, GATE_RESULT)
        print(f"     HTML   {args.html}")

if __name__ == "__main__":
    main()
