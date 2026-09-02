#!/bin/bash
################################################################################
# GPMS Galera Cluster Dashboard
# 작성: 2026-09-02
# 용도: 실시간 클러스터 상태 모니터링 대시보드
# 실행: ./galera-dashboard.sh
################################################################################

set -e

# 설정
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASS="${MYSQL_PASS:-}"
REFRESH_INTERVAL=5  # 초 단위

################################################################################
# 색상 정의
################################################################################

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Color

################################################################################
# 함수 정의
################################################################################

run_mysql_query() {
    local query="$1"
    if [ -z "$MYSQL_PASS" ]; then
        mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -e "$query" -s -N 2>/dev/null || echo "ERROR"
    else
        mysql -h "$MYSQL_HOST" -P "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASS" -e "$query" -s -N 2>/dev/null || echo "ERROR"
    fi
}

get_status() {
    local query="SELECT 
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cluster_size') as cluster_size,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cluster_status') as cluster_status,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_local_state_comment') as node_state,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_ready') as ready,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_connected') as connected,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_flow_control_paused') as flow_control,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_cert_deps_distance') as cert_deps,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_local_recv_queue') as recv_queue,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_local_send_queue') as send_queue,
        (SELECT VARIABLE_VALUE FROM information_schema.GLOBAL_STATUS WHERE VARIABLE_NAME='wsrep_incoming_addresses') as members,
        @@wsrep_node_name as node_name,
        NOW() as timestamp;"
    run_mysql_query "$query"
}

format_status() {
    local value="$1"
    case "$value" in
        "Primary") echo -e "${GREEN}✓ Primary${NC}" ;;
        "Synced") echo -e "${GREEN}✓ Synced${NC}" ;;
        "ON") echo -e "${GREEN}✓ ON${NC}" ;;
        "Non-Primary") echo -e "${YELLOW}⚠ Non-Primary${NC}" ;;
        "Disconnected") echo -e "${RED}✗ Disconnected${NC}" ;;
        "Joining"|"Joined") echo -e "${YELLOW}⟳ $value${NC}" ;;
        "Donor"|"Desynced") echo -e "${YELLOW}⟳ $value${NC}" ;;
        "OFF") echo -e "${RED}✗ OFF${NC}" ;;
        "ERROR") echo -e "${RED}✗ ERROR${NC}" ;;
        *) echo "$value" ;;
    esac
}

color_number() {
    local value="$1"
    local good_min="${2:-0}"
    local good_max="${3:-999999}"
    
    if [ "$value" = "ERROR" ]; then
        echo -e "${RED}$value${NC}"
    elif [ "$value" -ge "$good_min" ] && [ "$value" -le "$good_max" ]; then
        echo -e "${GREEN}$value${NC}"
    else
        echo -e "${RED}$value${NC}"
    fi
}

draw_gauge() {
    local value="$1"
    local max="${2:-100}"
    local width=20
    
    local filled=$(( (value * width) / max ))
    local empty=$(( width - filled ))
    
    local bar="["
    for ((i = 0; i < filled; i++)); do bar+="█"; done
    for ((i = 0; i < empty; i++)); do bar+="░"; done
    bar+="]"
    
    if (( $(echo "$value > 50" | bc -l) )); then
        echo -e "${RED}$bar${NC}"
    elif (( $(echo "$value > 25" | bc -l) )); then
        echo -e "${YELLOW}$bar${NC}"
    else
        echo -e "${GREEN}$bar${NC}"
    fi
}

clear_screen() {
    clear
    echo -ne "\033[H"  # Move cursor to top
}

draw_header() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                    🔍 GPMS Galera Cluster Monitor - Real-time Dashboard                    ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

draw_footer() {
    local uptime=$(uptime | awk -F'up' '{print $2}' | cut -d',' -f1)
    local next_refresh=$(($(date +%s) + REFRESH_INTERVAL))
    local next_time=$(date -d @$next_refresh '+%H:%M:%S')
    
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "System Uptime: $uptime | Next refresh: ${BLUE}$next_time${NC} | Press Ctrl+C to exit"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════════════════════${NC}"
}

################################################################################
# 메인 루프
################################################################################

main() {
    echo "Connecting to MySQL at $MYSQL_HOST:$MYSQL_PORT..."
    echo "Press any key to start..."
    read -t 3 -n 1 || true
    
    while true; do
        clear_screen
        draw_header
        
        # 데이터 조회
        local data=$(get_status)
        
        if [ "$data" = "ERROR" ]; then
            echo -e "${RED}❌ Cannot connect to MySQL at $MYSQL_HOST:$MYSQL_PORT${NC}"
            echo ""
            echo "Retrying in $REFRESH_INTERVAL seconds..."
        else
            # 파싱
            IFS=$'\t' read -r cluster_size cluster_status node_state ready connected flow_control cert_deps recv_queue send_queue members node_name timestamp <<< "$data"
            
            # 상태 판정
            local overall_status="OK"
            if [ "$cluster_status" != "Primary" ] || [ "$node_state" != "Synced" ]; then
                overall_status="⚠️ WARNING"
            fi
            if [ "$ready" = "OFF" ] || [ "$connected" = "OFF" ]; then
                overall_status="🚨 CRITICAL"
            fi
            
            # 노드 정보
            echo -e "${BLUE}┌─ Node Information${NC}"
            echo -e "│  Node Name: ${CYAN}$node_name${NC}"
            echo -e "│  Timestamp: $timestamp"
            echo -e "│  Status: $overall_status"
            echo -e "${BLUE}└──────────────────────────────────────────────────────────────────────────────────────────${NC}"
            echo ""
            
            # 클러스터 상태
            echo -e "${BLUE}┌─ Cluster Status${NC}"
            echo -e "│  Cluster Size: $(color_number "$cluster_size" 2 999)"
            echo -e "│  Cluster Status: $(format_status "$cluster_status")"
            echo -e "│  Available Members: ${CYAN}$members${NC}"
            echo -e "${BLUE}└──────────────────────────────────────────────────────────────────────────────────────────${NC}"
            echo ""
            
            # 노드 상태
            echo -e "${BLUE}┌─ Node Status${NC}"
            echo -e "│  Node State: $(format_status "$node_state")"
            echo -e "│  Ready: $(format_status "$ready")"
            echo -e "│  Connected: $(format_status "$connected")"
            echo -e "${BLUE}└──────────────────────────────────────────────────────────────────────────────────────────${NC}"
            echo ""
            
            # 성능 지표
            echo -e "${BLUE}┌─ Performance Metrics${NC}"
            echo -e "│  Flow Control Paused: $(draw_gauge "${flow_control%.*}" 100) ${CYAN}${flow_control}${NC}"
            echo -e "│  Cert Deps Distance: $(draw_gauge "$cert_deps" 100) ${CYAN}${cert_deps}${NC}"
            echo -e "│  Recv Queue: ${CYAN}$recv_queue${NC}"
            echo -e "│  Send Queue: ${CYAN}$send_queue${NC}"
            echo -e "${BLUE}└──────────────────────────────────────────────────────────────────────────────────────────${NC}"
            echo ""
        fi
        
        draw_footer
        sleep "$REFRESH_INTERVAL"
    done
}

# 실행
trap 'echo -e "\n${YELLOW}Monitor stopped${NC}"; exit 0' SIGINT SIGTERM
main "$@"
