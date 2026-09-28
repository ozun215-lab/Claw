#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edge 필터 · 워크포워드 · 숏 대칭 검증 (3단 검증 드라이버)
=========================================================

`alt_long_backtest.py` 의 신호 엔진을 그대로 import 해서 세 가지를 순차 검증한다.

  Phase 1  edge 필터 검증
           기본 신호 vs edge 필터(거래량 2.0배↑ · ATR 4%↑ · '추세지속' 제외) 성과 비교

  Phase 2  워크포워드 검증
           파라미터 그리드를 IS(2024-10~2025-12)에서 평가 → 상위 설정을
           OOS(2026-01~)에서 확인. 과최적화(IS→OOS 성과 붕괴) 여부 측정.

  Phase 3  숏 대칭 검증
           가격 역수 미러로 숏 로직을 같은 코드로 검증. 롱/숏·연도별 비교.

사용법
------
  python3 alt_long_validate.py --split 2026-01-01 --html edge_validation_report.html
  python3 alt_long_validate.py --top-is 8 --no-grid      # 그리드 생략(빠른 재실행)
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import alt_long_backtest as B

KST = timezone(timedelta(hours=9))
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bt_cache")

EDGE_EXCL = {"추세지속"}


def load_cache(bars: int) -> dict[str, list[list[float]]]:
    data = {}
    for f in sorted(glob.glob(os.path.join(CACHE_DIR, f"okx_*_{bars}.json"))):
        sym = os.path.basename(f).split("_", 1)[1].rsplit("_", 1)[0].replace("_", "/")
        try:
            with open(f, encoding="utf-8") as fh:
                c = json.load(fh)
            if len(c) >= 240:
                data[sym] = c
        except Exception:  # noqa: BLE001
            continue
    return data


def run(data, min_score=60, max_hold=42, tp_r=2.0, fee_bps=8.5,
        vol_min=0.0, atr_min=0.0, excl=None, short=False) -> list[dict]:
    side = "short" if short else "long"
    out = []
    for sym, c in data.items():
        cc = B.mirror_candles(c) if short else c
        out.extend(B.backtest_symbol(sym, cc, min_score, max_hold, fee_bps, tp_r, 1.5,
                                     vol_min=vol_min, atr_min=atr_min,
                                     exclude_setups=excl, side=side))
    return out


def with_low(st: dict) -> dict:
    if st.get("n"):
        st["win_lower"] = B.wilson_lower(st["tp_exits"], st["n"])
    else:
        st["win_lower"] = 0.0
    return st


def sub(trades, pred) -> list[dict]:
    return [t for t in trades if pred(t)]


