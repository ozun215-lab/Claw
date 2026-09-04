#!/bin/bash
################################################################################
# GPMS Galera Cluster Health Check Script
# 작성: 2026-09-02
# 용도: 주기적 클러스터 상태 모니터링 및 알람
# 설치: /usr/local/bin/galera-health-check.sh
# 권한: chmod +x /usr/local/bin/galera-health-check.sh
################################################################################

set -e

# 설정
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASS="${MYSQL_PASS:-gooroom}"  # 비밀번호 설정
LOG_FILE="/var/log/galera-health-check.log"
ALERT_LOG="/var/log/galera-alerts.log"

# 임계값
CLUSTER_SIZE_MIN=2          # 최소 클러스터 크기 (garb 포함 가능)
FLOW_CONTROL_THRESHOLD=0.1  # Flow Control 임계값 (10%)
CERT_DEPS_THRESHOLD=50      # 인증 거리 임계값

# 알람 설정
ALERT_EMAIL="dba@company.com"
ENABLE_EMAIL_ALERT=false    # true로 변경하여 이메일 알람 활성화
ENABLE_SLACK_ALERT=false    # true로 변경하여 Slack 알람 활성화
SLACK_WEBHOOK=""            # Slack Webhook URL

################################################################################
# 함수 정의
################################################################################

log_message() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" >> "$LOG_FILE"
}

run_mysql_query() {
    local query="$1"
    # 소켓으로 연결 (TCP 대신 로컬 소켓 사용)
    mysql --socket=/GPMS/DBMS/DATA/mysql.sock -u "$MYSQL_USER" -p"$MYSQL_PASS" -sN -e "$query" 2>/dev/null || echo "ERROR"
}

send_email_alert() {
    local subject="$1"
    local message="$2"
    
    if [ "$ENABLE_EMAIL_ALERT" = true ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL" 2>/dev/null || true
        log_message "ALERT" "Email sent: $subject"
    fi
}

send_slack_alert() {
    local message="$1"
    local color="$2"  # "danger" or "warning"
    
    if [ "$ENABLE_SLACK_ALERT" = true ] && [ -n "$SLACK_WEBHOOK" ]; then
        local payload=$(cat <<EOF
{
    "attachments": [
        {
            "color": "$color",
            "title": "🚨 Galera Cluster Alert",
            "text": "$message",
            "footer": "GPMS Galera Monitor",
            "ts": $(date +%s)
        }
    ]
}
EOF
)
        curl -X POST -H 'Content-type: application/json' \
            --data "$payload" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
        log_message "ALERT" "Slack notification sent"
    fi
}

check_mysql_connection() {
    local result=$(run_mysql_query "SELECT 1")
    if [ "$result" = "ERROR" ] || [ -z "$result" ]; then
        log_message "ERROR" "MySQL connection failed on $MYSQL_HOST:$MYSQL_PORT"
        send_email_alert "🚨 GPMS Galera: MySQL Connection Failed" \
            "Cannot connect to MySQL on $MYSQL_HOST:$MYSQL_PORT\n\nPlease check immediately."
        return 1
    fi
    return 0
}

get_cluster_status() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cluster_size';"
    run_mysql_query "$query"
}

get_cluster_state() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cluster_status';"
    run_mysql_query "$query"
}

get_node_state() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_local_state_comment';"
    run_mysql_query "$query"
}

get_node_ready() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_ready';"
    run_mysql_query "$query"
}

get_node_connected() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_connected';"
    run_mysql_query "$query"
}

get_flow_control() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_flow_control_paused';"
    run_mysql_query "$query"
}

get_cert_deps_distance() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cert_deps_distance';"
    run_mysql_query "$query"
}

get_incoming_addresses() {
    local query="SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_incoming_addresses';"
    run_mysql_query "$query"
}

get_node_name() {
    local query="SELECT @@wsrep_node_name;"
    run_mysql_query "$query"
}

################################################################################
# 메인 체크 함수
################################################################################

