const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  const symbol = 'XAUUSDT';
  const t = (await pub('/v5/market/tickers', { category: 'linear', symbol })).result?.list?.[0];
  console.log('=== XAU Ticker ===');
  console.log(JSON.stringify(t, null, 2));

  console.log('\n=== 1D Klines (10) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol, interval: 'D', limit: '10' });
  (kd.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().slice(0,10);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(2);
    console.log(`${dt}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%`);
  });

  console.log('\n=== 4h Klines (10) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '240', limit: '10' });
  (k4.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(2);
    console.log(`${dt}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%`);
  });
})().catch(e => console.error(e));
