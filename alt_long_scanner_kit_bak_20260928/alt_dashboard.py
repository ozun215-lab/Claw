#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
알림 대시보드 생성기 (자동 실행 모니터)
=======================================

`alt_scan_runner.py` 가 30분마다 쌓는 산출물을 읽어 **운영 대시보드 HTML** 을 만든다.
데이터는 파이썬이 HTML 마크업에 직접 박아넣는다 → JavaScript 가 막힌 뷰어에서도 보인다.

읽는 파일 (기본 reports/ 안)
----------------------------
  history.csv   전 회차 종목별 점수 시계열
  alerts.csv    NEW / REENTER 알림 이벤트 로그
  summary.json  최근 회차 요약 (후보·알림·소요)
  state.json    중복 알림 방지 상태

표시 항목
---------
  1) 운영 상태    : 최근 실행·다음 예정 시각·회차 수·실패/누락
  2) 펄스 바      : 최근 24시간 30분 슬롯 48칸 (실행 여부·알림 발생을 색으로)
  3) 알림 피드    : 최근 알림 (NEW/REENTER · 점수 · 셋업 · 진입/손절/TP)
  4) 현재 후보    : 최근 회차 후보 (점수 미터 · 셋업 · 레벨)
  5) 반복 종목    : 알림 횟수 상위 + 점수 스파크라인 (Python 생성 SVG)
  6) 회차 로그    : 회차별 후보 수·평균 점수

사용법
------
  python3 alt_dashboard.py                                  # 1회 생성
  python3 alt_dashboard.py --outdir reports --out reports/dashboard.html
  python3 alt_dashboard.py --serve 8080                      # HTTP 서빙(요청마다 재생성)