def ts_of(datestr: str) -> int:
    d = datetime.strptime(datestr, "%Y-%m-%d").replace(tzinfo=KST)
    return int(d.timestamp() * 1000)


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #
CSS = """
:root{--ink:#0b1220;--panel:#121e30;--panel2:#16243a;--line:#20304a;--line2:#2a3d5c;
 --txt:#e6edf7;--dim:#8ea3bf;--dim2:#63799a;--amber:#e8b45c;--azure:#5fa8f5;
 --teal:#3fc7a4;--rose:#e0655f;--violet:#9d8bf0;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1100px 620px at 10% -12%,#16263f 0,transparent 60%),
 radial-gradient(900px 520px at 96% 2%,#1a2033 0,transparent 55%),var(--ink);color:var(--txt);
 font-family:"IBM Plex Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
 font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1420px;margin:0 auto;padding:34px 22px 80px}
h1{margin:0;font-size:26px;font-weight:700;letter-spacing:.13em}
h1 small{display:block;font-size:11px;font-weight:500;letter-spacing:.3em;color:var(--dim2);margin-top:3px}
.top{display:flex;flex-wrap:wrap;gap:22px;align-items:flex-end;justify-content:space-between;
 border-bottom:1px solid var(--line);padding-bottom:20px}
.meta{font-family:var(--mono);font-size:12px;color:var(--dim);text-align:right;line-height:1.85}
.meta b{color:var(--txt);font-weight:500}
.phase{margin-top:40px}
.ph{display:flex;align-items:center;gap:14px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:6px}
.ph .no{font-family:var(--mono);font-size:12px;color:var(--ink);background:var(--amber);
 border-radius:6px;padding:2px 9px;font-weight:600;letter-spacing:.05em}
.ph h2{margin:0;font-size:16px;font-weight:600;letter-spacing:.04em}
.ph span{font-size:12px;color:var(--dim2);margin-left:auto;text-align:right}
.verdict{margin:16px 0 20px;border-left:3px solid var(--amber);background:rgba(22,36,58,.55);
 border-radius:0 11px 11px 0;padding:15px 18px}
.verdict.pos{border-color:var(--teal)} .verdict.neg{border-color:var(--rose)}
.verdict b{color:var(--amber)} .verdict.pos b{color:var(--teal)} .verdict.neg b{color:var(--rose)}
.strip{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:18px 0}
.stat{background:linear-gradient(180deg,var(--panel2),var(--panel));border:1px solid var(--line);
 border-radius:12px;padding:15px 17px}
.stat .k{font-size:11px;letter-spacing:.16em;color:var(--dim2)}
.stat .v{font-family:var(--mono);font-size:27px;font-weight:600;margin-top:5px}
.stat .s{font-size:12px;color:var(--dim);margin-top:2px}
.tblwrap{border:1px solid var(--line);border-radius:13px;overflow:auto;background:var(--panel);margin-bottom:6px}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 12px;border-bottom:1px solid rgba(32,48,74,.6);text-align:right;
 font-family:var(--mono);font-size:13px;white-space:nowrap}
th{font-size:11px;letter-spacing:.09em;color:var(--dim2);font-weight:600;background:var(--panel2);
 border-bottom:1px solid var(--line2)}
th.l,td.l{text-align:left;font-family:inherit}
tr:last-child td{border-bottom:none}
.pos{color:var(--teal)}.neg{color:var(--rose)}.mut{color:var(--dim2)}
.hi{background:rgba(63,199,164,.09)}
.badge{display:inline-block;padding:1px 7px;border-radius:6px;font-size:11px;
 background:rgba(232,180,92,.14);color:var(--amber);border:1px solid rgba(232,180,92,.3)}
.chartbox{border:1px solid var(--line);border-radius:13px;background:var(--panel);padding:14px;margin-bottom:6px}
.legend{font-family:var(--mono);font-size:12px;color:var(--dim2);margin-top:6px}
.note{margin-top:44px;border-top:1px solid var(--line);padding-top:20px;
 display:grid;grid-template-columns:1.35fr 1fr;gap:26px;font-size:13px;color:var(--dim)}
.note h3{font-size:11.5px;letter-spacing:.2em;color:var(--dim2);margin:0 0 9px}
.note ul{margin:0;padding-left:17px}.note li{margin-bottom:5px}
.note code{font-family:var(--mono);font-size:12px;background:var(--panel);border:1px solid var(--line);
 border-radius:5px;padding:1px 6px;color:var(--txt)}
.warn{color:var(--rose);font-size:12.5px}
@media (max-width:860px){.strip{grid-template-columns:repeat(2,1fr)}.note{grid-template-columns:1fr}}
"""

HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EDGE VALIDATION — __STAMP__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>__CSS__</style></head><body><div class="wrap">
<header class="top">
  <h1>EDGE VALIDATION<small>FILTER · WALK-FORWARD · SHORT SYMMETRY</small></h1>
  <div class="meta">검증 시각 <b>__STAMP__</b><br>
    데이터 <b>OKX USDT 무기한 · 4H</b> · <b>__PERIOD__</b><br>
    유니버스 <b>__NSYM__</b>종목 · 캐시 <b>__BARS__</b>봉/종목<br>
    IS 구간 <b>__IS__</b> / OOS 구간 <b>__OOS__</b></div>
