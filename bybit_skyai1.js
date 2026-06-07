const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  const ticker = await pub('/v5/market/tickers', { category: 'linear', symbol: 'SKYAI1USDT' });
  console.log('=== SKYAI1 Ticker ===');
  console.log(JSON.stringify(ticker.result?.list?.[0], null, 2));

  console.log('\n=== SKYAI1 1D Klines (last 30) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol: 'SKYAI1USDT', interval: 'D', limit: '30' });
  (kd.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().slice(0,10);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  console.log('\n=== SKYAI1 4h Klines (last 24) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol: 'SKYAI1USDT', interval: '240', limit: '24' });
  (k4.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  console.log('\n=== SKYAI1 1h Klines (last 24) ===');
  const k1 = await pub('/v5/market/kline', { category: 'linear', symbol: 'SKYAI1USDT', interval: '60', limit: '24' });
  (k1.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  console.log('\n=== Funding Rate (recent 10) ===');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol: 'SKYAI1USDT', limit: '10' });
  (fr.result?.list || []).forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString()}  rate=${f.fundingRate}`);
  });

  console.log('\n=== OI history (4h, last 10) ===');
  const oi = await pub('/v5/market/open-interest', { category: 'linear', symbol: 'SKYAI1USDT', intervalTime: '4h', limit: '10' });
  (oi.result?.list || []).reverse().forEach(o => {
    console.log(`${new Date(parseInt(o.timestamp)).toISOString()}  OI=${o.openInterest}`);
  });
})().catch(e => console.error(e));
