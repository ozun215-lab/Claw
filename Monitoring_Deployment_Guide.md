# GPMS Galera 모니터링 스크립트 배포 가이드

**작성일:** 2026-09-02  
**상태:** 준비 완료

---

## 제공되는 스크립트

### 1. `galera-health-check.sh` — 자동 헬스 체크
- **용도**: 주기적 모니터링 및 자동 알람
- **실행**: cron으로 자동 실행
- **기능**:
  - 클러스터 크기, 상태, 노드 상태 모니터링
  - Flow Control 및 성능 메트릭 수집
  - 임계값 초과 시 자동 알람 (이메일/Slack)
  - 상세 로그 기록

### 2. `setup-galera-cron.sh` — 자동 설치
- **용도**: cron 일괄 설정
- **기능**:
  - 헬스 체크 스크립트 설치
  - crontab 자동 등록
  - 로그 디렉토리 생성

### 3. `galera-dashboard.sh` — 실시간 대시보드
- **용도**: 실시간 모니터링 (터미널 기반)
- **기능**:
  - 5초마다 실시간 업데이트
  - 색상별 상태 표시
  - 성능 게이지 시각화

---

## 설치 절차

### Step 1: 스크립트 복사 (모든 노드에서)

```bash
# Node1 (gpms-db01)에서
scp galera-health-check.sh root@gpms-db01:/usr/local/bin/
scp galera-dashboard.sh root@gpms-db01:/usr/local/bin/

# Node2 (gpms-db02)에서
scp galera-health-check.sh root@gpms-db02:/usr/local/bin/
scp galera-dashboard.sh root@gpms-db02:/usr/local/bin/

# 권한 설정
ssh root@gpms-db01 "chmod +x /usr/local/bin/galera-*.sh"
ssh root@gpms-db02 "chmod +x /usr/local/bin/galera-*.sh"
```

### Step 2: MySQL 자격증명 설정

**Option A: /root/.my.cnf 사용 (권장)**

```bash
# Node1, Node2 각각에서
ssh root@gpms-db01 "cat > /root/.my.cnf <<'EOF'
[client]
user=root
password=YOUR_MYSQL_PASSWORD
host=localhost
port=3306
EOF
chmod 600 /root/.my.cnf"

# Node2도 동일
ssh root@gpms-db02 "cat > /root/.my.cnf <<'EOF'
[client]
user=root
password=YOUR_MYSQL_PASSWORD
host=localhost
port=3306
EOF
chmod 600 /root/.my.cnf"
```

**Option B: 환경변수 사용**

```bash
# crontab에서 환경변수 설정
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASS=password
```

### Step 3: cron 자동 설정

```bash
# Node1 (gpms-db01)에서
ssh root@gpms-db01 'bash -s' < setup-galera-cron.sh

# Node2 (gpms-db02)에서
ssh root@gpms-db02 'bash -s' < setup-galera-cron.sh
```

**설정 확인:**
```bash
# Node1, Node2에서
ssh root@gpms-db01 "crontab -l | grep galera"
```

**예상 출력:**
```
*/10 6-22 * * 1-5 /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
*/30 22-23,0-5 * * * /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
*/30 * * * 0,6 /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
```

---

## 알람 설정 (선택사항)

### 이메일 알람 활성화

**Step 1: 스크립트에서 설정**

```bash
ssh root@gpms-db01 "sed -i 's/ENABLE_EMAIL_ALERT=false/ENABLE_EMAIL_ALERT=true/' /usr/local/bin/galera-health-check.sh"
ssh root@gpms-db01 "sed -i 's/ALERT_EMAIL=\"dba@company.com\"/ALERT_EMAIL=\"dba@company.com\"/' /usr/local/bin/galera-health-check.sh"

# Node2도 동일
ssh root@gpms-db02 "sed -i 's/ENABLE_EMAIL_ALERT=false/ENABLE_EMAIL_ALERT=true/' /usr/local/bin/galera-health-check.sh"
```

**Step 2: mail 설정 확인**

```bash
# postfix/sendmail 실행 확인
ssh root@gpms-db01 "systemctl status postfix"
# 또는
ssh root@gpms-db01 "systemctl status sendmail"
```

### Slack 알람 활성화

**Step 1: Slack Webhook URL 생성**

Slack 채널에서:
1. "Incoming Webhooks" 앱 설치
2. "Add New Webhook to Workspace"
3. 채널 선택 후 생성 (URL 예: `https://hooks.slack.com/services/T.../B.../X...`)

**Step 2: 스크립트 설정**

```bash
WEBHOOK_URL="https://hooks.slack.com/services/YOUR_WEBHOOK_URL"

ssh root@gpms-db01 "sed -i 's|SLACK_WEBHOOK=\"\"|SLACK_WEBHOOK=\"'$WEBHOOK_URL'\"|' /usr/local/bin/galera-health-check.sh"
ssh root@gpms-db01 "sed -i 's/ENABLE_SLACK_ALERT=false/ENABLE_SLACK_ALERT=true/' /usr/local/bin/galera-health-check.sh"

# Node2도 동일
ssh root@gpms-db02 "sed -i 's|SLACK_WEBHOOK=\"\"|SLACK_WEBHOOK=\"'$WEBHOOK_URL'\"|' /usr/local/bin/galera-health-check.sh"
ssh root@gpms-db02 "sed -i 's/ENABLE_SLACK_ALERT=false/ENABLE_SLACK_ALERT=true/' /usr/local/bin/galera-health-check.sh"
```

---

## 사용 방법

### 실시간 대시보드 (즉시 모니터링)

```bash
# 로컬 서버에서
ssh root@gpms-db01 "/usr/local/bin/galera-dashboard.sh"

# 또는 로컬에서 바로 실행
/usr/local/bin/galera-dashboard.sh
```

