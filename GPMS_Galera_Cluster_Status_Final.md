# GPMS Galera 클러스터 - 최종 복구 보고서

**작성일:** 2026-09-03 11:24  
**상태:** ✅ 완전 복구 및 정상 운영 중

---

## 1. 클러스터 구성

| 구성 요소 | 상태 | 세부정보 |
|-----------|------|---------|
| **Node1** | ✅ Synced | gpms-db01 (192.168.217.103) |
| **Node2** | ✅ Synced | gpms-db02 (192.168.217.104) |
| **garb** | ✅ Synced | Arbitrator (쿼럼 유지) |
| **클러스터 크기** | 3 | 완전 구성 |
| **상태** | Primary | 정상 작동 |

---

## 2. 복구 과정 (9/2 ~ 9/3)

### 문제 1: Node1 Crash (9/2 15:46)
```
증상: aria_log_control lock error, InnoDB lock error
원인: 비정상 종료
해결: aria 로그 파일 정리, 자동 재기동
```

### 문제 2: Node2 Disconnected
```
증상: cluster_size=0, Disconnected 상태
원인: grastate.dat seqno=-1, 데이터 손상
해결: 완전 초기화 → SST로 Node1에서 데이터 동기화
```

### 문제 3: 네트워크 연결 실패
```
증상: Connection timed out (4567 포트)
원인: 
  1. wsrep_cluster_address 포트 누락
  2. /etc/hosts 호스트명 오류 (DNS 해석 실패)
  3. NTP 미동기화
  4. iptables/firewall 포트 미허용

해결: 
  1. 포트 명시 추가 (gcomm://gpms-db01:4567,gpms-db02:4567)
  2. /etc/hosts 수정
  3. NTP 강제 동기화 (ntpdate)
  4. iptables 포트 허용
```

---

## 3. 최종 상태 (9/3 11:23)

```sql
WSREP_CLUSTER_SIZE: 3
WSREP_CLUSTER_STATUS: Primary
WSREP_LOCAL_STATE_COMMENT: Synced
WSREP_INCOMING_ADDRESSES: gpms-db02:3306,gpms-db01:3306
WSREP_FLOW_CONTROL_PAUSED: 0.0000415 (정상)
WSREP_CERT_DEPS_DISTANCE: 1.12631 (정상)
WSREP_READY: ON
WSREP_CONNECTED: ON
```

---

## 4. 주요 교훈

### A. 설정 일관성
- ✅ Node1 ↔ Node2 wsrep_node_address, wsrep_node_name 일치 필수
- ✅ wsrep_cluster_address에 포트 명시 (기본값 사용 금지)

### B. 네트워크 확인 항목
- ✅ /etc/hosts 호스트명 올바른 IP 매핑
- ✅ DNS 해석 검증 (ping, nslookup)
- ✅ 포트 연결 테스트 (nc, telnet)
- ✅ 방화벽 포트 허용 확인

### C. 시스템 동기화
- ✅ NTP 시간 동기화 필수 (System clock synchronized: yes)
- ✅ 노드 간 시간 차이 1초 이내

### D. 데이터 무결성
- ✅ InnoDB 파일 손상 시 완전 초기화 + SST 권장
- ✅ grastate.dat seqno 값으로 데이터 신선도 판단

---

## 5. 모니터링 체크리스트

### 일일 확인 (권장)

```sql
-- Node1 또는 Node2에서
SELECT 
  (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS 
   WHERE VARIABLE_NAME='wsrep_cluster_size') AS cluster_size,
  (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS 
   WHERE VARIABLE_NAME='wsrep_cluster_status') AS status,
  (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS 
   WHERE VARIABLE_NAME='wsrep_local_state_comment') AS node_state,
  (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS 
   WHERE VARIABLE_NAME='wsrep_ready') AS ready;
```

### 자동 모니터링

- `galera-health-check.sh`: 10분~30분 주기 (cron)
- `galera-dashboard.sh`: 실시간 터미널 대시보드
- `setup-galera-cron.sh`: 자동 배포 스크립트

---

## 6. 응급 상황 대응

### Scenario A: 한 노드 Crash
```bash
# 크래시된 노드 재시작
sudo systemctl restart mariadb

# 60초 대기 (SST 진행)
# 자동으로 Primary 그룹에 재조인
```

### Scenario B: 전체 클러스터 다운
```bash
# 각 노드의 grastate.dat seqno 확인
cat /GPMS/DBMS/DATA/grastate.dat | grep seqno

# 가장 큰 seqno를 가진 노드에서 bootstrap
sudo galera_new_cluster

# 나머지 노드 재시작
sudo systemctl restart mariadb
```

### Scenario C: Split-Brain (양쪽 Primary)
```bash
# Non-Primary 그룹의 노드에서
sudo systemctl restart mariadb
# 자동으로 Primary 그룹에 재조인
```

---

## 7. 예방 조치

### 정기 점검 (월 1회)
- [ ] 클러스터 health check
- [ ] 디스크 여유 공간 확인
- [ ] 로그 파일 로테이션 확인
- [ ] NTP 동기화 상태 확인

### 성능 모니터링
- Flow Control Paused < 10% 유지
- Cert Deps Distance < 100 유지
- 모든 노드 wsrep_ready=ON

### 백업 전략
- SST 자동화 (mariabackup)
- 정기 백업 (주 1회)
- 백업 검증 (월 1회)

---

## 8. 연락처 및 문서

| 항목 | 정보 |
|------|------|
| **담당자** | 박영준 대표님 |
| **긴급연락** | DBA 팀 |
| **기술문서** | `GPMS_Galera_Cluster_Operations_Guide.md` |
| **모니터링** | `Monitoring_Deployment_Guide.md` |
| **대시보드** | `/usr/local/bin/galera-dashboard.sh` |

---

## 9. 결론

✅ **Galera 클러스터가 완전히 복구되었습니다.**

- 3멤버 구성 (node01 + node02 + garb)
- 모든 노드 Synced 상태
- Primary 쿼럼 유지
- Pacemaker HA와 통합 운영 중

이제 안정적으로 운영할 수 있습니다. 🚀

---

**보고 일자:** 2026-09-03  
**상태:** ✅ 완료  
**다음 점검:** 2026-09-10