</header>
__BODY__
<footer class="note"><div>
  <h3>해석 주의</h3><ul>
  <li>IS(과거)에서 고른 설정이 OOS(미래)에서 무너지면 그것은 과최적화다. Phase 2가 그걸 측정한다.</li>
  <li>숏 검증은 가격 역수 미러 근사 — 레버리지·청산·펀딩은 반영되지 않는다.</li>
  <li>생존편향: 현재 거래대금 상위 종목만 표본. 상장폐지 종목은 빠져 있다.</li>
  <li>동일 봉 손절 우선(보수적) 가정. 갭 하락 시 실제 손실은 1R을 넘을 수 있다.</li></ul>
  <p class="warn">정보 제공용 검증 결과이며 투자 자문이 아닙니다. 과거 성과는 미래를 보장하지 않습니다.</p>
</div><div><h3>재현</h3><ul>
  <li><code>python3 alt_long_validate.py --split __SPLIT__</code></li>
  <li><code>alt_long_backtest.py --edge --html x.html</code></li>
  <li><code>bybit_alt_long_scanner.py --edge</code> (실시간 스캔)</li>
</ul></div></footer>
</div>
<script>
const CURVES = __CURVES__;
(function(){
  const svg = document.getElementById("eq");
  if (!svg) return;
  const W = 1200, H = 320, PAD = 26;
  const all = CURVES.flatMap(c => c.pts);
  if (!all.length) return;
  const tmin = Math.min(...all.map(p=>p.t)), tmax = Math.max(...all.map(p=>p.t));
  const ys = all.map(p=>p.eq).concat([0]);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const X = t => PAD + (t-tmin)/(tmax-tmin||1)*(W-2*PAD);
  const Y = v => H-PAD - (v-ymin)/(ymax-ymin||1)*(H-2*PAD);
  let out = `<line x1="0" y1="${Y(0)}" x2="${W}" y2="${Y(0)}" stroke="#2a3d5c" stroke-dasharray="4 5"/>`;
  CURVES.forEach(c => {
    out += `<path d="${c.pts.map((p,i)=>`${i?"L":"M"}${X(p.t).toFixed(1)},${Y(p.eq).toFixed(1)}`).join(" ")}"
      fill="none" stroke="${c.color}" stroke-width="${c.w||2}" opacity="${c.o||1}"/>`;
  });
  svg.innerHTML = out;
})();
</script></body></html>
"""


def stat_strip(items: list[tuple[str, str, str, str]]) -> str:
    return '<div class="strip">' + "".join(
        f'<div class="stat"><div class="k">{k}</div><div class="v"{st}>{v}</div>'
        f'<div class="s">{s}</div></div>' for k, v, st, s in items) + "</div>"


def tbl(head: list[str], rows: list[list[str]], left_cols: int = 2, hi_rows: set | None = None) -> str:
    hi_rows = hi_rows or set()
    out = ['<div class="tblwrap"><table><tr>']
    out += [f'<th class="{"l" if i < left_cols else ""}">{h}</th>' for i, h in enumerate(head)]
    out.append("</tr>")
    for ri, r in enumerate(rows):
        cls = ' class="hi"' if ri in hi_rows else ""
        out.append(f"<tr{cls}>")
        out += [f'<td class="{"l" if i < left_cols else ""}">{c}</td>' for i, c in enumerate(r)]
        out.append("</tr>")
    out.append("</table></div>")
    return "".join(out)


def eq_pts(trades: list[dict]) -> list[dict]:
    eq, pts = 0.0, []
    for t in sorted(trades, key=lambda x: x.get("entry_ts") or 0):
        eq += t["r"]
        pts.append({"t": t.get("entry_ts") or 0, "eq": round(eq, 3)})
    return pts


def f2(v): return f"{v:+.2f}"


def pf(v): return "∞" if v == float("inf") else f"{v:.2f}"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="edge/워크포워드/숏 3단 검증")
    ap.add_argument("--bars", type=int, default=4400)
    ap.add_argument("--split", default="2026-01-01", help="IS/OOS 분리일 (기본 2026-01-01)")
    ap.add_argument("--top-is", type=int, default=8, help="IS 상위 몇 개 설정을 OOS로 넘길지")
    ap.add_argument("--no-grid", action="store_true")
    ap.add_argument("--html", default="edge_validation_report.html")
    ap.add_argument("--csv", default="edge_validation_tables.csv")
    args = ap.parse_args()

    stamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    data = load_cache(args.bars)
    if not data:
        print("캐시 없음 — alt_long_backtest.py 를 먼저 실행하세요.", file=sys.stderr)
        return 1
    split_ms = ts_of(args.split)
    print(f"  · 캐시 {len(data)}종목 · 분리일 {args.split}")

    body: list[str] = []
    csv_rows: list[dict] = []

    # ================= PHASE 1 : edge 필터 =================
    print("  [Phase 1] edge 필터 검증…", file=sys.stderr)
    base_tr = run(data, 60, 42, 2.0, 8.5)
    edge_tr = run(data, 60, 42, 2.0, 8.5, vol_min=2.0, atr_min=4.0, excl=EDGE_EXCL)
    s_base, s_edge = with_low(B.stats(base_tr)), with_low(B.stats(edge_tr))

    p1 = stat_strip([
        ("TRADES (edge)", f"{s_edge['n']}", "", f"기본 {s_base['n']}건 중 {s_edge['n']/max(s_base['n'],1)*100:.0f}%"),
        ("WIN RATE", f"{s_edge['win_rate']:.1f}%", ' style="color:var(--teal)"' if s_edge['win_rate'] > 33.3 else ' style="color:var(--rose)"',
         f"하한 {s_edge['win_lower']:.1f}% · 손익분기 33.3%"),
        ("EXPECTANCY", f"{s_edge['avg_r']:+.3f}R", ' style="color:var(--teal)"' if s_edge['avg_r'] > 0 else ' style="color:var(--rose)"',
         f"기본 모드 {s_base['avg_r']:+.3f}R"),
        ("PROFIT FACTOR", pf(s_edge['profit_factor']), "", f"기본 모드 {pf(s_base['profit_factor'])}"),
    ])
    verd = ("pos" if s_edge["avg_r"] > 0 else "neg")
    body.append(f"""
