# GPMS Galera 클러스터 운영 가이드

**작성일:** 2026-09-02  
**클러스터 상태:** ✅ 정상 운영 (3멤버)  
**마지막 업데이트:** 9/2 13:57

---

## 1. 클러스터 구성 정보

### 현재 구성

| 구성 요소 | 호스트명 | IP 주소 | 역할 | 상태 |
|-----------|---------|---------|------|------|
| Node1 | gpms-db01 | 192.168.217.103 | MariaDB + Primary | ✅ Synced |
| Node2 | gpms-db02 | 192.168.217.104 | MariaDB | ✅ Synced |
| garb | (arbiter 서버) | 192.168.217.102? | Arbiter (쿼럼 유지) | ✅ Synced |

### 클러스터 정보

```
클러스터명: galera_cluster
그룹 UUID: fbfc80fc-a5c8-11f1-8d3c-2a17c832b34d
현재 멤버: 3명 (node01 + node02 + garb)
상태: Primary (쿼럼 만족)
동기화: 완전 동기화 (Synced)
```

### 네트워크 설정

| 포트 | 용도 | 프로토콜 |
|------|------|---------|
| 3306 | MySQL 쿼리 | TCP |
| 4567 | Galera 그룹 통신 (gcomm) | TCP |
| 4568 | IST (Incremental State Transfer) | TCP |
| 4444 | SST (State Snapshot Transfer) | TCP |
| 9568 | garb arbiter 포트 | TCP |

---

## 2. 일상 모니터링

### 2.1 클러스터 상태 확인 (권장: 매 시간)

```sql
-- Node1 (gpms-db01) 또는 Node2 (gpms-db02)에서 실행
SELECT 
    @@wsrep_node_name AS node_name,
    @@wsrep_node_address AS address;

SELECT 
    VARIABLE_NAME,
    VARIABLE_VALUE
FROM information_schema.GLOBAL_STATUS
WHERE VARIABLE_NAME IN (
    'wsrep_cluster_size',
    'wsrep_cluster_status',
    'wsrep_local_state_comment',
    'wsrep_ready',
    'wsrep_connected',
    'wsrep_incoming_addresses',
    'wsrep_flow_control_paused'
);
```

### 2.2 예상 정상 결과

| 변수 | 정상값 | 주의값 | 심각값 |
|------|--------|--------|--------|
| `wsrep_cluster_size` | 3 | 2 | < 2 |
| `wsrep_cluster_status` | Primary | Non-Primary | Disconnected |
| `wsrep_local_state_comment` | Synced | Joined/Joining | Donor/Desynced |
| `wsrep_ready` | ON | - | OFF |
| `wsrep_connected` | ON | - | OFF |
| `wsrep_flow_control_paused` | 0 | < 0.1 | > 0.1 |

---

## 3. 트러블슈팅

### 3.1 Node가 Disconnected 상태

**증상:**
- `wsrep_cluster_size` = 0
- `wsrep_cluster_status` = Disconnected
- `wsrep_connected` = OFF

**원인:**
1. 노드가 Primary 그룹과 네트워크 단절
2. 4567 포트 방화벽 차단
3. MariaDB 크래시 후 미복구

**조치:**
```bash
# 1. 네트워크 확인
ping gpms-db01
nc -zv gpms-db01 4567

# 2. MariaDB 로그 확인
sudo tail -50 /var/log/mysql/error.log | grep -E "WSREP|ERROR|InnoDB"

# 3. MariaDB 재시작
sudo systemctl stop mariadb
sudo systemctl start mariadb

# 4. 로그 모니터링
sudo tail -f /var/log/mysql/error.log | grep WSREP
```

**예상 복구 로그:**
```
WSREP: gcomm thread scheduling priority set
WSREP: Connecting to group 'galera_cluster'
WSREP: State transfer to X.0 (node02) complete.
WSREP: Shifting JOINED -> SYNCED
```

---

### 3.2 Flow Control 지연 심각 (`wsrep_flow_control_paused` > 0.1)

**증상:**
- 쓰기 성능 저하
- 복제 지연 증가

**원인:**
1. 느린 쿼리 (장시간 트랜잭션)
2. 충돌 많은 워크로드
3. 디스크 I/O 병목

**조치:**
```sql
-- 느린 쿼리 확인
SHOW PROCESSLIST;

-- 대기 중인 트랜잭션
SELECT * FROM information_schema.INNODB_TRX WHERE TIME_TO_SEC(TIMEDIFF(NOW(), TRX_STARTED)) > 60;
```

---

### 3.3 한 노드만 Synced, 나머지 Joining/Donor

