#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
알트 롱 신호 백테스터 (Alt Long Signal Backtest)
================================================

`bybit_alt_long_scanner.py` 의 4H 코어 신호 로직을 과거 데이터에 그대로 재현해
승률 / 기대값(R) / 손익비 / MDD 를 검증한다.

검증 방법
---------
  · 유니버스: 거래대금 상위 N 종목의 USDT 무기한 (기본 OKX, Bybit 사용 가능)
  · 데이터  : 4H 봉 N개 (기본 4,400개 ≈ 2년)
  · 신호    : 스캐너와 동일한 4H 점수(추세16·기울기8·모멘텀14·거래량14·구조16·진입14)
              + 과열/이격/급등 하드 필터. 1H 타이밍(8점)·펀딩(10점)은 제외 → 만점 82
  · 진입    : 신호 봉 **다음 봉 시가** (룩어헤드 없음)
  · 손절/목표: 신호 봉 종가·ATR 기준 (스캐너와 동일 공식), TP1 = 2.0R / TP2 = 3.2R
  · 청산    : 봉 저가가 손절가 이탈 → 손절(-1R) / 봉 고가가 TP1 도달 → +2R
              같은 봉에서 둘 다 닿으면 **손절 우선**(보수적) / 최대 보유 N봉 초과 시 종가 청산
  · 비용    : 편도 수수료+슬리피지(bps) 를 R 로 환산해 차감
  · 중복    : 종목당 포지션 1개(보유 중 신규 신호 무시)
  · 기준선  : 같은 유니버스·같은 청산규칙의 **무작위 진입** 성과와 비교

사용법
------
  python3 alt_long_backtest.py                          # 기본 (OKX, 상위 60종목, 2년)
  python3 alt_long_backtest.py --exchange bybit         # Bybit API (차단 지역에서는 실패)
  python3 alt_long_backtest.py --top 80 --bars 6600     # 3년, 80종목
  python3 alt_long_backtest.py --min-score 70 --max-hold 30
  python3 alt_long_backtest.py --html backtest.html --csv trades.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
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
UA = {"User-Agent": "Mozilla/5.0 (compatible; AltLongBacktest/1.0)"}
_tl = threading.local()

EQUITY_TICKERS = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "MSTR", "COIN",
    "HOOD", "CRCL", "SPY", "QQQ", "TQQQ", "SQQQ", "SOXL", "SOXS", "AMD", "NFLX",
    "PLTR", "JPM", "V", "MA", "DIS", "INTC", "MU", "ORCL", "CRM", "UBER",
    "ABNB", "SBUX", "NKE", "BA", "SKHYNIX", "SKHY", "SAMSUNG", "HYNIX", "AVGO",
    "LLY", "UNH", "XOM",
}
INCLUDE_EQUITIES = False


def base_of(symbol: str) -> str:
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
def _sess():
    s = getattr(_tl, "s", None)
    if s is None:
        s = requests.Session()
        s.headers.update(UA)
        _tl.s = s
    return s


def http_json(url: str, params: dict | None = None, tries: int = 5, timeout: int = 25,
              proxy_prefix: str | None = None) -> dict:
    last = "unknown"
    for i in range(tries):
        try:
            if proxy_prefix:
                target = proxy_prefix + requests.utils.quote(url, safe="")
                r = _sess().get(target, timeout=timeout)
            else:
                r = _sess().get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code} {r.text[:120]}"
            time.sleep(0.6 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            time.sleep(0.6 * (i + 1))
    raise RuntimeError(last)


# --------------------------------------------------------------------------- #
# 지표
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


def atr_series(highs, lows, closes, n: int = 14) -> list[float | None]:
    m = len(closes)
    tr = [0.0] * m
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


# --------------------------------------------------------------------------- #
# 거래소
# --------------------------------------------------------------------------- #
class OKX:
    name = "okx"
    label = "OKX USDT 무기한"
    BASE = "https://www.okx.com"
    TF = {"4h": "4H", "1h": "1H"}

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
        rows = []
        for t in tk.get("data", []):
            sym = t.get("instId", "")
            if sym not in meta or (is_equity(sym) and not INCLUDE_EQUITIES):
                continue
            try:
                px = float(t.get("last") or 0)
                vol = float(t.get("vol24h") or 0)
            except (TypeError, ValueError):
                continue
            turn = vol * meta[sym] * px
            if turn <= 0 or px <= 0:
                continue
            rows.append({"symbol": sym, "turnover": turn})
        return rows

    def candles_all(self, symbol: str, tf: str, bars: int) -> list[list[float]]:
        """history-candles 페이지네이션으로 최대 bars 개 수집 (오래된 → 최신 정렬)."""
        got: list[list[float]] = []
        after = None
        while len(got) < bars:
            p = {"instId": symbol, "bar": self.TF[tf], "limit": 100}
            if after is not None:
                p["after"] = str(after)
            # OKX 는 레이트리밋을 HTTP 200 + code!=0 으로 돌려준다 → 코드 검사 + 재시도
            j, batch = {}, []
            for attempt in range(6):
                j = http_json(self.BASE + "/api/v5/market/history-candles", p, tries=3)
                if j.get("code") == "0" and j.get("data"):
                    batch = j["data"]
                    break
                time.sleep(0.7 * (attempt + 1))
            if not batch:
                break
            parsed = []
            for r in batch:
                try:
                    parsed.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                                   float(r[4]), float(r[5])])
                except (TypeError, ValueError):
                    continue
            if not parsed:
                break
            got.extend(parsed)
            after = min(x[0] for x in parsed)
            if len(batch) < 100:
                break
            time.sleep(0.06)
        got.sort(key=lambda x: x[0])
        return got[-bars:]


