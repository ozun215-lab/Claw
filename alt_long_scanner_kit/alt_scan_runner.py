#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
알트 롱 스캔 러너 (30분 주기 실행용 엔트리포인트)
=================================================

`bybit_alt_long_scanner.py` 를 감싸서 반복 실행에 필요한 것을 붙인다.

  · 실행마다 타임스탬프 리포트: reports/scan_YYYYmmdd_HHMM.{html,csv}
  · 안정 경로 사본        : reports/latest.{html,csv}   (항상 최신)
  · 누적 이력             : reports/history.csv          (전 회차 종목별 점수 시계열)
  · **알림 이력**         : reports/alerts.csv           (NEW / REENTER 이벤트 로그)
  · 요약 JSON             : reports/summary.json         (워크플로/알림/대시보드가 파싱)
  · 상태                  : reports/state.json           (중복 알림 방지)
  · 보존 정책             : --keep 로 최근 N회차만 남기고 자동 정리
  · 락 파일               : 동시 실행 방지

알림 종류
---------
  NEW     : 이 러너가 처음 보는 종목이 후보에 진입
  REENTER : 이전에 후보였고, 직전 회차에는 빠졌다가 다시 진입

사용법
------
  python3 alt_scan_runner.py                       # 1회 실행
  python3 alt_scan_runner.py --edge                # edge 필터 모드
  python3 alt_scan_runner.py --alert-new --quiet    # 신규/재진입만 ALERT 라인 출력
  python3 alt_scan_runner.py --top 250 --min-score 65 --outdir reports

30분 주기 등록
--------------
  cron  : */30 * * * * cd /path/to/scanner && /usr/bin/python3 alt_scan_runner.py --edge --alert-min-score 70 >> logs/scan.log 2>&1
  systemd: bybit-alt-scan.timer (OnUnitActiveSec=30min)

주의: 정보 제공용이며 투자 자문이 아니다.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import bybit_alt_long_scanner as S
except ImportError:
    print("bybit_alt_long_scanner.py 가 같은 폴더에 있어야 합니다.", file=sys.stderr)
    raise SystemExit(2)

KST = timezone(timedelta(hours=9))
HIST_COLS = ["run_at", "symbol", "base", "score", "setup", "last", "chg24", "rsi_4h",
             "rsi_1h", "vol_ratio", "funding", "atr_pct", "risk_pct", "dist_high20",
             "stop", "tp1", "turnover"]
RUN_COLS = ["run_at", "ok", "scanned", "candidates", "alerts", "errors", "seconds", "edge_rule"]
MKT_COLS = ["run_at", "breadth_pct", "n_above", "n_uni", "btc_up", "btc_close", "btc_ema200",
            "regime", "gate", "rejected", "halved", "gate_rule"]
ALERT_COLS = ["run_at", "kind", "base", "score", "setup", "last", "stop", "tp1", "tp2",
              "risk_pct", "rsi_4h", "rsi_1h", "vol_ratio", "funding", "atr_pct",
              "dist_high20", "turnover"]


def read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return default


def write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def append_csv(path: str, cols: list[str], rows: list[list]) -> None:
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(cols)
        for r in rows:
            w.writerow(r)


