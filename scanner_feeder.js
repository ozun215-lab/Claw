#!/usr/bin/env node
/**
 * Scanner Data Feeder
 * 스캔 결과를 대시보드로 자동 전송
 */

const BASE_URL = 'https://api.bybit.com';
const DASHBOARD_URL = 'http://localhost:3000';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

const FIB_SEQUENCE = [5, 8, 13, 21, 34, 55];

function analyzeFibonacciTimeSignalsShort(candles1h) {
  let fibScore = 0;
  let fibReasons = [];
  if (!candles1h || candles1h.length < 5) return { fibScore: 0, fibReasons: [] };
  const sortedCandles = candles1h.reverse();
  FIB_SEQUENCE.forEach(fib => {
    if (sortedCandles.length >= fib) {
      const currentCandle = sortedCandles[sortedCandles.length - 1];
      const fibCandle = sortedCandles[sortedCandles.length - fib];
      const currentClose = parseFloat(currentCandle[4]);
      const currentOpen = parseFloat(currentCandle[1]);
      const fibHigh = parseFloat(fibCandle[2]);
      const fibLow = parseFloat(fibCandle[3]);
      if (fibHigh > currentClose && (fibHigh - currentClose) / fibHigh > 0.02) {
        fibScore += 3;
        fibReasons.push(`fib_${fib}h_decline`);
      }
      const fibChange = parseFloat(fibCandle[4]) - parseFloat(fibCandle[1]);
      const currentChange = currentClose - currentOpen;
      if (fibChange > 0 && currentChange < 0) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_reversal`);
      }
      if (currentClose < fibLow * 0.98) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_breakdown`);
      }
    }
  });
  let consecutiveDownCandles = 0;
  for (let i = sortedCandles.length - 1; i >= 0; i--) {
    if (parseFloat(sortedCandles[i][4]) < parseFloat(sortedCandles[i][1])) {
      consecutiveDownCandles++;
    } else break;
  }
  if ([5, 8, 13, 21].includes(consecutiveDownCandles)) {
    fibScore += 4;
    fibReasons.push(`fib_downtrend_${consecutiveDownCandles}h`);
  } else if (consecutiveDownCandles > 3 && consecutiveDownCandles < 5) {
    fibScore += 2;
    fibReasons.push(`pre_fib_reversal_${consecutiveDownCandles}h`);
  }
  return { fibScore: Math.min(fibScore, 15), fibReasons };
}

function analyzeFib4hShort(candles4h) {
  let fib4hScore = 0;
  let fib4hReasons = [];
  if (!candles4h || candles4h.length < 5) return { fib4hScore: 0, fib4hReasons: [] };
  const sorted4h = candles4h.reverse();
  const checkPoints = [5, 8, 13, 21];
  checkPoints.forEach(cp => {
    if (sorted4h.length >= cp) {
      const now = sorted4h[sorted4h.length - 1];
      const pastCandle = sorted4h[sorted4h.length - cp];
      const nowClose = parseFloat(now[4]);
      const pastHigh = parseFloat(pastCandle[2]);
      if (nowClose < pastHigh * 0.95) {
        fib4hScore += 2;
        fib4hReasons.push(`fib4h_${cp}candle_loss`);
      }
    }
  });
  return { fib4hScore: Math.min(fib4hScore, 8), fib4hReasons };
}

function analyzeFibonacciTimeSignalsLong(candles1h) {
  let fibScore = 0;
  let fibReasons = [];
  if (!candles1h || candles1h.length < 5) return { fibScore: 0, fibReasons: [] };
  const sortedCandles = candles1h.reverse();
  FIB_SEQUENCE.forEach(fib => {
    if (sortedCandles.length >= fib) {
      const currentCandle = sortedCandles[sortedCandles.length - 1];
      const fibCandle = sortedCandles[sortedCandles.length - fib];
      const currentClose = parseFloat(currentCandle[4]);
      const currentOpen = parseFloat(currentCandle[1]);
      const fibLow = parseFloat(fibCandle[3]);
      const fibHigh = parseFloat(fibCandle[2]);
      if (fibLow < currentClose && (currentClose - fibLow) / fibLow > 0.02) {
        fibScore += 3;
        fibReasons.push(`fib_${fib}h_recovery`);
      }
      const fibChange = parseFloat(fibCandle[4]) - parseFloat(fibCandle[1]);
      const currentChange = currentClose - currentOpen;
      if (fibChange < 0 && currentChange > 0) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_reversal`);
      }
      if (currentClose > fibHigh * 1.02) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_breakout`);
      }
    }
  });
  let consecutiveUpCandles = 0;
  for (let i = sortedCandles.length - 1; i >= 0; i--) {
    if (parseFloat(sortedCandles[i][4]) > parseFloat(sortedCandles[i][1])) {
      consecutiveUpCandles++;
    } else break;
  }
  if ([5, 8, 13, 21].includes(consecutiveUpCandles)) {
    fibScore += 4;
    fibReasons.push(`fib_uptrend_${consecutiveUpCandles}h`);
  }
  return { fibScore: Math.min(fibScore, 15), fibReasons };
}