class Bybit:
    name = "bybit"
    label = "Bybit USDT 무기한"
    BASE = "https://api.bybit.com"
    TF = {"4h": "240", "1h": "60"}

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy or os.environ.get("BYBIT_PROXY") or None

    def universe(self) -> list[dict]:
        j = http_json(self.BASE + "/v5/market/tickers", {"category": "linear"},
                      proxy_prefix=self.proxy)
        rows = []
        for t in j.get("result", {}).get("list", []):
            sym = t.get("symbol", "")
            if not sym.endswith("USDT") or (is_equity(sym) and not INCLUDE_EQUITIES):
                continue
            try:
                turn = float(t.get("turnover24h") or 0)
                px = float(t.get("lastPrice") or 0)
            except (TypeError, ValueError):
                continue
            if turn <= 0 or px <= 0:
                continue
            rows.append({"symbol": sym, "turnover": turn})
        return rows

    def candles_all(self, symbol: str, tf: str, bars: int) -> list[list[float]]:
        """Bybit kline 은 end 커서로 과거를 페이지네이션."""
        got: list[list[float]] = []
        end = None
        while len(got) < bars:
            p = {"category": "linear", "symbol": symbol, "interval": self.TF[tf], "limit": 1000}
            if end is not None:
                p["end"] = end
            j = http_json(self.BASE + "/v5/market/kline", p, proxy_prefix=self.proxy)
            batch = j.get("result", {}).get("list", [])
            if not batch:
                break
            parsed = []
            for r in batch:
                try:
                    parsed.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                                   float(r[4]), float(r[5])])
                except (TypeError, ValueError):
                    continue
            if not parsed:
                break
            got.extend(parsed)
            end = min(x[0] for x in parsed) - 1
            if len(batch) < 1000:
                break
            time.sleep(0.06)
        got.sort(key=lambda x: x[0])
        # Bybit 은 ms, OKX 는 ms 아님 → 통일(초 단위)하지 않고 ms 유지하되 표시만 변환
        return got[-bars:]


def build_exchange(name: str):
    if name == "okx":
        return OKX()
    if name == "bybit":
        return Bybit()
    try:
        ex = Bybit()
        ex.universe()
        return ex
    except Exception as e:  # noqa: BLE001
        print(f"  · Bybit 접속 실패({type(e).__name__}) → OKX로 자동 전환", file=sys.stderr)
        return OKX()


# --------------------------------------------------------------------------- #
# 신호 (스캐너 4H 코어 로직 그대로 — 룩어헤드 없이 i 시점까지의 데이터만 사용)
# --------------------------------------------------------------------------- #
def signal_at(i, cl, hi, lo, vol, e20, e50, e200, e50p10, rsi, atr, mean_vol) -> dict | None:
    close = cl[i]
    a = atr[i]
    if close <= 0 or not a or a <= 0:
        return None
    if not e20[i] or not e50[i] or not e200[i] or rsi[i] is None:
        return None

    e20v, e50v, e200v = e20[i], e50[i], e200[i]
    rv = rsi[i]
    slope = None
    if e50p10[i]:
        slope = (e50v / e50p10[i] - 1.0) * 100.0
    vol_ratio = None
    if mean_vol[i] and mean_vol[i] > 0:
        vol_ratio = (sum(vol[i - 2: i + 1]) / 3.0) / mean_vol[i]

    high20 = max(hi[i - 20: i])
    dist_high = (high20 - close) / close * 100.0
    broke = close > high20
    ext = (close - e20v) / a
    atr_pct = a / close * 100.0
    chg24 = (close / cl[i - 6] - 1.0) * 100.0 if cl[i - 6] else 0.0

    sc = 0.0
    if close > e200v:
        sc += 8
    if e20v > e50v:
        sc += 4
    if e50v > e200v:
        sc += 4
    if slope is not None:
        if slope > 2:
            sc += 8
        elif slope > 0:
            sc += 5
    if 52 <= rv <= 70:
        sc += 14
    elif 45 <= rv < 52 or 70 < rv <= 76:
        sc += 8
    if vol_ratio is not None:
        if vol_ratio >= 2.0:
            sc += 14
        elif vol_ratio >= 1.5:
            sc += 11
        elif vol_ratio >= 1.2:
            sc += 7
        elif vol_ratio >= 1.0:
            sc += 3
    if broke:
        sc += 16
    elif dist_high <= 1.0:
        sc += 12
    elif dist_high <= 3.0:
        sc += 8
    elif dist_high <= 6.0:
        sc += 4
    if ext <= 1.0:
        sc += 14
    elif ext <= 1.8:
        sc += 10
    elif ext <= 2.6:
        sc += 5

    hard = []
    if rv > 80:
        hard.append("4H 과열")
    if ext > 3.0:
        hard.append("EMA 이격 과다")
    if chg24 > 25:
        hard.append("24h 급등")
    if atr_pct > 12:
        hard.append("변동성 과다")

    setup = "관찰"
    if broke and (vol_ratio or 0) >= 1.2:
        setup = "돌파"
    elif close > e20v > e50v and ext <= 2.0:
        setup = "추세지속"

    swing_low = min(lo[i - 9: i + 1])
    atr_stop = close - 1.5 * a
    struct_stop = swing_low - 0.25 * a
    stop = max(atr_stop, struct_stop) if struct_stop < close else atr_stop
    if stop >= close:
        stop = close - 1.5 * a

    return {"score": round(sc, 1), "setup": setup, "hard": hard, "atr": a,
            "stop": stop, "rsi4h": rv, "vol_ratio": vol_ratio, "ext": ext,
            "dist_high": dist_high, "chg24": chg24, "atr_pct": atr_pct,
            "close": close, "high20": high20}


def mirror_candles(c: list[list[float]]) -> list[list[float]]:
    """가격 역수 변환 — 원본 숏 ≈ 역수 시계열 롱 (대칭 숏 검증용)."""
    out = []
    for ts, o, h, l, cl, v in c:
        if o <= 0 or h <= 0 or l <= 0 or cl <= 0:
            continue
        out.append([ts, 1.0 / o, 1.0 / l, 1.0 / h, 1.0 / cl, v])
    return out


