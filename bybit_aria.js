const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  const symbol = 'ARIAUSDT';
  const t = (await pub('/v5/market/tickers', { category: 'linear', symbol })).result?.list?.[0];
  console.log('=== ARIA Ticker ===');
  console.log(`Price: ${t.lastPrice}  24h: ${(parseFloat(t.price24hPcnt)*100).toFixed(2)}%  H: ${t.highPrice24h}  L: ${t.lowPrice24h}  Vol: $${(parseFloat(t.turnover24h)/1e6).toFixed(2)}M  OI: $${(parseFloat(t.openInterestValue)/1e6).toFixed(2)}M  Funding: ${(parseFloat(t.fundingRate)*100).toFixed(4)}% (${t.fundingIntervalHour}h)`);

  const inst = (await pub('/v5/market/instruments-info', { category: 'linear', symbol })).result?.list?.[0];
  console.log(`Launch: ${new Date(parseInt(inst.launchTime)).toISOString()}  MaxLev: ${inst.leverageFilter.maxLeverage}  MinQty: ${inst.lotSizeFilter.minOrderQty}  Step: ${inst.lotSizeFilter.qtyStep}  Tick: ${inst.priceFilter.tickSize}`);

  console.log('\n=== 1D Klines (14) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol, interval: 'D', limit: '14' });
  (kd.result?.list || []).reverse().forEach(r => {
    const date = new Date(parseInt(r[0])).toISOString().slice(0,10);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(1);
    console.log(`${date}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%  V:${(parseFloat(r[5])/1000).toFixed(0)}K`);
  });

  console.log('\n=== 4h Klines (20) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '240', limit: '20' });
  (k4.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(1);
    console.log(`${dt}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%`);
  });

  console.log('\n=== 1h Klines (24) ===');
  const k1 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '60', limit: '24' });
  (k1.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(1);
    console.log(`${dt}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  ${pct}%`);
  });

  console.log('\n=== Funding (10) ===');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol, limit: '10' });
  (fr.result?.list || []).forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString().slice(0,16).replace('T',' ')}  ${(parseFloat(f.fundingRate)*100).toFixed(4)}%`);
  });

  console.log('\n=== OI (4h, 10) ===');
  const oi = await pub('/v5/market/open-interest', { category: 'linear', symbol, intervalTime: '4h', limit: '10' });
  (oi.result?.list || []).reverse().forEach(o => {
    console.log(`${new Date(parseInt(o.timestamp)).toISOString().slice(0,16).replace('T',' ')}  OI=${(parseFloat(o.openInterest)/1000).toFixed(0)}K`);
  });
})().catch(e => console.error(e));
