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

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const url = `${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`;
  const res = await fetch(url);
  return res.json();
}

(async () => {
  // 1) Ticker
  const ticker = await pub('/v5/market/tickers', { category: 'linear', symbol: 'LABUSDT' });
  console.log('=== LAB Ticker ===');
  console.log(JSON.stringify(ticker.result?.list?.[0], null, 2));

  // 2) Recent klines (4h, last 50)
  console.log('\n=== LAB 4h Klines (last 30) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol: 'LABUSDT', interval: '240', limit: '30' });
  const rows4 = (k4.result?.list || []).reverse();
  rows4.forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  // 3) Daily klines (last 30)
  console.log('\n=== LAB 1D Klines (last 30) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol: 'LABUSDT', interval: 'D', limit: '30' });
  const rowsD = (kd.result?.list || []).reverse();
  rowsD.forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().slice(0,10);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  // 4) Funding rate history
  console.log('\n=== LAB Funding rate (recent 10) ===');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol: 'LABUSDT', limit: '10' });
  (fr.result?.list || []).forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString()}  rate=${f.fundingRate}`);
  });
})().catch(e => console.error(e));