**증상:**
- 일부 노드만 `Synced`
- 나머지는 `Joining`, `Donor`, `Joined`

**원인:**
1. SST(State Snapshot Transfer) 진행 중
2. 대용량 데이터 동기화

**조치:**
- 대기 (일반적으로 5~30분 소요, DB 크기에 따라)
- 로그 모니터링:
  ```bash
  sudo tail -f /var/log/mysql/error.log | grep -E "SST|IST|transfer"
  ```

---

### 3.4 전체 클러스터 다운 (모든 노드 Dead)

**증상:**
- 모든 노드에서 MariaDB 미실행
- `grastate.dat` 파일 손상 가능

**원인:**
1. 전원 차단 (UPS 배터리 방전)
2. 동시 OS crash
3. 스토리지 장애

**복구 절차:**

**Step 1: 각 노드의 grastate.dat 확인**
```bash
# Node1
sudo cat /home/gpms/GPMS/DBMS/DATA/grastate.dat

# Node2
sudo cat /home/gpms/GPMS/DBMS/DATA/grastate.dat
```

**Step 2: seqno 값 비교**
```ini
# 예: Node1
version: 2.1
uuid: fbfc80fc-a5c8-11f1-8d3c-2a17c832b34d
seqno: 12345          ← 큰 값 = 최신 데이터
safe_to_bootstrap: 0

# 예: Node2
version: 2.1
uuid: fbfc80fc-a5c8-11f1-8d3c-2a17c832b34d
seqno: 12000          ← 작은 값 = 뒤처짐
safe_to_bootstrap: 0
```

**Step 3: 가장 큰 seqno를 가진 노드에서 bootstrap**
```bash
# 예: Node1의 seqno가 12345로 가장 큼
# Node1에서
sudo galera_new_cluster

# Node2에서
sudo systemctl start mariadb
```

**Step 4: 클러스터 복구 확인**
```sql
-- Node1 또는 Node2에서
SHOW STATUS LIKE 'wsrep_cluster_size';  -- 결과: 2 (이상적) 또는 3 (garb 포함)
SHOW STATUS LIKE 'wsrep_cluster_status';  -- 결과: Primary
```

---

## 4. 유지보수

### 4.1 노드 정기 재부팅

**절차 (한 번에 한 노드씩):**

```bash
# Step 1: 대기 중인 트랜잭션 확인
mysql -e "SHOW PROCESSLIST \G"

# Step 2: 해당 노드에서 MariaDB 중지
sudo systemctl stop mariadb

# Step 3: 다른 노드에서 cluster_size 확인 (2로 감소해야 함)
# Node1에서
SHOW STATUS LIKE 'wsrep_cluster_size';

# Step 4: 재부팅
sudo reboot

# Step 5: 재부팅 후 MariaDB 자동 시작 확인
# (약 2~3분 소요)
sudo systemctl status mariadb

# Step 6: 로그에서 'Synced' 확인
sudo tail -20 /var/log/mysql/error.log | grep Synced
```

**반복:** 모든 노드에 대해 Step 1~6 반복 (한 번에 하나씩)

---

### 4.2 MariaDB 업그레이드

**절차:**
1. 비프로덕션 환경에서 테스트
2. Node2부터 업그레이드 (Node1은 마지막)
3. 각 업그레이드 후 SST 대기 (~10~30분)

```bash
# Step 1: Node2에서
sudo apt update
sudo apt upgrade mariadb-server
sudo systemctl restart mariadb

# Step 2: Node2가 Synced 될 때까지 대기
# Node1에서
SHOW STATUS LIKE 'wsrep_incoming_addresses';  -- Node2가 목록에 있는지 확인

# Step 3: Node1에서 동일 업그레이드
sudo systemctl stop mariadb
sudo apt upgrade mariadb-server
sudo systemctl start mariadb
```

---

### 4.3 garb(Arbiter) 재시작

```bash
# garb 서버에서
sudo systemctl restart garbd

# 상태 확인
systemctl status garbd
sudo tail -20 /GPMS/LOG/mariadb/garbd.log
```

**Node에서 확인:**
```sql
SHOW STATUS LIKE 'wsrep_cluster_size';  -- 계속 3이어야 함
```

---

## 5. 긴급 조치

### 5.1 특정 노드 강제 제거 (evict)

한 노드가 계속 문제를 일으키는 경우:

```sql
-- Primary 그룹의 다른 노드에서
SET GLOBAL wsrep_provider_options='evict=<node_uuid>';
```

> 일반적으로 자동으로 처리되므로 수동 조치 거의 불필요

---

### 5.2 Split-Brain 복구