function analyzeFib4hLong(candles4h) {
  let fib4hScore = 0;
  let fib4hReasons = [];
  if (!candles4h || candles4h.length < 5) return { fib4hScore: 0, fib4hReasons: [] };
  const sorted4h = candles4h.reverse();
  const checkPoints = [5, 8, 13, 21];
  checkPoints.forEach(cp => {
    if (sorted4h.length >= cp) {
      const now = sorted4h[sorted4h.length - 1];
      const pastCandle = sorted4h[sorted4h.length - cp];
      const nowClose = parseFloat(now[4]);
      const pastLow = parseFloat(pastCandle[3]);
      if (nowClose > pastLow * 1.05) {
        fib4hScore += 2;
        fib4hReasons.push(`fib4h_${cp}candle_gain`);
      }
    }
  });
  return { fib4hScore: Math.min(fib4hScore, 8), fib4hReasons };
}

async function scanLongs() {
  const instruments = await pub('/v5/market/instruments-info', { 
    category: 'linear', 
    status: 'Trading',
    limit: 1000 
  });
  
  if (!instruments.result?.list) return [];
  
  const symbols = instruments.result.list
    .filter(i => i.symbol.endsWith('USDT') && !i.symbol.includes('USDC'))
    .map(i => i.symbol);
  
  const candidates = [];
  const BATCH_SIZE = 8;
  
  for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
    const batch = symbols.slice(i, i + BATCH_SIZE);
    
    await Promise.all(batch.map(async (symbol) => {
      try {
        const tickerRes = await pub('/v5/market/tickers', { 
          category: 'linear', 
          symbol 
        });
        const ticker = tickerRes.result?.list?.[0];
        if (!ticker) return;
        
        const price = parseFloat(ticker.lastPrice);
        const chg24 = parseFloat(ticker.price24hPcnt) * 100;
        const high24 = parseFloat(ticker.highPrice24h);
        const low24 = parseFloat(ticker.lowPrice24h);
        const vol24 = parseFloat(ticker.turnover24h) / 1e6;
        const fund = parseFloat(ticker.fundingRate) * 100;
        
        const pricePos = ((price - low24) / (high24 - low24) * 100);
        
        const MIN_VOLUME = 5;
        const MIN_FUNDING = -0.0001;
        const MAX_PRICE = 50;
        
        if (vol24 < MIN_VOLUME || price > MAX_PRICE || fund > MIN_FUNDING) return;
        
        let score = 0;
        let reasons = [];
        
        if (chg24 < -10) { score += 15; reasons.push('crashed'); }
        else if (chg24 < -5) { score += 10; reasons.push('oversold'); }
        else if (chg24 < -2) { score += 5; reasons.push('falling'); }
        
        if (pricePos < 20) { score += 12; reasons.push('24h_bottom'); }
        else if (pricePos < 40) { score += 10; reasons.push('24h_lower'); }
        
        if (fund < -0.001) { 
          const fundScore = Math.min(20, Math.abs(fund) * 10000);
          score += fundScore;
          reasons.push(`fund_neg_earn(${Math.abs(fund).toFixed(5)})`); 
        }
        
        const k1hRes = await pub('/v5/market/kline', { 
          category: 'linear', 
          symbol, 
          interval: '60', 
          limit: '55'
        });
        const k4hRes = await pub('/v5/market/kline', { 
          category: 'linear', 
          symbol, 
          interval: '240', 
          limit: '21'
        });
        
        const { fibScore, fibReasons } = analyzeFibonacciTimeSignalsLong(k1hRes.result?.list || []);
        const { fib4hScore, fib4hReasons } = analyzeFib4hLong(k4hRes.result?.list || []);
        
        score += fibScore + fib4hScore;
        reasons.push(...fibReasons, ...fib4hReasons);
        
        if (score >= 12) {
          candidates.push({
            symbol: symbol.replace('USDT', ''),
            price: price.toFixed(price < 0.1 ? 6 : 4),
            chg24: chg24.toFixed(2),
            fund: fund.toFixed(4),
            vol24: vol24.toFixed(0),
            score,
            reasons: reasons.join(',')
          });
        }
      } catch (e) {}
    }));
  }
  
  return candidates.sort((a, b) => b.score - a.score);
}