def backtest_symbol(symbol: str, c: list[list[float]], min_score: float,
                    max_hold: int, fee_bps: float, tp_r: float, sl_atr_mult: float,
                    vol_min: float = 0.0, atr_min: float = 0.0,
                    exclude_setups: set | None = None, side: str = "long") -> list[dict]:
    n = len(c)
    if n < 240:
        return []
    ts = [r[0] for r in c]
    op = [r[1] for r in c]
    hi = [r[2] for r in c]
    lo = [r[3] for r in c]
    cl = [r[4] for r in c]
    vo = [r[5] for r in c]

    e20 = ema_series(cl, 20)
    e50 = ema_series(cl, 50)
    e200 = ema_series(cl, 200)
    rsi = rsi_series(cl, 14)
    atr = atr_series(hi, lo, cl, 14)
    e50p10 = [e50[i - 10] if i >= 10 else None for i in range(n)]
    mean_vol = [None] * n
    for i in range(23, n):
        base = sum(vo[i - 22: i - 2]) / 20.0
        mean_vol[i] = base if base > 0 else None

    trades: list[dict] = []
    i = 210
    cost_R = fee_bps * 2.0 / 10000.0  # 진입가 대비 비율 → R 로 환산해 차감
    while i < n - 2:
        sig = signal_at(i, cl, hi, lo, vo, e20, e50, e200, e50p10, rsi, atr, mean_vol)
        if not sig or sig["hard"] or sig["score"] < min_score:
            i += 1
            continue
        if vol_min and (sig["vol_ratio"] or 0.0) < vol_min:
            i += 1
            continue
        if atr_min and sig["atr_pct"] < atr_min:
            i += 1
            continue
        if exclude_setups and sig["setup"] in exclude_setups:
            i += 1
            continue

        entry = op[i + 1]
        if entry <= 0:
            i += 1
            continue
        # 손절을 진입가 기준으로 재계산 (스캐너는 신호 종가 기준 → 진입가로 이동)
        gap = entry - sig["close"]
        stop = max(sig["stop"] + gap, entry - 2.2 * sig["atr"])
        risk = entry - stop
        if risk <= 0:
            i += 1
            continue
        tp1 = entry + tp_r * risk
        tp2 = entry + (tp_r * 1.6) * risk

        exit_kind, exit_px, exit_i = None, None, None
        mfe = 0.0
        for j in range(i + 1, min(i + 1 + max_hold, n)):
            mfe = max(mfe, (hi[j] - entry) / risk)
            if lo[j] <= stop:               # 같은 봉 손절·목표 동시 → 손절 우선(보수적)
                exit_kind, exit_px, exit_i = "stop", stop, j
                break
            if hi[j] >= tp1:
                exit_kind, exit_px, exit_i = "tp1", tp1, j
                break
        if exit_kind is None:
            k = min(i + max_hold, n - 1)
            exit_kind, exit_px, exit_i = "time", cl[k], k

        r = (exit_px - entry) / risk - cost_R * (entry / risk)
        tp2_hit = any(hi[j] >= tp2 for j in range(i + 1, exit_i + 1))
        trades.append({
            "symbol": symbol,
            "base": base_of(symbol),
            "side": side,
            "signal_ts": ts[i],
            "entry_ts": ts[i + 1],
            "exit_ts": ts[exit_i],
            "bars_held": exit_i - i,
            "score": sig["score"],
            "setup": sig["setup"],
            "rsi4h": round(sig["rsi4h"], 1),
            "vol_ratio": round(sig["vol_ratio"], 2) if sig["vol_ratio"] is not None else None,
            "ext_atr": round(sig["ext"], 2),
            "atr_pct": round(sig["atr_pct"], 2),
            "dist_high20": round(sig["dist_high"], 2),
            "entry": round(entry, 8),
            "stop": round(stop, 8),
            "tp1": round(tp1, 8),
            "risk_pct": round(risk / entry * 100.0, 2),
            "exit": exit_kind,
            "r": round(r, 4),
            "mfe_r": round(mfe, 2),
            "tp2_hit": tp2_hit,
            "year": datetime.fromtimestamp(ts[i] / 1000.0, KST).year if ts[i] > 1e11
                    else datetime.fromtimestamp(ts[i], KST).year,
            "month": datetime.fromtimestamp(ts[i] / 1000.0, KST).strftime("%Y-%m")
                     if ts[i] > 1e11 else datetime.fromtimestamp(ts[i], KST).strftime("%Y-%m"),
        })
        i = exit_i + 1  # 보유 중 중복 신호 금지
    return trades


def random_baseline(symbol: str, c: list[list[float]], min_score: float, max_hold: int,
                    fee_bps: float, tp_r: float, rng: random.Random) -> list[dict]:
    """동일 청산 규칙의 무작위 진입 — 신호 로직의 부가가치 측정용."""
    n = len(c)
    if n < 240:
        return []
    ts = [r[0] for r in c]
    op = [r[1] for r in c]
    hi = [r[2] for r in c]
    lo = [r[3] for r in c]
    cl = [r[4] for r in c]
    atr = atr_series(hi, lo, cl, 14)
    trades = []
    i = 210
    cost_R = fee_bps * 2.0 / 10000.0
    while i < n - 2:
        if rng.random() > 0.06:  # 신호와 비슷한 빈도
            i += 1
            continue
        if not atr[i] or atr[i] <= 0:
            i += 1
            continue
        entry = op[i + 1]
        stop = entry - 1.5 * atr[i]
        risk = entry - stop
        if risk <= 0:
            i += 1
            continue
        tp1 = entry + tp_r * risk
        exit_kind, exit_px, exit_i = None, None, None
        for j in range(i + 1, min(i + 1 + max_hold, n)):
            if lo[j] <= stop:
                exit_kind, exit_px, exit_i = "stop", stop, j
                break
            if hi[j] >= tp1:
                exit_kind, exit_px, exit_i = "tp1", tp1, j
                break
        if exit_kind is None:
            k = min(i + max_hold, n - 1)
            exit_kind, exit_px, exit_i = "time", cl[k], k
        r = (exit_px - entry) / risk - cost_R * (entry / risk)
        trades.append({"symbol": symbol, "base": base_of(symbol), "signal_ts": ts[i],
                       "exit": exit_kind, "r": round(r, 4), "setup": "무작위",
                       "score": round(min_score, 1), "bars_held": exit_i - i,
                       "risk_pct": round(risk / entry * 100.0, 2),
                       "year": datetime.fromtimestamp(ts[i] / 1000.0, KST).year if ts[i] > 1e11
                               else datetime.fromtimestamp(ts[i], KST).year})
        i = exit_i + 1
    return trades


