// 숏 진입 적합 종목 스캔
// 기준: 24h +20% 이상 폭등 + 거래량 활발 + 신고점 후 후퇴 신호
const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  console.log('=== Bybit Linear Tickers (전체 스캔) ===\n');
  const tickers = await pub('/v5/market/tickers', { category: 'linear' });
  const list = tickers.result?.list || [];
  
  // USDT 페어만, 24h 변동율 + 거래대금 충분한 것
  const filtered = list
    .filter(t => t.symbol.endsWith('USDT'))
    .filter(t => parseFloat(t.turnover24h) > 5_000_000) // $5M 이상
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
      // 정점 대비 후퇴율
      pullback: ((parseFloat(t.lastPrice) - parseFloat(t.highPrice24h)) / parseFloat(t.highPrice24h)) * 100,
      // 정점 대비 현재 위치 (0=저점, 1=고점)
      pos: (parseFloat(t.lastPrice) - parseFloat(t.lowPrice24h)) / (parseFloat(t.highPrice24h) - parseFloat(t.lowPrice24h) + 0.0000001)
    }));

  // 1) 폭등 + 위꼬리 형성 (정점 대비 후퇴 3~15%)
  console.log('## 🎯 SHORT 후보 #1: 폭등 후 후퇴 (24h +25% 이상, 정점 후 -3~15%)');
  const cat1 = filtered
    .filter(t => t.pct24h >= 25 && t.pullback <= -3 && t.pullback >= -20)
    .sort((a,b) => b.pct24h - a.pct24h)
    .slice(0, 15);
  console.log('Symbol           | 24h%    | Price    | High24h  | Pullback | OI($)    | Turnover | Funding');
  console.log('-'.repeat(120));
  cat1.forEach(t => {
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(1) + '%').padStart(7)} | ${t.price.toFixed(5).padStart(8)} | ${t.high24h.toFixed(5).padStart(8)} | ${(t.pullback.toFixed(1) + '%').padStart(8)} | ${(t.oi/1e6).toFixed(2).padStart(8)}M | ${(t.turnover/1e6).toFixed(1).padStart(6)}M | ${(t.funding*100).toFixed(4)}%`);
  });

  // 2) 펀딩비 극단적으로 높음 (롱 강제 청산 임박)
  console.log('\n## 🎯 SHORT 후보 #2: 펀딩비 폭증 (롱이 막대한 비용 지불 중)');
  const cat2 = filtered
    .filter(t => t.pct24h > 5)
    .map(t => ({ ...t, annualFunding: t.funding * (8760/t.fundingHour) * 100 }))
    .filter(t => t.annualFunding > 100)
    .sort((a,b) => b.annualFunding - a.annualFunding)
    .slice(0, 10);
  console.log('Symbol           | 24h%    | Funding(h) | 연환산  | Price    | OI($)');
  console.log('-'.repeat(80));
  cat2.forEach(t => {
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(1) + '%').padStart(7)} | ${(t.funding*100).toFixed(4)}%   | ${t.annualFunding.toFixed(0)}%   | ${t.price.toFixed(5).padStart(8)} | ${(t.oi/1e6).toFixed(2)}M`);
  });

  // 3) 24h 변동률 큰 코인 중 거래량 폭증
  console.log('\n## 🎯 SHORT 후보 #3: 거래량 폭증 종목 (Turnover > $50M + 24h +15%)');
  const cat3 = filtered
    .filter(t => t.pct24h >= 15 && t.turnover > 50_000_000)
    .sort((a,b) => b.turnover - a.turnover)
    .slice(0, 10);
  console.log('Symbol           | 24h%    | Price    | Turnover  | OI($)    | Pullback');
  console.log('-'.repeat(90));
  cat3.forEach(t => {
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(1) + '%').padStart(7)} | ${t.price.toFixed(5).padStart(8)} | $${(t.turnover/1e6).toFixed(1).padStart(6)}M | ${(t.oi/1e6).toFixed(2).padStart(6)}M | ${t.pullback.toFixed(1)}%`);
  });
})().catch(e => console.error(e));
