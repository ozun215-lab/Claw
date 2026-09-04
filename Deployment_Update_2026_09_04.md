# GPMS Galera 스크립트 배포 가이드
# 2026-09-04 업데이트

## 📦 배포할 스크립트

1. galera-dashboard.sh - 실시간 대시보드 (소켓 연결)
2. galera-health-check.sh - 주기적 헬스 체크 (소켓 연결)
3. setup-galera-cron.sh - cron 자동 설치

## 🚀 배포 단계

### Node1 (192.168.217.103)

```bash
# 스크립트 복사
sudo cp galera-dashboard.sh /usr/local/bin/
sudo cp galera-health-check.sh /usr/local/bin/
sudo cp setup-galera-cron.sh /usr/local/bin/

# 권한 설정
sudo chmod +x /usr/local/bin/galera-*.sh

# cron 설치
sudo bash /usr/local/bin/setup-galera-cron.sh

# 테스트
/usr/local/bin/galera-health-check.sh
/usr/local/bin/galera-dashboard.sh &
```

### Node2 (192.168.217.104)

```bash
# 동일하게 배포
scp galera-dashboard.sh root@gpms-db02:/usr/local/bin/
scp galera-health-check.sh root@gpms-db02:/usr/local/bin/
scp setup-galera-cron.sh root@gpms-db02:/usr/local/bin/

ssh root@gpms-db02 "sudo chmod +x /usr/local/bin/galera-*.sh"
ssh root@gpms-db02 "sudo bash /usr/local/bin/setup-galera-cron.sh"
```

## ✅ 검증

```bash
# 대시보드 실행
/usr/local/bin/galera-dashboard.sh

# 헬스 체크 실행
/usr/local/bin/galera-health-check.sh

# 로그 확인
tail -f /var/log/galera-health-check.log
tail -f /var/log/galera-alerts.log

# cron 확인
crontab -l | grep galera
```

## 📋 변경 사항 요약

### galera-dashboard.sh
- ✅ TCP 연결 → 유닉스 소켓 연결
- ✅ 소켓 경로: /GPMS/DBMS/DATA/mysql.sock
- ✅ 비밀번호: gooroom (기본값)
- ✅ 색상 터미널 UI 유지

### galera-health-check.sh
- ✅ TCP 연결 → 유닉스 소켓 연결
- ✅ MYSQL_PASS 기본값: gooroom
- ✅ 주기적 헬스 체크 및 알람 기능

### setup-galera-cron.sh
- ✅ /root/.my.cnf 자동 생성
- ✅ cron 작업 자동 설정
- ✅ 로그 디렉토리 자동 생성

## 🔧 수동 설정 (필요시)

```bash
# 비밀번호 변경
export MYSQL_PASS=your_password
/usr/local/bin/galera-dashboard.sh

# 환경 변수로 설정
export MYSQL_USER=monitoring_user
export MYSQL_PASS=monitoring_pass
/usr/local/bin/galera-health-check.sh
```

## 📊 모니터링 스케줄

- 주중 낮 (6:00-22:00): 10분 주기
- 주중 야간 (22:00-06:00): 30분 주기
- 주말: 30분 주기

---

**배포 완료 후 대시보드를 실행하세요!** 🚀