<section class="phase">
  <div class="ph"><span class="no">PHASE 1</span>
    <h2>edge 필터 — 거래량 2.0배 이상 · ATR 4% 이상 · '추세지속' 제외</h2>
    <span>전체 기간 · 기본 신호와 동일한 청산 규칙</span></div>
  <div class="verdict {verd}">기본 신호는 <b>{s_base['avg_r']:+.3f}R</b>/건으로 손실이었다.
    edge 필터 적용 시 <b>{s_edge['avg_r']:+.3f}R</b>/건 (승률 {s_edge['win_rate']:.1f}%, PF {pf(s_edge['profit_factor'])},
    기대값 합 {s_edge['expectancy_sum_r']:+.1f}R, 최대 MDD {s_edge['max_dd_r']:.1f}R, 최대 연속손실 {s_edge['max_consec_loss']}).
    표본이 {s_base['n']} → {s_edge['n']}건으로 줄어드는 대신, 손실 구간(«추세지속»·저변동)을 걷어낸 결과다.</div>
  {p1}
  {tbl(["구분", "설정", "표본", "승률", "승률 하한", "평균 R", "기대값 합", "PF", "최대 MDD", "최대 연속손실", "평균 보유봉"],
       [["기본 신호", "전체 통과", s_base["n"], f"{s_base['win_rate']:.1f}%", f"{s_base['win_lower']:.1f}%",
         f2(s_base["avg_r"]), f2(s_base["expectancy_sum_r"]), pf(s_base["profit_factor"]),
         f"{s_base['max_dd_r']:.1f}", s_base["max_consec_loss"], s_base["avg_bars"]],
        ["<b>edge 필터</b>", "거래량 2.0배·ATR 4%·추세지속 제외", s_edge["n"], f"{s_edge['win_rate']:.1f}%",
         f"{s_edge['win_lower']:.1f}%", f2(s_edge["avg_r"]), f2(s_edge["expectancy_sum_r"]),
         pf(s_edge["profit_factor"]), f"{s_edge['max_dd_r']:.1f}", s_edge["max_consec_loss"], s_edge["avg_bars"]]],
       hi_rows={1})}
  <div class="chartbox"><svg id="eq" viewBox="0 0 1200 320" width="100%" height="320" preserveAspectRatio="none"></svg>
  <div class="legend">— 기본 신호 누적 R &nbsp;·&nbsp; — edge 필터 누적 R &nbsp;·&nbsp; 점선 = 손익분기</div></div>