async function scanShorts() {
  const instruments = await pub('/v5/market/instruments-info', { 
    category: 'linear', 
    status: 'Trading',
    limit: 1000 
  });
  
  if (!instruments.result?.list) return [];
  
  const symbols = instruments.result.list
    .filter(i => i.symbol.endsWith('USDT') && !i.symbol.includes('USDC'))
    .map(i => i.symbol);
  
  const candidates = [];
  const BATCH_SIZE = 8;
  
  for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
    const batch = symbols.slice(i, i + BATCH_SIZE);
    
    await Promise.all(batch.map(async (symbol) => {
      try {
        const tickerRes = await pub('/v5/market/tickers', { 
          category: 'linear', 
          symbol 
        });
        const ticker = tickerRes.result?.list?.[0];
        if (!ticker) return;
        
        const price = parseFloat(ticker.lastPrice);
        const chg24 = parseFloat(ticker.price24hPcnt) * 100;
        const high24 = parseFloat(ticker.highPrice24h);
        const low24 = parseFloat(ticker.lowPrice24h);
        const vol24 = parseFloat(ticker.turnover24h) / 1e6;
        const fund = parseFloat(ticker.fundingRate) * 100;
        
        const pricePos = ((price - low24) / (high24 - low24) * 100);
        
        let score = 0;
        let reasons = [];
        
        if (pricePos > 80) { score += 20; reasons.push('24h_top'); }
        if (fund > 0.01) { score += 10; reasons.push('fund_pos_shortEarns'); }
        
        const k1hRes = await pub('/v5/market/kline', { 
          category: 'linear', 
          symbol, 
          interval: '60', 
          limit: '55'
        });
        const k4hRes = await pub('/v5/market/kline', { 
          category: 'linear', 
          symbol, 
          interval: '240', 
          limit: '21'
        });
        
        const { fibScore, fibReasons } = analyzeFibonacciTimeSignalsShort(k1hRes.result?.list || []);
        const { fib4hScore, fib4hReasons } = analyzeFib4hShort(k4hRes.result?.list || []);
        
        score += fibScore + fib4hScore;
        reasons.push(...fibReasons, ...fib4hReasons);
        
        if (score >= 10) {
          candidates.push({
            symbol: symbol.replace('USDT', ''),
            price: price.toFixed(price < 0.1 ? 6 : 4),
            chg24: chg24.toFixed(2),
            fund: fund.toFixed(4),
            vol24: vol24.toFixed(0),
            score,
            reasons: reasons.join(',')
          });
        }
      } catch (e) {}
    }));
  }
  
  return candidates.sort((a, b) => b.score - a.score);
}

async function updateDashboard(longCandidates, shortCandidates) {
  try {
    const data = {
      longCandidates,
      shortCandidates,
      statistics: {
        totalScanned: 770,
        topLongScore: longCandidates[0]?.score || 0,
        topShortScore: shortCandidates[0]?.score || 0
      },
      alerts: [{
        timestamp: new Date(),
        message: `스캔 완료: 롱 ${longCandidates.length}개, 숏 ${shortCandidates.length}개`
      }]
    };
    
    const res = await fetch(`${DASHBOARD_URL}/api/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    
    if (res.ok) {
      console.log('✅ 대시보드 업데이트 완료');
      console.log(`   롱: ${longCandidates.length}개, 숏: ${shortCandidates.length}개`);
    } else {
      console.log('⚠️ 대시보드 연결 실패. 대시보드를 먼저 시작하세요:');
      console.log('   node trading_dashboard.js');
    }
  } catch (e) {
    console.log('⚠️ 대시보드 연결 불가. 대시보드를 시작해주세요.');
  }
}

(async () => {
  console.log('🔍 스캔 시작...\n');
  
  const [longs, shorts] = await Promise.all([
    scanLongs().catch(() => []),
    scanShorts().catch(() => [])
  ]);
  
  console.log(`\n✅ 스캔 완료`);
  console.log(`   롱 후보: ${longs.length}개 (TOP: ${longs[0]?.symbol} ${longs[0]?.score}점)`);
  console.log(`   숏 후보: ${shorts.length}개 (TOP: ${shorts[0]?.symbol} ${shorts[0]?.score}점)`);
  
  await updateDashboard(longs, shorts);
  
  console.log('\n📊 최상위 후보:');
  longs.slice(0, 3).forEach((c, i) => {
    console.log(`  ${i+1}. ${c.symbol.padEnd(6)} 점수: ${c.score} (${c.chg24}%)`);
  });
})().catch(e => console.error(e));
