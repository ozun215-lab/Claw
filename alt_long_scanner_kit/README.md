# 알트 롱 스캐너 키트 — Claw 배포용

Bybit/OKX USDT 무기한 시장을 훑어 **롱 진입 후보**를 점수화하는 스캐너 + 백테스트/검증 + 30분 주기 러너 묶음입니다.
전부 표준 라이브러리 + `requests` 만 쓰는 단일 파일 스크립트이며, 서버·VM(Genspark Claw 등)에서 그대로 실행됩니다.

> ⚠️ 정보 제공용 도구입니다. 투자 자문이 아니며, 레버리지 상품은 원금 전액 손실이 가능합니다.

---

## 1. 설치 (Claw 터미널에서)

```bash
# 1) 압축 해제
unzip alt_long_scanner_kit_*.zip -d ~/alt-scanner
cd ~/alt-scanner

# 2) 의존성 (Python 3.10 이상 필요 — 타입 문법 `float | None` 사용)
python3 --version
pip3 install -r requirements.txt

# 3) 동작 확인 (실시간 스캔 1회)
python3 alt_scan_runner.py --edge --print-n 10
```

Claw에서 인터넷이 열려 있으면 Bybit API가 그대로 붙습니다. 차단 환경이면 `--exchange okx`를 쓰거나 생략(자동 폴백)하세요.

---

## 2. 파일 구성

| 파일 | 역할 |
|------|------|
| `bybit_alt_long_scanner.py` | 실시간 스캐너 — 점수화·셋업 분류·손절/TP 산출, `--html`/`--csv` 출력 |
| `alt_long_backtest.py` | 4H 과거 데이터 백테스트 — 승률·기대값(R)·PF·MDD, `--edge`/`--short` 옵션 |
| `alt_long_validate.py` | 3단 검증 — edge 필터 / 워크포워드 / 숏 대칭 (백테스터 선행 필요) |
| `alt_scan_runner.py` | **30분 주기 실행 엔트리포인트** — 타임스탬프 리포트·이력·알림 로그·회차 원장·락·정리 |
| `alt_dashboard.py` | **알림 대시보드 생성기** — 실행 펄스·알림 피드·현재 후보·반복 신호, `--serve` 로 상시 서빙 |
| `cron.example` | cron 등록 예시 |
| `bybit-alt-scan.service` / `.timer` | systemd 30분 타이머 (재부팅 후에도 유지) |
| `requirements.txt` | 의존성 (`requests`) |

---

## 3. 명령 레퍼런스

### 3-1. 주기 실행 (러너) — 주력

```bash
python3 alt_scan_runner.py                              # 1회 실행 (기본 모드)
python3 alt_scan_runner.py --edge                        # edge 프리셋: 거래량 2.0배↑ · ATR 4%↑ · '추세지속' 제외
python3 alt_scan_runner.py --alert-new --quiet           # 신규 후보만 ALERT 출력 (워크플로/알림 연동)
python3 alt_scan_runner.py --top 300 --min-score 65      # 유니버스·기준 상향
python3 alt_scan_runner.py --keep 48 --outdir reports    # 최근 48회차만 보존 (30분×48 = 24시간)
python3 alt_scan_runner.py --exchange bybit              # Bybit 직접 (한국 IP)
```

러너가 남기는 산출물:

| 경로 | 내용 |
|------|------|
| `reports/scan_YYYYmmdd_HHMM.html` / `.csv` | 회차별 리포트 (HTML은 **JS 없이도 표가 보이는 정적 데이터 내장**) |
| `reports/latest.html` / `.csv` | 항상 최신 사본 — 알림·공유용 고정 경로 |
| `reports/history.csv` | 전 회차 **종목별 점수 시계열** 누적 |
| `reports/alerts.csv` | **알림 이벤트 로그** — `NEW`(처음 보는 종목) / `REENTER`(빠졌다 재진입) |
| `reports/runs.csv` | **회차 원장** — 회차별 상태·후보 수·알림 수·소요시간 |
| `reports/summary.json` | 워크플로/알림/대시보드가 파싱하는 요약 (`ok`, `scanned`, `candidates`, `alert_count`, `alerts[]`, `top[]`) |
| `reports/state.json` | 직전 후보 목록 — 중복 알림 방지 |
| stdout `ALERT\|NEW\|심볼\|score=..\|셋업\|price=..\|stop=..\|tp1=..` | 알림 라인 (Slack·메일 연동용) |

알림은 **직전 회차 대비 후보 구성 변화**만 잡습니다 — 같은 종목이 계속 후보면 조용합니다. 최소 점수는 `--alert-min-score`(기본 70).

### 3-2. 알림 대시보드

```bash
python3 alt_dashboard.py                                  # reports/dashboard.html 생성
python3 alt_dashboard.py --outdir reports --out dash.html
python3 alt_dashboard.py --serve 8080                      # 요청마다 재생성하며 서빙
```