</section>""")
    csv_rows += [{"phase": "1-edge", "config": "기본 신호", **{k: s_base.get(k) for k in
                  ("n", "win_rate", "win_lower", "avg_r", "expectancy_sum_r", "profit_factor", "max_dd_r")}},
                 {"phase": "1-edge", "config": "edge 필터", **{k: s_edge.get(k) for k in
                  ("n", "win_rate", "win_lower", "avg_r", "expectancy_sum_r", "profit_factor", "max_dd_r")}}]

    # ================= PHASE 2 : 워크포워드 =================
    print("  [Phase 2] 워크포워드 검증…", file=sys.stderr)
    combos = []
    if args.no_grid:
        combos = [dict(min_score=60, vol_min=2.0, atr_min=4.0, excl=EDGE_EXCL, tp_r=2.0, max_hold=42)]
    else:
        for ms in (60, 70):
            for vm in (0.0, 2.0):
                for am in (0.0, 4.0):
                    for ex in (False, True):
                        for tp in (1.5, 2.0, 2.5):
                            for mh in (18, 42):
                                combos.append(dict(min_score=ms, vol_min=vm, atr_min=am,
                                                   excl=EDGE_EXCL if ex else None, tp_r=tp, max_hold=mh))

    grid = []
    for i, cfg in enumerate(combos, 1):
        tr = run(data, cfg["min_score"], cfg["max_hold"], cfg["tp_r"], 8.5,
                 vol_min=cfg["vol_min"], atr_min=cfg["atr_min"], excl=cfg["excl"])
        is_tr = sub(tr, lambda t: (t.get("entry_ts") or 0) < split_ms)
        oos_tr = sub(tr, lambda t: (t.get("entry_ts") or 0) >= split_ms)
        si, so = with_low(B.stats(is_tr)), with_low(B.stats(oos_tr))
        grid.append({"cfg": cfg, "is": si, "oos": so, "n_all": len(tr), "trades": tr})
        if i % 20 == 0:
            print(f"    · {i}/{len(combos)} 설정 평가…", file=sys.stderr)

    valid = [g for g in grid if g["is"].get("n", 0) >= 100 and g["oos"].get("n", 0) >= 30]
    ranked = sorted(valid, key=lambda g: -g["is"]["avg_r"])
    top = ranked[:args.top_is]
    med = ranked[len(ranked) // 2] if ranked else None

    def label(g):
        c = g["cfg"]
        return (f"점수≥{c['min_score']} · vol≥{c['vol_min']:.1f} · ATR≥{c['atr_min']:.0f}% · "
                f"{'추세지속 제외' if c['excl'] else '전체셋업'} · TP{c['tp_r']:.1f}R · {c['max_hold']}봉")

    if ranked:
        is_avg = [g["is"]["avg_r"] for g in ranked]
        oos_avg = [g["oos"]["avg_r"] for g in ranked]
        pos_is = [g for g in ranked if g["is"]["avg_r"] > 0]
        pos_both = [g for g in pos_is if g["oos"]["avg_r"] > 0]
        top_is = top[0]["is"]["avg_r"]
        top_oos = top[0]["oos"]["avg_r"]
        degrade = top_oos / top_is if top_is else 0
        best_oos = max(g["oos"]["avg_r"] for g in ranked)

        body.append(f"""
