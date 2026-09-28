#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit 알트 롱 스캐너 (Bybit Alt Long Scanner)
============================================

USDT 무기한(perp) 전 종목을 훑어서 **롱 진입 후보**만 뽑아내는 스캐너.
4시간봉으로 추세/구조를, 1시간봉으로 타이밍을 판정하고 0~100 점수로 순위를 매긴다.

판정에 쓰는 것
--------------
  · 4H 추세 정렬   : 종가 > EMA200, EMA20 > EMA50 > EMA200, EMA50 기울기
  · 4H 모멘텀      : RSI(14) 52~70 구간(과열 전), 1H RSI 타이밍
  · 거래량 확장    : 최근 3봉 거래량 / 직전 20봉 평균
  · 구조           : 직전 20봉 고점 돌파 여부·근접도
  · 진입 품질      : EMA20 대비 ATR 이격도(추격 금지)
  · 펀딩비         : 롱 쏠림(과열) 감점
  · 리스크         : ATR 기반 손절/목표가(2.0R / 3.2R) 자동 산출

산출물
------
  · 콘솔 순위표
  · CSV  (bybit_alt_long_scan_YYYYMMDD_HHMM.csv)
  · HTML 대시보드 (--html, 단일 파일, 데이터 내장)

사용법
------
  python3 bybit_alt_long_scanner.py                        # Bybit 자동
  python3 bybit_alt_long_scanner.py --exchange bybit --top 250
  python3 bybit_alt_long_scanner.py --exchange okx         # OKX로 대체 스캔
  python3 bybit_alt_long_scanner.py --min-turnover 20 --min-score 65
  # Bybit API가 지역 차단된 네트워크에서는 프록시 접두어로 우회 가능:
  BYBIT_PROXY="https://api.allorigins.win/raw?url=" python3 bybit_alt_long_scanner.py

주의: 본 스크립트는 정보 제공용이며 투자 조언이 아니다.
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
except ImportError:  # pragma: no cover
    print("requests 가 필요합니다:  pip install requests", file=sys.stderr)
    raise

KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (compatible; AltLongScanner/1.0)"}
_tl = threading.local()

# 토큰화 주식(xStocks 등)·ETF 심볼 — '알트코인' 스캔에서 기본 제외 (--include-equities 로 포함)
EQUITY_TICKERS = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "MSTR", "COIN",
    "HOOD", "CRCL", "SPY", "QQQ", "TQQQ", "SQQQ", "SOXL", "SOXS", "AMD", "NFLX",
    "PLTR", "BRK.B", "JPM", "V", "MA", "DIS", "INTC", "MU", "ORCL", "CRM", "UBER",
    "ABNB", "SBUX", "NKE", "BA", "SKHYNIX", "SKHY", "SAMSUNG", "HYNIX", "AVGO", "LLY", "UNH", "XOM",
}
INCLUDE_EQUITIES = False

# --- edge 필터(백테스트에서 플러스 기대값을 낸 조합) ---
EDGE = {"min_vol_ratio": 0.0, "min_atr_pct": 0.0, "exclude_setup": set()}


def edge_reject(x: dict) -> str | None:
    e = EDGE
    if e["min_vol_ratio"] and (x.get("vol_ratio") or 0) < e["min_vol_ratio"]:
        return f"거래량 {e['min_vol_ratio']:.1f}배 미달"
    if e["min_atr_pct"] and (x.get("atr_pct") or 0) < e["min_atr_pct"]:
        return f"ATR {e['min_atr_pct']:.1f}% 미달"
    if x.get("setup") in e["exclude_setup"]:
        return f"셋업 제외({x['setup']})"
    return None


def edge_rule_text() -> str:
    e = EDGE
    bits = []
    if e["min_vol_ratio"]:
        bits.append(f"거래량 ≥ {e['min_vol_ratio']:.1f}배")
    if e["min_atr_pct"]:
        bits.append(f"ATR ≥ {e['min_atr_pct']:.1f}%")
    if e["exclude_setup"]:
        bits.append("셋업 제외 " + "/".join(sorted(e["exclude_setup"])))
    return " · ".join(bits) if bits else "없음(기본 모드)"


def base_of(symbol: str) -> str:
    """'BCH-USDT-SWAP' / 'BCHUSDT' / 'BCHUSDC' → 'BCH'"""
    s = symbol.upper()
    for suf in ("-USDT-SWAP", "-USDC-SWAP", "-USDT", "-USDC", "USDT", "USDC", "PERP"):
        if s.endswith(suf):
            s = s[: -len(suf)]
            break
    return s.strip("-")


