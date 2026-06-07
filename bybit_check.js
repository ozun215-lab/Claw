// Bybit V5 API - Check orders & positions
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// Load .env.bybit
const envPath = path.join(__dirname, '.env.bybit');
const envContent = fs.readFileSync(envPath, 'utf8');
const env = {};
envContent.split(/\r?\n/).forEach(line => {
  const m = line.match(/^([^=]+)=(.+)$/);
  if (m) env[m[1].trim()] = m[2].trim();
});

const API_KEY = env.BYBIT_API_KEY;
const API_SECRET = env.BYBIT_API_SECRET;
const BASE_URL = 'https://api.bybit.com';
const RECV_WINDOW = '5000';

function sign(timestamp, params) {
  const queryString = Object.keys(params).sort().map(k => `${k}=${params[k]}`).join('&');
  const payload = timestamp + API_KEY + RECV_WINDOW + queryString;
  return {
    sig: crypto.createHmac('sha256', API_SECRET).update(payload).digest('hex'),
    qs: queryString
  };
}

async function get(endpoint, params = {}) {
  const timestamp = Date.now().toString();
  const { sig, qs } = sign(timestamp, params);
  const url = `${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      'X-BAPI-API-KEY': API_KEY,
      'X-BAPI-TIMESTAMP': timestamp,
      'X-BAPI-RECV-WINDOW': RECV_WINDOW,
      'X-BAPI-SIGN': sig,
    }
  });
  return res.json();
}

(async () => {
  console.log('=== 1. Open Orders (linear/USDT perpetual) ===');
  const open = await get('/v5/order/realtime', { category: 'linear', settleCoin: 'USDT' });
  console.log(JSON.stringify(open, null, 2));

  console.log('\n=== 2. Open Orders (spot) ===');
  const openSpot = await get('/v5/order/realtime', { category: 'spot' });
  console.log(JSON.stringify(openSpot, null, 2));

  console.log('\n=== 3. Active Positions (linear) ===');
  const pos = await get('/v5/position/list', { category: 'linear', settleCoin: 'USDT' });
  console.log(JSON.stringify(pos, null, 2));

  console.log('\n=== 4. Recent Order History (linear, last 10) ===');
  const hist = await get('/v5/order/history', { category: 'linear', settleCoin: 'USDT', limit: '10' });
  console.log(JSON.stringify(hist, null, 2));
})().catch(e => { console.error('ERROR:', e); process.exit(1); });
