// ONG deep analysis with correct funding interpretation
// Funding > 0: longs pay shorts (short earns) | Funding < 0: shorts pay longs (short pays!)
const BASE_URL = 'https://api.bybit.com';
const SYMBOL = process.argv[2] || 'ONGUSDT';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  console.log(`=== ${SYMBOL} Analysis ===`);
  console.log(`Time: ${new Date().toISOString()}\n`);

  const t = (await pub('/v5/market/tickers', { category: 'linear', symbol: SYMBOL })).result?.list?.[0];
  if (!t) { console.log('No ticker'); return; }

  const price = parseFloat(t.lastPrice);
  const high = parseFloat(t.highPrice24h);
  const low = parseFloat(t.lowPrice24h);
  const fund = parseFloat(t.fundingRate) * 100;
  const fundH = parseInt(t.fundingIntervalHour);
  const perDay = fund * (24 / fundH);

  console.log('=== Ticker ===');
  console.log(`Price: $${t.lastPrice}`);
  console.log(`24h: ${(parseFloat(t.price24hPcnt)*100).toFixed(2)}% | High: $${t.highPrice24h} | Low: $${t.lowPrice24h}`);
  console.log(`24h Position: ${((price-low)/(high-low)*100).toFixed(1)}%`);
  console.log(`Vol24h: $${(parseFloat(t.turnover24h)/1e6).toFixed(1)}M | OI: $${(parseFloat(t.openInterestValue)/1e6).toFixed(1)}M`);
  console.log(`\n=== FUNDING (interval ${fundH}h, cap ${t.fundingCap}) ===`);
  console.log(`Current: ${fund.toFixed(4)}% per ${fundH}h  =>  ${perDay.toFixed(2)}%/day`);
  if (fund < 0) {
    console.log(`>>> NEGATIVE: SHORT PAYS ${Math.abs(perDay).toFixed(2)}%/day to longs. LONG EARNS. <<<`);
    console.log(`>>> SHORT ENTRY = DANGEROUS (funding bleed + squeeze risk) <<<`);
  } else if (fund > 0) {
    console.log(`>>> POSITIVE: LONG PAYS ${perDay.toFixed(2)}%/day to shorts. SHORT EARNS. <<<`);
  }
  console.log(`Next funding: ${new Date(parseInt(t.nextFundingTime)).toISOString()}`);

  console.log('\n=== 1D (last 10) ===');
  const kd = await pub('/v5/market/kline', { category: 'linear', symbol: SYMBOL, interval: 'D', limit: '10' });
  (kd.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().slice(5,10);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    console.log(`${dt} O:$${o.toFixed(4)} H:$${parseFloat(r[2]).toFixed(4)} L:$${parseFloat(r[3]).toFixed(4)} C:$${c.toFixed(4)} ${((c-o)/o*100).toFixed(2)}%`);
  });

  console.log('\n=== 4h (last 12) ===');
  const k4 = await pub('/v5/market/kline', { category: 'linear', symbol: SYMBOL, interval: '240', limit: '12' });
  (k4.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(5,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    console.log(`${dt} O:$${o.toFixed(4)} H:$${parseFloat(r[2]).toFixed(4)} L:$${parseFloat(r[3]).toFixed(4)} C:$${c.toFixed(4)} ${((c-o)/o*100).toFixed(2)}%`);
  });

  console.log('\n=== 1h (last 10) ===');
  const k1 = await pub('/v5/market/kline', { category: 'linear', symbol: SYMBOL, interval: '60', limit: '10' });
  (k1.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().replace('T',' ').slice(5,16);
    const o = parseFloat(r[1]), c = parseFloat(r[4]);
    console.log(`${dt} O:$${o.toFixed(4)} H:$${parseFloat(r[2]).toFixed(4)} L:$${parseFloat(r[3]).toFixed(4)} C:$${c.toFixed(4)} ${((c-o)/o*100).toFixed(2)}%`);
  });

  console.log('\n=== Funding history (last 12) with cumulative ===');
  const fr = await pub('/v5/market/funding/history', { category: 'linear', symbol: SYMBOL, limit: '12' });
  let cum = 0;
  const rows = (fr.result?.list || []);
  rows.forEach(f => cum += parseFloat(f.fundingRate) * 100);
  rows.forEach(f => {
    console.log(`${new Date(parseInt(f.fundingRateTimestamp)).toISOString().slice(5,16).replace('T',' ')}  ${(parseFloat(f.fundingRate)*100).toFixed(4)}%`);
  });
  console.log(`Cumulative last ${rows.length} periods: ${cum.toFixed(2)}% (short P&L impact: ${(-cum).toFixed(2)}%)`);

  console.log('\n=== OI history (1h, last 12) ===');
  const oi = await pub('/v5/market/open-interest', { category: 'linear', symbol: SYMBOL, intervalTime: '1h', limit: '12' });
  const oiList = (oi.result?.list || []).reverse();
  let prev = null;
  oiList.forEach(o => {
    const v = parseFloat(o.openInterest);
    const chg = prev ? ((v - prev) / prev * 100).toFixed(2) + '%' : '-';
    console.log(`${new Date(parseInt(o.timestamp)).toISOString().slice(5,16).replace('T',' ')}  OI=${(v/1e6).toFixed(2)}M  (${chg})`);
    prev = v;
  });

  // Simple verdict
  console.log('\n=== VERDICT ===');
  const pos = (price - low) / (high - low) * 100;
  if (fund < -0.1) {
    console.log('SHORT: BLOCKED (heavy funding bleed). Squeeze fuel present.');
    console.log(pos < 50 ? 'LONG: possible on dips w/ tight SL (earns funding).' : 'LONG: chasing top is risky; wait for dip.');
  } else if (fund > 0.05) {
    console.log('SHORT: favorable (earns funding). Check trend before entry.');
  } else {
    console.log('Funding neutral. Trade on technicals only.');
  }
})().catch(e => console.error(e));
