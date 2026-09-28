#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
숏 방향 국면 게이트 (Short Regime Gate)
=======================================
2026-09-28 실측: **게이트는 대칭이 아니다.** 롱 게이트를 부호만 뒤집어 숏에 적용하면
숏 성적이 오히려 붕괴한다(−0.152R). 숏에는 **같은 조건**(BTC 4H > EMA200)이 유효하다.

실측 근거 (67종목 · 4H · 2025-05-18~2026-09-27 · 3,747건, TP2R/SL1R, 비용 0.12% 왕복)
  · 숏 기준선                       3,747건 · 34.4% · −0.011R · PF 0.984
  · BTC 4H > EMA200 (같은 조건)      1,216건 · 41.0% · +0.188R · PF 1.306  ← 채택
  · BTC 4H < EMA200 (대칭 반전)      2,531건 · 31.2% · −0.106R · PF 0.852  ← 차단
  · 대칭 4종 조합                   1,838건 · 29.8% · −0.152R · PF 0.793  ← 폐기
  · BTC 상단 + 거래량 ≥ 1.5×          691건 · 44.3% · +0.283R · PF 1.487  ← 최우선
  · BTC 상단 + ATR ≥ 3%              621건 · 42.5% · +0.242R · PF 1.408  ← 차선

이 모듈은 숏 스캐너 키트의 내부 구조를 건드리지 않는 **독립 판정기**다.
  · 라이브 판정 : python3 short_regime_gate.py --check --exchange okx --top 150
  · CSV 필터   : python3 short_regime_gate.py --csv scan_rows.csv --out gated.csv
  · JSON 출력  : --json

다른 스크립트에서 쓰기 (3줄):
    import short_regime_gate as G
    v = G.verdict(G.market_state("okx", 150, 3_000_000))
    print(v["action"], v["reasons"], v["size"])

주의: 정보 제공용 도구이며 투자 자문이 아니다.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (compatible; ShortRegimeGate/1.0)"}
EXCLUDE_BASE = {"MSTR", "NVDA", "SOXL", "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "META",
                "COIN", "HOOD", "QQQ", "SPY", "USDC", "DAI", "FDUSD", "XAUT", "PAXG"}

# ---- 게이트 파라미터 (실측값 그대로) ----
G = {
    "btc_required": True,       # BTC 4H > EMA200 필수 (미충족 시 숏 금지)
    "breadth_confirm": 50.0,    # 이 미만이면 포지션 축소 (확정 조건, 차단 조건 아님)
    "scale_below_breadth": 0.6,
    "prefer_vol_ratio": 1.5,    # 최우선 조합 조건 (선호, 차단 아님)
    "prefer_min_atr_pct": 3.0,  # 차선 조합 조건 (선호)
    "block_chg24_below": -15.0, # 급락 추격 제외
}


def _get(url: str, tries: int = 3, timeout: int = 25):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.0 * (i + 1))
    raise last


# ---------------------------------------------------------------- 지표
def ema(vals: list[float], n: int) -> float | None:
    if len(vals) < n:
        return None
    k = 2.0 / (n + 1)
    e = sum(vals[:n]) / n
    for v in vals[n:]:
        e = v * k + e * (1 - k)
    return e


def atr_pct(c: list[list[float]], n: int = 14) -> float | None:
    if len(c) < n + 1:
        return None
    tr = []
    for i in range(1, len(c)):
        h, l = c[i][2], c[i][3]
        pc = c[i - 1][4]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(tr) < n:
        return None
    a = sum(tr[:n]) / n
    for t in tr[n:]:
        a = (a * (n - 1) + t) / n
    close = c[-1][4]
    return a / close * 100.0 if close else None


