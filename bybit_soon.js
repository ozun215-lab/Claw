const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  // 1) 심볼 확인 - SOON 들어간 종목 검색
  console.log('=== SOON 관련 종목 검색 ===');
  const tickers = await pub('/v5/market/tickers', { category: 'linear' });
  const soons = (tickers.result?.list || []).filter(t => t.symbol.includes('SOON'));
  soons.forEach(t => {
    console.log(`Symbol: ${t.symbol}`);
    console.log(`  Price: ${t.lastPrice}`);
    console.log(`  24h%: ${(parseFloat(t.price24hPcnt)*100).toFixed(2)}%`);
    console.log(`  High24h: ${t.highPrice24h}, Low24h: ${t.lowPrice24h}`);
    console.log(`  Turnover: $${(parseFloat(t.turnover24h)/1e6).toFixed(1)}M`);
    console.log(`  OI Value: $${(parseFloat(t.openInterestValue)/1e6).toFixed(1)}M`);
    console.log(`  Funding: ${(parseFloat(t.fundingRate)*100).toFixed(4)}% (${t.fundingIntervalHour}h)`);
  });

  if (soons.length === 0) {
    console.log('SOON 종목 없음');
    return;
  }

  // 가장 적합한 SOON 종목 선택 (보통 SOONUSDT)
  const symbol = soons[0].symbol;
  console.log(`\n=== ${symbol} 상세 분석 ===\n`);

  // Instruments info
  const inst = await pub('/v5/market/instruments-info', { category: 'linear', symbol });
  const i = inst.result?.list?.[0];
  if (i) {
    console.log('Instrument Info:');
    console.log(`  launchTime: ${new Date(parseInt(i.launchTime)).toISOString()}`);
    console.log(`  maxLeverage: ${i.leverageFilter?.maxLeverage}`);
    console.log(`  minOrderQty: ${i.lotSizeFilter?.minOrderQty}`);
    console.log(`  qtyStep: ${i.lotSizeFilter?.qtyStep}`);
    console.log(`  tickSize: ${i.priceFilter?.tickSize}`);
  }

  // 1D Klines
  console.log('\n=== 1D Klines (last 30) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol, interval: 'D', limit: '30' });
  (kd.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().slice(0,10);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  // 4h Klines
  console.log('\n=== 4h Klines (last 30) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '240', limit: '30' });
  (k4.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  // 1h Klines
  console.log('\n=== 1h Klines (last 24) ===');
  const k1 = await pub('/v5/market/kline', { category: 'linear', symbol, interval: '60', limit: '24' });
  (k1.result?.list || []).reverse().forEach(r => {
    const t = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(0,16);
    console.log(`${t}  O:${r[1]}  H:${r[2]}  L:${r[3]}  C:${r[4]}  V:${r[5]}`);
  });

  // Funding rate
  console.log('\n=== Funding Rate (recent 10) ===');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol, limit: '10' });
  (fr.result?.list || []).forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString()}  rate=${f.fundingRate}`);
  });

  // Open Interest
  console.log('\n=== OI history (4h, last 10) ===');
  const oi = await pub('/v5/market/open-interest', { category: 'linear', symbol, intervalTime: '4h', limit: '10' });
  (oi.result?.list || []).reverse().forEach(o => {
    console.log(`${new Date(parseInt(o.timestamp)).toISOString()}  OI=${o.openInterest}`);
  });
})().catch(e => console.error(e));