양쪽 그룹이 Primary라고 생각하는 상태:

**증상:**
```sql
-- 한 노드
SHOW STATUS LIKE 'wsrep_cluster_status';  -- Primary

-- 다른 노드
SHOW STATUS LIKE 'wsrep_cluster_status';  -- Primary (잘못됨)
```

**복구:**
```bash
# 더 많은 트랜잭션을 가진 노드 확인
# (grastate.dat seqno가 큰 노드)

# Non-Primary 그룹의 노드에서
sudo systemctl stop mariadb
sudo systemctl start mariadb
# → Primary 그룹으로 자동 복구
```

---

## 6. 성능 최적화

### 6.1 wsrep_cache_size 조정

```ini
# /etc/my.cnf.d/galera.cnf
[mysqld]
wsrep_provider_options="cache_size=330M"  # 기본값, 필요시 증가
```

### 6.2 Flow Control 임계값

```ini
[mysqld]
wsrep_provider_options="gcs.fc_limit=256;gcs.fc_factor=0.9"
# fc_limit: 캐시 크기, 커질수록 더 많은 쓰기 허용
# fc_factor: 임계값 비율 (0.9 = 90% 찼을 때 제한)
```

---

## 7. 모니터링 스크립트

### 7.1 주기적 상태 확인 (cron)

```bash
#!/bin/bash
# /usr/local/bin/galera-health.sh

CLUSTER_SIZE=$(mysql -h localhost -e "SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cluster_size';" -s -N 2>/dev/null)
CLUSTER_STATUS=$(mysql -h localhost -e "SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cluster_status';" -s -N 2>/dev/null)
FLOW_CONTROL=$(mysql -h localhost -e "SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_flow_control_paused';" -s -N 2>/dev/null)

if [ "$CLUSTER_SIZE" != "3" ] || [ "$CLUSTER_STATUS" != "Primary" ]; then
    echo "ALERT: Galera Cluster Issue"
    echo "Cluster Size: $CLUSTER_SIZE (expected 3)"
    echo "Cluster Status: $CLUSTER_STATUS (expected Primary)"
    # 이메일/Slack 알림 발송
fi

if (( $(echo "$FLOW_CONTROL > 0.1" | bc -l) )); then
    echo "WARNING: Flow Control Paused > 10% ($FLOW_CONTROL)"
fi
```

**crontab 등록:**
```bash
# 15분마다 실행
*/15 * * * * /usr/local/bin/galera-health.sh >> /var/log/galera-health.log 2>&1
```

---

## 8. 자주 묻는 질문 (FAQ)

### Q1: 한 노드의 데이터가 손상되었어도 안전한가?
**A:** 예. Galera는 모든 노드가 동일 데이터를 유지하므로, 손상된 노드는 다른 노드에서 SST로 복구됩니다.

### Q2: 읽기 성능이 중요하면?
**A:** 모든 노드에서 읽기 가능합니다. 로드 밸런서를 사용하여 3개 노드에 분산하면 읽기 처리량 증가.

### Q3: garb 없이 2멤버만 운영 가능?
**A:** 가능하나 권장하지 않음. 한 노드 다운 시 자동 페일오버 불가. garb 추가 권장.

### Q4: 쓰기 성능은?
**A:** 모든 쓰기가 모든 노드에 동기화되므로 단일 서버보다 느림. 하지만 고가용성 확보.

### Q5: 네트워크 파티션 발생 시?
**A:** Primary 그룹 > Non-Primary 그룹 (쿼럼 기준). Non-Primary 그룹은 쓰기 차단.

---

## 9. 통보 및 문서

### 긴급 연락처

| 역할 | 연락처 | 담당 사항 |
|------|--------|-----------|
| DBA | `dba@company.com` | Galera 운영 |
| 시스템팀 | `ops@company.com` | 인프라 |
| 개발팀 | `dev@company.com` | 애플리케이션 |

### 문서 참고

- MariaDB Galera 공식: https://mariadb.com/kb/en/galera/
- gcomm 설정: https://mariadb.com/kb/en/galera-cluster-system-variables/

---

## 10. 변경 로그

| 날짜 | 사건 | 조치 |
|------|------|------|
| 9/1 15:46 | Node1 crash (aria lock) | 자동 재기동 |
| 9/2 11:32 | Node2 Disconnected | 데이터 경로 확인 |
| 9/2 13:57 | Node2 재조인 완료 | ✅ 클러스터 정상화 |

---

**문서 작성:** 박영준 대표님  
**마지막 업데이트:** 2026-09-02 14:08  
**상태:** ✅ 정상 운영 중