주의: 정보 제공용이며 투자 자문이 아니다.
"""

from __future__ import annotations

import argparse
import csv
import glob
import html
import json
import os
import sys
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
FMT = "%Y-%m-%d %H:%M"
FMT_S = "%Y-%m-%d %H:%M:%S"


def parse_ts(v: str):
    """초 단위·분 단위 타임스탬프 모두 허용."""
    v = (v or "").strip()
    for f in (FMT_S, FMT):
        try:
            return datetime.strptime(v, f).replace(tzinfo=KST)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------- #
# 데이터 로드
# --------------------------------------------------------------------------- #
def load_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r]


def fnum(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load_reports(outdir: str) -> dict:
    hist = load_csv(os.path.join(outdir, "history.csv"))
    alerts = load_csv(os.path.join(outdir, "alerts.csv"))
    ledger = load_csv(os.path.join(outdir, "runs.csv"))
    summary = {}
    sp = os.path.join(outdir, "summary.json")
    if os.path.exists(sp):
        try:
            with open(sp, encoding="utf-8") as f:
                summary = json.load(f)
        except Exception:  # noqa: BLE001
            summary = {}

    # 회차 원장(runs.csv) 우선 — 없으면 history 에서 유추
    ledger_runs = []
    for r in ledger:
        ledger_runs.append({
            "run_at": r.get("run_at") or "", "ok": (r.get("ok") or "ok") == "ok",
            "scanned": int(fnum(r.get("scanned"), 0) or 0),
            "candidates": int(fnum(r.get("candidates"), 0) or 0),
            "alerts": int(fnum(r.get("alerts"), 0) or 0),
            "errors": int(fnum(r.get("errors"), 0) or 0),
            "seconds": fnum(r.get("seconds"), 0) or 0,
            "edge_rule": r.get("edge_rule") or "",
        })
    ledger_runs.sort(key=lambda x: x["run_at"])

    runs: dict[str, dict] = {}
    for r in hist:
        ra = r.get("run_at") or ""
        g = runs.setdefault(ra, {"run_at": ra, "n": 0, "scores": [], "setups": Counter()})
        g["n"] += 1
        s = fnum(r.get("score"))
        if s is not None:
            g["scores"].append(s)
        g["setups"][r.get("setup") or "-"] += 1
    for ra, g in runs.items():
        g["avg"] = (sum(g["scores"]) / len(g["scores"])) if g["scores"] else 0.0
        g["top"] = max(g["scores"]) if g["scores"] else 0.0
    run_list = [runs[k] for k in sorted(runs)]
    if ledger_runs:
        by_ts = {g["run_at"]: g for g in run_list}
        for lr in ledger_runs:
            g = by_ts.get(lr["run_at"])
            if g is None:
                # 초 단위 원장 ↔ 분 단위 history 매칭
                g = {"run_at": lr["run_at"], "n": 0, "scores": [], "setups": Counter(),
                     "avg": 0.0, "top": 0.0}
            g.update({"ledger": lr, "ok": lr["ok"], "candidates": lr["candidates"],
                      "alerts": lr["alerts"], "errors": lr["errors"],
                      "seconds": lr["seconds"], "scanned": lr["scanned"]})
            by_ts[lr["run_at"]] = g
        run_list = [by_ts[k] for k in sorted(by_ts)]

    # 종목별 점수 추이 / 알림 횟수
    series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for r in hist:
        s = fnum(r.get("score"))
        if s is not None:
            series[r.get("base") or "?"].append((r.get("run_at") or "", s))
    a_count = Counter((a.get("base") or "?") for a in alerts)
    a_last = {}
    for a in alerts:
        a_last[a.get("base")] = a.get("run_at")

    alerts_sorted = sorted(alerts, key=lambda a: a.get("run_at") or "", reverse=True)

    latest_cand = []
    if summary.get("top"):
        latest_cand = summary["top"]

    return {"hist": hist, "alerts": alerts, "alerts_sorted": alerts_sorted, "ledger": ledger,
            "summary": summary, "runs": run_list, "series": series,
            "alert_count": a_count, "alert_last": a_last,
            "latest_cand": latest_cand, "outdir": outdir}


# --------------------------------------------------------------------------- #
# HTML 조각 (정적 생성)
# --------------------------------------------------------------------------- #
def esc(v) -> str:
    return html.escape(str(v), quote=True)


def _num(v, nd=4) -> str:
    if v is None:
        return "-"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}"


def _usd(v) -> str:
    v = fnum(v)
    if not v:
        return "-"
    if v >= 1e9:
        return f"${v/1e9:.1f}B"
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:.0f}"


def _meter(score, n=20) -> str:
    k = int(round(float(score) / 5.0))
    hib = " hi" if float(score) >= 75 else ""
    bars = "".join(f'<i class="{"on" + hib if i < k else ""}"></i>' for i in range(n))
    return f'<span class="meter">{bars}</span>'


def _spark(pts: list[tuple[str, float]], w=132, h=26) -> str:
    if len(pts) < 2:
        return '<span class="mut">–</span>'
    vals = [p[1] for p in pts]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    step = w / float(len(vals) - 1)
    coords = " ".join(f"{i*step:.1f},{h - 2 - (v - lo)/rng*(h-4):.1f}"
                      for i, v in enumerate(vals))
    color = "var(--teal)" if vals[-1] >= vals[0] else "var(--rose)"
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'preserveAspectRatio="none"><polyline points="{coords}" fill="none" '
            f'stroke="{color}" stroke-width="1.8"/></svg>')


def _slot_of(dt: datetime, interval_min: int) -> datetime:
    """30분 슬롯 경계로 내림 — 실행 시각이 09:13 이어도 09:00 슬롯에 배정."""
    d = dt.replace(second=0, microsecond=0)
    return d - timedelta(minutes=d.minute % interval_min)


def _pulse_slots(rep: dict, slots: int = 48, interval_min: int = 30) -> str:
    if slots <= 0:
        return ""
    now = datetime.now(KST)
    cur = _slot_of(now, interval_min)
    starts = [cur - timedelta(minutes=interval_min * (slots - 1 - i)) for i in range(slots)]

    run_map: dict[str, dict] = {}
    for r in rep["runs"]:
        dt = parse_ts(r["run_at"])
        if dt:
            run_map[_slot_of(dt, interval_min).strftime(FMT)] = r
    alert_map: dict[str, int] = defaultdict(int)
    for a in rep["alerts"]:
        dt = parse_ts(a.get("run_at"))
        if dt:
            alert_map[_slot_of(dt, interval_min).strftime(FMT)] += 1

    cells = []
    for st in starts:
        key = st.strftime(FMT)
        g = run_map.get(key)
        n_alert = alert_map.get(key, 0)
        label = st.strftime("%m-%d %H:%M")
        if g is None:
            cls, tip = "off", f"{label} · 실행 기록 없음"
        elif not g.get("ok", True):
            cls, tip = "fail", f"{label} · 실행 실패"
        elif n_alert:
            cls, tip = ("alert", f"{label} · 알림 {n_alert}건 · 후보 {g.get('candidates', g['n'])}")
        else:
            cls, tip = ("ok", f"{label} · 후보 {g.get('candidates', g['n'])} · "
                              f"최고 {g['top']:.0f}점")
        cells.append(f'<span class="slot {cls}" title="{esc(tip)}"></span>')
    return "".join(cells)


def build_html(rep: dict) -> str:
    s = rep["summary"] or {}
    runs = rep["runs"]
    alerts = rep["alerts_sorted"]
    now = datetime.now(KST)

    last_run = s.get("run_at") or (runs[-1]["run_at"] if runs else "—")
    interval = int(s.get("interval_min") or 30)

    last_dt = None
    last_dt = parse_ts(runs[-1]["run_at"]) if runs else None
    if last_dt:
        nxt = last_dt + timedelta(minutes=interval)
        next_txt = nxt.strftime("%H:%M")
        if nxt < now:
            overdue = int((now - nxt).total_seconds() // 60)
            health = f'<span class="neg">지연 {overdue}분</span>' if overdue >= interval else "정상"
        else:
            eta_min = int((nxt - now).total_seconds() // 60)
            health = f"정상 · 다음 {eta_min}분 후"
    else:
        next_txt, health = "—", "데이터 없음"

    # 최근 24시간 실행 누락 계산
    if last_dt:
        expect = max(1, int(24 * 60 / interval))
        have = len([r for r in runs
                    if (parse_ts(r["run_at"]) or now) >= now - timedelta(hours=24)])
        missing = max(0, expect - have)
    else:
        expect, have, missing = 0, 0, 0

    alerts_24 = len([a for a in alerts
                     if (a.get("run_at") or "") >= (now - timedelta(hours=24)).strftime(FMT)])
    ok_flag = s.get("ok", True)
    cand_n = s.get("candidates", runs[-1]["n"] if runs else 0)

    # ---- 알림 피드
    feed_rows = []
    for a in alerts[:40]:
        kind = (a.get("kind") or "NEW").upper()
        kcls = "k-new" if kind == "NEW" else "k-re"
        feed_rows.append(
            "<tr>"
            f'<td class="l mut">{esc(a.get("run_at"))}</td>'
            f'<td class="l"><span class="kbadge {kcls}">{esc(kind)}</span></td>'
            f'<td class="l"><b>{esc(a.get("base"))}</b></td>'
            f'<td class="l"><span class="badge b-{esc(a.get("setup"))}">{esc(a.get("setup"))}</span></td>'
            f'<td class="amber">{fnum(a.get("score"), 0):.0f}</td>'
            f'<td>{_num(a.get("last"))}</td>'
            f'<td class="neg">{_num(a.get("stop"))}</td>'
            f'<td class="pos">{_num(a.get("tp1"))}</td>'
            f'<td class="mut">{fnum(a.get("risk_pct"), 0):.2f}%</td>'
            f'<td>{fnum(a.get("rsi_4h"), 0):.0f}</td>'
            f'<td>{fnum(a.get("vol_ratio"), 0):.2f}×</td>'
            f'<td class="mut">{_usd(a.get("turnover"))}</td>'
            "</tr>")
    feed = ("<tr><th class='l'>시각</th><th class='l'>종류</th><th class='l'>심볼</th>"
            "<th class='l'>셋업</th><th>점수</th><th>가격</th><th>손절</th><th>TP1</th>"
            "<th>손절폭</th><th>RSI4h</th><th>거래량</th><th>거래대금</th></tr>"
            + ("".join(feed_rows) if feed_rows else
               "<tr><td class='l mut' colspan='12'>알림 없음 — 회차가 쌓이면 여기에 표시됩니다</td></tr>"))

    # ---- 최근 후보
    cand_rows = []
    for i, x in enumerate(rep["latest_cand"][:20], 1):
        cand_rows.append(
            "<tr>"
            f'<td class="l rk">{i}</td>'
            f'<td class="l"><b>{esc(x.get("base"))}</b></td>'
            f'<td class="l">{_meter(x.get("score", 0))}<b class="amber">{fnum(x.get("score"),0):.0f}</b></td>'
            f'<td class="l"><span class="badge b-{esc(x.get("setup"))}">{esc(x.get("setup"))}</span></td>'
            f'<td>{_num(x.get("last"))}</td>'
            f'<td class="{"pos" if fnum(x.get("chg24"),0) > 0 else "neg"}">{fnum(x.get("chg24"),0):+.2f}</td>'
            f'<td class="neg">{_num(x.get("stop"))}</td>'
            f'<td class="pos">{_num(x.get("tp1"))}</td>'
            f'<td class="mut">{fnum(x.get("risk_pct"),0):.2f}%</td>'
            f'<td>{fnum(x.get("rsi_4h"),0):.0f}</td>'
            f'<td>{fnum(x.get("vol_ratio"),0):.2f}×</td>'
            "</tr>")
    cand_tbl = ("<tr><th class='l'>#</th><th class='l'>심볼</th><th class='l'>점수</th>"
                "<th class='l'>셋업</th><th>가격</th><th>24h%</th><th>손절</th><th>TP1</th>"
                "<th>손절폭</th><th>RSI4h</th><th>거래량</th></tr>"
                + ("".join(cand_rows) if cand_rows else
                   "<tr><td class='l mut' colspan='11'>후보 데이터 없음</td></tr>"))

    # ---- 반복 종목
    persist_rows = []
    for base, cnt in rep["alert_count"].most_common(14):
        ser = rep["series"].get(base, [])
        score = ser[-1][1] if ser else None
        persist_rows.append(
            "<tr>"
            f'<td class="l"><b>{esc(base)}</b></td>'
            f'<td class="amber">{cnt}</td>'
            f'<td class="mut">{esc(rep["alert_last"].get(base) or "-")}</td>'
            f'<td>{fnum(score,0):.0f}</td>' if score is not None else
            f'<td class="l"><b>{esc(base)}</b></td><td class="amber">{cnt}</td>'
            f'<td class="mut">{esc(rep["alert_last"].get(base) or "-")}</td><td>-</td>')
        persist_rows[-1] += f'<td class="l">{_spark(ser)}</td></tr>'
    persist = ("<tr><th class='l'>심볼</th><th>알림 횟수</th><th class='l'>최근 알림</th>"
               "<th>현재 점수</th><th class='l'>점수 추이</th></tr>"
               + ("".join(persist_rows) if persist_rows else
                  "<tr><td class='l mut' colspan='5'>알림 이력 없음</td></tr>"))

    # ---- 회차 로그
    log_rows = []
    for g in sorted(runs, key=lambda r: r["run_at"], reverse=True)[:24]:
        d = str(g["run_at"])
        hhmm = d[5:16] if len(d) >= 16 else d
        okd = g.get("ok", True)
        cand_n = g.get("candidates", g["n"])
        log_rows.append(
            "<tr>"
            f'<td class="l mut">{esc(hhmm)}</td>'
            f'<td class="{"pos" if okd else "neg"}">{"OK" if okd else "FAIL"}</td>'
            f'<td class="amber">{cand_n}</td>'
            f'<td>{g.get("alerts", 0)}</td>'
            f'<td class="mut">{g.get("scanned", g["n"])}</td>'
            f'<td class="amber">{g["top"]:.0f}</td>'
            f'<td class="mut">{g["avg"]:.1f}</td>'
            f'<td class="mut">{g.get("seconds", 0):.1f}s</td>'
            "</tr>")
    log_tbl = ("<tr><th class='l'>회차</th><th>상태</th><th>후보</th><th>알림</th>"
               "<th>분석</th><th>최고점</th><th>평균점</th><th>소요</th></tr>"
               + ("".join(log_rows) if log_rows else
                  "<tr><td class='l mut' colspan='8'>실행 기록 없음</td></tr>"))

    edge_rule = esc(s.get("edge_rule") or "없음(기본 모드)")
    run_at_txt = esc(last_run)
    alert_total = len(alerts)

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALT SCAN OPS — 자동 실행 대시보드</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">

<header class="top">
  <div class="brand">
    <div class="pulse" aria-hidden="true"></div>
    <div><h1>ALT SCAN OPS<small>30-MIN AUTO SCAN · ALERT MONITOR</small></h1></div>
  </div>
  <div class="meta">
    최근 실행 <b>{run_at_txt}</b> · 다음 <b>{esc(next_txt)}</b><br>
    상태 <b>{health}</b> · 주기 <b>{interval}분</b> · 누락 <b>{missing}</b>회 / 24h<br>
    edge 필터 <b>{edge_rule}</b>
  </div>
</header>

<section class="strip">
  <div class="stat"><div class="k">RUNS (24h)</div><div class="v">{have}</div>
    <div class="s">기대 {expect}회 · 누락 {missing}회</div></div>
  <div class="stat"><div class="k">CANDIDATES</div>
    <div class="v" style="color:var(--teal)">{cand_n}</div>
    <div class="s">최근 회차 후보</div></div>
  <div class="stat"><div class="k">ALERTS (24h)</div>
    <div class="v" style="color:var(--amber)">{alerts_24}</div>
    <div class="s">전체 누적 {alert_total}건</div></div>
  <div class="stat"><div class="k">LAST RUN</div>
    <div class="v" style="color:{'var(--teal)' if ok_flag else 'var(--rose)'}">
      {'OK' if ok_flag else 'FAIL'}</div>
    <div class="s">{esc(str(s.get('seconds','-')))}s · 분석 {esc(str(s.get('scanned','-')))}종목</div></div>
</section>

<section class="sec">
  <div class="sech"><h2>RUN PULSE</h2>
    <span>최근 24시간 · 30분 슬롯 {48}칸 — 회색 실행 없음 / 청록 정상 / 노랑 알림 발생</span></div>
  <div class="pulsebar">{_pulse_slots(rep, 48, interval)}</div>
</section>

<section class="sec">
  <div class="sech"><h2>ALERT FEED</h2>
    <span>NEW = 처음 보는 종목 · REENTER = 직전 회차에 빠졌다가 재진입 (최근 40건)</span></div>
  <div class="tblwrap"><table>{feed}</table></div>
</section>

<section class="sec">
  <div class="sech"><h2>CURRENT CANDIDATES</h2>
    <span>최근 회차 상위 후보 · 손절/TP는 스캐너 산출값</span></div>
  <div class="tblwrap"><table>{cand_tbl}</table></div>
</section>

<section class="sec">
  <div class="sech"><h2>REPEAT SIGNALS</h2>
    <span>알림이 반복된 종목 = 신호 지속성 · 스파크라인은 회차별 점수 추이</span></div>
  <div class="tblwrap"><table>{persist}</table></div>
</section>

<section class="sec">
  <div class="sech"><h2>RUN LOG</h2><span>회차별 후보 수·최고점·셋업 분포 (최근 24회차)</span></div>
  <div class="tblwrap"><table>{log_tbl}</table></div>
</section>

<footer class="note"><div>
  <h3>운영 메모</h3><ul>
    <li>알림은 <b>직전 회차 대비 후보 구성 변화</b>만 잡습니다 — 같은 종목이 계속 후보면 조용합니다.</li>
    <li>알림 최소 점수는 러너의 <code>--alert-min-score</code> 로 조절합니다(기본 70).</li>
    <li>REPEAT SIGNALS 의 반복 알림은 신호 지속성이지 매수 신호가 아닙니다 — 백테스트상 <b>«추세지속» 셋업과 거래량 1.5배 미만 구간은 마이너스 기대값</b>이었습니다.</li>
    <li>이 대시보드는 러너 산출물만 읽습니다. 스캔 자체는 러너가 수행합니다.</li>
  </ul>
  <p class="warn">정보 제공용이며 투자 자문이 아닙니다. 과거 성과는 미래를 보장하지 않습니다.</p>
</div><div>
  <h3>재생성 / 서빙</h3><ul>
    <li><code>python3 alt_dashboard.py --outdir reports</code></li>
    <li><code>python3 alt_dashboard.py --serve 8080</code> (요청마다 재생성)</li>
    <li>30분 주기: <code>*/30 * * * * python3 alt_scan_runner.py --edge && python3 alt_dashboard.py</code></li>
  </ul>
  <h3>데이터 파일</h3><ul>
    <li><code>{esc(os.path.join(rep['outdir'], 'alerts.csv'))}</code></li>
    <li><code>{esc(os.path.join(rep['outdir'], 'history.csv'))}</code></li>
    <li><code>{esc(os.path.join(rep['outdir'], 'summary.json'))}</code></li>
  </ul>
</div></footer>
</div>
<script>
/* 정적 데이터에 대한 점진적 향상 — 검색/정렬만 담당 */
(function(){{
  var q = document.getElementById('f-base'); if (!q) return;
  var rows = Array.prototype.slice.call(document.querySelectorAll('#feed-tbl tr[data-base]'));
  q.addEventListener('input', function(){{
    var v = q.value.trim().toUpperCase();
    rows.forEach(function(tr){{
      tr.style.display = (!v || (tr.getAttribute('data-base')||'').indexOf(v) >= 0) ? '' : 'none';
    }});
  }});
}})();
</script>
</body></html>
"""