def is_equity(symbol: str) -> bool:
    return base_of(symbol) in EQUITY_TICKERS


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _sess() -> "requests.Session":
    s = getattr(_tl, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(UA)
        _tl.s = s
    return s


def http_json(url: str, params: dict | None = None, tries: int = 3, timeout: int = 25,
              proxy_prefix: str | None = None) -> dict:
    last = "unknown"
    for i in range(tries):
        try:
            target = url
            q = None
            if proxy_prefix:
                target = proxy_prefix + requests.utils.quote(url, safe="")
            else:
                q = params
            r = _sess().get(target, params=q, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code} {r.text[:140]}"
            if r.status_code in (403, 418, 429, 451):
                time.sleep(1.0 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(last)


# --------------------------------------------------------------------------- #
# 지표 (순수 파이썬 — 의존성 최소화)
# --------------------------------------------------------------------------- #
def ema_series(vals: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(vals)
    if len(vals) < n:
        return out
    k = 2.0 / (n + 1)
    e = sum(vals[:n]) / n
    out[n - 1] = e
    for i in range(n, len(vals)):
        e = vals[i] * k + e * (1 - k)
        out[i] = e
    return out


def rsi_series(vals: list[float], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(vals)
    if len(vals) < n + 1:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = vals[i] - vals[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / n, losses / n
    out[n] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(n + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def atr_series(highs: list[float], lows: list[float], closes: list[float],
               n: int = 14) -> list[float | None]:
    m = len(closes)
    tr: list[float] = [0.0] * m
    for i in range(m):
        if i == 0:
            tr[i] = highs[i] - lows[i]
        else:
            pc = closes[i - 1]
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - pc), abs(lows[i] - pc))
    out: list[float | None] = [None] * m
    if m < n:
        return out
    a = sum(tr[:n]) / n
    out[n - 1] = a
    for i in range(n, m):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def last(seq: list[float | None], back: int = 0) -> float | None:
    idx = len(seq) - 1 - back
    if idx < 0:
        return None
    return seq[idx]


# --------------------------------------------------------------------------- #
# 거래소 어댑터
# --------------------------------------------------------------------------- #
TF_BYBIT = {"15m": "15", "1h": "60", "4h": "240", "1d": "D"}
TF_OKX = {"15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}


class Exchange:
    """공통 인터페이스: universe() / candles() / funding()"""

    name = ""
    label = ""
    fee_hint = ""

    def universe(self) -> list[dict]:
        raise NotImplementedError

    def candles(self, symbol: str, tf: str) -> list[list[float]]:
        raise NotImplementedError

    def funding(self, symbols: list[str]) -> dict[str, float]:
        return {}


class Bybit(Exchange):
    name = "bybit"
    label = "Bybit USDT 무기한"
    BASE = "https://api.bybit.com"

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy or os.environ.get("BYBIT_PROXY") or None

    def universe(self) -> list[dict]:
        j = http_json(self.BASE + "/v5/market/tickers", {"category": "linear"},
                      proxy_prefix=self.proxy)
        rows: list[dict] = []
        for t in j.get("result", {}).get("list", []):
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            if is_equity(sym) and not INCLUDE_EQUITIES:
                continue
            def f(k):
                try:
                    return float(t.get(k) or 0.0)
                except (TypeError, ValueError):
                    return 0.0
            turn = f("turnover24h")
            if turn <= 0:
                continue
            rows.append({
                "symbol": sym,
                "last": f("lastPrice"),
                "chg24": f("price24hPcnt") * 100.0,
                "turnover": turn,
                "funding": f("fundingRate") * 100.0,   # % per 8h
                "oi_value": f("openInterestValue"),
            })
        return rows

    def candles(self, symbol: str, tf: str) -> list[list[float]]:
        j = http_json(self.BASE + "/v5/market/kline",
                      {"category": "linear", "symbol": symbol,
                       "interval": TF_BYBIT[tf], "limit": 1000},
                      proxy_prefix=self.proxy)
        raw = j.get("result", {}).get("list", [])
        raw = list(reversed(raw))  # 최신 → 과거 로 정렬되어 옴
        out = []
        for r in raw:
            try:
                out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
            except (TypeError, ValueError):
                continue
        return out


class OKX(Exchange):
    name = "okx"
    label = "OKX USDT 무기한"
    BASE = "https://www.okx.com"

    def universe(self) -> list[dict]:
        inst = http_json(self.BASE + "/api/v5/public/instruments", {"instType": "SWAP"})
        meta = {}
        for d in inst.get("data", []):
            if d.get("settleCcy") == "USDT" and d.get("state") == "live":
                try:
                    meta[d["instId"]] = float(d.get("ctVal") or 0.0)
                except (TypeError, ValueError):
                    continue
        tk = http_json(self.BASE + "/api/v5/market/tickers", {"instType": "SWAP"})
        rows: list[dict] = []
        for t in tk.get("data", []):
            sym = t.get("instId", "")
            if sym not in meta:
                continue
            if is_equity(sym) and not INCLUDE_EQUITIES:
                continue
            try:
                px = float(t.get("last") or 0)
                vol = float(t.get("vol24h") or 0)
                o24 = float(t.get("open24h") or 0)
            except (TypeError, ValueError):
                continue
            turn = vol * meta[sym] * px  # 계약수 × 계약승수 × 가격 ≈ USD 회전대금
            if turn <= 0 or px <= 0:
                continue
            rows.append({
                "symbol": sym,
                "last": px,
                "chg24": (px / o24 - 1.0) * 100.0 if o24 else 0.0,
                "turnover": turn,
                "funding": None,
                "oi_value": None,
            })
        return rows

    def candles(self, symbol: str, tf: str) -> list[list[float]]:
        j = http_json(self.BASE + "/api/v5/market/candles",
                      {"instId": symbol, "bar": TF_OKX[tf], "limit": 300})
        raw = sorted(j.get("data", []), key=lambda r: int(r[0]))
        out = []
        for r in raw:
            try:
                out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])])
            except (TypeError, ValueError):
                continue
        return out

    def funding(self, symbols: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}

        def one(sym):
            try:
                j = http_json(self.BASE + "/api/v5/public/funding-rate", {"instId": sym}, tries=2)
                d = (j.get("data") or [{}])[0]
                return sym, float(d.get("fundingRate") or 0.0) * 100.0
            except Exception:  # noqa: BLE001
                return sym, None

        with ThreadPoolExecutor(max_workers=6) as ex:
            for sym, v in ex.map(one, symbols):
                if v is not None:
                    out[sym] = v
        return out


def build_exchange(name: str) -> Exchange:
    if name == "okx":
        return OKX()
    if name == "bybit":
        return Bybit()
    # auto: Bybit 먼저 시도, 지역 차단/실패 시 OKX로 자동 전환
    try:
        ex = Bybit()
        ex.universe()
        return ex
    except Exception as e:  # noqa: BLE001
        print(f"  · Bybit 접속 실패({type(e).__name__}) → OKX로 자동 전환", file=sys.stderr)
        return OKX()


# --------------------------------------------------------------------------- #
# 스코어링
# --------------------------------------------------------------------------- #
def analyze(row: dict, c4: list[list[float]], c1: list[list[float]]) -> dict | None:
    """4H·1H 캔들 → 롱 후보 점수/레벨/근거."""
    if len(c4) < 210 or len(c1) < 60:
        return None

    ts4 = [r[0] for r in c4]
    o4 = [r[1] for r in c4]
    h4 = [r[2] for r in c4]
    l4 = [r[3] for r in c4]
    cl4 = [r[4] for r in c4]
    v4 = [r[5] for r in c4]

    cl1 = [r[4] for r in c1]
    lo1 = [r[3] for r in c1]
    v1 = [r[5] for r in c1]

    close = cl4[-1]
    if close <= 0:
        return None

    e20_4 = last(ema_series(cl4, 20))
    e50_4 = last(ema_series(cl4, 50))
    e200_4 = last(ema_series(cl4, 200))
    rsi4 = last(rsi_series(cl4, 14))
    atr4 = last(atr_series(h4, l4, cl4, 14))
    if None in (e20_4, e50_4, e200_4, rsi4, atr4) or atr4 <= 0:
        return None

    e20_4_prev = last(ema_series(cl4, 20), 5)
    e50_ser = ema_series(cl4, 50)
    e50_slope = None
    if last(e50_ser, 10):
        e50_slope = (e50_4 / last(e50_ser, 10) - 1.0) * 100.0

    rsi1 = last(rsi_series(cl1, 14))
    e20_1 = last(ema_series(cl1, 20))
    e9_1 = last(ema_series(cl1, 9))
    e21_1 = last(ema_series(cl1, 21))

    # 거래량 확장(1H): 최근 3봉 평균 vs 직전 20봉 평균
    vol_ratio = None
    if len(v1) >= 23:
        base = sum(v1[-23:-3]) / 20.0
        if base > 0:
            vol_ratio = (sum(v1[-3:]) / 3.0) / base

    # 구조: 직전 20봉 고점
    high20 = max(h4[-21:-1])
    dist_high = (high20 - close) / close * 100.0
    broke = close > high20
    swing_low = min(l4[-10:])

    atr_pct = atr4 / close * 100.0
    ext = (close - e20_4) / atr4  # ATR 이격도

    # 눌림목: 최근 6봉 내 1H EMA20 터치 후 종가 회복
    pullback = False
    if e20_1 and len(lo1) >= 6:
        touched = min(lo1[-6:]) <= e20_1 * 1.006
        pullback = bool(touched and close > e20_1 and e9_1 and e21_1 and e9_1 > e21_1)

    # ---- 점수 (기본 90 + 펀딩 10) ----
    sc = 0.0
    tags: list[str] = []

    if close > e200_4:
        sc += 8
        tags.append("4H 장기추세 상단")
    if e20_4 > e50_4:
        sc += 4
    if e50_4 > e200_4:
        sc += 4
        tags.append("EMA 정배열")

    if e50_slope is not None:
        if e50_slope > 2:
            sc += 8
            tags.append("EMA50 가파른 상승")
        elif e50_slope > 0:
            sc += 5

    if 52 <= rsi4 <= 70:
        sc += 14
        tags.append(f"4H RSI {rsi4:.0f} 건전")
    elif 45 <= rsi4 < 52 or 70 < rsi4 <= 76:
        sc += 8

    if vol_ratio is not None:
        if vol_ratio >= 2.0:
            sc += 14
            tags.append(f"거래량 {vol_ratio:.1f}배")
        elif vol_ratio >= 1.5:
            sc += 11
            tags.append(f"거래량 {vol_ratio:.1f}배")
        elif vol_ratio >= 1.2:
            sc += 7
        elif vol_ratio >= 1.0:
            sc += 3

    if broke:
        sc += 16
        tags.append("20봉 고점 돌파")
    elif dist_high <= 1.0:
        sc += 12
        tags.append("고점 1% 이내")
    elif dist_high <= 3.0:
        sc += 8
    elif dist_high <= 6.0:
        sc += 4

    if ext <= 1.0:
        sc += 14
        tags.append("EMA20 근접(추격 아님)")
    elif ext <= 1.8:
        sc += 10
    elif ext <= 2.6:
        sc += 5

    if rsi1 is not None:
        if 50 <= rsi1 <= 68:
            sc += 8
        elif 40 <= rsi1 < 50:
            sc += 5
        elif 68 < rsi1 <= 75:
            sc += 3

    flags: list[str] = []
    if rsi1 is not None and rsi1 > 78:
        flags.append("1H 과열")
    if rsi4 > 80:
        flags.append("4H 과열")
    if ext > 3.0:
        flags.append("EMA 이격 과다")
    if row["chg24"] > 25:
        flags.append("24h 급등")
        sc -= 6
    if atr_pct > 12:
        flags.append("변동성 과다")
        sc -= 4
    if row["turnover"] < 10_000_000:
        flags.append("유동성 낮음")

    setup = "관찰"
    if broke and (vol_ratio or 0) >= 1.2:
        setup = "돌파"
    elif pullback and ext <= 1.6:
        setup = "눌림목"
    elif close > e20_4 > e50_4 and (ext <= 2.0):
        setup = "추세지속"

    # ---- 레벨 ----
    atr_stop = close - 1.5 * atr4
    struct_stop = swing_low - 0.25 * atr4
    stop = max(atr_stop, struct_stop) if struct_stop < close else atr_stop
    if stop >= close:
        stop = close - 1.5 * atr4
    risk = close - stop
    if risk <= 0:
        return None
    tp1 = close + 2.0 * risk
    tp2 = close + 3.2 * risk

    return {
        "symbol": row["symbol"],
        "base": base_of(row["symbol"]),
        "last": close,
        "chg24": row["chg24"],
        "turnover": row["turnover"],
        "funding": row["funding"],
        "oi_value": row.get("oi_value"),
        "score_base": round(sc, 1),
        "score": round(sc, 1),
        "setup": setup,
        "ema20_4h": e20_4,
        "ema50_4h": e50_4,
        "ema200_4h": e200_4,
        "ema50_slope": round(e50_slope, 2) if e50_slope is not None else None,
        "rsi_4h": round(rsi4, 1),
        "rsi_1h": round(rsi1, 1) if rsi1 is not None else None,
        "vol_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
        "atr_4h": atr4,
        "atr_pct": round(atr_pct, 2),
        "ext_atr": round(ext, 2),
        "dist_high20": round(dist_high, 2),
        "high20": high20,
        "broke": broke,
        "pullback": pullback,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2,
        "risk_pct": round(risk / close * 100.0, 2),
        "rr1": 2.0,
        "tags": tags,
        "flags": flags,
        "ts4": ts4[-1],
    }


def apply_funding(res: dict, rate: float | None) -> None:
    """펀딩비(8h, %) 가점/감점."""
    if rate is None:
        return
    res["funding"] = rate
    if rate < 0:
        add, note = 10, "펀딩 마이너스(숏 쏠림)"
    elif rate < 0.01:
        add, note = 8, None
    elif rate < 0.03:
        add, note = 6, None
    elif rate < 0.05:
        add, note = 4, None
    elif rate <= 0.08:
        add, note = 1, None
    else:
        add, note = 0, "펀딩 과열(롱 쏠림)"
    res["score"] = round(res["score_base"] + add, 1)
    if note:
        if add > 0:
            res["tags"].append(note)
        else:
            res["flags"].append(note)


# --------------------------------------------------------------------------- #
# 스캔
# --------------------------------------------------------------------------- #
def scan(ex: Exchange, top: int, min_turnover: float, workers: int, quiet: bool) -> tuple[list[dict], dict]:
    t0 = time.time()
    uni = [r for r in ex.universe() if r["turnover"] >= min_turnover and r["last"] > 0]
    uni.sort(key=lambda r: -r["turnover"])
    uni = uni[:top]
    stats = {"universe_all": len(uni), "exchange": ex.label, "min_turnover": min_turnover}

    results: list[dict] = []
    errors = 0
    done = 0

    def work(r):
        c4 = ex.candles(r["symbol"], "4h")
        time.sleep(0.05)
        c1 = ex.candles(r["symbol"], "1h")
        return r, c4, c1

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(work, r): r for r in uni}
        for fu in as_completed(futs):
            done += 1
            if not quiet and done % 25 == 0:
                print(f"  · {done}/{len(uni)} 종목 분석 중…", file=sys.stderr)
            try:
                r, c4, c1 = fu.result()
            except Exception:  # noqa: BLE001
                errors += 1
                continue
            try:
                a = analyze(r, c4, c1)
            except Exception:  # noqa: BLE001
                errors += 1
                continue
            if a:
                results.append(a)

    # 후보 상위 60개에 한해 펀딩비 보정
    results.sort(key=lambda x: -x["score_base"])
    head = results[:60]
    need = [x["symbol"] for x in head if x.get("funding") is None]
    if need:
        fmap = ex.funding(need)
        for x in head:
            if x["symbol"] in fmap:
                apply_funding(x, fmap[x["symbol"]])
    for x in head:
        if x.get("funding") is not None and "score" not in x:
            apply_funding(x, x["funding"])

    results.sort(key=lambda x: -x["score"])
    stats.update({
        "scanned": len(results),
        "errors": errors,
        "seconds": round(time.time() - t0, 1),
        "scanned_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
    })
    return results, stats