<section class="phase">
  <div class="ph"><span class="no">PHASE 2</span>
    <h2>워크포워드 — IS({args.split} 이전)에서 고르고 OOS(이후)에서 검증</h2>
    <span>설정 {len(combos)}개 × 유니버스 {len(data)}종목 · 유효 표본(IS≥100·OOS≥30) {len(ranked)}개</span></div>
  <div class="verdict {'pos' if degrade > 0.6 else 'neg'}">
    IS 상위 설정 <b>{top_is:+.3f}R</b> → OOS <b>{top_oos:+.3f}R</b> (성과 보존율 {degrade*100:.0f}%).
    설정 간 IS 평균 {sum(is_avg)/len(is_avg):+.3f}R vs OOS 평균 {sum(oos_avg)/len(oos_avg):+.3f}R.
    IS에서 플러스였던 {len(pos_is)}개 중 OOS에서도 플러스인 설정 {len(pos_both)}개({len(pos_both)/max(len(pos_is),1)*100:.0f}%).
    전체 중 그 시점 최고 OOS는 {best_oos:+.3f}R — 즉 <b>IS 성과로 미래를 고르는 능력</b>이 핵심이다.</div>
  {tbl(["순위", "설정 (IS 기준 정렬)", "IS 표본", "IS 평균 R", "IS PF", "OOS 표본", "OOS 평균 R", "OOS PF", "OOS 승률", "성과 보존율"],
       [[i + 1, label(g), g["is"]["n"], f2(g["is"]["avg_r"]), pf(g["is"]["profit_factor"]),
         g["oos"]["n"], f2(g["oos"]["avg_r"]), pf(g["oos"]["profit_factor"]),
         f"{g['oos']['win_rate']:.1f}%",
         f"{g['oos']['avg_r']/g['is']['avg_r']*100:.0f}%" if g["is"]["avg_r"] else "-"]
        for i, g in enumerate(top)], hi_rows={0})}
  <div class="verdict">
    <b>중앙값 대조군</b> — IS 중위 설정({label(med)})의 IS {med['is']['avg_r']:+.3f}R → OOS {med['oos']['avg_r']:+.3f}R.
    상위 설정과 중위 설정의 OOS 차이가 작다면, IS 순위 자체가 미래를 예측하지 못한다는 뜻이다.</div>
</section>""")
        csv_rows += [{"phase": "2-walkforward", "config": label(g), "n_is": g["is"]["n"],
                      "is_avg_r": g["is"]["avg_r"], "is_pf": g["is"]["profit_factor"],
                      "n_oos": g["oos"]["n"], "oos_avg_r": g["oos"]["avg_r"],
                      "oos_pf": g["oos"]["profit_factor"], "oos_win": g["oos"]["win_rate"]}
                     for g in ranked]

    # ================= PHASE 3 : 숏 대칭 =================
    print("  [Phase 3] 숏 대칭 검증…", file=sys.stderr)
    sh_base = run(data, 60, 42, 2.0, 8.5, short=True)
    sh_edge = run(data, 60, 42, 2.0, 8.5, vol_min=2.0, atr_min=4.0, excl=EDGE_EXCL, short=True)
    s_sb, s_se = with_low(B.stats(sh_base)), with_low(B.stats(sh_edge))

    def by_year(tr):
        return B.group_stats(tr, lambda t: t["year"])

    yl_e, ys_e = by_year(edge_tr), by_year(sh_edge)
    years = sorted(set(yl_e) | set(ys_e))
    rows = []
    for y in years:
        a, b = yl_e.get(y, {"n": 0}), ys_e.get(y, {"n": 0})
        rows.append([y, f"{a.get('n',0)}", f"{a.get('avg_r',0):+.3f}" if a.get("n") else "-",
                     f"{a.get('win_rate',0):.1f}%" if a.get("n") else "-",
                     f"{b.get('n',0)}", f"{b.get('avg_r',0):+.3f}" if b.get("n") else "-",
                     f"{b.get('win_rate',0):.1f}%" if b.get("n") else "-"])

    body.append(f"""
