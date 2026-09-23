const http = require('http');
const os = require('os');

// Dashboard 데이터 저장소
let dashboardData = {
  lastUpdate: new Date(),
  longCandidates: [],
  shortCandidates: [],
  positions: [],
  alerts: [],
  statistics: {
    totalScanned: 0,
    topLongScore: 0,
    topShortScore: 0
  }
};

const getDashboardHTML = () => `
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bybit Trading Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0e27; color: #e0e0e0; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        h1 { font-size: 32px; margin-bottom: 5px; }
        .timestamp { font-size: 12px; opacity: 0.8; }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin-bottom: 20px; }
        
        .card { 
            background: #1a1f3a; 
            border: 1px solid #2d3561; 
            border-radius: 8px; 
            padding: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        
        .card h3 { color: #667eea; margin-bottom: 10px; font-size: 14px; text-transform: uppercase; }
        .card-value { font-size: 24px; font-weight: bold; }
        
        .tab-buttons { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .tab-btn {
            background: #2d3561;
            border: 1px solid #444;
            color: #e0e0e0;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .tab-btn.active {
            background: #667eea;
            border-color: #667eea;
            color: white;
        }
        
        .candidate-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; }
        
        .candidate-item {
            background: #1a1f3a;
            border-left: 4px solid #667eea;
            padding: 12px;
            border-radius: 4px;
        }
        
        .candidate-item.short { border-left-color: #ff6b6b; }
        
        .position-item {
            background: #1a2d4d;
            border-left: 4px solid #11b981;
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        
        .symbol { font-size: 16px; font-weight: bold; margin-bottom: 5px; }
        .score { 
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
        }
        .score.high { background: #11b981; }
        
        .stats { font-size: 11px; margin-top: 8px; opacity: 0.7; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Bybit Trading Dashboard</h1>
            <div class="timestamp">Last updated: <span id="timestamp">${new Date().toLocaleString()}</span></div>
        </header>
        
        <div class="grid">
            <div class="card">
                <h3>🎯 Total Scanned</h3>
                <div class="card-value" id="totalScanned">0</div>
            </div>
            <div class="card">
                <h3>🟢 Top Long Score</h3>
                <div class="card-value" id="topLongScore">0</div>
            </div>
            <div class="card">
                <h3>🔴 Top Short Score</h3>
                <div class="card-value" id="topShortScore">0</div>
            </div>
            <div class="card">
                <h3>💼 Active Positions</h3>
                <div class="card-value" id="activePositions">0</div>
            </div>
        </div>
        
        <div class="tab-buttons">
            <button class="tab-btn active" onclick="showTab('positions')">💼 Active Positions</button>
            <button class="tab-btn" onclick="showTab('longs')">🟢 Long Candidates</button>
            <button class="tab-btn" onclick="showTab('shorts')">🔴 Short Candidates</button>
            <button class="tab-btn" onclick="showTab('alerts')">🔔 Alerts</button>
        </div>
        
        <div id="positions-tab" style="display: block;">
            <h2 style="margin-bottom: 15px;">💼 Active Positions (with TP)</h2>
            <div id="positionList">
                <div style="opacity: 0.6;">활성 포지션 없음</div>
            </div>
        </div>
        
        <div id="longs-tab" style="display: none;">
            <h2 style="margin-bottom: 15px;">🟢 Long Candidates (Entry only)</h2>
            <div class="candidate-list" id="longList">
                <div style="opacity: 0.6;">로딩 중...</div>
            </div>
        </div>
        
        <div id="shorts-tab" style="display: none;">
            <h2 style="margin-bottom: 15px;">🔴 Short Candidates (Entry only)</h2>
            <div class="candidate-list" id="shortList">
                <div style="opacity: 0.6;">로딩 중...</div>
            </div>
        </div>
        
        <div id="alerts-tab" style="display: none;">
            <h2 style="margin-bottom: 15px;">🔔 Alerts</h2>
            <div id="alertList" style="background: #1a1f3a; border-radius: 8px; padding: 15px;">
                <div style="opacity: 0.6;">알림 없음</div>
            </div>
        </div>
    </div>
    
    <script>
        function showTab(tab) {
            document.querySelectorAll('[id$="-tab"]').forEach(el => el.style.display = 'none');
            document.getElementById(tab + '-tab').style.display = 'block';
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            event.target.classList.add('active');
        }
        
        async function updateDashboard() {
            try {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                
                document.getElementById('timestamp').textContent = new Date().toLocaleString();
                document.getElementById('totalScanned').textContent = data.statistics.totalScanned;
                document.getElementById('topLongScore').textContent = data.statistics.topLongScore || 0;
                document.getElementById('topShortScore').textContent = data.statistics.topShortScore || 0;
                document.getElementById('activePositions').textContent = data.positions.length;
                
                // Render positions (with TP)
                const positionList = document.getElementById('positionList');
                if (data.positions.length > 0) {
                    positionList.innerHTML = data.positions.map(p => \`
                        <div class="position-item">
                            <div class="symbol">\${p.symbol} <span class="score">\${p.direction}</span></div>
                            <div style="margin-top: 8px; font-size: 12px;">
                                <div>📍 진입: \$\${p.entryPrice}</div>
                                <div>🛑 SL: \$\${p.sl}</div>
                                <div style="color: #11b981; font-weight: bold;">✅ TP1: \$\${p.tp1}</div>
                                <div style="color: #11b981; font-weight: bold;">✅ TP2: \$\${p.tp2}</div>
                                <div style="margin-top: 5px; padding-top: 5px; border-top: 1px solid #2d3561;">현재: \$\${p.currentPrice} <span style="color: \${p.pnl.includes('-') ? '#ff6b6b' : '#11b981'};">\${p.pnl}%</span></div>
                            </div>
                        </div>
                    \`).join('');
                }
                
                // Render longs (후보 - SL, Entry만 표시)
                const longList = document.getElementById('longList');
                if (data.longCandidates.length > 0) {
                    longList.innerHTML = data.longCandidates.slice(0, 12).map(c => \`
                        <div class="candidate-item">
                            <div class="symbol">\${c.symbol}</div>
                            <span class="score high">\${c.score}</span>
                            <div style="margin-top: 8px; font-size: 12px;">
                                <div>📍 진입: \$\${c.price}</div>
                                <div>🛑 SL: \$\${(parseFloat(c.price) * 0.97).toFixed(c.price < 0.1 ? 6 : 4)}</div>
                                <div style="margin-top: 5px; border-top: 1px solid #2d3561; padding-top: 5px;">
                                    <div>📈 24h: \${c.chg24}%</div>
                                    <div>📊 Funding: \${c.fund}%</div>
                                </div>
                            </div>
                        </div>
                    \`).join('');
                }
                
                // Render shorts (후보 - SL, Entry만 표시)
                const shortList = document.getElementById('shortList');
                if (data.shortCandidates.length > 0) {
                    shortList.innerHTML = data.shortCandidates.slice(0, 12).map(c => \`
                        <div class="candidate-item short">
                            <div class="symbol">\${c.symbol}</div>
                            <span class="score high">\${c.score}</span>
                            <div style="margin-top: 8px; font-size: 12px;">
                                <div>📍 진입: \$\${c.price}</div>
                                <div>🛑 SL: \$\${(parseFloat(c.price) * 1.03).toFixed(c.price < 0.1 ? 6 : 4)}</div>
                                <div style="margin-top: 5px; border-top: 1px solid #2d3561; padding-top: 5px;">
                                    <div>📈 24h: \${c.chg24}%</div>
                                    <div>📊 Funding: \${c.fund}%</div>
                                </div>
                            </div>
                        </div>
                    \`).join('');
                }
                
                // Render alerts
                const alertList = document.getElementById('alertList');
                if (data.alerts.length > 0) {
                    alertList.innerHTML = data.alerts.slice(-15).map(a => \`
                        <div style="background: #2d3561; padding: 10px; margin-bottom: 8px; border-radius: 4px; border-left: 3px solid #667eea;">
                            <div>\${a.message}</div>
                            <div style="opacity: 0.6; font-size: 11px; margin-top: 5px;">\${new Date(a.timestamp).toLocaleString()}</div>
                        </div>
                    \`).join('');
                }
            } catch (e) {
                console.error('Dashboard update error:', e);
            }
        }
        
        updateDashboard();
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>
`;

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.url === '/' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(getDashboardHTML());
  } 
  else if (req.url === '/api/dashboard' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(dashboardData, null, 2));
  }
  else if (req.url === '/api/update' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const newData = JSON.parse(body);
        dashboardData = { ...dashboardData, ...newData, lastUpdate: new Date() };
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok' }));
      } catch (e) {
        res.writeHead(400);
        res.end('Invalid JSON');
      }
    });
  }
  else if (req.url === '/api/position/add' && req.method === 'POST') {
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        const position = JSON.parse(body);
        dashboardData.positions.push(position);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'ok', positionCount: dashboardData.positions.length }));
      } catch (e) {
        res.writeHead(400);
        res.end('Invalid JSON');
      }
    });
  }
  else if (req.url.startsWith('/api/position/close/') && req.method === 'POST') {
    const symbol = req.url.split('/').pop();
    dashboardData.positions = dashboardData.positions.filter(p => p.symbol !== symbol);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', positionCount: dashboardData.positions.length }));
  }
  else {
    res.writeHead(404);
    res.end('Not found');
  }
});