check_cluster_health() {
    local cluster_size=$(get_cluster_status)
    local cluster_state=$(get_cluster_state)
    local node_state=$(get_node_state)
    local node_ready=$(get_node_ready)
    local node_connected=$(get_node_connected)
    local flow_control=$(get_flow_control)
    local cert_deps=$(get_cert_deps_distance)
    local incoming=$(get_incoming_addresses)
    local node_name=$(get_node_name)
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local status="OK"
    local alerts=""
    
    # 로그에 기본 정보 기록
    log_message "INFO" "Node: $node_name | Cluster Size: $cluster_size | State: $cluster_state | Node State: $node_state"
    
    # 1. 클러스터 크기 확인
    if [ "$cluster_size" = "ERROR" ]; then
        status="CRITICAL"
        alerts="${alerts}\n❌ CRITICAL: Cannot query cluster size"
    elif [ "$cluster_size" -lt "$CLUSTER_SIZE_MIN" ]; then
        status="WARNING"
        alerts="${alerts}\n⚠️ WARNING: Cluster size ($cluster_size) < minimum ($CLUSTER_SIZE_MIN)"
    fi
    
    # 2. 클러스터 상태 확인
    if [ "$cluster_state" != "Primary" ]; then
        if [ "$cluster_state" = "Disconnected" ]; then
            status="CRITICAL"
            alerts="${alerts}\n❌ CRITICAL: Cluster status is DISCONNECTED"
        else
            status="WARNING"
            alerts="${alerts}\n⚠️ WARNING: Cluster status is $cluster_state (not Primary)"
        fi
    fi
    
    # 3. 노드 상태 확인
    if [ "$node_state" != "Synced" ]; then
        if [ "$node_state" = "ERROR" ]; then
            status="CRITICAL"
            alerts="${alerts}\n❌ CRITICAL: Cannot query node state"
        else
            status="WARNING"
            alerts="${alerts}\n⚠️ WARNING: Node state is $node_state (not Synced)"
        fi
    fi
    
    # 4. 노드 준비 상태 확인
    if [ "$node_ready" = "OFF" ]; then
        status="CRITICAL"
        alerts="${alerts}\n❌ CRITICAL: wsrep_ready is OFF"
    fi
    
    # 5. 노드 연결 상태 확인
    if [ "$node_connected" = "OFF" ]; then
        status="CRITICAL"
        alerts="${alerts}\n❌ CRITICAL: wsrep_connected is OFF"
    fi
    
    # 6. Flow Control 확인 (숫자 비교)
    if [ "$flow_control" != "ERROR" ]; then
        if (( $(echo "$flow_control > $FLOW_CONTROL_THRESHOLD" | bc -l) )); then
            status="WARNING"
            alerts="${alerts}\n⚠️ WARNING: Flow control paused ($flow_control) > threshold ($FLOW_CONTROL_THRESHOLD)"
        fi
    fi
    
    # 7. 인증 거리 확인
    if [ "$cert_deps" != "ERROR" ]; then
        if [ "$cert_deps" -gt "$CERT_DEPS_THRESHOLD" ]; then
            status="WARNING"
            alerts="${alerts}\n⚠️ WARNING: Cert deps distance ($cert_deps) > threshold ($CERT_DEPS_THRESHOLD)"
        fi
    fi
    
    # 결과 저장 및 출력
    local report="
===============================================
GPMS Galera Cluster Health Check
===============================================
Timestamp: $timestamp
Node: $node_name
Host: $(hostname -I | awk '{print $1}'):3306
Status: $status

CLUSTER INFORMATION:
  Cluster Size: $cluster_size
  Cluster Status: $cluster_state
  Node State: $node_state
  Ready: $node_ready
  Connected: $node_connected
  Incoming Addresses: $incoming

PERFORMANCE METRICS:
  Flow Control Paused: $flow_control
  Cert Deps Distance: $cert_deps

ALERTS:
$alerts

===============================================
"
    
    echo "$report"
    log_message "$status" "$report"
    
    # 알람 발송
    if [ "$status" = "CRITICAL" ]; then
        send_email_alert "🚨 GPMS Galera: CRITICAL Alert" "$report"
        send_slack_alert "$(echo -e "$report" | head -20)" "danger"
    elif [ "$status" = "WARNING" ]; then
        send_email_alert "⚠️ GPMS Galera: Warning Alert" "$report"
        send_slack_alert "$(echo -e "$report" | head -20)" "warning"
    fi
    
    # 상태 코드 반환
    case "$status" in
        OK) return 0 ;;
        WARNING) return 1 ;;
        CRITICAL) return 2 ;;
        *) return 3 ;;
    esac
}

################################################################################
# 메인 실행
################################################################################

main() {
    # 로그 초기화 (날짜별 로테이션)
    if [ ! -d "$(dirname "$LOG_FILE")" ]; then
        mkdir -p "$(dirname "$LOG_FILE")"
    fi
    
    log_message "INFO" "=== Galera Health Check Started ==="
    
    # MySQL 연결 확인
    if ! check_mysql_connection; then
        log_message "CRITICAL" "Cannot proceed without MySQL connection"
        exit 2
    fi
    
    # 클러스터 상태 확인
    check_cluster_health
    exit_code=$?
    
    log_message "INFO" "=== Galera Health Check Completed (exit code: $exit_code) ==="
    exit $exit_code
}

# 실행
main "$@"