표시 항목: 운영 상태(최근/다음 실행·24h 누락) · **RUN PULSE**(30분 슬롯 48칸, 회색=미실행/청록=정상/노랑=알림/빨강=실패) · ALERT FEED · CURRENT CANDIDATES · REPEAT SIGNALS(반복 알림 + 점수 스파크라인) · RUN LOG.

서빙 모드에서 외부 노출이 필요하면: `gsk get_service_url --port 8080` (Claw/샌드박스 환경).

### 3-3. 백테스트 / 검증

```bash
python3 alt_long_backtest.py --html backtest.html --csv trades.csv
python3 alt_long_backtest.py --edge  --html backtest_edge.html
python3 alt_long_backtest.py --short --html backtest_short.html
python3 alt_long_backtest.py --top 80 --bars 6600 --workers 5      # 3년치

python3 alt_long_validate.py --split 2026-01-01                     # 3단 검증 (백테스터 선행 필수)
```

검증기는 `alt_long_backtest.py` 를 import 하고 `.bt_cache/` 를 재사용합니다. **같은 폴더·같은 `--bars`** 로 먼저 백테스터를 돌려 캐시를 만든 뒤 실행하세요.

---

### 3-4. 스캐너 단독

```bash
python3 bybit_alt_long_scanner.py --html scan.html --csv scan.csv
python3 bybit_alt_long_scanner.py --edge --html edge.html
python3 bybit_alt_long_scanner.py --min-vol-ratio 2 --min-atr-pct 4 --exclude-setup 추세지속
python3 bybit_alt_long_scanner.py --include-equities        # 토큰화 주식/ETF 포함
```

---

## 4. 30분 주기 등록

### 4-1. cron (간단)

```cron
*/30 * * * * cd /root/alt-scanner && mkdir -p logs reports && /usr/bin/python3 alt_scan_runner.py --edge --alert-new --alert-min-score 70 --outdir reports >> logs/scan.log 2>&1
```

### 4-2. systemd (권장 — 재부팅 후에도 유지)

```bash
sudo cp bybit-alt-scan.service bybit-alt-scan.timer /etc/systemd/system/
sudo nano /etc/systemd/system/bybit-alt-scan.service   # WorkingDirectory/ExecStart 경로 수정
sudo systemctl daemon-reload
sudo systemctl enable --now bybit-alt-scan.timer
systemctl list-timers bybit-alt-scan.timer             # 다음 실행 시각 확인
journalctl -u bybit-alt-scan.service -n 50             # 실행 로그
```

### 4-3. Claw의 스케줄 기능을 쓰는 경우

Claw 쪽 예약 실행 기능이 있으면 위 cron 한 줄을 그대로 등록하면 됩니다. 실행 후 `reports/summary.json` 의 `ok` 를 확인하고, `alert_count > 0` 이면 stdout의 `ALERT|NEW|...` 라인을 알림으로 전달하면 됩니다.

---

## 5. 점수 체계 (만점 100)

| 항목 | 배점 | 조건 |
|------|------|------|
| 4H 추세 | 16 | 종가 > EMA200, EMA20 > EMA50 > EMA200 |
| EMA50 기울기 | 8 | 10봉 대비 +2% 이상 |
| 4H 모멘텀 | 14 | RSI(14) 52~70 |
| 거래량 확장 | 14 | 최근 3봉 ÷ 직전 20봉 평균 (2.0배 이상 만점) |
| 구조 | 16 | 직전 20봉 고점 돌파 / 1% 이내 |
| 진입 품질 | 14 | EMA20 대비 ATR 이격 ≤ 1.0 (추격 금지) |
| 1H 타이밍 | 8 | RSI(14) 50~68 |
| 펀딩비 | 10 | 마이너스(숏 쏠림) 만점, 0.08% 이상 0점 |

감점·제외: 4H RSI 80↑ / 1H RSI 78↑, EMA 이격 3 ATR↑, 24h +25%↑, ATR 12%↑, 유동성 $10M 미만.
셋업: **돌파 / 눌림목 / 추세지속 / 관찰**. 손절 = max(진입 − 1.5×ATR, 최근 10봉 저점 − 0.25×ATR), TP1 = 2.0R, TP2 = 3.2R.

---

## 6. 검증 결과 요약 (2024-10 ~ 2026-09, OKX 4H, 57종목)

| 검증 | 결과 |
|------|------|
| 기본 롱 신호 | 3,000건 · 승률 34.2% · 평균 **−0.048R** · PF 0.93 (엣지 없음) |
| **edge 필터 롱** | 158건 · 승률 38.0% · 평균 **+0.075R** · PF 1.12 · MDD 13R (표본 얇음, 2026 국면 의존) |
| **숏 기본 (미러)** | 4,289건 · 승률 38.9% · 평균 **+0.089R** · PF 1.14 (표본 최다) |
| 워크포워드 | IS 최고 +0.010R → OOS +0.020R — **IS 순위가 OOS를 예측하지 못함** |