<section class="phase">
  <div class="ph"><span class="no">PHASE 3</span>
    <h2>숏 대칭 검증 — 같은 로직을 가격 역수 미러로</h2>
    <span>롱/숏 동일 규칙 · 롱 표본 {s_edge['n']}건 / 숏 표본 {s_se['n']}건</span></div>
  <div class="verdict {'pos' if s_se['avg_r'] > 0 else 'neg'}">
    숏 기본 모드 <b>{s_sb['avg_r']:+.3f}R</b> · 숏 edge 필터 <b>{s_se['avg_r']:+.3f}R</b>
    (승률 {s_se['win_rate']:.1f}%, PF {pf(s_se['profit_factor'])}, 기대값 합 {s_se['expectancy_sum_r']:+.1f}R).
    롱 edge {s_edge['avg_r']:+.3f}R 와 비교하면 <b>{'숏이 우세' if s_se['avg_r'] > s_edge['avg_r'] else '롱이 우세'}</b>.
    연도별로 보면 하락 국면에서 어느 방향이 살아 있었는지 드러난다.</div>
  {tbl(["구분", "모드", "표본", "승률", "승률 하한", "평균 R", "기대값 합", "PF", "최대 MDD"],
       [["롱", "기본", s_base["n"], f"{s_base['win_rate']:.1f}%", f"{s_base['win_lower']:.1f}%",
         f2(s_base["avg_r"]), f2(s_base["expectancy_sum_r"]), pf(s_base["profit_factor"]), f"{s_base['max_dd_r']:.1f}"],
        ["롱", "edge", s_edge["n"], f"{s_edge['win_rate']:.1f}%", f"{s_edge['win_lower']:.1f}%",
         f2(s_edge["avg_r"]), f2(s_edge["expectancy_sum_r"]), pf(s_edge["profit_factor"]), f"{s_edge['max_dd_r']:.1f}"],
        ["숏", "기본", s_sb["n"], f"{s_sb['win_rate']:.1f}%", f"{s_sb['win_lower']:.1f}%",
         f2(s_sb["avg_r"]), f2(s_sb["expectancy_sum_r"]), pf(s_sb["profit_factor"]), f"{s_sb['max_dd_r']:.1f}"],
        ["숏", "edge", s_se["n"], f"{s_se['win_rate']:.1f}%", f"{s_se['win_lower']:.1f}%",
         f2(s_se["avg_r"]), f2(s_se["expectancy_sum_r"]), pf(s_se["profit_factor"]), f"{s_se['max_dd_r']:.1f}"]],
       hi_rows={3})}
  {tbl(["연도", "롱 표본", "롱 평균 R", "롱 승률", "숏 표본", "숏 평균 R", "숏 승률"], rows)}
  <div class="chartbox"><svg id="eq2" viewBox="0 0 1200 320" width="100%" height="320" preserveAspectRatio="none"></svg>
  <div class="legend">— 롱 edge 누적 R &nbsp;·&nbsp; — 숏 edge 누적 R &nbsp;·&nbsp; 점선 = 손익분기</div></div>
  <script>(function(){{const C=[{{pts:{json.dumps(eq_pts(edge_tr))},color:"#5fa8f5"}},{{pts:{json.dumps(eq_pts(sh_edge))},color:"#e0655f"}}];
    const svg=document.getElementById("eq2");const W=1200,H=320,PAD=26;
    const all=C.flatMap(c=>c.pts);if(!all.length)return;
    const tmin=Math.min(...all.map(p=>p.t)),tmax=Math.max(...all.map(p=>p.t));
    const ys=all.map(p=>p.eq).concat([0]);const ymin=Math.min(...ys),ymax=Math.max(...ys);
    const X=t=>PAD+(t-tmin)/(tmax-tmin||1)*(W-2*PAD);const Y=v=>H-PAD-(v-ymin)/(ymax-ymin||1)*(H-2*PAD);
    let out=`<line x1="0" y1="${{Y(0)}}" x2="${{W}}" y2="${{Y(0)}}" stroke="#2a3d5c" stroke-dasharray="4 5"/>`;
    C.forEach(c=>{{out+=`<path d="${{c.pts.map((p,i)=>`${{i?"L":"M"}}${{X(p.t).toFixed(1)}},${{Y(p.eq).toFixed(1)}}`).join(" ")}}" fill="none" stroke="${{c.color}}" stroke-width="2.1"/>`;}});
    svg.innerHTML=out;}})();</script>
