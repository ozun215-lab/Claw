#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
알트 숏 스캔 러너 (30분 주기 실행 엔트리포인트)
================================================

`bybit_alt_short_scanner.py` + `short_regime_gate.py` 를 감싸는 반복 실행기.

산출물
  reports_short/scan_YYYYmmdd_HHMM.{html,csv}   회차별 리포트
  reports_short/latest.{html,csv}               항상 최신 사본
  reports_short/history.csv                     종목별 점수 시계열
  reports_short/alerts.csv                      NEW / REENTER 이벤트 로그
  reports_short/runs.csv                        회차 원장
  reports_short/summary.json                    워크플로/알림 파싱용 요약
  reports_short/state.json                      중복 알림 방지 상태

stdout ALERT 라인
  ALERT|NEW|심볼|score=..|셋업|price=..|stop=..|tp1=..|gate=ALLOW
  GATE_BLOCK                                    게이트 차단 시

사용법
  python3 alt_short_runner.py                        # 1회 실행
  python3 alt_short_runner.py --edge                 # edge 필터
  python3 alt_short_runner.py --alert-new --quiet    # 신규만 ALERT 출력
  python3 alt_short_runner.py --top 200 --min-score 60 --outdir reports_short
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
    import bybit_alt_short_scanner as S
except ImportError:
    print("bybit_alt_short_scanner.py 가 같은 폴더에 있어야 합니다.", file=sys.stderr)
    raise SystemExit(2)

KST = timezone(timedelta(hours=9))
HIST_COLS = ["run_at","symbol","score","setup","last","chg24","rsi_4h","rsi_1h",
             "vol_ratio","funding","atr_pct","dist_low20","stop","tp1","risk_pct","turnover","gate_size"]
RUN_COLS  = ["run_at","ok","scanned","candidates","alerts","errors","seconds","edge_rule","gate_action","gate_size"]


# ── 유틸 ──

def _outdir_setup(outdir):
    os.makedirs(outdir, exist_ok=True)

def _load_state(state_path):
    try:
        with open(state_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"candidates": {}}

def _save_state(state_path, state):
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def _append_csv(path, row, cols):
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow(row)

def _prune_old(outdir, keep):
    if keep <= 0:
        return
    files = sorted(glob.glob(os.path.join(outdir, "scan_*.html")))
    for f in files[:-keep]:
        try:
            os.remove(f)
            csv_f = f.replace(".html", ".csv")
            if os.path.exists(csv_f):
                os.remove(csv_f)
        except Exception:
            pass


# ── 메인 ──