def passes(x: dict, min_score: float) -> bool:
    hard_flags = {"1H 과열", "4H 과열", "EMA 이격 과다"}
    if x["score"] < min_score:
        return False
    if hard_flags & set(x["flags"]):
        return False
    if edge_reject(x):
        return False
    return True


# --------------------------------------------------------------------------- #
# 출력
# --------------------------------------------------------------------------- #
def fmt_usd(v: float | None) -> str:
    if not v:
        return "-"
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def num(v: float | None) -> str:
    """가격 표시: 8.478e+04 같은 지수 표기를 쓰지 않는다."""
    if v is None:
        return "-"
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}"


def print_table(rows: list[dict], limit: int) -> None:
    w = f"{'#':>3} {'심볼':<12} {'점수':>5} {'셋업':<9} {'가격':>12} {'24h%':>7} {'RSI4h':>6} {'RSI1h':>6} {'거래량':>6} {'펀딩%':>7} {'손절':>10} {'TP1':>10} {'손절폭':>6}"
    print("\n" + w)
    print("-" * len(w))
    for i, x in enumerate(rows[:limit], 1):
        px = x["last"]
        pxs, st, tp = num(px), num(x['stop']), num(x['tp1'])
        fr = f"{x['funding']:.4f}" if x.get("funding") is not None else "  -  "
        vr = f"{x['vol_ratio']:.2f}" if x.get("vol_ratio") is not None else "  - "
        r1 = f"{x['rsi_1h']:.0f}" if x.get("rsi_1h") is not None else " -"
        print(f"{i:>3} {x['base'][:12]:<12} {x['score']:>5.1f} {x['setup']:<9} {pxs:>12} "
              f"{x['chg24']:>7.2f} {x['rsi_4h']:>6.0f} {r1:>6} {vr:>6} {fr:>7} {st:>10} {tp:>10} {x['risk_pct']:>6.2f}")


