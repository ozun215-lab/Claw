# 📊 GPMS Galera 모니터링 배포 완료

**작성 날짜:** 2026-09-02 14:10  
**상태:** ✅ 배포 준비 완료

---

## 📦 배포 패키지 구성

### 1️⃣ 핵심 스크립트 (3개)

#### A. `galera-health-check.sh` — 자동 헬스 체크
```
크기: ~9.2 KB
기능:
  • 10분/30분 주기 자동 실행
  • 클러스터 상태 모니터링
  • 임계값 초과 시 자동 알람 (이메일/Slack)
  • 상세 로그 기록 (/var/log/galera-health-check.log)

체크 항목:
  ✓ Cluster Size (최소 2)
  ✓ Cluster Status (Primary 여부)
  ✓ Node State (Synced 여부)
  ✓ wsrep_ready (ON/OFF)
  ✓ wsrep_connected (ON/OFF)
  ✓ Flow Control Paused (> 10% = 경고)
  ✓ Cert Deps Distance (> 50 = 경고)
```

#### B. `galera-dashboard.sh` — 실시간 대시보드
```
크기: ~8.4 KB
기능:
  • 5초 주기 실시간 업데이트
  • 색상별 상태 표시 (✓✗⚠)
  • 성능 게이지 시각화
  • 터미널 기반 UI

표시 정보:
  • 노드 정보 (이름, 타임스탬프, 전체 상태)
  • 클러스터 상태 (크기, 상태, 멤버)
  • 노드 상태 (동기화, 준비, 연결)
  • 성능 지표 (Flow Control, Cert Deps, 큐 상태)
```

#### C. `setup-galera-cron.sh` — 자동 설치
```
크기: ~3 KB
기능:
  • 한 번에 모든 설정 자동화
  • 스크립트 설치 및 권한 설정
  • crontab 자동 등록
  • 로그 디렉토리 생성

설정 내용:
  • 업무시간 (월-금 6-22시): 10분마다
  • 야간 (22-06시): 30분마다
  • 주말: 30분마다
```

### 2️⃣ 문서 (2개)

#### 운영 가이드
- `GPMS_Galera_Cluster_Operations_Guide.md`
  - 클러스터 구성 정보
  - 일상 모니터링 절차
  - 트러블슈팅 가이드
  - 유지보수 절차
  - 성능 최적화

#### 배포 가이드
- `Monitoring_Deployment_Guide.md`
  - 설치 단계별 절차
  - 알람 설정 (이메일/Slack)
  - 사용 방법
  - 트러블슈팅
  - 로그 로테이션

---

## 🚀 빠른 시작 (5단계)

### Step 1: 스크립트 배포 (5분)
```bash
# 대표님 컴퓨터에서
scp galera-health-check.sh root@gpms-db01:/usr/local/bin/
scp galera-health-check.sh root@gpms-db02:/usr/local/bin/
scp galera-dashboard.sh root@gpms-db01:/usr/local/bin/
scp galera-dashboard.sh root@gpms-db02:/usr/local/bin/

# 권한 설정
ssh root@gpms-db01 "chmod +x /usr/local/bin/galera-*.sh"
ssh root@gpms-db02 "chmod +x /usr/local/bin/galera-*.sh"
```

### Step 2: MySQL 인증 설정 (3분)
```bash
# Node1, Node2에서
ssh root@gpms-db01 "cat > /root/.my.cnf <<'EOF'
[client]
user=root
password=YOUR_PASSWORD
host=localhost
port=3306
EOF
chmod 600 /root/.my.cnf"
```

### Step 3: cron 자동 설정 (2분)
```bash
# Node1에서
ssh root@gpms-db01 'bash -s' < setup-galera-cron.sh

# Node2에서
ssh root@gpms-db02 'bash -s' < setup-galera-cron.sh
```

### Step 4: 알람 활성화 (3분, 선택)
```bash
# Slack Webhook 설정 (선택)
# 또는 이메일 알람 활성화
```

### Step 5: 검증 (2분)
```bash
# 대시보드 실행 (실시간 확인)
ssh root@gpms-db01 "/usr/local/bin/galera-dashboard.sh"

# 또는 수동 헬스 체크
ssh root@gpms-db01 "/usr/local/bin/galera-health-check.sh"
```

**총 소요 시간: 약 15분**

---

## 📋 파일 위치

현재 작업 공간에 모든 파일이 준비되어 있습니다:

```
D:\Claw\workspace\
├── GPMS_Galera_Cluster_Operations_Guide.md      (운영 가이드)
├── Monitoring_Deployment_Guide.md               (배포 가이드)
├── galera-health-check.sh                       (자동 헬스 체크)
├── galera-dashboard.sh                          (실시간 대시보드)
└── setup-galera-cron.sh                         (자동 설치)
```

---

## 🎯 모니터링 기능 요약

### 자동 모니터링 (cron)

| 기능 | 동작 | 로그 위치 |
|------|------|-----------|
| **주기 실행** | 10~30분 | `/var/log/galera-health-check.log` |
| **상태 확인** | 클러스터, 노드, 성능 | 동일 파일 |
| **임계값 초과** | 자동 알람 | `/var/log/galera-alerts.log` |
| **이메일 알람** | CRITICAL/WARNING | 대표님 메일 |
| **Slack 알람** | CRITICAL/WARNING | Slack 채널 |