# --------------------------------------------------------------------------- #
# 통계
# --------------------------------------------------------------------------- #
def stats(trades: list[dict]) -> dict:
    n = len(trades)
    if n == 0:
        # 표본 0일 때도 모든 키를 채워 반환 — 소비 측 KeyError 방지
        return {"n": 0, "win_rate": 0.0, "avg_r": 0.0, "expectancy_sum_r": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0, "profit_factor": 0.0, "max_dd_r": 0.0,
                "max_consec_loss": 0, "avg_bars": 0.0, "tp_exits": 0, "sl_exits": 0,
                "time_exits": 0, "tp2_rate": 0.0, "avg_mfe": 0.0}
    rs = [t["r"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_w = sum(wins)
    gross_l = abs(sum(losses))
    eq, peak, mdd = 0.0, 0.0, 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    # 최대 연속 손실
    cur = worst = 0
    for t in trades:
        if t["r"] <= 0:
            cur += 1
            worst = max(worst, cur)
        else:
            cur = 0
    return {
        "n": n,
        "win_rate": round(len(wins) / n * 100.0, 2),
        "avg_r": round(sum(rs) / n, 4),
        "expectancy_sum_r": round(sum(rs), 2),
        "avg_win": round(sum(wins) / len(wins), 3) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 3) if losses else 0.0,
        "profit_factor": round(gross_w / gross_l, 3) if gross_l > 0 else float("inf"),
        "max_dd_r": round(mdd, 2),
        "max_consec_loss": worst,
        "avg_bars": round(sum(t["bars_held"] for t in trades) / n, 1),
        "tp_exits": sum(1 for t in trades if t["exit"] == "tp1"),
        "sl_exits": sum(1 for t in trades if t["exit"] == "stop"),
        "time_exits": sum(1 for t in trades if t["exit"] == "time"),
        "tp2_rate": round(sum(1 for t in trades if t.get("tp2_hit")) / n * 100.0, 1),
        "avg_mfe": round(sum(t.get("mfe_r", 0) for t in trades) / n, 2),
    }


def group_stats(trades: list[dict], keyfn) -> dict[str, dict]:
    g: dict[str, list[dict]] = {}
    for t in trades:
        g.setdefault(str(keyfn(t)), []).append(t)
    return {k: stats(v) for k, v in sorted(g.items())}


def wilson_lower(wins: int, n: int, z: float = 1.96) -> float:
    """승률 신뢰구간 하한 (Wilson) — 표본이 작을 때 승률 과대평가 방지."""
    if n == 0:
        return 0.0
    p = wins / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return round(max(0.0, (c - m) / d) * 100.0, 2)


def equity_curve(trades: list[dict]) -> list[dict]:
    eq = 0.0
    pts = []
    for t in sorted(trades, key=lambda x: x.get("entry_ts") or x.get("signal_ts") or 0):
        eq += t["r"]
        pts.append({"t": t.get("entry_ts") or t.get("signal_ts") or 0, "eq": round(eq, 3), "r": t["r"]})
    return pts


# --------------------------------------------------------------------------- #
# HTML 리포트
# --------------------------------------------------------------------------- #
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALT LONG BACKTEST — __STAMP__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--ink:#0b1220;--panel:#121e30;--panel2:#16243a;--line:#20304a;--line2:#2a3d5c;
 --txt:#e6edf7;--dim:#8ea3bf;--dim2:#63799a;--amber:#e8b45c;--azure:#5fa8f5;
 --teal:#3fc7a4;--rose:#e0655f;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1100px 620px at 10% -12%,#16263f 0,transparent 60%),
 radial-gradient(900px 520px at 96% 2%,#1a2033 0,transparent 55%),var(--ink);color:var(--txt);
 font-family:"IBM Plex Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
 font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1400px;margin:0 auto;padding:34px 22px 80px}
.top{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-end;justify-content:space-between;
 border-bottom:1px solid var(--line);padding-bottom:20px}
h1{margin:0;font-size:26px;font-weight:700;letter-spacing:.14em}
h1 small{display:block;font-size:11px;font-weight:500;letter-spacing:.32em;color:var(--dim2);margin-top:3px}
.meta{font-family:var(--mono);font-size:12px;color:var(--dim);text-align:right;line-height:1.85}
.meta b{color:var(--txt);font-weight:500}
.strip{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:24px 0 6px}
.stat{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
 border-radius:12px;padding:16px 18px}
.stat .k{font-size:11px;letter-spacing:.18em;color:var(--dim2)}
.stat .v{font-family:var(--mono);font-size:30px;font-weight:600;margin-top:6px}
.stat .s{font-size:12px;color:var(--dim);margin-top:2px}
.sec{margin-top:36px}
.sech{display:flex;align-items:baseline;gap:12px;border-bottom:1px solid var(--line);
 padding-bottom:9px;margin-bottom:16px}
.sech h2{margin:0;font-size:13px;letter-spacing:.22em}
.sech span{font-size:12px;color:var(--dim2)}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 12px;border-bottom:1px solid rgba(32,48,74,.6);text-align:right;
 font-family:var(--mono);font-size:13px;white-space:nowrap}
th{font-size:11px;letter-spacing:.1em;color:var(--dim2);font-weight:600;background:var(--panel2);
 text-align:right;border-bottom:1px solid var(--line2)}
th.l,td.l{text-align:left;font-family:inherit}
.tblwrap{border:1px solid var(--line);border-radius:13px;overflow:auto;background:var(--panel)}
.pos{color:var(--teal)}.neg{color:var(--rose)}.mut{color:var(--dim2)}
.bar{height:7px;background:var(--line2);border-radius:4px;overflow:hidden;display:inline-block;
 width:90px;vertical-align:middle;margin-right:8px}