def write_csv(path: str, rows: list[dict]) -> None:
    cols = ["symbol", "base", "score", "setup", "last", "chg24", "turnover", "funding",
            "rsi_4h", "rsi_1h", "vol_ratio", "atr_pct", "ext_atr", "dist_high20", "broke",
            "ema20_4h", "ema50_4h", "ema200_4h", "ema50_slope", "stop", "tp1", "tp2",
            "risk_pct", "tags", "flags"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for x in rows:
            wr.writerow([
                x.get(c) if c not in ("tags", "flags") else " | ".join(x.get(c) or [])
                for c in cols
            ])


# --------------------------------------------------------------------------- #
# HTML 대시보드 (단일 파일, 데이터 내장)
# --------------------------------------------------------------------------- #
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALT LONG RADAR — __STAMP__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --ink:#0b1220; --ink2:#0f1929; --panel:#121e30; --panel2:#16243a;
  --line:#20304a; --line2:#2a3d5c;
  --txt:#e6edf7; --dim:#8ea3bf; --dim2:#63799a;
  --amber:#e8b45c; --azure:#5fa8f5; --teal:#3fc7a4; --rose:#e0655f; --violet:#9d8bf0;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:
    radial-gradient(1100px 620px at 12% -12%, #16263f 0%, transparent 60%),
    radial-gradient(900px 520px at 96% 4%, #1a2033 0%, transparent 55%),
    var(--ink);
  color:var(--txt);
  font-family:"IBM Plex Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
  font-size:15px; line-height:1.55; letter-spacing:-0.005em;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1400px;margin:0 auto;padding:34px 22px 80px}
a{color:var(--azure)}

/* ---------- header ---------- */
.top{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-end;justify-content:space-between;
     border-bottom:1px solid var(--line);padding-bottom:20px}
.brand{display:flex;align-items:center;gap:14px}
.sweep{width:44px;height:44px;border-radius:50%;border:1px solid var(--line2);position:relative;flex:0 0 auto;
  background:radial-gradient(circle at 50% 50%, rgba(63,199,164,.16), transparent 68%)}
.sweep::before{content:"";position:absolute;inset:0;border-radius:50%;
  background:conic-gradient(from 0deg, rgba(232,180,92,.55), transparent 42%);
  animation:spin 6.5s linear infinite}
.sweep::after{content:"";position:absolute;inset:12px;border-radius:50%;background:var(--ink);border:1px solid var(--line)}
@keyframes spin{to{transform:rotate(360deg)}}
h1{margin:0;font-size:26px;font-weight:700;letter-spacing:.14em}
h1 small{display:block;font-size:11px;font-weight:500;letter-spacing:.34em;color:var(--dim2);margin-top:3px}
.meta{font-family:var(--mono);font-size:12px;color:var(--dim);text-align:right;line-height:1.85}
.meta b{color:var(--txt);font-weight:500}
.pill{display:inline-block;padding:2px 9px;border:1px solid var(--line2);border-radius:999px;
      font-size:11px;letter-spacing:.04em;color:var(--dim)}

/* ---------- stat strip ---------- */
.strip{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0 8px}
.stat{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
      border-radius:12px;padding:16px 18px}
.stat .k{font-size:11px;letter-spacing:.18em;color:var(--dim2);text-transform:uppercase}
.stat .v{font-family:var(--mono);font-size:30px;font-weight:600;margin-top:6px;letter-spacing:-.02em}
.stat .s{font-size:12px;color:var(--dim);margin-top:2px}

/* ---------- radar heat grid ---------- */
.sec{margin-top:38px}
.sech{display:flex;align-items:baseline;gap:12px;border-bottom:1px solid var(--line);padding-bottom:9px;margin-bottom:16px}
.sech h2{margin:0;font-size:13px;letter-spacing:.22em;font-weight:600}
.sech span{font-size:12px;color:var(--dim2)}
.radar{display:flex;flex-wrap:wrap;gap:4px}
.cell{width:26px;height:26px;border-radius:5px;border:1px solid rgba(255,255,255,.06);
      cursor:default;position:relative;transition:transform .12s ease}
.cell:hover{transform:translateY(-3px) scale(1.12);z-index:3;box-shadow:0 6px 18px rgba(0,0,0,.5)}
.cell.hot{animation:pulse 2.6s ease-in-out infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(232,180,92,.5)}50%{box-shadow:0 0 0 5px rgba(232,180,92,0)}}

/* ---------- controls ---------- */
.ctl{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:4px 0 14px}
.ctl input[type=search]{background:var(--ink2);border:1px solid var(--line2);border-radius:9px;
  padding:9px 13px;color:var(--txt);font-family:var(--mono);font-size:13px;min-width:210px}
.ctl input:focus,.chip:focus-visible{outline:2px solid var(--azure);outline-offset:2px}
.chip{background:var(--ink2);border:1px solid var(--line2);color:var(--dim);border-radius:9px;
  padding:8px 13px;font-size:12.5px;cursor:pointer;font-family:inherit;letter-spacing:.02em}
.chip[aria-pressed=true]{background:rgba(232,180,92,.14);border-color:var(--amber);color:var(--amber)}
.cnt{font-family:var(--mono);font-size:12px;color:var(--dim2);margin-left:auto}

/* ---------- table ---------- */
.tblwrap{border:1px solid var(--line);border-radius:13px;overflow:auto;background:var(--panel)}
table{width:100%;border-collapse:collapse;min-width:1080px}
thead th{position:sticky;top:0;background:var(--panel2);z-index:2;text-align:right;
  font-size:11px;letter-spacing:.1em;color:var(--dim2);font-weight:600;padding:11px 12px;
  border-bottom:1px solid var(--line2);white-space:nowrap}
thead th.l{text-align:left}
tbody td{padding:11px 12px;border-bottom:1px solid rgba(32,48,74,.6);text-align:right;
  font-family:var(--mono);font-size:13px;white-space:nowrap}
tbody td.l{text-align:left;font-family:inherit}
tbody tr:hover{background:rgba(95,168,245,.055)}
tbody tr:last-child td{border-bottom:none}
.rk{color:var(--dim2);font-size:12px}
.sym{font-weight:600;letter-spacing:-.01em;font-size:14px}
.pos{color:var(--teal)} .neg{color:var(--rose)} .mut{color:var(--dim2)}
.meter{display:inline-flex;gap:2px;vertical-align:middle;margin-right:8px}
.meter i{width:3px;height:13px;border-radius:1px;background:var(--line2);display:block}
.meter i.on{background:var(--amber)}
.meter i.on.hi{background:var(--teal)}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11.5px;
  font-family:"IBM Plex Sans KR",sans-serif;border:1px solid transparent}