**대시보드 예시:**
```
╔════════════════════════════════════════════════════════════════════════════════════════════════╗
║                    🔍 GPMS Galera Cluster Monitor - Real-time Dashboard                    ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝

┌─ Node Information
│  Node Name: gpms-db01
│  Timestamp: 2026-09-02 14:10:25
│  Status: OK
└──────────────────────────────────────────────────────────────────────────────────────────

┌─ Cluster Status
│  Cluster Size: 3
│  Cluster Status: ✓ Primary
│  Available Members: gpms-db02:3306,gpms-db01:3306,
└──────────────────────────────────────────────────────────────────────────────────────────

┌─ Node Status
│  Node State: ✓ Synced
│  Ready: ✓ ON
│  Connected: ✓ ON
└──────────────────────────────────────────────────────────────────────────────────────────

┌─ Performance Metrics
│  Flow Control Paused: [░░░░░░░░░░░░░░░░░░░░] 0.0
│  Cert Deps Distance: [░░░░░░░░░░░░░░░░░░░░] 0
│  Recv Queue: 0
│  Send Queue: 0
└──────────────────────────────────────────────────────────────────────────────────────────

System Uptime: 2 days, 4:30 | Next refresh: 14:10:30 | Press Ctrl+C to exit
═══════════════════════════════════════════════════════════════════════════════════════════════
```

### 헬스 체크 로그 보기

```bash
# 실시간 로그
ssh root@gpms-db01 "tail -f /var/log/galera-health-check.log"

# 마지막 50줄
ssh root@gpms-db01 "tail -50 /var/log/galera-health-check.log"

# 알람만 보기
ssh root@gpms-db01 "tail -f /var/log/galera-alerts.log"
```

### 수동 헬스 체크 실행

```bash
# Node1에서 즉시 실행
ssh root@gpms-db01 "/usr/local/bin/galera-health-check.sh"

# 출력 예:
# ===============================================
# GPMS Galera Cluster Health Check
# ===============================================
# Timestamp: 2026-09-02 14:10:25
# Node: gpms-db01
# Status: OK
# 
# CLUSTER INFORMATION:
#   Cluster Size: 3
#   Cluster Status: Primary
#   Node State: Synced
#   Ready: ON
#   Connected: ON
#   ...
```

---

## 모니터링 임계값 커스터마이징

스크립트에서 다음 값을 편집하여 조정:

```bash
# /usr/local/bin/galera-health-check.sh에서

CLUSTER_SIZE_MIN=2          # 최소 클러스터 크기
FLOW_CONTROL_THRESHOLD=0.1  # Flow Control > 10% = 경고
CERT_DEPS_THRESHOLD=50      # 인증 거리 > 50 = 경고
```

변경 후:
```bash
ssh root@gpms-db01 "systemctl restart cron"
# 또는
ssh root@gpms-db01 "service cron restart"
```

---

## 트러블슈팅

### 문제: cron이 실행되지 않음

```bash
# cron 서비스 상태 확인
ssh root@gpms-db01 "systemctl status cron"

# cron 로그 확인
ssh root@gpms-db01 "grep CRON /var/log/syslog | tail -20"

# 권한 확인
ssh root@gpms-db01 "ls -la /usr/local/bin/galera-health-check.sh"
# 예상: -rwxr-xr-x
```

### 문제: MySQL 연결 실패

```bash
# 수동으로 쿼리 실행해보기
ssh root@gpms-db01 "mysql -e 'SELECT 1'"

# .my.cnf 권한 확인
ssh root@gpms-db01 "ls -la /root/.my.cnf"
# 예상: -rw------- (600)
```

### 문제: 알람이 발송되지 않음

```bash
# 이메일 서비스 확인
ssh root@gpms-db01 "systemctl status postfix"

# 테스트 이메일 발송
ssh root@gpms-db01 "echo 'Test' | mail -s 'Test Email' dba@company.com"

# 메일 큐 확인
ssh root@gpms-db01 "mailq"
```

---

## 성능 고려사항

### cron 스케줄 최적화

**현재 설정:**
```bash
# 업무 시간 (6:00~22:00, 주중): 10분마다
*/10 6-22 * * 1-5

# 야간 (22:00~06:00): 30분마다
*/30 22-23,0-5 * * *

# 주말: 30분마다
*/30 * * * 0,6
```

**고부하 환경 권장:**
```bash
# 업무 시간: 30분마다
*/30 6-22 * * 1-5

# 야간/주말: 1시간마다
0 * * * *
```

### MySQL 쿼리 최적화

스크립트는 대부분 system status 변수를 조회하므로 성능 영향 미미합니다.

---

## 로그 로테이션 설정 (선택)

```bash
# /etc/logrotate.d/galera 생성
ssh root@gpms-db01 "cat > /etc/logrotate.d/galera <<'EOF'
/var/log/galera-health-check.log
/var/log/galera-alerts.log
{
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF"
```

---

## 요약

| 구성 요소 | 파일 | 기능 | 실행 방식 |
|-----------|------|------|-----------|
| **자동 모니터링** | `galera-health-check.sh` | 주기적 상태 확인 및 알람 | cron (10~30분) |
| **실시간 대시보드** | `galera-dashboard.sh` | 터미널 기반 실시간 모니터링 | 수동 실행 |
| **설치 자동화** | `setup-galera-cron.sh` | crontab 자동 설정 | 일회 실행 |

---

**설치 완료 후:**

1. ✅ 헬스 체크 스크립트 배포 완료
2. ✅ cron 자동 실행 설정 완료
3. ✅ 로그 수집 시작
4. ✅ 필요 시 알람 활성화 완료

**모니터링 시작!** 🚀

