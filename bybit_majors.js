const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

async function analyze(symbol) {
  console.log(`\n${'='.repeat(60)}\n=== ${symbol} ===\n${'='.repeat(60)}`);
  const ticker = await pub('/v5/market/tickers', { category: 'linear', symbol });
  const t = ticker.result?.list?.[0];
  console.log(`Price: ${t.lastPrice}  24h: ${(parseFloat(t.price24hPcnt)*100).toFixed(2)}%  H: ${t.highPrice24h}  L: ${t.lowPrice24h}  Vol: $${(parseFloat(t.turnover24h)/1e6).toFixed(0)}M  OI: $${(parseFloat(t.openInterestValue)/1e6).toFixed(0)}M  Funding: ${(parseFloat(t.fundingRate)*100).toFixed(4)}% (${t.fundingIntervalHour}h)`);

  console.log('\n--- 1D Klines (14) ---');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol, interval: 'D', limit: '14' });
  (kd.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().slice(0,10);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c - o) / o * 100).toFixed(2);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%`);
  });

  console.log('\n--- 4h Klines (12) ---');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '240', limit: '12' });
  (k4.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c - o) / o * 100).toFixed(2);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%`);
  });

  console.log('\n--- 1h Klines (12) ---');
  const k1 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '60', limit: '12' });
  (k1.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c - o) / o * 100).toFixed(2);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%`);
  });

  console.log('\n--- OI (4h, 10) ---');
  const oi = await pub('/v5/market/open-interest', { category: 'linear', symbol, intervalTime: '4h', limit: '10' });
  (oi.result?.list || []).reverse().forEach(o => {
    console.log(`${new Date(parseInt(o.timestamp)).toISOString().slice(5,16).replace('T',' ')}  OI=${(parseFloat(o.openInterest)/1e6).toFixed(2)}M`);
  });

  console.log('\n--- Funding (8h, 5) ---');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol, limit: '5' });
  (fr.result?.list || []).forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString().slice(5,16).replace('T',' ')}  ${(parseFloat(f.fundingRate)*100).toFixed(4)}%`);
  });
}

(async () => {
  for (const sym of ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']) {
    await analyze(sym);
  }
})().catch(e => console.error(e));