→ 실전 기본값은 `--edge`. 검증 통과 전까지는 리스크 한도(회차당 손실 한도·최대 동시 포지션)를 먼저 정하세요.

---

## 7. 트러블슈팅

| 증상 | 원인 / 해결 |
|------|-------------|
| `ModuleNotFoundError: alt_long_backtest` | 검증기를 단독 실행 — 백테스터와 **같은 폴더**에 두기 |
| `캐시 없음 — alt_long_backtest.py 를 먼저 실행하세요` | 검증기 선행 조건 — 백테스터를 같은 `--bars` 로 먼저 실행 |
| `CloudFront ... block access from your country` | Bybit 지역 차단 — `--exchange okx` 또는 자동 폴백 사용 |
| HTML이 빈 표로 보임 | 구버전 리포트 — 새 버전은 정적 데이터 내장(JS 불필요) |
| Python 문법 오류 | 3.10 미만 — 업그레이드 필요 |
| 대시보드가 빈 표 | `reports/` 에 `history.csv` 없음 — 러너를 먼저 1회 실행 |
| RUN PULSE 가 전부 회색 | 최근 24시간 내 회차 없음(스케줄 미가동) 또는 구버전 러너(=초 단위 `run_at` 없음) |
| RUN LOG 수치가 과대 | 구버전 러너 사용 — 초 단위 타임스탬프 + `runs.csv` 원장을 쓰는 최신 러너로 교체 |

---

## 8. 국면 게이트 (2026-09-28 추가)

실측 검증(67종목 · 4H · 2025-05 ~ 2026-09 · 4,056건 프록시)에서 **승률과 기대값을 동시에 올린 것은 시장 국면 필터뿐**이었습니다.
스캐너·러너 모두 **기본 ON**이며 아래 플래그로 제어합니다.

| 게이트 | 기본값 | 스캐너 플래그 | 실측 근거 |
|---|---|---|---|
| 유니버스 브레드스 (EMA50 상회 비율) | ≥ 50% 통과 · < 40% 신호 폐기 | `--breadth-block 50 --breadth-discard 40` | ≥50%: 승률 35.1% / +0.008R · <40%: 30.4% / −0.125R |
| BTC 4H > EMA200 | ON (위반 시 점수 −10, 포지션 ½) | `--no-btc-gate` 로 해제 | +0.011R (단독), 게이트 조합 +0.054R |
| ATR14(4H) 상한 | ≤ 4% | `--max-atr-pct 4.0` (0=미적용) | ≥4%: 31.1% / −0.089R · ≥6%: 27.2% / −0.199R |
| 24h 변동 상한 | ≤ 15% | `--max-chg24 15.0` (0=미적용) | >15%: 29.3% / −0.151R |
| 전체 해제 | — | `--no-gate` | 기준선 33.7% / −0.033R / PF 0.952 |

게이트를 모두 적용한 조합은 **승률 36.7% · +0.054R · PF 1.081**(표본 1,889건)로, 기준선(33.7% / −0.033R / PF 0.952)을 앞섰습니다.
2026년 구간만 보면 1,153건 · 승률 39.4% · +0.133R · PF 1.209입니다.

### 폐기된 프리셋 (다시 쓰지 마세요)

| 항목 | 이전 | 2026-09-28 실측 | 조치 |
|---|---|---|---|
| `--edge` 의 거래량 ≥ 2.0배 | 엣지 근거 | 33.7% / −0.030R (중립~역효과), 3배는 −0.067R | 하한 폐기 |
| `--edge` 의 ATR ≥ 4% | 엣지 근거 | 31.1% / −0.089R | **상한(≤4%)으로 반전** |
| 목표 축소로 승률 올리기 | — | TP 1R: 승률 48.5%지만 기대값 −0.074R | 금지 |

`--edge` 프리셋은 이제 **'추세지속' 제외 + 국면 게이트**만 의미합니다. `--min-vol-ratio` / `--min-atr-pct` 플래그는 호환용으로만 남아 있습니다.

### 추가 산출물

- `reports/market_history.csv` — 회차별 브레드스·BTC 상태·게이트 판정 원장
- `reports/summary.json` 의 `market` 객체 — 최근 회차 국면 상태
- 대시보드 상단 **MARKET REGIME GATE** 패널 — 브레드스 바 · BTC 4H vs EMA200 · 게이트 탈락 수 · 포지션 ½ 축소 종목 수
- 러너 stdout 한 줄: `MARKET|breadth=..|btc_up=..|regime=..|gate=..|rejected=..|halved=..`

### 검증·반증

게이트 적용 후 6개월 실전(또는 페이퍼) 승률이 32% 미만이거나 기대값이 마이너스면 게이트를 폐기하십시오.
브레드스 ≥50% 구간과 <40% 구간의 성적 차이가 5%p 이내로 좁혀져도 이 변수는 노이즈로 판정합니다.
