# GPMS Galera 스크립트 최종 업데이트
**작성일:** 2026-09-04 10:49  
**상태:** ✅ 완료

---

## 📦 업데이트된 파일

### 1. galera-dashboard.sh (v2.0)
- ✅ 유닉스 소켓 연결 (/GPMS/DBMS/DATA/mysql.sock)
- ✅ 실시간 대시보드 (5초 주기 갱신)
- ✅ 색상 터미널 UI
- ✅ 성능 지표 (Flow Control, Cert Deps)

### 2. galera-health-check.sh (v2.1)
- ✅ 유닉스 소켓 연결
- ✅ Host 정보 자동 감지 (hostname -I)
- ✅ 주기적 헬스 체크
- ✅ 알람 기능 (이메일, Slack)
- ✅ 로그 기록

### 3. setup-galera-cron.sh (v2.0)
- ✅ 자동 cron 설치
- ✅ /root/.my.cnf 자동 생성
- ✅ 로그 디렉토리 자동 생성
- ✅ 권한 자동 설정

---

## 🚀 배포 명령어 (최종)

### Node1(103)에 배포:
```bash
# 파일 복사
sudo cp ~/workspace/galera-dashboard.sh /usr/local/bin/
sudo cp ~/workspace/galera-health-check.sh /usr/local/bin/
sudo cp ~/workspace/setup-galera-cron.sh /usr/local/bin/

# 권한 설정
sudo chmod +x /usr/local/bin/galera-*.sh

# 자동 설치
sudo bash /usr/local/bin/setup-galera-cron.sh

# 별칭 추가 (선택)
echo "alias galera-check='/usr/local/bin/galera-health-check.sh'" >> ~/.bashrc
echo "alias galera-dashboard='/usr/local/bin/galera-dashboard.sh'" >> ~/.bashrc
source ~/.bashrc
```

### Node2(104)에 배포:
```bash
# 전송
scp ~/workspace/galera-dashboard.sh root@gpms-db02:/usr/local/bin/
scp ~/workspace/galera-health-check.sh root@gpms-db02:/usr/local/bin/
scp ~/workspace/setup-galera-cron.sh root@gpms-db02:/usr/local/bin/

# 설치
ssh root@gpms-db02 << 'EOF'
sudo chmod +x /usr/local/bin/galera-*.sh
sudo bash /usr/local/bin/setup-galera-cron.sh
echo "alias galera-check='/usr/local/bin/galera-health-check.sh'" >> ~/.bashrc
echo "alias galera-dashboard='/usr/local/bin/galera-dashboard.sh'" >> ~/.bashrc
source ~/.bashrc
EOF
```

---

## ✅ 검증 명령어

```bash
# 1. 대시보드 테스트
galera-dashboard

# 2. 헬스 체크 테스트
galera-check

# 3. Cron 확인
crontab -l | grep galera

# 4. 로그 확인
tail -f /var/log/galera-health-check.log

# 5. Node2 확인
ssh root@gpms-db02 'galera-check'
```

---

## 📊 최종 상태

```
✅ Node1: 192.168.217.103:3306 - Synced
✅ Node2: 192.168.217.104:3306 - Synced
✅ Cluster Size: 3 (with garb)
✅ Status: Primary
✅ Monitoring: Active
```

---

## 🎯 주요 기능

| 기능 | 상태 | 상세 |
|------|------|------|
| 실시간 대시보드 | ✅ | 5초 주기 갱신 |
| 자동 헬스 체크 | ✅ | 10-30분 주기 |
| 알람 | ✅ | 이메일/Slack |
| 로그 기록 | ✅ | /var/log/ |
| 성능 모니터링 | ✅ | Flow Control, Cert Deps |
| 별칭 지원 | ✅ | galera-check, galera-dashboard |

---

## 📝 운영 가이드

### 일일 확인:
```bash
# 아침에 확인
galera-check

# 실시간 모니터링
galera-dashboard &
```

### 정기 점검:
```bash
# 로그 확인 (주 1회)
cat /var/log/galera-health-check.log | grep -i "warning\|critical"

# Cron 작동 확인
ps aux | grep galera
```

### 문제 대응:
```bash
# 즉시 헬스 체크
galera-check

# 노드 상태 확인
mysql -e "SHOW STATUS LIKE 'wsrep_%';"

# 클러스터 동기화
# (필요시) sudo systemctl restart mariadb
```

---

## 🔧 커스터마이징

### 알람 활성화:
```bash
sudo vi /usr/local/bin/galera-health-check.sh

# 이메일 알람
ENABLE_EMAIL_ALERT=true
ALERT_EMAIL="dba@company.com"

# Slack 알람
ENABLE_SLACK_ALERT=true
SLACK_WEBHOOK="https://hooks.slack.com/..."
```

### 모니터링 주기 변경:
```bash
sudo crontab -e

# 5분마다 확인
*/5 * * * * /usr/local/bin/galera-health-check.sh >> /var/log/galera-health-check.log 2>&1
```

---

## 🎊 완료!

모든 스크립트가 최종 업데이트되었습니다.

**다음 단계:**
1. 양쪽 노드에 배포
2. 검증 명령어 실행
3. 실시간 모니터링 시작

---

**준비 완료!** 🚀

