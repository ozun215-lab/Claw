const http = require('http');
const fs = require('fs');
const path = require('path');

// Dashboard 데이터 저장소
let dashboardData = {
  lastUpdate: new Date(),
  longCandidates: [],
  shortCandidates: [],
  positions: [],
  alerts: [],
  statistics: {
    totalScanned: 0,
    topScore: 0,
    avgScore: 0
  }
};

// 기본 대시보드 HTML
const getDashboardHTML = () => `
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bybit Trading Dashboard - Fibonacci Enhanced</title>
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
        .card-subtext { font-size: 12px; opacity: 0.6; margin-top: 5px; }
        
        .candidates { margin-top: 20px; }
        .candidate-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; }
        
        .candidate-item {
            background: #1a1f3a;
            border-left: 4px solid #667eea;
            padding: 12px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .candidate-item:hover { 
            transform: translateY(-2px); 
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
            border-left-color: #764ba2;
        }
        
        .candidate-item.short { border-left-color: #ff6b6b; }
        .candidate-item.short:hover { border-left-color: #ff8787; }
        
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
        .score.medium { background: #f59e0b; }
        .score.low { background: #ef4444; }
        
        .stats { font-size: 11px; margin-top: 8px; opacity: 0.7; }
        .stat { display: inline-block; margin-right: 10px; }
        
        .alerts { background: #1a1f3a; border: 1px solid #2d3561; border-radius: 8px; padding: 15px; }
        .alert-item { 
            background: #2d3561; 
            padding: 10px; 
            margin-bottom: 8px; 
            border-radius: 4px;
            border-left: 3px solid #667eea;
            font-size: 12px;
        }
        .alert-time { opacity: 0.6; font-size: 11px; }
        
        .tab-buttons { display: flex; gap: 10px; margin-bottom: 15px; }
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
        
        .loading { text-align: center; opacity: 0.6; }
        .spinner { 
            display: inline-block; 
            width: 20px; 
            height: 20px; 
            border: 2px solid #667eea; 
            border-radius: 50%; 
            border-top-color: transparent;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
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
                <h3>🎯 Total Symbols Scanned</h3>
                <div class="card-value" id="totalScanned">0</div>
            </div>
            <div class="card">
                <h3>🔥 Top Long Score</h3>
                <div class="card-value" id="topLongScore">0</div>
            </div>
            <div class="card">
                <h3>❄️ Top Short Score</h3>
                <div class="card-value" id="topShortScore">0</div>
            </div>
            <div class="card">
                <h3>💼 Active Positions</h3>
                <div class="card-value" id="activePositions">0</div>
            </div>
        </div>
        
        <div class="tab-buttons">
            <button class="tab-btn active" onclick="showTab('longs')">🟢 Long Candidates</button>
            <button class="tab-btn" onclick="showTab('shorts')">🔴 Short Candidates</button>
            <button class="tab-btn" onclick="showTab('alerts')">🔔 Alerts</button>
        </div>
        
        <div id="longs-tab" style="display: block;">
            <h2 style="margin-bottom: 15px;">Long Entry Candidates (Fibonacci Enhanced)</h2>
            <div class="candidate-list" id="longList">
                <div class="loading"><div class="spinner"></div> Loading...</div>
            </div>
        </div>
        
        <div id="shorts-tab" style="display: none;">
            <h2 style="margin-bottom: 15px;">Short Entry Candidates (Fibonacci Enhanced)</h2>
            <div class="candidate-list" id="shortList">
                <div class="loading"><div class="spinner"></div> Loading...</div>
            </div>
        </div>
        
        <div id="alerts-tab" style="display: none;">
            <div class="alerts">
                <h2 style="margin-bottom: 15px;">📢 Recent Alerts</h2>
                <div id="alertList">
                    <div style="opacity: 0.6; text-align: center;">No alerts yet</div>
                </div>
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
                
                // Render longs
                const longList = document.getElementById('longList');
                if (data.longCandidates.length > 0) {
                    longList.innerHTML = data.longCandidates.slice(0, 12).map(c => \`
                        <div class="candidate-item">
                            <div class="symbol">\${c.symbol}</div>
                            <span class="score high">\${c.score}</span>
                            <div style="margin-top: 8px; font-size: 12px;">
                                <div>💰 Price: \$\${c.price}</div>
                                <div>📈 24h: \${c.chg24}%</div>
                                <div>📊 Funding: \${c.fund}%</div>
                            </div>
                        </div>
                    \`).join('');
                }
                
                // Render shorts
                const shortList = document.getElementById('shortList');
                if (data.shortCandidates.length > 0) {
                    shortList.innerHTML = data.shortCandidates.slice(0, 12).map(c => \`
                        <div class="candidate-item short">
                            <div class="symbol">\${c.symbol}</div>
                            <span class="score high">\${c.score}</span>
                            <div style="margin-top: 8px; font-size: 12px;">
                                <div>💰 Price: \$\${c.price}</div>
                                <div>📈 24h: \${c.chg24}%</div>
                                <div>📊 Funding: \${c.fund}%</div>
                            </div>
                        </div>
                    \`).join('');
                }
                
                // Render alerts
                const alertList = document.getElementById('alertList');
                if (data.alerts.length > 0) {
                    alertList.innerHTML = data.alerts.slice(-20).map(a => \`
                        <div class="alert-item">
                            <div>\${a.message}</div>
                            <div class="alert-time">\${new Date(a.timestamp).toLocaleString()}</div>
                        </div>
                    \`).join('');
                }
            } catch (e) {
                console.error('Dashboard update error:', e);
            }
        }
        
        // Initial load
        updateDashboard();
        // Refresh every 30 seconds
        setInterval(updateDashboard, 30000);
    </script>
</body>
</html>
`;

// HTTP 서버 시작
const server = http.createServer((req, res) => {
  // CORS 헤더
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
  else {
    res.writeHead(404);
    res.end('Not found');
  }
});

const PORT = process.env.PORT || 3000;
const os = require('os');

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

const localIP = getLocalIP();

server.listen(PORT, '0.0.0.0', () => {
  console.log(`\n🎯 Dashboard running at:`);
  console.log(`   Local:   http://localhost:${PORT}`);
  console.log(`   Network: http://${localIP}:${PORT}`);
  console.log(`📊 API endpoint: http://${localIP}:${PORT}/api/dashboard`);
  console.log(`✅ Ready to receive scanner data\n`);
  console.log(`📱 폰에서 접속: http://${localIP}:${PORT}\n`);
});

// 종료 시 정리
process.on('SIGINT', () => {
  console.log('\n🛑 Dashboard stopped');
  process.exit(0);
});
