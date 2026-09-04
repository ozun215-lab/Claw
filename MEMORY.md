# GPMS Galera 클러스터 복구 기록

**최종 상태:** ✅ 완전 복구 및 안정화 (2026-09-04 10:49)

## 복구 일정
- **9/2 15:46**: Node1 crash (aria_log_control lock)
- **9/2 ~ 9/3**: 네트워크 설정, 포트 추가, /etc/hosts 수정, NTP 동기화
- **9/3 11:23**: Galera 클러스터 3멤버 복구 완료 (cluster_size=3, Primary, Synced)
- **9/4 10:31**: 모니터링 대시보드 정상 작동 확인
- **9/4 10:49**: 스크립트 최종 업데이트 완료

## 주요 이슈 및 해결책

### 1. Node1 Crash (9/2 15:46)
- **증상**: aria_log_control lock error
- **원인**: 비정상 종료
- **해결**: aria 로그 파일 정리

### 2. Node2 데이터 손상
- **증상**: seqno=-1, Disconnected
- **원인**: 크래시 후 InnoDB 손상
- **해결**: 완전 초기화 + SST

### 3. 네트워크 연결 실패
- **증상**: Connection timed out (4567 포트)
- **원인**: 
  - wsrep_cluster_address 포트 누락
  - /etc/hosts DNS 오류 (master-node1 → 127.0.0.1)
  - NTP 미동기화 (System clock synchronized: no)
  - iptables 포트 미허용
- **해결**: 포트 추가, hosts 수정, NTP 동기화, iptables 설정

### 4. MySQL 접속 오류
- **증상**: Access denied for user 'root'@'127.0.0.1'
- **원인**: TCP 연결 vs 소켓 연결 차이
- **해결**: 유닉스 소켓 연결 (/GPMS/DBMS/DATA/mysql.sock)

### 5. Host 정보 누락
- **증상**: Host: : (비어있음)
- **원인**: MYSQL_HOST/PORT 변수 사용 안 함
- **해결**: hostname -I로 자동 감지

## 최종 상태 (2026-09-04 10:49)
```
✅ Node1: node01 (192.168.217.103:3306) - Synced
✅ Node2: node02 (192.168.217.104:3306) - Synced
✅ Cluster Size: 3 (with garb arbitrator)
✅ Status: Primary
✅ Monitoring: Active (대시보드 + 헬스 체크)
```

## 배포된 스크립트
1. galera-dashboard.sh v2.0 - 실시간 모니터링 (5초 주기)
2. galera-health-check.sh v2.1 - 자동 헬스 체크 (10-30분 주기)
3. setup-galera-cron.sh v2.0 - 자동 설치 도구

## 문서 생성
1. GPMS_Galera_Cluster_Operations_Guide.md
2. Monitoring_Deployment_Guide.md
3. GPMS_Galera_Cluster_Status_Final.md
4. GPMS_Galera_Script_Installation_Guide.md
5. GPMS_Galera_Scripts_Final_Update.md

## 운영 스케줄
- 주중 낮 (6:00-22:00): 10분 주기
- 주중 야간 (22:00-06:00): 30분 주기
- 주말: 30분 주기

## 별칭 설정
```bash
alias galera-check='/usr/local/bin/galera-health-check.sh'
alias galera-dashboard='/usr/local/bin/galera-dashboard.sh'
```

---

**상태:** 🟢 안정적 운영 중