.b-돌파{background:rgba(232,180,92,.14);color:var(--amber);border-color:rgba(232,180,92,.35)}
.b-눌림목{background:rgba(95,168,245,.14);color:var(--azure);border-color:rgba(95,168,245,.35)}
.b-추세지속{background:rgba(63,199,164,.13);color:var(--teal);border-color:rgba(63,199,164,.32)}
.b-관찰{background:rgba(142,163,191,.1);color:var(--dim);border-color:var(--line2)}
.f{display:inline-block;margin-left:5px;font-size:11px;color:var(--rose);border:1px solid rgba(224,101,95,.4);
   border-radius:5px;padding:0 5px;font-family:"IBM Plex Sans KR",sans-serif}

/* ---------- detail cards ---------- */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px}
.card{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
      border-radius:14px;padding:20px;position:relative;overflow:hidden}
.card::before{content:"";position:absolute;left:0;top:0;height:100%;width:3px;background:var(--amber)}
.card.c2::before{background:var(--azure)} .card.c3::before{background:var(--teal)}
.card .hd{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.card .nm{font-size:20px;font-weight:700;letter-spacing:-.01em}
.card .sc{font-family:var(--mono);font-size:25px;font-weight:600;color:var(--amber)}
.card.c2 .sc{color:var(--azure)} .card.c3 .sc{color:var(--teal)}
.lv{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:15px 0 13px}
.lv div{background:rgba(11,18,32,.6);border:1px solid var(--line);border-radius:9px;padding:9px 11px}
.lv .k{font-size:10.5px;letter-spacing:.12em;color:var(--dim2)}
.lv .v{font-family:var(--mono);font-size:14.5px;margin-top:3px}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tag{font-size:11.5px;color:var(--dim);background:rgba(11,18,32,.55);border:1px solid var(--line);
     border-radius:999px;padding:2px 10px}
.tag.r{color:var(--rose);border-color:rgba(224,101,95,.35)}

/* ---------- footer ---------- */
.note{margin-top:40px;border-top:1px solid var(--line);padding-top:20px;display:grid;
      grid-template-columns:1.4fr 1fr;gap:26px;font-size:13px;color:var(--dim)}
.note h3{font-size:11.5px;letter-spacing:.2em;color:var(--dim2);margin:0 0 9px}
.note ul{margin:0;padding-left:17px} .note li{margin-bottom:5px}
.note code{font-family:var(--mono);font-size:12px;background:var(--ink2);border:1px solid var(--line);
  border-radius:5px;padding:1px 6px;color:var(--txt)}
.warn{color:var(--rose);font-size:12.5px}
@media (max-width:860px){
  .strip{grid-template-columns:repeat(2,1fr)} .note{grid-template-columns:1fr}
  .meta{text-align:left} h1{font-size:21px}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
</head>
<body>
<div class="wrap">

  <header class="top">
    <div class="brand">
      <div class="sweep" aria-hidden="true"></div>
      <div>
        <h1>ALT LONG RADAR<small>USDT PERPETUAL · LONG-ONLY SCANNER</small></h1>
      </div>
    </div>
    <div class="meta">
      스캔 시각 <b>__STAMP__</b><br>
      거래소 <b>__EXCHANGE__</b> · 최소 24h 거래대금 <b>__MINTURN__</b><br>
      표본 <b>__SCANNED__</b>종목 / 오류 <b>__ERRORS__</b> · 소요 <b>__SECS__</b>s
    </div>
  </header>

  <section class="strip">
    <div class="stat"><div class="k">Scanned</div><div class="v">__SCANNED__</div>
      <div class="s">분석 완료 종목</div></div>
    <div class="stat"><div class="k">Candidates</div><div class="v" style="color:var(--teal)">__NCAND__</div>
      <div class="s">__MINSCORE__점 이상 · 과열 제외</div></div>
    <div class="stat"><div class="k">Top score</div><div class="v" style="color:var(--amber)">__TOPS__</div>
      <div class="s">__TOPSYM__</div></div>
    <div class="stat"><div class="k">Avg RSI 4H</div><div class="v">__AVGRSI__</div>
      <div class="s">후보군 평균 모멘텀</div></div>
  </section>

  <section class="sec">
    <div class="sech"><h2>UNIVERSE RADAR</h2>
      <span>거래대금 상위 __SCANNED__종목 · 색이 밝을수록 롱 점수 높음 · 커서를 올려 심볼 확인</span></div>
    <div class="radar" id="radar">__RADARCELLS__</div>
  </section>

  <section class="sec">
    <div class="sech"><h2>SIGNAL BOARD</h2><span>점수 = 추세16 · 기울기8 · 모멘텀14 · 거래량14 · 구조16 · 진입14 · 타이밍8 + 펀딩10 · edge 필터 __EDGERULE__</span></div>
    <div class="ctl">
      <input id="q" type="search" placeholder="심볼 검색 (예: SOL)" autocomplete="off">
      <button class="chip" data-setup="전체" aria-pressed="true">전체</button>
      <button class="chip" data-setup="돌파" aria-pressed="false">돌파</button>
      <button class="chip" data-setup="눌림목" aria-pressed="false">눌림목</button>
      <button class="chip" data-setup="추세지속" aria-pressed="false">추세지속</button>
      <span class="cnt" id="cnt">__CNT__ / __DATALEN__ 종목</span>
    </div>
    <div class="tblwrap">
      <table>
        <thead><tr>
          <th class="l">#</th><th class="l">심볼</th><th class="l">점수</th><th class="l">셋업</th>
          <th>가격</th><th>24h %</th><th>RSI 4H</th><th>RSI 1H</th><th>거래량배수</th>
          <th>펀딩 8h</th><th>ATR%</th><th>고점이격</th><th>손절</th><th>TP1</th><th>손절폭</th><th>거래대금</th>
        </tr></thead>
        <tbody id="tb">__TABLEROWS__</tbody>
      </table>
    </div>
  </section>

  <section class="sec">
    <div class="sech"><h2>TOP SETUPS</h2><span>상위 3개 후보의 근거·레벨</span></div>
    <div class="cards" id="cards">__CARDS__</div>
  </section>

  <footer class="note">
    <div>
      <h3>판정 규칙</h3>
      <ul>
        <li><b>돌파</b> — 4H 직전 20봉 고점을 종가로 넘기고 거래량 1.2배 이상</li>
        <li><b>눌림목</b> — 1H EMA20 터치 후 회복, 1H EMA9 &gt; EMA21, EMA20 이격 ≤ 1.6 ATR</li>
        <li><b>추세지속</b> — 종가 &gt; EMA20 &gt; EMA50, 이격 ≤ 2 ATR</li>
        <li>점수 100 = 추세16 + 기울기8 + 모멘텀14 + 거래량14 + 구조16 + 진입품질14 + 타이밍8 + 펀딩10</li>
        <li>손절 = max(진입 − 1.5×ATR, 최근 10봉 저점 − 0.25×ATR) / TP1 = 2.0R / TP2 = 3.2R</li>
      </ul>
    </div>
    <div>
      <h3>재현</h3>
      <ul>
        <li><code>python3 bybit_alt_long_scanner.py --top __TOP__</code></li>
        <li><code>--min-score 65</code> 로 기준 상향, <code>--html out.html</code> 로 이 리포트 재생성</li>
      </ul>
      <p class="warn">본 리포트는 공개 시세 데이터를 기계적으로 계산한 정보 제공용 자료이며 투자 자문이 아닙니다. 레버리지 상품은 원금 전액 손실이 가능합니다.</p>
    </div>
  </footer>
</div>

<script>
/* 데이터는 이미 HTML에 정적 삽입되어 있다 — 스크립트가 막힌 뷰어에서도 표가 보인다.
   이 스크립트는 검색/셋업 필터만 담당하는 점진적 향상(progressive enhancement)이다. */
(function(){
  var rows = Array.prototype.slice.call(document.querySelectorAll('#tb tr'));
  var cnt = document.getElementById('cnt');
  var q = document.getElementById('q');
  var mode = '전체';
  function apply(){
    var needle = (q && q.value || '').trim().toUpperCase();
    var shown = 0;
    rows.forEach(function(tr){
      var ok = (mode === '전체' || tr.getAttribute('data-setup') === mode) &&
               (!needle || (tr.getAttribute('data-sym') || '').indexOf(needle) >= 0);
      tr.style.display = ok ? '' : 'none';
      if (ok) { shown++; var rk = tr.querySelector('.rk'); if (rk) rk.textContent = shown; }
    });
    if (cnt) cnt.textContent = shown + ' / ' + rows.length + ' 종목';
  }
  document.querySelectorAll('.chip').forEach(function(b){
    b.addEventListener('click', function(){
      document.querySelectorAll('.chip').forEach(function(o){ o.setAttribute('aria-pressed','false'); });
      b.setAttribute('aria-pressed','true'); mode = b.getAttribute('data-setup'); apply();
    });
  });
  if (q) q.addEventListener('input', apply);
  apply();
})();
</script>
</body>
</html>
"""


def _num(v, nd: int = 4) -> str:
    if v is None:
        return "-"
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}"


def _usd(v) -> str:
    if not v:
        return "-"
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def _heat(score: float) -> tuple[str, str]:
    if score >= 80:
        return "#3fc7a4", "#04231c"
    if score >= 70:
        return "#e8b45c", "#2a1c00"
    if score >= 60:
        return "#c98b3f", "#21150a"
    if score >= 48:
        return "#5f7fa8", "#0b1220"
    if score >= 36:
        return "#2f4360", "#c6d5ea"
    return "#1b2a3a", "#6d82a0"


def _meter(score: float) -> str:
    n = int(round(score / 5.0))
    hib = " hi" if score >= 75 else ""
    bars = "".join(f'<i class="{"on" + hib if i < n else ""}"></i>' for i in range(20))
    return f'<span class="meter">{bars}</span>'


def _radar_cells(rows: list[dict]) -> str:
    out = []
    for x in rows:
        bg, _fg = _heat(x["score"])
        hot = " hot" if x["score"] >= 80 else ""
        tip = (f'{x["base"]}  {x["score"]:.0f}점  {x["setup"]}  '
               f'24h {x["chg24"]:+.1f}%')
        out.append(f'<div class="cell{hot}" style="background:{bg}" title="{tip}"></div>')
    return "".join(out)


def _table_rows(cand: list[dict]) -> str:
    out = []
    for i, x in enumerate(cand, 1):
        flags = "".join(f'<span class="f">{f}</span>' for f in (x.get("flags") or []))
        r1 = f'{x["rsi_1h"]:.0f}' if x.get("rsi_1h") is not None else "-"
        vr = f'{x["vol_ratio"]:.2f}×' if x.get("vol_ratio") is not None else "-"
        fr = (f'{x["funding"]:.4f}' if x.get("funding") is not None else "-")
        fcls = "neg" if (x.get("funding") or 0) > 0.05 else "mut"
        dh = f'{x["dist_high20"]:+.1f}%'
        chg = f'{x["chg24"]:+.2f}'
        out.append(
            f'<tr data-sym="{x["base"]}" data-setup="{x["setup"]}">'
            f'<td class="l rk">{i}</td>'
            f'<td class="l"><span class="sym">{x["base"]}</span>{flags}</td>'
            f'<td class="l">{_meter(x["score"])}<b style="color:var(--amber)">{x["score"]:.0f}</b></td>'
            f'<td class="l"><span class="badge b-{x["setup"]}">{x["setup"]}</span></td>'
            f'<td>{_num(x["last"])}</td>'
            f'<td class="{"pos" if x["chg24"] > 0 else "neg" if x["chg24"] < 0 else "mut"}">{chg}</td>'
            f'<td>{x["rsi_4h"]:.0f}</td>'
            f'<td>{r1}</td>'
            f'<td>{vr}</td>'
            f'<td class="{fcls}">{fr}</td>'
            f'<td>{x["atr_pct"]:.1f}</td>'
            f'<td class="mut">{dh}</td>'
            f'<td class="neg">{_num(x["stop"])}</td>'
            f'<td class="pos">{_num(x["tp1"])}</td>'
            f'<td class="mut">{x["risk_pct"]:.2f}%</td>'
            f'<td class="mut">{_usd(x["turnover"])}</td>'
            f'</tr>')
    return "".join(out)


def _cards(cand: list[dict]) -> str:
    out = []
    for i, x in enumerate(cand[:3]):
        tags = "".join(f'<span class="tag">{t}</span>' for t in (x.get("tags") or []))
        flags = "".join(f'<span class="tag r">{f}</span>' for f in (x.get("flags") or []))
        out.append(
            f'<div class="card c{i+1}">'
            f'<div class="hd"><div class="nm">{x["base"]} '
            f'<span class="badge b-{x["setup"]}">{x["setup"]}</span></div>'
            f'<div class="sc">{x["score"]:.0f}</div></div>'
            f'<div class="lv">'
            f'<div><div class="k">ENTRY</div><div class="v">{_num(x["last"])}</div></div>'
            f'<div><div class="k">STOP</div><div class="v" style="color:var(--rose)">{_num(x["stop"])}</div></div>'
            f'<div><div class="k">TP1 (2R)</div><div class="v" style="color:var(--teal)">{_num(x["tp1"])}</div></div>'
            f'<div><div class="k">TP2 (3.2R)</div><div class="v">{_num(x["tp2"])}</div></div>'
            f'<div><div class="k">RISK</div><div class="v">{x["risk_pct"]:.2f}%</div></div>'
            f'<div><div class="k">ATR 4H</div><div class="v">{x["atr_pct"]:.1f}%</div></div>'
            f'</div><div class="tags">{tags}{flags}</div></div>')
    return "".join(out)


def write_html(path: str, rows: list[dict], stats: dict, min_score: float, top: int,
               edge_rule: str = "없음(기본 모드)") -> None:
    """HTML 리포트 생성.

    표·레이더·카드는 **정적 마크업**으로 삽입한다 → JavaScript 가 차단된 뷰어에서도
    데이터가 보인다. 스크립트는 검색/필터만 담당한다.
    """
    cand = [x for x in rows if passes(x, min_score)]
    univ = [{"base": x["base"], "score": x["score"], "setup": x["setup"], "chg24": x["chg24"]}
            for x in rows]
    tops = cand[0]["score"] if cand else 0.0
    topsym = cand[0]["base"] if cand else "—"
    avg_rsi = (sum(x["rsi_4h"] for x in cand) / len(cand)) if cand else 0.0
    html = (HTML_TEMPLATE
            .replace("__STAMP__", stats["scanned_at"])
            .replace("__EXCHANGE__", stats["exchange"])
            .replace("__MINTURN__", _usd(stats["min_turnover"]))
            .replace("__SCANNED__", str(stats["scanned"]))
            .replace("__ERRORS__", str(stats["errors"]))
            .replace("__SECS__", str(stats["seconds"]))
            .replace("__NCAND__", str(len(cand)))
            .replace("__MINSCORE__", f"{min_score:.0f}")
            .replace("__TOPS__", f"{tops:.0f}")
            .replace("__TOPSYM__", topsym)
            .replace("__AVGRSI__", f"{avg_rsi:.0f}")
            .replace("__TOP__", str(top))
            .replace("__EDGERULE__", edge_rule)
            .replace("__CNT__", str(len(cand)))
            .replace("__DATALEN__", str(len(cand)))
            .replace("__RADARCELLS__", _radar_cells(rows))
            .replace("__TABLEROWS__", _table_rows(cand))
            .replace("__CARDS__", _cards(cand))
            .replace("__UNIV__", json.dumps(univ, ensure_ascii=False))
            .replace("__DATA__", json.dumps(cand, ensure_ascii=False)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Bybit 알트 롱 스캐너")
    ap.add_argument("--exchange", default="auto", choices=["auto", "bybit", "okx"])
    ap.add_argument("--top", type=int, default=200, help="거래대금 상위 N종목만 스캔 (기본 200)")
    ap.add_argument("--min-turnover", type=float, default=5_000_000,
                    help="24h 최소 거래대금(USD, 기본 5,000,000)")
    ap.add_argument("--min-score", type=float, default=60, help="후보 최소 점수 (기본 60)")
    ap.add_argument("--topn-print", type=int, default=25, help="콘솔에 출력할 행 수")
    ap.add_argument("--workers", type=int, default=8, help="동시 요청 수 (기본 8)")
    ap.add_argument("--csv", default=None, help="CSV 저장 경로")
    ap.add_argument("--html", default=None, help="HTML 리포트 저장 경로")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--include-equities", action="store_true",
                    help="토큰화 주식/ETF 심볼도 포함 (기본은 제외)")
    ap.add_argument("--min-vol-ratio", type=float, default=0.0,
                    help="1H 거래량 배수 하한 (예: 2.0)")
    ap.add_argument("--min-atr-pct", type=float, default=0.0,
                    help="4H ATR퍼센트 하한 (예: 4.0)")
    ap.add_argument("--exclude-setup", default="",
                    help="제외할 셋업 (쉼표 구분, 예: 추세지속)")
    ap.add_argument("--edge", action="store_true",
                    help="edge 프리셋: 거래량 2.0배 + ATR 4%% + '추세지속' 제외")
    args = ap.parse_args()

    global INCLUDE_EQUITIES
    INCLUDE_EQUITIES = args.include_equities
    if args.edge:
        EDGE["min_vol_ratio"] = 2.0
        EDGE["min_atr_pct"] = 4.0
        EDGE["exclude_setup"] = {"추세지속"}
    if args.min_vol_ratio:
        EDGE["min_vol_ratio"] = args.min_vol_ratio
    if args.min_atr_pct:
        EDGE["min_atr_pct"] = args.min_atr_pct
    if args.exclude_setup:
        EDGE["exclude_setup"] = {x.strip() for x in args.exclude_setup.split(",") if x.strip()}

    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M")
    csv_path = args.csv or f"bybit_alt_long_scan_{stamp}.csv"

    print("=" * 78)
    print("  ALT LONG RADAR — USDT 무기한 롱 후보 스캐너")
    print(f"  {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}")
    print("=" * 78)

    ex = build_exchange(args.exchange)
    print(f"  · 데이터 소스: {ex.label}")

    rows, stats = scan(ex, args.top, args.min_turnover, args.workers, args.quiet)
    if not rows:
        print("  결과 없음 — 네트워크 또는 필터 조건을 확인하세요.", file=sys.stderr)
        return 1

    cand = [x for x in rows if passes(x, args.min_score)]
    print(f"  · 분석 {stats['scanned']}종목 (오류 {stats['errors']}) · {stats['seconds']}s")
    print(f"  · 후보 {len(cand)}종목 (점수 ≥ {args.min_score:.0f}, 과열/이격 과다 제외)")
    print(f"  · edge 필터: {edge_rule_text()}")
    print_table(cand if cand else rows, args.topn_print)

    write_csv(csv_path, rows)
    print(f"\n  CSV  → {csv_path}")

    if args.html:
        write_html(args.html, rows, stats, args.min_score, args.top, edge_rule_text())
        print(f"  HTML → {args.html}")

    print("\n  ※ 정보 제공용. 투자 조언이 아니며 레버리지 상품은 원금 전액 손실이 가능합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
