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
  console.log('=== Positions Summary ===\n');
  const pos = await get('/v5/position/list', { category: 'linear', settleCoin: 'USDT' });
  const list = pos.result?.list?.filter(p => parseFloat(p.size) > 0) || [];
  let totalPnL = 0;
  list.forEach(p => {
    totalPnL += parseFloat(p.unrealisedPnl);
    console.log(`${p.symbol.padEnd(14)} ${p.side.padEnd(5)} size=${p.size.padEnd(10)} avgP=${parseFloat(p.avgPrice).toFixed(5).padStart(10)} mark=${parseFloat(p.markPrice).toFixed(5).padStart(10)} PnL=${parseFloat(p.unrealisedPnl).toFixed(2).padStart(10)} SL=${p.stopLoss || 'none'}`);
  });
  console.log(`\nTotal Unrealised PnL: ${totalPnL.toFixed(2)} USDT`);
  console.log(`Positions: ${list.length}`);

  console.log('\n=== Account ===');
  const bal = await get('/v5/account/wallet-balance', { accountType: 'UNIFIED' });
  const a = bal.result?.list?.[0];
  if (a) {
    console.log(`Total Equity: $${parseFloat(a.totalEquity).toFixed(2)}`);
    console.log(`Available: $${parseFloat(a.totalAvailableBalance).toFixed(2)}`);
    console.log(`IM Rate: ${(parseFloat(a.accountIMRate)*100).toFixed(2)}%`);
    console.log(`MM Rate: ${(parseFloat(a.accountMMRate)*100).toFixed(2)}%`);
    console.log(`Unrealised: $${parseFloat(a.totalPerpUPL).toFixed(2)}`);
  }

  console.log('\n=== Open Orders ===');
  const orders = await get('/v5/order/realtime', { category: 'linear', settleCoin: 'USDT' });
  const ol = orders.result?.list || [];
  ol.forEach(o => {
    const typ = o.stopOrderType || 'Limit';
    console.log(`${o.symbol.padEnd(14)} ${typ.padEnd(20)} ${o.side.padEnd(5)} qty=${o.qty} trigger=${o.triggerPrice || o.price} (${o.orderStatus})`);
  });
})().catch(e => console.error(e));