### 실시간 대시보드

```
터미널에서 실행하면:

┌─ Node Information
│  ✓ 노드 상태 (Synced/Joining/Donor 등)
│  ✓ 현재 타임스탬프

┌─ Cluster Status
│  ✓ 전체 클러스터 크기
│  ✓ Primary 여부
│  ✓ 모든 멤버 목록

┌─ Node Status
│  ✓ 동기화 상태
│  ✓ 준비 상태
│  ✓ 연결 상태

┌─ Performance Metrics
│  ✓ Flow Control 게이지 (지연도 시각화)
│  ✓ 인증 거리
│  ✓ 수신/송신 큐
```

---

## ✅ 체크리스트

배포 전 확인:

- [ ] 모든 스크립트 다운로드 완료
- [ ] Node1, Node2 SSH 접속 확인
- [ ] MySQL root 비밀번호 준비
- [ ] Slack 알람 원하면 Webhook URL 준비 (선택)
- [ ] 이메일 알람 원하면 메일 설정 확인 (선택)

배포 후 확인:

- [ ] `/usr/local/bin/galera-*.sh` 파일 존재 확인
- [ ] 파일 실행 권한 (+x) 확인
- [ ] crontab에 3개 항목 등록 확인
- [ ] 대시보드 실행하여 실시간 업데이트 확인
- [ ] 헬스 체크 로그 생성 확인 (약 10분 후)

---

## 📞 지원

### 각 스크립트의 역할

1. **`galera-health-check.sh`**
   - 언제: cron으로 자동 실행 (10~30분마다)
   - 어디서: 각 노드 (gpms-db01, gpms-db02)
   - 뭘 하나: 상태 확인 + 임계값 초과 시 알람

2. **`galera-dashboard.sh`**
   - 언제: 수동으로 필요할 때
   - 어디서: 어느 노드에서든 실행 가능
   - 뭘 하나: 실시간 모니터링 (5초 주기 업데이트)

3. **`setup-galera-cron.sh`**
   - 언제: 설치 시 1회만 실행
   - 어디서: 각 노드에서
   - 뭘 하나: 자동 설치 및 cron 등록

---

## 🎓 알람 활성화 팁

### 이메일 알람 (권장)

```bash
# 1. postfix 설치 확인
ssh root@gpms-db01 "apt-get install -y postfix"

# 2. 스크립트 수정
ssh root@gpms-db01 "sed -i 's/ENABLE_EMAIL_ALERT=false/ENABLE_EMAIL_ALERT=true/' /usr/local/bin/galera-health-check.sh"

# 3. 대표님 메일 주소 설정
ssh root@gpms-db01 "sed -i 's/dba@company.com/zunn@eactive.co.kr/' /usr/local/bin/galera-health-check.sh"
```

### Slack 알람

```bash
# 1. Slack에서 Incoming Webhooks 앱 추가
# 2. 채널 선택 후 Webhook URL 생성
# 3. 스크립트에 설정

WEBHOOK="https://hooks.slack.com/services/YOUR_ID/YOUR_TOKEN"
ssh root@gpms-db01 "sed -i 's|SLACK_WEBHOOK=\"\"|SLACK_WEBHOOK=\"'$WEBHOOK'\"|' /usr/local/bin/galera-health-check.sh"
ssh root@gpms-db01 "sed -i 's/ENABLE_SLACK_ALERT=false/ENABLE_SLACK_ALERT=true/' /usr/local/bin/galera-health-check.sh"
```

---

## 📈 향후 확장 가능성

현재 구성 외에 추가 가능한 기능:

- [ ] Prometheus 메트릭 내보내기
- [ ] Grafana 대시보드 통합
- [ ] PagerDuty 긴급 알람
- [ ] 자동 페일오버 스크립트
- [ ] 백업 상태 모니터링
- [ ] 성능 리포트 자동 생성

---

## 📝 주의사항

1. **MySQL 비밀번호 관리**
   - `/root/.my.cnf`는 600 권한 유지
   - 정기적 비밀번호 변경 권장

2. **로그 관리**
   - 약 1주일 정도 로그 유지
   - `/etc/logrotate.d/` 설정으로 자동 로테이션 가능

3. **알람 오버로드**
   - 임계값 너무 낮으면 거짓 알람 증가
   - 환경에 맞게 조정 필요

4. **성능 영향**
   - 헬스 체크 쿼리는 매우 가볍습니다
   - 대시보드는 개인용 (프로덕션 배포 불권장)

---

## 🎉 결론

**GPMS Galera 클러스터 모니터링 시스템 준비 완료!**

- ✅ 자동 모니터링 (cron)
- ✅ 실시간 대시보드 (터미널)
- ✅ 자동 알람 (이메일/Slack)
- ✅ 상세 로그 기록

이제 안심하고 클러스터를 운영할 수 있습니다. 🚀

---

**다음 단계:**
1. 스크립트를 노드에 배포
2. cron 설정 자동화
3. 알람 활성화 (선택)
4. 대시보드로 실시간 확인

**문제 발생 시:**
- 배포 가이드의 "트러블슈팅" 섹션 참고
- 운영 가이드의 "FAQ" 참고

대표님께서 편하게 운영하시기를 바랍니다! 😊

