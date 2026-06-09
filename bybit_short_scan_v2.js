// 더 넓은 범위 스캔
const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  const tickers = await pub('/v5/market/tickers', { category: 'linear' });
  const list = tickers.result?.list || [];
  
  const filtered = list
    .filter(t => t.symbol.endsWith('USDT'))
    .filter(t => parseFloat(t.turnover24h) > 3_000_000)
    .map(t => ({
      symbol: t.symbol,
      price: parseFloat(t.lastPrice),
      high24h: parseFloat(t.highPrice24h),
      low24h: parseFloat(t.lowPrice24h),
      pct24h: parseFloat(t.price24hPcnt) * 100,
      turnover: parseFloat(t.turnover24h),
      oi: parseFloat(t.openInterestValue),
      funding: parseFloat(t.fundingRate),
      fundingHour: parseInt(t.fundingIntervalHour),
      pullback: ((parseFloat(t.lastPrice) - parseFloat(t.highPrice24h)) / parseFloat(t.highPrice24h)) * 100,
      bounce: ((parseFloat(t.lastPrice) - parseFloat(t.lowPrice24h)) / parseFloat(t.lowPrice24h)) * 100
    }))
    .map(t => ({ ...t, annualFunding: t.funding * (8760/t.fundingHour) * 100 }));

  console.log('## 🎯 SHORT 후보 종합 (펀딩 + 폭등 + 후퇴 종합 점수)');
  console.log('('+'대표님 보유 종목 제외'+')');
  const skip = ['BEATUSDT', 'CLOUSDT', 'LABUSDT', 'VELVETUSDT', 'ALLOUSDT', 'PEAQUSDT', 'CHIPUSDT', 'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT'];
  
  const scored = filtered
    .filter(t => !skip.includes(t.symbol))
    .filter(t => t.pct24h > 10)
    .filter(t => t.pullback <= -2)
    .map(t => {
      // 점수: 24h 폭등 + 펀딩 + 후퇴
      const score = Math.min(t.pct24h, 100) * 0.3 + Math.min(t.annualFunding, 500) * 0.4 + Math.abs(t.pullback) * 0.5;
      return { ...t, score };
    })
    .sort((a,b) => b.score - a.score)
    .slice(0, 15);

  console.log('\nSymbol           | Score | 24h%    | Price       | Pullback | OI($)    | Funding연 | Turnover');
  console.log('-'.repeat(120));
  scored.forEach(t => {
    console.log(`${t.symbol.padEnd(16)} | ${t.score.toFixed(0).padStart(5)} | ${(t.pct24h.toFixed(1) + '%').padStart(7)} | ${t.price.toFixed(5).padStart(11)} | ${(t.pullback.toFixed(1) + '%').padStart(8)} | $${(t.oi/1e6).toFixed(1).padStart(5)}M | ${t.annualFunding.toFixed(0).padStart(6)}% | $${(t.turnover/1e6).toFixed(1)}M`);
  });

  // 종합 추천 TOP 5에 대해 변동성/지지선 분석
  console.log('\n\n## 🎯 LONG 후보 (저점 반등)');
  const longs = filtered
    .filter(t => !skip.includes(t.symbol))
    .filter(t => t.pct24h <= -10 && t.bounce >= 5 && t.bounce <= 20)
    .sort((a,b) => a.pct24h - b.pct24h)
    .slice(0, 8);
  console.log('Symbol           | 24h%      | Price    | Low24h   | Bounce  | OI($)   | Funding연');
  console.log('-'.repeat(100));
  longs.forEach(t => {
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(1) + '%').padStart(8)} | ${t.price.toFixed(5).padStart(8)} | ${t.low24h.toFixed(5).padStart(8)} | ${(t.bounce.toFixed(1) + '%').padStart(6)} | $${(t.oi/1e6).toFixed(1).padStart(5)}M | ${t.annualFunding.toFixed(0)}%`);
  });
})().catch(e => console.error(e));
