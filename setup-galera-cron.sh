#!/bin/bash
################################################################################
# Galera Health Check - crontab 설치 스크립트
# 작성: 2026-09-02
# 용도: 모니터링 스크립트를 자동으로 cron에 등록
# 실행: sudo bash setup-galera-cron.sh
################################################################################

set -e

echo "================================================"
echo "GPMS Galera Health Check - Cron Setup"
echo "================================================"

SCRIPT_PATH="/usr/local/bin/galera-health-check.sh"
LOG_DIR="/var/log"
CRON_SCHEDULE="*/10 * * * *"  # 10분마다 실행

# Step 1: 스크립트 복사 및 권한 설정
echo ""
echo "[1/4] Installing health check script..."
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "⚠️ Script not found at $SCRIPT_PATH"
    echo "Please copy galera-health-check.sh to $SCRIPT_PATH first"
    exit 1
fi

chmod +x "$SCRIPT_PATH"
echo "✅ Script installed at $SCRIPT_PATH"

# Step 2: 로그 디렉토리 생성
echo ""
echo "[2/4] Setting up log directories..."
mkdir -p "$LOG_DIR"
touch "$LOG_DIR/galera-health-check.log"
touch "$LOG_DIR/galera-alerts.log"
chmod 644 "$LOG_DIR/galera-health-check.log"
chmod 644 "$LOG_DIR/galera-alerts.log"
echo "✅ Log files created"

# Step 3: crontab 설정
echo ""
echo "[3/4] Configuring crontab..."

# 기존 항목 확인
if crontab -l 2>/dev/null | grep -q "galera-health-check.sh"; then
    echo "⚠️ galera-health-check.sh already in crontab"
    crontab -l | grep "galera-health-check"
else
    # 새로운 cron 항목 추가
    (crontab -l 2>/dev/null || echo "") | cat - <<EOF | crontab -
# GPMS Galera Cluster Health Check
# 10분마다 실행 (6:00 ~ 22:00, 주중만)
*/10 6-22 * * 1-5 $SCRIPT_PATH >> $LOG_DIR/galera-health-check.log 2>&1

# 야간 체크 (22:00 ~ 06:00, 매 30분)
*/30 22-23,0-5 * * * $SCRIPT_PATH >> $LOG_DIR/galera-health-check.log 2>&1

# 주말 체크 (매 30분)
*/30 * * * 0,6 $SCRIPT_PATH >> $LOG_DIR/galera-health-check.log 2>&1
EOF
    echo "✅ Crontab configured"
fi

# Step 4: .my.cnf 설정 (MySQL 자격증명)
echo ""
echo "[4/4] MySQL credentials configuration..."
if [ ! -f "/root/.my.cnf" ]; then
    echo ""
    echo "⚠️ /root/.my.cnf not found"
    echo "Creating /root/.my.cnf..."
    cat > /root/.my.cnf <<EOF
[client]
user=root
password=gooroom
host=localhost
port=3306
EOF
    chmod 600 /root/.my.cnf
    echo "✅ /root/.my.cnf created"
else
    echo "✅ /root/.my.cnf already exists"
fi

# 최종 확인
echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "📋 Configuration Summary:"
echo "  Script: $SCRIPT_PATH"
echo "  Logs: $LOG_DIR/galera-health-check.log"
echo "  Alerts: $LOG_DIR/galera-alerts.log"
echo ""
echo "📅 Cron Schedule:"
crontab -l 2>/dev/null | grep galera || echo "No cron entries found"
echo ""
echo "🧪 Quick Test:"
echo "  Run: $SCRIPT_PATH"
echo ""
echo "📊 View Logs:"
echo "  Health: tail -f $LOG_DIR/galera-health-check.log"
echo "  Alerts: tail -f $LOG_DIR/galera-alerts.log"
echo ""
