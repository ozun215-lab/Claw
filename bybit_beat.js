const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  const ticker = await pub('/v5/market/tickers', { category: 'linear', symbol: 'BEATUSDT' });
  console.log('=== BEAT Ticker ===');
  console.log(JSON.stringify(ticker.result?.list?.[0], null, 2));

  console.log('\n=== BEAT 1D Klines (last 30) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol: 'BEATUSDT', interval: 'D', limit: '30' });
  (kd.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().slice(0,10);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  console.log('\n=== BEAT 4h Klines (last 30) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol: 'BEATUSDT', interval: '240', limit: '30' });
  (k4.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  console.log('\n=== BEAT 1h Klines (last 24) ===');
  const k1 = await pub('/v5/market/kline', { category: 'linear', symbol: 'BEATUSDT', interval: '60', limit: '24' });
  (k1.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  console.log('\n=== Funding Rate (recent 10) ===');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol: 'BEATUSDT', limit: '10' });
  (fr.result?.list || []).forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString()}  rate=${f.fundingRate}`);
  });

  console.log('\n=== Open Interest history (4h, last 10) ===');
  const oi = await pub('/v5/market/open-interest', { category: 'linear', symbol: 'BEATUSDT', intervalTime: '4h', limit: '10' });
  (oi.result?.list || []).reverse().forEach(o => {
    console.log(`${new Date(parseInt(o.timestamp)).toISOString()}  OI=${o.openInterest}`);
  });

  console.log('\n=== Instruments Info ===');
  const inst = await pub('/v5/market/instruments-info', { category: 'linear', symbol: 'BEATUSDT' });
  const i = inst.result?.list?.[0];
  if (i) {
    console.log('  launchTime:', new Date(parseInt(i.launchTime)).toISOString());
    console.log('  maxLeverage:', i.leverageFilter?.maxLeverage);
    console.log('  minOrderQty:', i.lotSizeFilter?.minOrderQty);
    console.log('  qtyStep:', i.lotSizeFilter?.qtyStep);
    console.log('  tickSize:', i.priceFilter?.tickSize);
  }
})().catch(e => console.error(e));