</section>""")
    csv_rows += [{"phase": "3-short", "config": k, **v} for k, v in
                 [("롱 기본", {x: s_base.get(x) for x in ("n", "win_rate", "avg_r", "profit_factor", "max_dd_r")}),
                  ("롱 edge", {x: s_edge.get(x) for x in ("n", "win_rate", "avg_r", "profit_factor", "max_dd_r")}),
                  ("숏 기본", {x: s_sb.get(x) for x in ("n", "win_rate", "avg_r", "profit_factor", "max_dd_r")}),
                  ("숏 edge", {x: s_se.get(x) for x in ("n", "win_rate", "avg_r", "profit_factor", "max_dd_r")})]]

    # ================= 조립 =================
    ts_all = [x[0] for c in data.values() for x in c]
    period = (f"{datetime.fromtimestamp(min(ts_all)/1000, KST):%Y-%m-%d} ~ "
              f"{datetime.fromtimestamp(max(ts_all)/1000, KST):%Y-%m-%d}")
    curves = [{"pts": eq_pts(base_tr), "color": "#e0655f", "w": 1.6, "o": 0.8},
              {"pts": eq_pts(edge_tr), "color": "#3fc7a4", "w": 2.4, "o": 1}]
    html = (HTML.replace("__CSS__", CSS).replace("__STAMP__", stamp)
            .replace("__PERIOD__", period).replace("__NSYM__", str(len(data)))
            .replace("__BARS__", str(args.bars)).replace("__IS__", f"~ {args.split} 이전")
            .replace("__OOS__", f"{args.split} ~")
            .replace("__SPLIT__", args.split)
            .replace("__BODY__", "".join(body))
            .replace("__CURVES__", json.dumps(curves)))
    with open(args.html, "w", encoding="utf-8") as f:
        f.write(html)

    keys = ["phase", "config", "n", "win_rate", "win_lower", "avg_r", "expectancy_sum_r",
            "profit_factor", "max_dd_r", "n_is", "is_avg_r", "is_pf", "n_oos", "oos_avg_r", "oos_pf", "oos_win"]
    with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in csv_rows:
            w.writerow(r)

    print("\n" + "=" * 78)
    print(f"  [Phase 1] 기본 {s_base['avg_r']:+.3f}R → edge {s_edge['avg_r']:+.3f}R "
          f"(승률 {s_edge['win_rate']:.1f}%, PF {pf(s_edge['profit_factor'])}, n={s_edge['n']})")
    if ranked:
        print(f"  [Phase 2] IS 상위 {top_is:+.3f}R → OOS {top_oos:+.3f}R (보존 {degrade*100:.0f}%) · "
              f"IS+ {len(pos_is)}개 중 OOS+ {len(pos_both)}개")
    print(f"  [Phase 3] 롱 edge {s_edge['avg_r']:+.3f}R vs 숏 edge {s_se['avg_r']:+.3f}R "
          f"(숏 승률 {s_se['win_rate']:.1f}%, PF {pf(s_se['profit_factor'])})")
    print(f"\n  HTML → {args.html}\n  CSV  → {args.csv}")
    print("  ※ 정보 제공용이며 투자 자문이 아닙니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
