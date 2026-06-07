// 롱 진입 적합 종목 스캔 (헷지/메이저 반등 베팅)
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
    .filter(t => parseFloat(t.turnover24h) > 5_000_000)
    .map(t => {
      const price = parseFloat(t.lastPrice);
      const high = parseFloat(t.highPrice24h);
      const low = parseFloat(t.lowPrice24h);
      return {
        symbol: t.symbol,
        price,
        high24h: high,
        low24h: low,
        pct24h: parseFloat(t.price24hPcnt) * 100,
        turnover: parseFloat(t.turnover24h),
        oi: parseFloat(t.openInterestValue),
        funding: parseFloat(t.fundingRate),
        fundingHour: parseInt(t.fundingIntervalHour),
        bounce: ((price - low) / low) * 100,
        posInRange: ((price - low) / (high - low + 0.0000001)) * 100
      };
    });

  // 1) 저점에서 반등 시작 종목 (24h 음수 후 회복 중)
  console.log('## 🎯 LONG 후보 #1: 저점 반등 시작 (24h -10% 이상 하락 후 저점에서 +3% 이상 반등)');
  const cat1 = filtered
    .filter(t => t.pct24h <= -10 && t.bounce >= 3 && t.bounce <= 15)
    .sort((a,b) => a.pct24h - b.pct24h)
    .slice(0, 12);
  console.log('Symbol           | 24h%     | Price    | Low24h   | Bounce  | OI($)   | Turnover');
  console.log('-'.repeat(100));
  cat1.forEach(t => {
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(1) + '%').padStart(7)} | ${t.price.toFixed(5).padStart(8)} | ${t.low24h.toFixed(5).padStart(8)} | ${(t.bounce.toFixed(1) + '%').padStart(6)} | ${(t.oi/1e6).toFixed(2).padStart(6)}M | ${(t.turnover/1e6).toFixed(1)}M`);
  });

  // 2) 메이저 코인 반등 신호 (BTC/ETH/SOL/XRP 등)
  console.log('\n## 🎯 LONG 후보 #2: 메이저 코인 반등 신호 (양수 펀딩비 안정)');
  const majors = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOGEUSDT', 'DOTUSDT', 'MATICUSDT', 'TRXUSDT', 'LTCUSDT'];
  const cat2 = filtered
    .filter(t => majors.includes(t.symbol))
    .sort((a,b) => b.pct24h - a.pct24h);
  console.log('Symbol           | 24h%     | Price       | OI($)    | Funding(%) | 연환산');
  console.log('-'.repeat(100));
  cat2.forEach(t => {
    const annual = t.funding * (8760/t.fundingHour) * 100;
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(2) + '%').padStart(8)} | ${t.price.toFixed(4).padStart(11)} | ${(t.oi/1e6).toFixed(2).padStart(8)}M | ${(t.funding*100).toFixed(4)}% | ${annual.toFixed(1)}%`);
  });

  // 3) 펀딩비 마이너스 큰 종목 (숏이 비용 지불 = 롱에 유리)
  console.log('\n## 🎯 LONG 후보 #3: 펀딩비 음수 (숏 강제 청산 임박)');
  const cat3 = filtered
    .map(t => ({ ...t, annualFunding: t.funding * (8760/t.fundingHour) * 100 }))
    .filter(t => t.annualFunding < -50)
    .sort((a,b) => a.annualFunding - b.annualFunding)
    .slice(0, 10);
  console.log('Symbol           | 24h%     | Funding(h) | 연환산   | Price    | OI($)');
  console.log('-'.repeat(100));
  cat3.forEach(t => {
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(1) + '%').padStart(7)} | ${(t.funding*100).toFixed(4)}%   | ${t.annualFunding.toFixed(0)}%   | ${t.price.toFixed(5).padStart(8)} | ${(t.oi/1e6).toFixed(2)}M`);
  });

  // 4) 횡보 후 박스권 상단 돌파 시도 (저점/고점 차이 작은 안정 종목)
  console.log('\n## 🎯 LONG 후보 #4: 안정 박스권에서 약한 상승 (24h +0~5%, 변동성 낮음)');
  const cat4 = filtered
    .filter(t => t.pct24h >= 0 && t.pct24h <= 5)
    .filter(t => (t.high24h - t.low24h) / t.price < 0.08) // 8% 미만 변동
    .filter(t => t.turnover > 20_000_000)
    .sort((a,b) => b.turnover - a.turnover)
    .slice(0, 8);
  console.log('Symbol           | 24h%   | Price    | Range(%)| Turnover  | OI($)');
  console.log('-'.repeat(90));
  cat4.forEach(t => {
    const range = ((t.high24h - t.low24h) / t.price * 100);
    console.log(`${t.symbol.padEnd(16)} | ${(t.pct24h.toFixed(1) + '%').padStart(5)} | ${t.price.toFixed(4).padStart(8)} | ${range.toFixed(1).padStart(5)}% | $${(t.turnover/1e6).toFixed(1).padStart(6)}M | ${(t.oi/1e6).toFixed(2)}M`);
  });
})().catch(e => console.error(e));
