const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const envPath = path.join(__dirname, '.env.bybit');
const env = {};
fs.readFileSync(envPath, 'utf8').split(/\r?\n/).forEach(line => {
  const m = line.match(/^([^=]+)=(.+)$/);
  if (m) env[m[1].trim()] = m[2].trim();
});
const API_KEY = env.BYBIT_API_KEY;
const API_SECRET = env.BYBIT_API_SECRET;
const BASE_URL = 'https://api.bybit.com';
const RECV = '5000';

async function get(endpoint, params = {}) {
  const ts = Date.now().toString();
  const qs = Object.keys(params).sort().map(k => `${k}=${params[k]}`).join('&');
  const payload = ts + API_KEY + RECV + qs;
  const sig = crypto.createHmac('sha256', API_SECRET).update(payload).digest('hex');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`, {
    headers: { 'X-BAPI-API-KEY': API_KEY, 'X-BAPI-TIMESTAMP': ts, 'X-BAPI-RECV-WINDOW': RECV, 'X-BAPI-SIGN': sig }
  });
  return res.json();
}

(async () => {
  const pos = await get('/v5/position/list', { category: 'linear', symbol: 'LABUSDT' });
  const lab = pos.result?.list?.find(p => p.symbol === 'LABUSDT' && parseFloat(p.size) > 0);
  if (!lab) { console.log('No active LAB position'); return; }
  console.log('LAB Position:');
  console.log('  size:', lab.size, lab.side);
  console.log('  avgPrice:', lab.avgPrice);
  console.log('  markPrice:', lab.markPrice);
  console.log('  stopLoss:', lab.stopLoss);
  console.log('  takeProfit:', lab.takeProfit);
  console.log('  unrealisedPnl:', lab.unrealisedPnl);
})().catch(e => console.error(e));