CSS = """
:root{--ink:#0b1220;--panel:#121e30;--panel2:#16243a;--line:#20304a;--line2:#2a3d5c;
 --txt:#e6edf7;--dim:#8ea3bf;--dim2:#63799a;--amber:#e8b45c;--azure:#5fa8f5;
 --teal:#3fc7a4;--rose:#e0655f;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1100px 620px at 10% -12%,#16263f 0,transparent 60%),
 radial-gradient(900px 520px at 96% 2%,#1a2033 0,transparent 55%),var(--ink);color:var(--txt);
 font-family:"IBM Plex Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
 font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1420px;margin:0 auto;padding:34px 22px 80px}
.top{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-end;justify-content:space-between;
 border-bottom:1px solid var(--line);padding-bottom:20px}
.brand{display:flex;align-items:center;gap:14px}
.pulse{width:42px;height:42px;border-radius:50%;border:1px solid var(--line2);position:relative;
 background:radial-gradient(circle at 50% 50%,rgba(232,180,92,.18),transparent 68%)}
.pulse::after{content:"";position:absolute;inset:11px;border-radius:50%;background:var(--amber);
 animation:beat 2.2s ease-in-out infinite}
@keyframes beat{0%,100%{opacity:.35;transform:scale(.82)}50%{opacity:1;transform:scale(1)}}
h1{margin:0;font-size:25px;font-weight:700;letter-spacing:.13em}
h1 small{display:block;font-size:11px;font-weight:500;letter-spacing:.3em;color:var(--dim2);margin-top:3px}
.meta{font-family:var(--mono);font-size:12px;color:var(--dim);text-align:right;line-height:1.85}
.meta b{color:var(--txt);font-weight:500}
.strip{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:24px 0 6px}
.stat{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
 border-radius:12px;padding:15px 17px}
.stat .k{font-size:11px;letter-spacing:.16em;color:var(--dim2)}
.stat .v{font-family:var(--mono);font-size:28px;font-weight:600;margin-top:5px}
.stat .s{font-size:12px;color:var(--dim);margin-top:2px}
.sec{margin-top:34px}
.sech{display:flex;align-items:baseline;gap:12px;border-bottom:1px solid var(--line);
 padding-bottom:9px;margin-bottom:14px}
.sech h2{margin:0;font-size:13px;letter-spacing:.22em}
.sech span{font-size:12px;color:var(--dim2)}
.pulsebar{display:flex;gap:3px;flex-wrap:wrap;background:var(--panel);border:1px solid var(--line);
 border-radius:12px;padding:12px}
.slot{width:20px;height:34px;border-radius:4px;display:block;border:1px solid rgba(255,255,255,.05)}
.slot.off{background:#1b2a3a}
.slot.ok{background:#3fc7a4}
.slot.alert{background:#e8b45c}
.slot.fail{background:#e0655f}
.tblwrap{border:1px solid var(--line);border-radius:13px;overflow:auto;background:var(--panel)}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 12px;border-bottom:1px solid rgba(32,48,74,.6);text-align:right;
 font-family:var(--mono);font-size:13px;white-space:nowrap}
th{font-size:11px;letter-spacing:.09em;color:var(--dim2);font-weight:600;background:var(--panel2);
 border-bottom:1px solid var(--line2)}
th.l,td.l{text-align:left;font-family:inherit}
tr:last-child td{border-bottom:none}
.pos{color:var(--teal)}.neg{color:var(--rose)}.mut{color:var(--dim2)}.amber{color:var(--amber)}
.rk{color:var(--dim2);font-size:12px}
.meter{display:inline-flex;gap:2px;vertical-align:middle;margin-right:8px}
.meter i{width:3px;height:13px;border-radius:1px;background:var(--line2);display:block}
.meter i.on{background:var(--amber)} .meter i.on.hi{background:var(--teal)}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11.5px;border:1px solid transparent}
.b-돌파{background:rgba(232,180,92,.14);color:var(--amber);border-color:rgba(232,180,92,.35)}
.b-눌림목{background:rgba(95,168,245,.14);color:var(--azure);border-color:rgba(95,168,245,.35)}
.b-추세지속{background:rgba(63,199,164,.13);color:var(--teal);border-color:rgba(63,199,164,.32)}
.b-관찰{background:rgba(142,163,191,.1);color:var(--dim);border-color:var(--line2)}
.kbadge{display:inline-block;padding:2px 7px;border-radius:5px;font-family:"IBM Plex Sans KR",sans-serif;
 font-size:11px;font-weight:600;letter-spacing:.04em}
.k-new{background:rgba(232,180,92,.16);color:var(--amber);border:1px solid rgba(232,180,92,.4)}
.k-re{background:rgba(95,168,245,.14);color:var(--azure);border:1px solid rgba(95,168,245,.35)}
.spark{display:block}
.note{margin-top:42px;border-top:1px solid var(--line);padding-top:20px;
 display:grid;grid-template-columns:1.35fr 1fr;gap:26px;font-size:13px;color:var(--dim)}
.note h3{font-size:11.5px;letter-spacing:.2em;color:var(--dim2);margin:0 0 9px}
.note ul{margin:0;padding-left:17px}.note li{margin-bottom:5px}
.note code{font-family:var(--mono);font-size:12px;background:var(--panel);border:1px solid var(--line);
 border-radius:5px;padding:1px 6px;color:var(--txt)}
.warn{color:var(--rose);font-size:12.5px}
@media (max-width:860px){.strip{grid-template-columns:repeat(2,1fr)}.note{grid-template-columns:1fr}}
"""


