# GPMS Galera 클러스터 - 스크립트 설치 가이드
**작성일:** 2026-09-04  
**버전:** 2.0 (소켓 연결 최적화)

---

## 📋 개요

이 가이드는 Galera 클러스터 모니터링 스크립트를 **두 노드에 설치**하는 방법을 설명합니다.

| 스크립트 | 용도 | 실행 주기 |
|---------|------|---------|
| **galera-dashboard.sh** | 실시간 대시보드 | 수동 실행 |
| **galera-health-check.sh** | 자동 헬스 체크 | cron (10-30분) |
| **setup-galera-cron.sh** | 자동 설치 도구 | 1회 실행 |

---

## 🚀 빠른 시작 (3단계)

### Step 1: 파일 준비

작업 공간에서 스크립트 파일 확인:
```bash
ls -la ~/workspace/galera-*.sh
```

**확인되는 파일:**
- ✅ galera-dashboard.sh
- ✅ galera-health-check.sh
- ✅ setup-galera-cron.sh

---

### Step 2: Node1(103)에 설치

```bash
# Node1에서 실행

# 1. 파일 복사
sudo cp ~/workspace/galera-dashboard.sh /usr/local/bin/
sudo cp ~/workspace/galera-health-check.sh /usr/local/bin/
sudo cp ~/workspace/setup-galera-cron.sh /usr/local/bin/

# 2. 권한 설정
sudo chmod +x /usr/local/bin/galera-*.sh

# 3. 자동 설치 실행
sudo bash /usr/local/bin/setup-galera-cron.sh

# 4. 완료 확인
echo "✅ Node1 설치 완료"
```

---

### Step 3: Node2(104)에 설치

```bash
# Node1에서 Node2로 전송

scp ~/workspace/galera-dashboard.sh root@gpms-db02:/usr/local/bin/
scp ~/workspace/galera-health-check.sh root@gpms-db02:/usr/local/bin/
scp ~/workspace/setup-galera-cron.sh root@gpms-db02:/usr/local/bin/

# Node2에서 권한 및 설치
ssh root@gpms-db02 << 'EOF'
sudo chmod +x /usr/local/bin/galera-*.sh
sudo bash /usr/local/bin/setup-galera-cron.sh
echo "✅ Node2 설치 완료"
EOF
```

---

## ✅ 설치 후 검증

### 1. 대시보드 테스트

```bash
# Node1에서
/usr/local/bin/galera-dashboard.sh
```

**예상 화면:**
```
╔════════════════════════════════════════════╗
║ 🔍 GPMS Galera Cluster Monitor             ║
╚════════════════════════════════════════════╝

┌─ Node Information
│ Node Name: node01
│ Status: OK
└────────────────────────────────────────────

┌─ Cluster Status
│ Cluster Size: 3
│ Cluster Status: ✓ Primary
└────────────────────────────────────────────
```

**종료:** `Ctrl+C`

---

### 2. 헬스 체크 테스트

```bash
# Node1에서
/usr/local/bin/galera-health-check.sh

# 또는 Node2에서
ssh root@gpms-db02 '/usr/local/bin/galera-health-check.sh'
```

**예상 결과:**
```
===============================================
GPMS Galera Cluster Health Check
===============================================
Timestamp: 2026-09-04 10:37:00
Node: node01
Status: OK

CLUSTER INFORMATION:
  Cluster Size: 3
  Cluster Status: Primary
  Node State: Synced
  ...
```

---

### 3. Cron 설정 확인

```bash
# Node1에서
crontab -l | grep galera

# Node2에서
ssh root@gpms-db02 'crontab -l | grep galera'
```

**예상 결과:**
```
*/10 6-22 * * 1-5 /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
*/30 22-23,0-5 * * * /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
*/30 * * * 0,6 /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
```

---

### 4. 로그 확인

```bash
# 헬스 체크 로그
sudo tail -f /var/log/galera-health-check.log

# 알람 로그
sudo tail -f /var/log/galera-alerts.log
```

---

## 🔧 설정 커스터마이징

### 비밀번호 변경

```bash
# /root/.my.cnf 수정
sudo vi /root/.my.cnf
```

**내용:**
```ini
[client]
user=root
password=YOUR_NEW_PASSWORD
host=localhost
port=3306
```

**또는 환경 변수로:**
```bash
export MYSQL_PASS=YOUR_PASSWORD
/usr/local/bin/galera-dashboard.sh
```

---

### 모니터링 주기 변경

Crontab 수정:
```bash
sudo crontab -e
```

**예시:**
```bash
# 5분마다 (더 자주)
*/5 * * * * /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1

# 1시간마다 (덜 자주)
0 * * * * /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
```

---

### 알람 활성화

헬스 체크 스크립트에서:
```bash
sudo vi /usr/local/bin/galera-health-check.sh
```

**찾아서 수정:**
```bash
# 이메일 알람
ENABLE_EMAIL_ALERT=true
ALERT_EMAIL="your-email@company.com"

# Slack 알람
ENABLE_SLACK_ALERT=true
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

---

## 📊 모니터링 스케줄

| 기간 | 주기 | 상세 |
|------|------|------|
| **주중 낮** | 10분 | 6:00 ~ 22:00 (업무 시간) |
| **주중 야간** | 30분 | 22:00 ~ 06:00 (야간) |
| **주말** | 30분 | 매일 24시간 |

---

## 🆘 트러블슈팅

### 문제: "Cannot connect to MySQL"

```bash
# 소켓 경로 확인
ls -la /GPMS/DBMS/DATA/mysql.sock

# MySQL 상태 확인
sudo systemctl status mariadb

# 수동 연결 테스트
mysql --socket=/GPMS/DBMS/DATA/mysql.sock -u root -pgooroom -e "SELECT 1;"
```

---

### 문제: Cron이 실행되지 않음

```bash
# Cron 로그 확인
sudo tail -f /var/log/cron

# Cron 서비스 상태
sudo systemctl status crond

# 권한 확인
ls -la /usr/local/bin/galera-*.sh
# 모두 -rwxr-xr-x 이어야 함
```

---

### 문제: 로그 파일이 없음

```bash
# 로그 디렉토리 생성
sudo mkdir -p /var/log
sudo touch /var/log/galera-health-check.log
sudo touch /var/log/galera-alerts.log
sudo chmod 644 /var/log/galera-*.log
```

---

## 📝 설치 체크리스트

- [ ] 파일 3개 준비됨 (galera-*.sh)
- [ ] Node1에 설치 완료
- [ ] Node2에 설치 완료
- [ ] 대시보드 테스트 성공
- [ ] 헬스 체크 테스트 성공
- [ ] Cron 작업 등록 확인
- [ ] 로그 파일 생성 확인
- [ ] 실시간 모니터링 정상 작동

---

## 🎊 완료!

모든 스크립트가 설치되고 모니터링이 자동으로 시작됩니다.

**다음 단계:**
1. 대시보드를 실시간으로 확인
2. 로그를 정기적으로 검토
3. 알람이 정상 동작하는지 확인

---

**질문이나 문제가 있으면 언제든 알려주세요!** 📞