def main():
    ap = argparse.ArgumentParser(description="알트 숏 스캔 러너")
    ap.add_argument("--exchange",       default="bybit", choices=["bybit","okx"])
    ap.add_argument("--top",            type=int,   default=200)
    ap.add_argument("--min-turnover",   dest="min_turnover", type=float, default=5.0)
    ap.add_argument("--min-score",      dest="min_score",    type=int,   default=55)
    ap.add_argument("--workers",        type=int,   default=8)
    ap.add_argument("--print-n",        dest="print_n",      type=int,   default=15)
    ap.add_argument("--edge",           action="store_true")
    ap.add_argument("--no-gate",        dest="no_gate",      action="store_true")
    ap.add_argument("--alert-new",      dest="alert_new",    action="store_true",  help="신규/재진입만 ALERT 출력")
    ap.add_argument("--alert-min-score",dest="alert_min_score", type=int, default=65)
    ap.add_argument("--quiet",          action="store_true", help="ALERT 외 stdout 억제")
    ap.add_argument("--outdir",         default="reports_short")
    ap.add_argument("--keep",           type=int,   default=48, help="보관할 최대 회차 수")
    args = ap.parse_args()

    t0 = time.time()
    outdir     = args.outdir
    state_path = os.path.join(outdir, "state.json")
    hist_path  = os.path.join(outdir, "history.csv")
    alert_path = os.path.join(outdir, "alerts.csv")
    runs_path  = os.path.join(outdir, "runs.csv")
    summ_path  = os.path.join(outdir, "summary.json")
    _outdir_setup(outdir)

    state = _load_state(state_path)
    prev_cands = state.get("candidates", {})

    # 스캔 실행
    results, total, ts_str, stamp, edge_rule = S.run_scan(args)

    gate_action = S.GATE_RESULT.get("action", "N/A")
    gate_size   = S.GATE_RESULT.get("size", 1.0)

    # 게이트 BLOCK이면 조기 종료
    if gate_action == "BLOCK":
        elapsed = round(time.time() - t0, 1)
        summary = {
            "ok": True, "run_at": ts_str, "scanned": total,
            "candidates": 0, "alert_count": 0,
            "gate_action": "BLOCK", "gate_size": 0.0,
            "alerts": [], "top": [], "error": None,
        }
        with open(summ_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"GATE_BLOCK")
        print(f"SUMMARY {json.dumps({'ok':True,'run_at':ts_str,'scanned':total,'candidates':0,'alert_count':0,'gate_action':'BLOCK'})}")
        return

    # 리포트 저장
    html_path   = os.path.join(outdir, f"scan_{stamp}.html")
    csv_path    = os.path.join(outdir, f"scan_{stamp}.csv")
    latest_html = os.path.join(outdir, "latest.html")
    latest_csv  = os.path.join(outdir, "latest.csv")

    S.write_html(results, html_path, ts_str, total, args.exchange, edge_rule, S.GATE_RESULT)
    S.write_html(results, latest_html, ts_str, total, args.exchange, edge_rule, S.GATE_RESULT)
    if results:
        S.write_csv(results, csv_path)
        S.write_csv(results, latest_csv)

    # history.csv 누적
    for r in results:
        _append_csv(hist_path, {"run_at": ts_str, **r}, HIST_COLS)

    # 알림 판정
    cur_syms  = {r["symbol"]: r for r in results if r["score"] >= args.alert_min_score}
    new_cands, reenter_cands = [], []

    for sym, r in cur_syms.items():
        if sym not in prev_cands:
            new_cands.append(r)
        elif sym not in state.get("last_round", {}):
            reenter_cands.append(r)

    alerts = []
    for r in new_cands + reenter_cands:
        kind = "NEW" if r in new_cands else "REENTER"
        alert = {
            "run_at": ts_str, "kind": kind, "symbol": r["symbol"],
            "score": r["score"], "setup": r["setup"], "price": r["last"],
            "stop": r["stop"], "tp1": r["tp1"], "gate": gate_action, "gate_size": gate_size,
        }
        alerts.append(alert)
        _append_csv(alert_path, alert,
                    ["run_at","kind","symbol","score","setup","price","stop","tp1","gate","gate_size"])
        line = (f"ALERT|{kind}|{r['symbol']}|score={r['score']}|{r['setup']}|"
                f"price={r['last']}|stop={r['stop']}|tp1={r['tp1']}|gate={gate_action}")
        print(line)

    # 상태 업데이트
    state["candidates"]  = {s: {"score": r["score"], "setup": r["setup"]} for s, r in cur_syms.items()}
    state["last_round"]  = {s: True for s in cur_syms}
    _save_state(state_path, state)

    # runs.csv
    elapsed = round(time.time() - t0, 1)
    _append_csv(runs_path,
                {"run_at": ts_str, "ok": True, "scanned": total,
                 "candidates": len(results), "alerts": len(alerts),
                 "errors": 0, "seconds": elapsed, "edge_rule": edge_rule,
                 "gate_action": gate_action, "gate_size": gate_size},
                RUN_COLS)

    # 오래된 파일 정리
    _prune_old(outdir, args.keep)

    # summary.json
    summary = {
        "ok": True, "run_at": ts_str, "scanned": total,
        "candidates": len(results), "alert_count": len(alerts),
        "gate_action": gate_action, "gate_size": gate_size,
        "gate_reasons": S.GATE_RESULT.get("reasons", []),
        "gate_warnings": S.GATE_RESULT.get("warnings", []),
        "alerts": [{"kind":a["kind"],"symbol":a["symbol"],"score":a["score"],"setup":a["setup"]} for a in alerts],
        "top": [{"symbol":r["symbol"],"score":r["score"],"setup":r["setup"],"price":r["last"]} for r in results[:5]],
        "error": None,
    }
    with open(summ_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    if not args.quiet:
        print(f"[숏ok] 후보 {len(results)}개 / 분석 {total}개 — {elapsed}s — 알림 {len(alerts)}개")
        print(f"       리포트 {html_path}")
        if results:
            print(f"       이력   {hist_path}")
        if alerts:
            print(f"       알림   {alert_path}")
    print(f"SUMMARY {json.dumps({'ok':True,'run_at':ts_str,'scanned':total,'candidates':len(results),'alert_count':len(alerts),'gate_action':gate_action,'gate_size':gate_size,'error':None})}")


if __name__ == "__main__":
    main()