# --------------------------------------------------------------------------- #
# 생성 / 서빙
# --------------------------------------------------------------------------- #
def generate(outdir: str, out_path: str) -> str:
    rep = load_reports(outdir)
    html_txt = build_html(rep)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_txt)
    return out_path


def serve(outdir: str, out_path: str, port: int) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/dashboard", "/dashboard.html"):
                try:
                    generate(outdir, out_path)
                    with open(out_path, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:  # noqa: BLE001
                    msg = f"generate failed: {e}".encode()
                    self.send_response(500)
                    self.send_header("Content-Length", str(len(msg)))
                    self.end_headers()
                    self.wfile.write(msg)
            else:
                target = os.path.normpath(os.path.join(outdir, self.path.lstrip("/")))
                if target.startswith(os.path.abspath(outdir)) and os.path.isfile(target):
                    with open(target, "rb") as f:
                        body = f.read()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

        def log_message(self, *a):  # 조용히
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    print(f"[serve] http://0.0.0.0:{port}/  (outdir={outdir}) — 요청마다 재생성")
    print("[serve] 샌드박스/Claw 외부 노출: gsk get_service_url --port {0}".format(port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[serve] 종료")


def main() -> int:
    ap = argparse.ArgumentParser(description="알림 대시보드 생성기")
    ap.add_argument("--outdir", default="reports", help="러너 산출물 폴더")
    ap.add_argument("--out", default=None, help="대시보드 출력 경로 (기본 <outdir>/dashboard.html)")
    ap.add_argument("--serve", type=int, default=0, help="지정 포트로 HTTP 서빙")
    args = ap.parse_args()

    outdir = os.path.abspath(args.outdir)
    out_path = args.out or os.path.join(outdir, "dashboard.html")

    if not os.path.isdir(outdir):
        print(f"[fail] 산출물 폴더가 없습니다: {outdir} — 러너를 먼저 실행하세요.", file=sys.stderr)
        return 1

    rep = load_reports(outdir)
    if not rep["hist"]:
        print(f"[warn] {outdir}/history.csv 가 비어 있습니다 — 러너를 먼저 실행하세요.", file=sys.stderr)

    p = generate(outdir, out_path)
    print(f"[ok] 대시보드 생성 → {p}")
    print(f"     회차 {len(rep['runs'])} · 알림 {len(rep['alerts'])}건 · "
          f"최근 후보 {len(rep['latest_cand'])}종목")

    if args.serve:
        serve(outdir, out_path, args.serve)
    return 0


if __name__ == "__main__":
    sys.exit(main())