function getLocalIP() {
  const interfaces = os.networkInterfaces();
  for (const name of Object.keys(interfaces)) {
    for (const iface of interfaces[name]) {
      if (iface.family === 'IPv4' && !iface.internal) {
        return iface.address;
      }
    }
  }
  return 'localhost';
}

const PORT = process.env.PORT || 3000;
const localIP = getLocalIP();

server.listen(PORT, '0.0.0.0', () => {
  console.log(`
╔════════════════════════════════════════════════════════════╗
║           📊 Bybit Trading Dashboard - Updated             ║
╚════════════════════════════════════════════════════════════╝

✨ 개선 사항:
   ✅ 진입 중인 포지션에만 TP1/TP2 표시
   ✅ 후보에는 진입가 + SL만 표시
   ✅ 포지션 추가/제거 API 엔드포인트

📱 접속:
   Local:   http://localhost:${PORT}
   Network: http://${localIP}:${PORT}

🔌 API 엔드포인트:
   GET  /api/dashboard           - 모든 데이터 조회
   POST /api/update              - 후보 데이터 업데이트
   POST /api/position/add        - 포지션 추가
   POST /api/position/close/SYMBOL - 포지션 종료

`);
});

process.on('SIGINT', () => {
  console.log('\n🛑 Dashboard stopped');
  process.exit(0);
});
