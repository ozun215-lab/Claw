const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  const symbol = 'ELSAUSDT';
  
  console.log(`=== ELSAUSDT Analysis ===`);
  console.log(`Time: ${new Date().toISOString()}\n`);
  
  // Ticker
  const t = (await pub('/v5/market/tickers', { category: 'linear', symbol })).result?.list?.[0];
  if (!t) { console.log('No ticker data'); return; }
  
  console.log('=== Ticker ===');
  console.log(`Price: $${t.lastPrice}`);
  console.log(`24h Change: ${(parseFloat(t.price24hPcnt)*100).toFixed(2)}%`);
  console.log(`24h High: $${t.highPrice24h} | Low: $${t.lowPrice24h}`);
  console.log(`OI Value: $${(parseFloat(t.openInterestValue)/1e6).toFixed(1)}M`);
  console.log(`Volume 24h: $${(parseFloat(t.turnover24h)/1e6).toFixed(1)}M`);
  console.log(`Funding: ${(parseFloat(t.fundingRate)*100).toFixed(4)}% (${t.fundingIntervalHour}h)`);
  console.log(`Prev 1h: $${t.prevPrice1h}`);
  
  // Price position in 24h range
  const price = parseFloat(t.lastPrice);
  const high24 = parseFloat(t.highPrice24h);
  const low24 = parseFloat(t.lowPrice24h);
  const pos24 = ((price - low24) / (high24 - low24) * 100).toFixed(1);
  console.log(`24h Position: ${pos24}% (0=low, 100=high)\n`);
  
  // 1D Klines
  console.log('=== Daily (last 15) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol, interval: 'D', limit: '15' });
  (kd.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().slice(5,10);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(2);
    console.log(`${dt} O:$${parseFloat(r[1]).toFixed(6)} H:$${parseFloat(r[2]).toFixed(6)} L:$${parseFloat(r[3]).toFixed(6)} C:$${parseFloat(r[4]).toFixed(6)} ${pct}%`);
  });
  
  // 4h Klines
  console.log('\n=== 4h (last 12) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '240', limit: '12' });
  (k4.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(2);
    console.log(`${dt} O:$${o.toFixed(6)} H:$${parseFloat(r[2]).toFixed(6)} L:$${parseFloat(r[3]).toFixed(6)} C:$${c.toFixed(6)} ${pct}%`);
  });
  
  // 1h Klines
  console.log('\n=== 1h (last 8) ===');
  const k1 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '60', limit: '8' });
  (k1.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    const pct = ((c-o)/o*100).toFixed(2);
    console.log(`${dt} O:$${o.toFixed(6)} H:$${parseFloat(r[2]).toFixed(6)} L:$${parseFloat(r[3]).toFixed(6)} C:$${c.toFixed(6)} ${pct}%`);
  });
  
  // Funding history
  console.log('\n=== Funding (last 6) ===');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol, limit: '6' });
  (fr.result?.list || []).forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString().slice(0,16).replace('T',' ')}  ${(parseFloat(f.fundingRate)*100).toFixed(4)}%`);
  });
  
  // OI history
  console.log('\n=== OI (4h, last 6) ===');
  const oi = await pub('/v5/market/open-interest', { category: 'linear', symbol, intervalTime: '4h', limit: '6' });
  (oi.result?.list || []).reverse().forEach(o => {
    console.log(`${new Date(parseInt(o.timestamp)).toISOString().slice(0,16).replace('T',' ')}  ${(parseFloat(o.openInterest)/1e3).toFixed(0)}K`);
  });
  
  console.log('\n=== Done ===');
})().catch(e => console.error(e));