def prune(outdir: str, keep: int) -> int:
    """오래된 회차 리포트 정리 (latest.* · history.csv · alerts.csv 는 보존)."""
    files = sorted(glob.glob(os.path.join(outdir, "scan_*.*")))  
    if len(files) <= keep * 2:
        return 0
    removed = 0
    for p in files[: len(files) - keep * 2]:
        try:
            os.remove(p)
            removed += 1
        except OSError:
            pass
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description="알트 롱 스캔 러너 (주기 실행용)")
    ap.add_argument("--exchange", default="auto", choices=["auto", "bybit", "okx"])
    ap.add_argument("--top", type=int, default=220)
    ap.add_argument("--min-turnover", type=float, default=5_000_000)
    ap.add_argument("--min-score", type=float, default=60)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--edge", action="store_true", help="edge 프리셋 적용")
    ap.add_argument("--no-gate", action="store_true", help="국면 게이트 해제")
    ap.add_argument("--breadth-block", type=float, default=50.0)
    ap.add_argument("--breadth-discard", type=float, default=40.0)
    ap.add_argument("--max-atr-pct", type=float, default=4.0)
    ap.add_argument("--max-chg24", type=float, default=15.0)
    ap.add_argument("--no-btc-gate", action="store_true")
    ap.add_argument("--min-vol-ratio", type=float, default=0.0)
    ap.add_argument("--min-atr-pct", type=float, default=0.0)
    ap.add_argument("--exclude-setup", default="")
    ap.add_argument("--outdir", default="reports")
    ap.add_argument("--keep", type=int, default=48, help="보존 회차 수 (30분×48 = 24시간)")
    ap.add_argument("--alert-min-score", type=float, default=70, help="알림 최소 점수")
    ap.add_argument("--no-alerts", action="store_true", help="알림 기록/출력 비활성")
    ap.add_argument("--state", default=None, help="상태 파일 (기본 <outdir>/state.json)")
    ap.add_argument("--print-n", type=int, default=12, help="콘솔 출력 행 수")
    ap.add_argument("--quiet", action="store_true", help="진행 로그 최소화")
    args = ap.parse_args()

    if args.min_vol_ratio:
        S.EDGE["min_vol_ratio"] = args.min_vol_ratio
    if args.min_atr_pct:
        S.EDGE["min_atr_pct"] = args.min_atr_pct
    if args.exclude_setup:
        S.EDGE["exclude_setup"] = {x.strip() for x in args.exclude_setup.split(",") if x.strip()}
    if args.edge:
        S.EDGE["exclude_setup"] = S.EDGE["exclude_setup"] or {"추세지속"}
    S.GATE["enabled"] = not args.no_gate
    S.GATE["breadth_block"] = args.breadth_block
    S.GATE["breadth_discard"] = args.breadth_discard
    S.GATE["max_atr_pct"] = args.max_atr_pct
    S.GATE["max_chg24"] = args.max_chg24
    S.GATE["btc_gate"] = not args.no_btc_gate

    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)
    state_path = args.state or os.path.join(outdir, "state.json")

    lock_path = os.path.join(outdir, ".lock")
    if os.path.exists(lock_path):
        age = time.time() - os.path.getmtime(lock_path)
        if age < 1800:
            print(f"[skip] 이전 회차가 진행 중입니다 (락 {age:.0f}s). 종료.")
            return 0
        os.remove(lock_path)
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    started = time.time()
    now = datetime.now(KST)
    stamp = now.strftime("%Y%m%d_%H%M")
    rc = 0
    summary: dict = {"run_at": now.strftime("%Y-%m-%d %H:%M:%S KST"), "stamp": stamp,
                     "ok": False, "edge_rule": S.edge_rule_text(),
                     "gate_rule": S.gate_rule_text()}
    try:
        if not args.quiet:
            print(f"[run] {summary['run_at']} · edge 필터: {summary['edge_rule']}")
        ex = S.build_exchange(args.exchange)
        rows, stats = S.scan(ex, args.top, args.min_turnover, args.workers, True)
        if not rows:
            raise RuntimeError("스캔 결과 0건 (네트워크 또는 필터 확인)")
        cand = [x for x in rows if S.passes(x, args.min_score)]

        html_path = os.path.join(outdir, f"scan_{stamp}.html")
        csv_path = os.path.join(outdir, f"scan_{stamp}.csv")
        S.write_html(html_path, rows, stats, args.min_score, args.top, S.edge_rule_text())
        S.write_csv(csv_path, rows)

        latest_html = os.path.join(outdir, "latest.html")
        latest_csv = os.path.join(outdir, "latest.csv")
        for src, dst in ((html_path, latest_html), (csv_path, latest_csv)):
            with open(src, "r", encoding="utf-8") as fi, open(dst, "w", encoding="utf-8") as fo:
                fo.write(fi.read())

        run_at = now.strftime("%Y-%m-%d %H:%M:%S")
        mkt = stats.get("market") or {}
        if mkt:
            append_csv(os.path.join(outdir, "market_history.csv"), MKT_COLS, [[
                run_at, mkt.get("breadth"), mkt.get("n_above"), mkt.get("n_uni"),
                mkt.get("btc_up"), mkt.get("btc_close"), mkt.get("btc_ema200"),
                mkt.get("regime"), mkt.get("gate"), mkt.get("rejected"), mkt.get("halved"),
                S.gate_rule_text()]])
        append_csv(os.path.join(outdir, "history.csv"), HIST_COLS,
                   [[run_at] + [x.get(c) for c in HIST_COLS[1:]] for x in rows])

        # ---- 알림 판정: NEW(처음 보는 종목) / REENTER(직전 회차에 없다가 재진입) ----
        state = read_json(state_path, {})
        prev_seen = set(state.get("seen") or [])
        prev_last = set(state.get("last") or [])
        cur = {x["base"] for x in cand}
        kind_new = cur - prev_seen
        kind_re = (cur - prev_last) - kind_new
        alerts: list[dict] = []
        if not args.no_alerts:
            for x in sorted(cand, key=lambda v: -v["score"]):
                if x["base"] in kind_new:
                    k = "NEW"
                elif x["base"] in kind_re:
                    k = "REENTER"
                else:
                    continue
                if x["score"] < args.alert_min_score:
                    continue
                alerts.append({"kind": k, "base": x["base"], "score": x["score"],
                               "setup": x["setup"], "last": x["last"], "stop": x["stop"],
                               "tp1": x["tp1"], "tp2": x["tp2"], "risk_pct": x["risk_pct"],
                               "rsi_4h": x["rsi_4h"], "rsi_1h": x.get("rsi_1h"),
                               "vol_ratio": x.get("vol_ratio"), "funding": x.get("funding"),
                               "atr_pct": x["atr_pct"], "dist_high20": x["dist_high20"],
                               "turnover": x["turnover"]})
            if alerts:
                append_csv(os.path.join(outdir, "alerts.csv"), ALERT_COLS,
                           [[run_at, a["kind"], a["base"], a["score"], a["setup"], a["last"],
                             a["stop"], a["tp1"], a["tp2"], a["risk_pct"], a["rsi_4h"],
                             a["rsi_1h"], a["vol_ratio"], a["funding"], a["atr_pct"],
                             a["dist_high20"], a["turnover"]] for a in alerts])

        top = cand[:args.print_n]
        summary.update({
            "ok": True, "exchange": stats["exchange"], "scanned": stats["scanned"],
            "candidates": len(cand), "errors": stats["errors"],
            "market": stats.get("market") or {},
            "seconds": round(time.time() - started, 1),
            "new_candidates": sorted(kind_new), "reentered": sorted(kind_re),
            "alert_count": len(alerts),
            "alert_min_score": args.alert_min_score,
            "alerts": alerts,
            "interval_min": 30,
            "report_html": html_path, "report_csv": csv_path,
            "latest_html": latest_html, "latest_csv": latest_csv,
            "history_csv": os.path.join(outdir, "history.csv"),
            "alerts_csv": os.path.join(outdir, "alerts.csv"),
            "top": [{"base": x["base"], "score": x["score"], "setup": x["setup"],
                     "last": x["last"], "chg24": x["chg24"], "stop": x["stop"],
                     "tp1": x["tp1"], "risk_pct": x["risk_pct"],
                     "rsi_4h": x["rsi_4h"], "vol_ratio": x.get("vol_ratio")} for x in top],
        })
        append_csv(os.path.join(outdir, "runs.csv"), RUN_COLS, [[
            run_at, "ok", stats["scanned"], len(cand), len(alerts), stats["errors"],
            summary["seconds"], S.edge_rule_text()]])
        write_json(os.path.join(outdir, "summary.json"), summary)
        write_json(state_path, {"seen": sorted(prev_seen | cur), "last": sorted(cur),
                                "last_run": summary["run_at"],
                                "last_top": [x["base"] for x in top]})

        removed = prune(outdir, args.keep)
        if not args.quiet:
            S.print_table(cand if cand else rows, args.print_n)
            print(f"[ok] 후보 {len(cand)}종목 / 분석 {stats['scanned']}종목 · "
                  f"{summary['seconds']}s · 알림 {len(alerts)}건"
                  + (f" · 정리 {removed}개" if removed else ""))
            print(f"     리포트 {html_path}")
            print(f"     이력   {summary['history_csv']}")
            print(f"     알림   {summary['alerts_csv']}")
            mk = summary.get("market") or {}
            if mk:
                bs = f"{mk['breadth']:.1f}%" if isinstance(mk.get("breadth"), (int, float)) else "—"
                print(f"     국면   브레드스 {bs} · BTC 4H "
                      f"{'상단' if mk.get('btc_up') is True else '하단' if mk.get('btc_up') is False else '미판정'}"
                      f" · {mk.get('gate', '—')} · 탈락 {mk.get('rejected', 0)}종목")
                print(f"MARKET|breadth={mk.get('breadth')}|btc_up={mk.get('btc_up')}|"
                      f"regime={mk.get('regime')}|gate={mk.get('gate')}|rejected={mk.get('rejected')}|"
                      f"halved={mk.get('halved')}")

        for a in alerts:
            print(f"ALERT|{a['kind']}|{a['base']}|score={a['score']:.0f}|{a['setup']}|"
                  f"price={a['last']}|stop={a['stop']}|tp1={a['tp1']}|"
                  f"rsi4h={a['rsi_4h']}|vol={(a['vol_ratio'] or 0):.2f}")
        rc = 0
    except Exception as e:  # noqa: BLE001
        summary.update({"ok": False, "error": f"{type(e).__name__}: {e}"})
        try:
            append_csv(os.path.join(outdir, "runs.csv"), RUN_COLS, [[
                now.strftime("%Y-%m-%d %H:%M:%S"), "fail", 0, 0, 0, 0, 0, S.edge_rule_text()]])
        except Exception:  # noqa: BLE001
            pass
        write_json(os.path.join(outdir, "summary.json"), summary)
        print(f"[fail] {summary['error']}", file=sys.stderr)
        rc = 1
    finally:
        try:
            os.remove(lock_path)
        except OSError:
            pass

    print(f"SUMMARY {json.dumps({k: summary.get(k) for k in ('ok', 'run_at', 'scanned', 'candidates', 'alert_count', 'market', 'error')}, ensure_ascii=False)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