.bar i{display:block;height:100%;background:var(--amber)}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11.5px;border:1px solid transparent}
.b-돌파{background:rgba(232,180,92,.14);color:var(--amber);border-color:rgba(232,180,92,.35)}
.b-추세지속{background:rgba(63,199,164,.13);color:var(--teal);border-color:rgba(63,199,164,.32)}
.b-관찰{background:rgba(142,163,191,.1);color:var(--dim);border-color:var(--line2)}
.b-무작위{background:rgba(224,101,95,.12);color:var(--rose);border-color:rgba(224,101,95,.3)}
.note{margin-top:38px;border-top:1px solid var(--line);padding-top:20px;
 display:grid;grid-template-columns:1.3fr 1fr;gap:26px;font-size:13px;color:var(--dim)}
.note h3{font-size:11.5px;letter-spacing:.2em;color:var(--dim2);margin:0 0 9px}
.note ul{margin:0;padding-left:17px}.note li{margin-bottom:5px}
.note code{font-family:var(--mono);font-size:12px;background:var(--panel);border:1px solid var(--line);
 border-radius:5px;padding:1px 6px;color:var(--txt)}
.warn{color:var(--rose);font-size:12.5px}
.chartbox{border:1px solid var(--line);border-radius:13px;background:var(--panel);padding:14px}
.legend{font-family:var(--mono);font-size:12px;color:var(--dim2);margin-top:8px}
@media (max-width:860px){.strip{grid-template-columns:repeat(2,1fr)}.note{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>ALT LONG BACKTEST<small>SIGNAL VERIFICATION · R-MULTIPLE ENGINE</small></h1>
    <div class="meta">
      검증 시각 <b>__STAMP__</b><br>
      데이터 <b>__EXCHANGE__</b> · 4H · <b>__PERIOD__</b><br>
      유니버스 <b>__NSYM__</b>종목 · 봉 <b>__BARS__</b>개/종목 · 수집 오류 <b>__ERRORS__</b>
    </div>
  </header>

  <section class="strip">
    <div class="stat"><div class="k">TRADES</div><div class="v">__N__</div>
      <div class="s">신호 발생·청산 완료</div></div>
    <div class="stat"><div class="k">WIN RATE</div><div class="v" style="color:__WCOLOR__">__WIN__%</div>
      <div class="s">승률 하한(95% Wilson) __WINLOW__%</div></div>
    <div class="stat"><div class="k">EXPECTANCY</div><div class="v" style="color:__ECOLOR__">__EXP__R</div>
      <div class="s">1회 매매 평균 손익</div></div>
    <div class="stat"><div class="k">PROFIT FACTOR</div><div class="v">__PF__</div>
      <div class="s">총이익 / 총손실</div></div>
  </section>

  <section class="sec">
    <div class="sech"><h2>RULE SET</h2><span>검증한 규칙과 체결 가정</span></div>
    <div class="tblwrap"><table>
      <tr><th class="l">항목</th><th class="l">값</th></tr>
      <tr><td class="l">신호 조건</td><td class="l">4H 점수 ≥ __MINSCORE__ (추세16·기울기8·모멘텀14·거래량14·구조16·진입14) + 과열/이격/급등 하드 필터</td></tr>
      <tr><td class="l">진입</td><td class="l">신호 봉 다음 봉 시가 (룩어헤드 없음)</td></tr>
      <tr><td class="l">손절</td><td class="l">진입 − 1.5×ATR(14, 4H), 최근 10봉 저점 기준으로 보정 (최대 2.2×ATR)</td></tr>
      <tr><td class="l">목표</td><td class="l">TP1 = __TPR__R · TP2 = __TPR2__R</td></tr>
      <tr><td class="l">청산</td><td class="l">손절 −1R / TP1 +__TPR__R / 최대 __MAXHOLD__봉(4H) 초과 시 종가 청산</td></tr>
      <tr><td class="l">동시 터치</td><td class="l">한 봉에서 손절·목표 동시 도달 → <b>손절 우선</b> (보수적 가정)</td></tr>
      <tr><td class="l">비용</td><td class="l">편도 __FEE__bps (수수료+슬리피지) ×2 를 R 로 환산해 차감</td></tr>
      <tr><td class="l">중복</td><td class="l">종목당 1포지션 — 보유 중 신규 신호 무시</td></tr>
    </table></div>
  </section>

  <section class="sec">
    <div class="sech"><h2>EQUITY CURVE</h2><span>누적 R (1 = 손절폭 1배) · 무작위 진입 대조군 포함</span></div>
    <div class="chartbox">
      <svg id="eq" viewBox="0 0 1200 320" width="100%" height="320" preserveAspectRatio="none"></svg>
      <div class="legend">— 신호 전략 누적 R &nbsp;&nbsp;·&nbsp;&nbsp; — 무작위 진입 누적 R &nbsp;&nbsp;·&nbsp;&nbsp; 점선 = 손익분기</div>
    </div>
  </section>

  <section class="sec">
    <div class="sech"><h2>SIGNAL vs BASELINE</h2><span>동일 청산 규칙의 무작위 진입과 비교 — 신호 로직의 부가가치</span></div>
    <div class="tblwrap"><table id="cmp"></table></div>
  </section>

  <section class="sec">
    <div class="sech"><h2>BREAKDOWN</h2><span>셋업 · 점수 구간 · 연도별 분해</span></div>
    <div class="tblwrap"><table id="grp"></table></div>
  </section>

  <section class="sec">
    <div class="sech"><h2>TRADE LOG</h2><span>__N__건 중 최근 120건 (전체는 CSV)</span></div>
    <div class="tblwrap"><table id="tr"></table></div>
  </section>

  <footer class="note">
    <div>
      <h3>해석 주의</h3>
      <ul>
        <li>승률만 보면 기대값을 알 수 없다. 손익비 __TPR__R 전략에서 손익분기 승률은 약 __BE__% 다.</li>
        <li>표본이 적은 구간(점수 구간·연도별)은 Wilson 하한을 함께 봐야 한다.</li>
        <li>생존편향: 현재 상장·거래대금 상위 종목만 검증했다. 상장폐지·유동성 소멸 종목은 표본에 없다.</li>
        <li>동일 봉 손절 우선 가정은 실제보다 보수적이며, 갭 하락 시 실제 손실은 1R을 넘을 수 있다.</li>
        <li>과거 성과는 미래 성과를 보장하지 않는다.</li>
      </ul>
      <p class="warn">본 리포트는 공개 시세 데이터의 기계적 검증 결과이며 투자 자문이 아닙니다.</p>
    </div>
    <div>
      <h3>재현</h3>
      <ul>
        <li><code>python3 alt_long_backtest.py --top __TOP__ --bars __BARS__</code></li>
        <li><code>--min-score __MINSCORE__ --max-hold __MAXHOLD__</code></li>
        <li>스캐너와 동일 로직: <code>bybit_alt_long_scanner.py</code></li>
      </ul>
    </div>
  </footer>
</div>

<script>
const S = __STATS__, B = __BASE__, G = __GROUPS__, TR = __TRADES__;
const EQ = __EQ__, BEQ = __BEQ__;
const f2 = v => (v>=0?"+":"") + v.toFixed(2);
const pct = v => (v==null?"-":v.toFixed(1)+"%");

/* ---- equity curve ---- */
(function(){
  const svg = document.getElementById("eq");
  const W = 1200, H = 320, PAD = 26;
  const all = EQ.concat(BEQ);
  if (!all.length) return;
  const tmin = Math.min(...all.map(p=>p.t)), tmax = Math.max(...all.map(p=>p.t));
  const ys = all.map(p=>p.eq); ys.push(0);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const X = t => PAD + (t-tmin)/(tmax-tmin||1)*(W-2*PAD);
  const Y = v => H-PAD - (v-ymin)/(ymax-ymin||1)*(H-2*PAD);
  const path = arr => arr.map((p,i)=>`${i?"L":"M"}${X(p.t).toFixed(1)},${Y(p.eq).toFixed(1)}`).join(" ");
  const zero = `M${PAD},${Y(0).toFixed(1)} L${W-PAD},${Y(0).toFixed(1)}`;
  svg.innerHTML = `
    <line x1="0" y1="${Y(0)}" x2="${W}" y2="${Y(0)}" stroke="#2a3d5c" stroke-dasharray="4 5"/>
    <path d="${path(BEQ)}" fill="none" stroke="#e0655f" stroke-width="1.6" opacity=".75"/>
    <path d="${path(EQ)}" fill="none" stroke="#3fc7a4" stroke-width="2.2"/>`;
})();

/* ---- comparison table ---- */
(function(){
  const cols = ["표본","승률","승률 하한","평균 R","기대값 합","Profit Factor","최대 MDD","최대 연속손실","평균 보유봉","TP 도달","TP2 도달"];
  const rows = [["신호 전략", S], ["무작위 진입", B]];
  document.getElementById("cmp").innerHTML =
    "<tr><th class='l'>구분</th>" + cols.map(c=>`<th>${c}</th>`).join("") + "</tr>" +
    rows.map(([nm,s]) => `<tr><td class="l">${nm}</td>
      <td>${s.n||0}</td>
      <td class="${(s.win_rate||0)>=_BE_?"pos":"neg"}">${pct(s.win_rate)}</td>
      <td class="mut">${pct(s.win_lower)}</td>
      <td class="${(s.avg_r||0)>=0?"pos":"neg"}">${f2(s.avg_r||0)}</td>
      <td class="${(s.expectancy_sum_r||0)>=0?"pos":"neg"}">${f2(s.expectancy_sum_r||0)}</td>
      <td>${s.profit_factor==null?"-":(s.profit_factor===Infinity?"∞":s.profit_factor.toFixed(2))}</td>
      <td class="neg">${(s.max_dd_r||0).toFixed(1)}</td>
      <td>${s.max_consec_loss||0}</td>
      <td>${s.avg_bars||0}</td>
      <td>${s.tp_exits||0}</td>
      <td>${(s.tp2_rate||0).toFixed(0)}%</td></tr>`).join("");
})();

/* ---- breakdown ---- */
(function(){
  const names = {setup:"셋업",score:"점수 구간",year:"연도"};
  let html = "<tr><th class='l'>구분</th><th class='l'>값</th><th>표본</th><th>승률</th><th>승률 하한</th><th>평균 R</th><th>기대값 합</th><th>PF</th><th>최대 MDD</th></tr>";
  Object.keys(G).forEach(k => {
    html += `<tr><td class="l mut" colspan="9" style="background:rgba(22,36,58,.6);letter-spacing:.1em;font-size:11px">${names[k]||k}</td></tr>`;
    Object.entries(G[k]).forEach(([v,s]) => {
      html += `<tr><td class="l"></td><td class="l">${k==="setup"?`<span class="badge b-${v}">${v}</span>`:v}</td>
        <td>${s.n}</td>
        <td class="${s.win_rate>=_BE_?"pos":"neg"}">${pct(s.win_rate)}</td>
        <td class="mut">${pct(s.win_lower)}</td>
        <td class="${s.avg_r>=0?"pos":"neg"}">${f2(s.avg_r)}</td>
        <td class="${s.expectancy_sum_r>=0?"pos":"neg"}">${f2(s.expectancy_sum_r)}</td>
        <td>${s.profit_factor===Infinity?"∞":(s.profit_factor||0)}</td>
        <td class="neg">${(s.max_dd_r||0).toFixed(1)}</td></tr>`;
    });
  });
  document.getElementById("grp").innerHTML = html;
})();

/* ---- trades ---- */
(function(){
  const rows = TR.slice(0,120);
  const dt = t => new Date(t > 1e11 ? t : t*1000).toISOString().slice(0,10);
  document.getElementById("tr").innerHTML =
    "<tr><th class='l'>#</th><th class='l'>심볼</th><th class='l'>셋업</th><th>점수</th><th>진입일</th>"
    + "<th>진입</th><th>손절</th><th>TP1</th><th>손절폭</th><th>청산</th><th>R</th><th>MFE</th><th>보유봉</th></tr>"
    + rows.map((t,i)=>`<tr>
      <td class="l mut">${i+1}</td>
      <td class="l"><b>${t.base}</b></td>
      <td class="l"><span class="badge b-${t.setup}">${t.setup}</span></td>
      <td>${t.score.toFixed(0)}</td>
      <td class="mut">${dt(t.entry_ts)}</td>
      <td>${t.entry<1?t.entry.toPrecision(4):t.entry.toFixed(4)}</td>
      <td class="neg">${t.stop<1?t.stop.toPrecision(4):t.stop.toFixed(4)}</td>
      <td class="pos">${t.tp1<1?t.tp1.toPrecision(4):t.tp1.toFixed(4)}</td>
      <td class="mut">${t.risk_pct.toFixed(1)}%</td>
      <td class="${t.exit==="tp1"?"pos":t.exit==="stop"?"neg":"mut"}">${t.exit}</td>
      <td class="${t.r>=0?"pos":"neg"}"><b>${f2(t.r)}</b></td>
      <td class="mut">${t.mfe_r.toFixed(1)}</td>
      <td class="mut">${t.bars_held}</td></tr>`).join("");
})();
</script>
</body>
</html>
"""


def write_html(path: str, s: dict, b: dict, groups: dict, trades: list[dict], eq, beq,
               info: dict) -> None:
    be = 100.0 / (info["tp_r"] + 1.0)
    html = (HTML_TEMPLATE
            .replace("__STAMP__", info["stamp"])
            .replace("__EXCHANGE__", info["exchange"])
            .replace("__PERIOD__", info["period"])
            .replace("__NSYM__", str(info["nsym"]))
            .replace("__BARS__", str(info["bars"]))
            .replace("__ERRORS__", str(info["errors"]))
            .replace("__N__", str(s.get("n", 0)))
            .replace("__WIN__", f"{s.get('win_rate', 0):.1f}")
            .replace("__WINLOW__", f"{s.get('win_lower', 0):.1f}")
            .replace("__WCOLOR__", "var(--teal)" if s.get("win_rate", 0) >= be else "var(--rose)")
            .replace("__EXP__", f"{s.get('avg_r', 0):+.3f}")
            .replace("__ECOLOR__", "var(--teal)" if s.get("avg_r", 0) >= 0 else "var(--rose)")
            .replace("__PF__", ("∞" if s.get("profit_factor") == float("inf")
                                else f"{s.get('profit_factor', 0):.2f}"))
            .replace("__MINSCORE__", f"{info['min_score']:.0f}")
            .replace("__TPR__", f"{info['tp_r']:.1f}")
            .replace("__TPR2__", f"{info['tp_r']*1.6:.1f}")
            .replace("__MAXHOLD__", str(info["max_hold"]))
            .replace("__FEE__", f"{info['fee_bps']:.1f}")
            .replace("__TOP__", str(info["top"]))
            .replace("__BE__", f"{be:.1f}")
            .replace("__STATS__", json.dumps(s, ensure_ascii=False, default=str))
            .replace("__BASE__", json.dumps(b, ensure_ascii=False, default=str))
            .replace("__GROUPS__", json.dumps(groups, ensure_ascii=False, default=str))
            .replace("__TRADES__", json.dumps(
                sorted(trades, key=lambda x: -x["signal_ts"])[:120], ensure_ascii=False, default=str))
            .replace("__EQ__", json.dumps(eq))
            .replace("__BEQ__", json.dumps(beq))
            .replace("_BE_", f"{be:.2f}"))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="알트 롱 신호 백테스터")
    ap.add_argument("--exchange", default="auto", choices=["auto", "bybit", "okx"])
    ap.add_argument("--top", type=int, default=60, help="거래대금 상위 N종목 (기본 60)")
    ap.add_argument("--bars", type=int, default=4400, help="종목당 4H 봉 수 (기본 4400 ≈ 2년)")
    ap.add_argument("--min-score", type=float, default=60)
    ap.add_argument("--max-hold", type=int, default=42, help="최대 보유 봉 (4H, 기본 42 ≈ 7일)")
    ap.add_argument("--tp-r", type=float, default=2.0, help="TP1 배수 (기본 2.0R)")
    ap.add_argument("--fee-bps", type=float, default=8.5, help="편도 수수료+슬리피지 (bps, 기본 8.5)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--vol-min", type=float, default=0.0, help="1H 거래량 배수 하한")
    ap.add_argument("--atr-min", type=float, default=0.0, help="4H ATR%% 하한")
    ap.add_argument("--exclude-setup", default="", help="제외 셋업 (쉼표 구분)")
    ap.add_argument("--edge", action="store_true",
                    help="edge 프리셋: 거래량 2.0배 · ATR 4%% · '추세지속' 제외")
    ap.add_argument("--short", action="store_true", help="숏 대칭 검증 (가격 역수 미러)")
    ap.add_argument("--label", default="", help="리포트/CSV 파일명 접두어")
    ap.add_argument("--baseline", action="store_true", default=True)
    ap.add_argument("--html", default=None)
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    global INCLUDE_EQUITIES
    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    print("=" * 78)
    print("  ALT LONG BACKTEST — 4H 신호 승률/기대값 검증")
    print(f"  {stamp}")
    print("=" * 78)

    ex = build_exchange(args.exchange)
    print(f"  · 데이터 소스: {ex.label}" + ("  [숏 미러 모드]" if args.short else ""))
    uni = sorted(ex.universe(), key=lambda r: -r["turnover"])[:args.top]
    print(f"  · 유니버스 {len(uni)}종목 · 종목당 {args.bars}봉 4H 수집 중…")

    # 디스크 캐시 — 중단 후 재실행 시 이미 받은 종목은 재사용
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bt_cache")
    os.makedirs(cache_dir, exist_ok=True)

    def cache_path(sym: str) -> str:
        tag = ex.name + "_" + sym.replace("/", "_") + f"_{args.bars}.json"
        return os.path.join(cache_dir, tag)

    data: dict[str, list[list[float]]] = {}
    todo = []
    for r in uni:
        cp = cache_path(r["symbol"])
        if os.path.exists(cp):
            try:
                with open(cp, encoding="utf-8") as f:
                    c = json.load(f)
                if len(c) >= 240:
                    data[r["symbol"]] = c
                    continue
            except Exception:  # noqa: BLE001
                pass
        todo.append(r["symbol"])

    print(f"    · 캐시 {len(data)}종목 · 신규 수집 {len(todo)}종목", file=sys.stderr)
    errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(ex.candles_all, sym, "4h", args.bars): sym for sym in todo}
        done = 0
        for fu in as_completed(futs):
            sym = futs[fu]
            done += 1
            if done % 5 == 0 or done == len(todo):
                print(f"    · {done}/{len(todo)} …", file=sys.stderr)
            try:
                c = fu.result()
                if len(c) >= 240:
                    data[sym] = c
                    with open(cache_path(sym), "w", encoding="utf-8") as f:
                        json.dump(c, f)
            except Exception:  # noqa: BLE001
                errors += 1

    if not data:
        print("  데이터 수집 실패 — 네트워크/거래소를 확인하세요.", file=sys.stderr)
        return 1
    print(f"  · 수집 완료 {len(data)}종목 (오류 {errors})")

    if args.edge:
        args.vol_min, args.atr_min = 2.0, 4.0
        args.exclude_setup = args.exclude_setup or "추세지속"
    excl = {x.strip() for x in args.exclude_setup.split(",") if x.strip()}
    side = "short" if args.short else "long"
    if args.short:
        data = {k: mirror_candles(v) for k, v in data.items()}

    trades: list[dict] = []
    for sym, c in data.items():
        try:
            trades.extend(backtest_symbol(sym, c, args.min_score, args.max_hold,
                                          args.fee_bps, args.tp_r, 1.5,
                                          vol_min=args.vol_min, atr_min=args.atr_min,
                                          exclude_setups=excl, side=side))
        except Exception:  # noqa: BLE001
            errors += 1

    rng = random.Random(7)
    bl: list[dict] = []
    if args.baseline:
        for sym, c in data.items():
            bl.extend(random_baseline(sym, c, args.min_score, args.max_hold, args.fee_bps,
                                      args.tp_r, rng))

    if not trades:
        print("  신호 0건 — --min-score 를 낮춰보세요.", file=sys.stderr)
        return 1

    s = stats(trades)
    s["win_lower"] = wilson_lower(s["tp_exits"], s["n"])
    b = stats(bl)
    if b.get("n"):
        b["win_lower"] = wilson_lower(b["tp_exits"], b["n"])

    groups = {
        "setup": group_stats(trades, lambda t: t["setup"]),
        "score": group_stats(trades, lambda t: ("80+" if t["score"] >= 80 else
                                                "70-79" if t["score"] >= 70 else "60-69")),
        "year": group_stats(trades, lambda t: t["year"]),
    }

    ts_all = [x[0] for c in data.values() for x in c]
    unit = 1000.0 if max(ts_all) > 1e11 else 1.0
    period = (f"{datetime.fromtimestamp(min(ts_all)/unit, KST):%Y-%m-%d} ~ "
              f"{datetime.fromtimestamp(max(ts_all)/unit, KST):%Y-%m-%d}")

    print("\n" + "-" * 78)
    print(f"  표본 {s['n']}건 · 승률 {s['win_rate']:.1f}% (95% 하한 {s['win_lower']:.1f}%) · "
          f"평균 R {s['avg_r']:+.3f} · 기대값 합 {s['expectancy_sum_r']:+.1f}R")
    print(f"  Profit Factor {s['profit_factor']:.2f} · 최대 MDD {s['max_dd_r']:.1f}R · "
          f"최대 연속손실 {s['max_consec_loss']} · 평균 보유 {s['avg_bars']}봉")
    print(f"  청산: TP1 {s['tp_exits']} / 손절 {s['sl_exits']} / 시간 {s['time_exits']} · "
          f"TP2 도달률 {s['tp2_rate']}%")
    be = 100.0 / (args.tp_r + 1.0)
    print(f"  ※ 손익분기 승률(TP1 {args.tp_r}R 기준) = {be:.1f}%")
    if b.get("n"):
        print(f"\n  [대조군] 무작위 진입 {b['n']}건 · 승률 {b['win_rate']:.1f}% · "
              f"평균 R {b['avg_r']:+.3f} · PF {b['profit_factor']:.2f}")
    print("\n  [셋업별]")
    for k, v in groups["setup"].items():
        print(f"    {k:<8} n={v['n']:<5} 승률 {v['win_rate']:>5.1f}%  평균 R {v['avg_r']:+.3f}  "
              f"기대값합 {v['expectancy_sum_r']:+.1f}R  PF {v['profit_factor']:.2f}")
    print("  [점수 구간별]")
    for k, v in groups["score"].items():
        print(f"    {k:<8} n={v['n']:<5} 승률 {v['win_rate']:>5.1f}%  평균 R {v['avg_r']:+.3f}  "
              f"기대값합 {v['expectancy_sum_r']:+.1f}R  PF {v['profit_factor']:.2f}")
    print("  [연도별]")
    for k, v in groups["year"].items():
        print(f"    {k:<8} n={v['n']:<5} 승률 {v['win_rate']:>5.1f}%  평균 R {v['avg_r']:+.3f}  "
              f"기대값합 {v['expectancy_sum_r']:+.1f}R  PF {v['profit_factor']:.2f}")
    print("-" * 78)

    prefix = (args.label + "_") if args.label else ""
    csv_path = args.csv or f"{prefix}alt_long_backtest_trades_{datetime.now(KST):%Y%m%d_%H%M}.csv"
    cols = ["symbol", "base", "score", "setup", "entry_ts", "entry", "stop", "tp1", "risk_pct",
            "exit", "r", "mfe_r", "tp2_hit", "bars_held", "rsi4h", "vol_ratio", "ext_atr",
            "atr_pct", "dist_high20", "year", "month"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for t in sorted(trades, key=lambda x: x["entry_ts"]):
            wr.writerow([t.get(c) for c in cols])
    print(f"  CSV  → {csv_path}")

    if args.html:
        write_html(args.html, s, b, groups, trades, equity_curve(trades), equity_curve(bl), {
            "stamp": stamp, "exchange": ex.label, "period": period, "nsym": len(data),
            "bars": args.bars, "errors": errors, "min_score": args.min_score,
            "max_hold": args.max_hold, "tp_r": args.tp_r, "fee_bps": args.fee_bps,
            "top": args.top,
        })
        print(f"  HTML → {args.html}")

    print("\n  ※ 과거 성과는 미래 성과를 보장하지 않습니다. 정보 제공용이며 투자 자문이 아닙니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