# ---------------------------------------------------------------- 거래소
def candles_okx(inst: str, bar: str = "4H", limit: int = 300) -> list[list[float]]:
    j = _get(f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={bar}&limit={limit}")
    out = []
    for r in sorted(j.get("data", []), key=lambda x: int(x[0])):
        try:
            out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
        except (TypeError, ValueError):
            continue
    return out


def candles_bybit(sym: str, interval: str = "240", limit: int = 300) -> list[list[float]]:
    j = _get(f"https://api.bybit.com/v5/market/kline?category=linear&symbol={sym}"
             f"&interval={interval}&limit={limit}")
    raw = list(reversed(j.get("result", {}).get("list", [])))
    out = []
    for r in raw:
        try:
            out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
        except (TypeError, ValueError):
            continue
    return out


def universe_okx(min_turnover: float, top: int) -> list[dict]:
    tk = _get("https://www.okx.com/api/v5/market/tickers?instType=SWAP")
    rows = []
    for t in tk.get("data", []):
        iid = t.get("instId", "")
        if not iid.endswith("-USDT-SWAP"):
            continue
        base = iid.split("-")[0]
        if base in EXCLUDE_BASE:
            continue
        try:
            q = float(t.get("volCcy24h") or 0)
            px = float(t.get("last") or 0)
        except (TypeError, ValueError):
            continue
        if q < min_turnover or px <= 0:
            continue
        rows.append({"symbol": iid, "base": base, "turnover": q, "last": px})
    rows.sort(key=lambda r: -r["turnover"])
    return rows[:top]


def universe_bybit(min_turnover: float, top: int) -> list[dict]:
    j = _get("https://api.bybit.com/v5/market/tickers?category=linear")
    rows = []
    for t in j.get("result", {}).get("list", []):
        sym = t.get("symbol", "")
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        if base in EXCLUDE_BASE:
            continue
        try:
            q = float(t.get("turnover24h") or 0)
            px = float(t.get("lastPrice") or 0)
        except (TypeError, ValueError):
            continue
        if q < min_turnover or px <= 0:
            continue
        rows.append({"symbol": sym, "base": base, "turnover": q, "last": px})
    rows.sort(key=lambda r: -r["turnover"])
    return rows[:top]


def pick_exchange(name: str) -> str:
    if name in ("okx", "bybit"):
        return name
    try:
        _get("https://api.bybit.com/v5/market/time", tries=1, timeout=12)
        return "bybit"
    except Exception:  # noqa: BLE001
        return "okx"


# ---------------------------------------------------------------- 시장 상태
def market_state(exchange: str = "auto", top: int = 150, min_turnover: float = 3_000_000,
                 workers: int = 8, verbose: bool = True) -> dict:
    """브레드스(EMA50 상회 비율) · BTC 4H EMA200 상태를 계산한다."""
    ex = pick_exchange(exchange)
    uni = universe_okx(min_turnover, top) if ex == "okx" else universe_bybit(min_turnover, top)
    btc_sym = "BTC-USDT-SWAP" if ex == "okx" else "BTCUSDT"
    fetch = candles_okx if ex == "okx" else candles_bybit

    def one(r):
        try:
            return r, fetch(r["symbol"])
        except Exception:  # noqa: BLE001
            return r, []

    n_above = n_ok = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for r, c in pool.map(one, uni):
            cl = [x[4] for x in c]
            e50 = ema(cl, 50)
            if e50 is None or not cl:
                continue
            n_ok += 1
            if cl[-1] > e50:
                n_above += 1
    breadth = (n_above / n_ok * 100.0) if n_ok else None

    btc_up = None
    btc_px = btc_e200 = None
    try:
        bc = fetch(btc_sym)
        cl = [x[4] for x in bc]
        e200 = ema(cl, 200)
        if e200 and cl:
            btc_up = bool(cl[-1] > e200)
            btc_px, btc_e200 = cl[-1], e200
    except Exception as e:  # noqa: BLE001
        if verbose:
            print(f"  · BTC 조회 실패({type(e).__name__}) → 판정 불가", file=sys.stderr)

    st = {"exchange": ex, "universe": len(uni), "evaluated": n_ok, "n_above": n_above,
          "breadth": breadth, "btc_up": btc_up, "btc_close": btc_px, "btc_ema200": btc_e200,
          "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    return st


def verdict(st: dict, atr_pct_val: float | None = None, vol_ratio: float | None = None,
            chg24: float | None = None) -> dict:
    """시장 상태(+개별 종목 지표) → 숏 진입 판정."""
    reasons, warns = [], []
    action, size = "ALLOW", 1.0

    if st.get("btc_up") is False:
        action, size = "BLOCK", 0.0
        reasons.append("BTC 4H < EMA200 — 실측 31.2% / −0.106R / PF 0.852 구간, 숏 전면 금지")
    elif st.get("btc_up") is None:
        action, size = "CAUTION", 0.5
        warns.append("BTC 국면 판정 불가 — 포지션 절반")

    b = st.get("breadth")
    if isinstance(b, (int, float)):
        if b < G["breadth_confirm"] and action == "ALLOW":
            size = min(size, G["scale_below_breadth"])
            warns.append(f"브레드스 {b:.0f}% < {G['breadth_confirm']:.0f}% — 확인 조건 미충족(포지션 {size:.1f}배)")
        elif b >= G["breadth_confirm"]:
            reasons.append(f"브레드스 {b:.0f}% ≥ {G['breadth_confirm']:.0f}% — 확인 조건 충족")
    else:
        warns.append("브레드스 계산 불가")

    if chg24 is not None and chg24 < G["block_chg24_below"]:
        action, size = "BLOCK", 0.0
        reasons.append(f"24h {chg24:+.1f}% — 급락 추격 구간(실측 33.3% / −0.051R)")

    if action == "ALLOW":
        if vol_ratio is not None and vol_ratio >= G["prefer_vol_ratio"]:
            reasons.append(f"거래량 {vol_ratio:.1f}× ≥ {G['prefer_vol_ratio']} — 최우선 조합(44.3% / +0.283R)")
        elif atr_pct_val is not None and atr_pct_val >= G["prefer_min_atr_pct"]:
            reasons.append(f"ATR {atr_pct_val:.1f}% ≥ {G['prefer_min_atr_pct']}% — 차선 조합(42.5% / +0.242R)")
        else:
            warns.append("선호 조건(거래량 ≥1.5× 또는 ATR ≥3%) 미충족 — 기대값이 기준선 수준")

    return {"action": action, "size": round(size, 2), "reasons": reasons, "warnings": warns,
            "market": st, "rules": dict(G)}


def gate_rule_text() -> str:
    return ("BTC 4H > EMA200 필수 · 브레드스 ≥ 50% 확인 · "
            f"거래량 ≥ {G['prefer_vol_ratio']}× 또는 ATR ≥ {G['prefer_min_atr_pct']}% 선호 · "
            f"24h {G['block_chg24_below']:.0f}% 이하 차단")


# ---------------------------------------------------------------- CLI
def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="숏 방향 국면 게이트 (독립 판정기)")
    ap.add_argument("--exchange", default="auto", choices=["auto", "okx", "bybit"])
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--min-turnover", type=float, default=3_000_000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--check", action="store_true", help="현재 시장 상태로 숏 진입 판정 출력")
    ap.add_argument("--csv", default=None, help="숏 스캐너 CSV에 게이트 컬럼 추가")
    ap.add_argument("--out", default=None, help="필터된 CSV 저장 경로")
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    args = ap.parse_args()

    if not args.check and not args.csv:
        ap.print_help()
        return 0

    st = market_state(args.exchange, args.top, args.min_turnover, args.workers)
    v = verdict(st)

    if args.csv:
        rows = list(csv.DictReader(open(args.csv, encoding="utf-8-sig")))
        extra = ["short_gate", "short_gate_size", "short_gate_note"]
        for r in rows:
            vv = verdict(st, _f(r.get("atr_pct")), _f(r.get("vol_ratio")), _f(r.get("chg24")))
            r["short_gate"] = vv["action"]
            r["short_gate_size"] = vv["size"]
            r["short_gate_note"] = " ; ".join(vv["reasons"] + vv["warnings"])
        out = args.out or args.csv.replace(".csv", "_gated.csv")
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        keep = sum(1 for r in rows if r["short_gate"] != "BLOCK")
        print(f"CSV → {out} · 통과 {keep}/{len(rows)}행")
        return 0

    if args.json:
        print(json.dumps(v, ensure_ascii=False, indent=2, default=str))
        return 0

    print("=" * 74)
    print("  SHORT REGIME GATE — 숏 방향 국면 판정")
    print(f"  {st['checked_at']} · 거래소 {st['exchange']} · 유니버스 {st['universe']}종목")
    print("=" * 74)
    b = st.get("breadth")
    bs = f"{b:.1f}%" if isinstance(b, (int, float)) else "—"
    up = st.get("btc_up")
    btc = "상단" if up is True else ("하단" if up is False else "미판정")
    bpx = f"{st['btc_close']:,.0f}" if st.get("btc_close") else "—"
    be2 = f"{st['btc_ema200']:,.0f}" if st.get("btc_ema200") else "—"
    print(f"  브레드스(EMA50 상회) {bs}  ({st.get('n_above')}/{st.get('evaluated')})")
    print(f"  BTC 4H {btc}  (BTC {bpx} vs EMA200 {be2})")
    print(f"  판정: {v['action']}  ·  포지션 배수 {v['size']}")
    for r in v["reasons"]:
        print(f"    + {r}")
    for w in v["warnings"]:
        print(f"    ! {w}")
    print(f"  규칙: {gate_rule_text()}")
    print("\n  ※ 정보 제공용. 투자 자문이 아니며 과거 성과가 미래를 보장하지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
