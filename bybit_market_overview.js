const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  const symbols = ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','SUIUSDT','PEPEUSDT'];
  const now = new Date();
  
  console.log(`=== 시장 전반 분석 (${now.toISOString().slice(0,16)}) ===\n`);
  
  for (const symbol of symbols) {
    const t = (await pub('/v5/market/tickers', { category: 'linear', symbol })).result?.list?.[0];
    if (!t) continue;
    
    const price = parseFloat(t.lastPrice);
    const chg24 = parseFloat(t.price24hPcnt) * 100;
    const high24 = parseFloat(t.highPrice24h);
    const low24 = parseFloat(t.lowPrice24h);
    const vol24 = parseFloat(t.turnover24h) / 1e6;
    const fund = parseFloat(t.fundingRate) * 100;
    const oi = parseFloat(t.openInterestValue) / 1e6;
    
    const range = ((high24 - low24) / low24 * 100).toFixed(1);
    const pos = ((price - low24) / (high24 - low24) * 100).toFixed(0);
    
    let emoji = chg24 > 5 ? '🚀' : chg24 > 2 ? '📈' : chg24 < -5 ? '💥' : chg24 < -2 ? '📉' : '➡️';
    let fundEmoji = fund > 0.05 ? '🔴' : fund < -0.05 ? '🟢' : '⚪';
    
    console.log(`${symbol.replace('USDT','')}: $${price} | 24h: ${chg24>0?'+':''}${chg24.toFixed(2)}% ${emoji} | 펀딩: ${fund.toFixed(4)}% ${fundEmoji} | OI: $${oi.toFixed(0)}M | 변동성: ${range}% | 위치: ${pos}%`);
  }
  
  console.log('\n=== BTC/ETH 일봉 추세 ===');
  const btcD = await pub('/v5/market/kline', { category: 'linear', symbol: 'BTCUSDT', interval: 'D', limit: '7' });
  (btcD.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().slice(5,10);
    const c = parseFloat(r[4]);
    const o = parseFloat(r[1]);
    const pct = ((c-o)/o*100).toFixed(2);
    console.log(`BTC ${dt}: $${c} (${pct>0?'+':''}${pct}%)`);
  });
  
  const ethD = await pub('/v5/market/kline', { category: 'linear', symbol: 'ETHUSDT', interval: 'D', limit: '7' });
  (ethD.result?.list || []).reverse().forEach(r => {
    const dt = new Date(parseInt(r[0])).toISOString().slice(5,10);
    const c = parseFloat(r[4]);
    const o = parseFloat(r[1]);
    const pct = ((c-o)/o*100).toFixed(2);
    console.log(`ETH ${dt}: $${c} (${pct>0?'+':''}${pct}%)`);
  });
  
  console.log('\n=== 알트코인 심층 ===');
  const altSymbols = ['SPORTFUNUSDT','ONDOUSDT','ESPUSDT','PYTHUSDT'];
  for (const symbol of altSymbols) {
    const t = (await pub('/v5/market/tickers', { category: 'linear', symbol })).result?.list?.[0];
    if (!t) continue;
    const price = parseFloat(t.lastPrice);
    const chg24 = parseFloat(t.price24hPcnt) * 100;
    const fund = parseFloat(t.fundingRate) * 100;
    console.log(`${symbol.replace('USDT','')}: $${price} | 24h: ${chg24>0?'+':''}${chg24.toFixed(2)}% | 펀딩: ${fund.toFixed(4)}%`);
  }
})().catch(e => console.error(e));
