const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

// Fibonacci sequence for time-based analysis
const FIB_SEQUENCE = [5, 8, 13, 21, 34, 55];

// Analyze 1h candles for Fibonacci time reversal signals
function analyzeFibonacciTimeSignals(candles1h) {
  let fibScore = 0;
  let fibReasons = [];
  
  if (!candles1h || candles1h.length < 5) return { fibScore: 0, fibReasons: [] };
  
  // Reverse to chronological order (oldest first)
  const sortedCandles = candles1h.reverse();
  
  FIB_SEQUENCE.forEach(fib => {
    if (sortedCandles.length >= fib) {
      const currentCandle = sortedCandles[sortedCandles.length - 1];
      const fibCandle = sortedCandles[sortedCandles.length - fib];
      
      const currentClose = parseFloat(currentCandle[4]);
      const currentOpen = parseFloat(currentCandle[1]);
      const fibLow = parseFloat(fibCandle[3]);
      const fibHigh = parseFloat(fibCandle[2]);
      
      // Signal 1: Price at Fib time was in downtrend, now recovering
      if (fibLow < currentClose && (currentClose - fibLow) / fibLow > 0.02) {
        fibScore += 3;
        fibReasons.push(`fib_${fib}h_recovery`);
      }
      
      // Signal 2: Fib candle was red, current is green (reversal)
      const fibChange = parseFloat(fibCandle[4]) - parseFloat(fibCandle[1]);
      const currentChange = currentClose - currentOpen;
      if (fibChange < 0 && currentChange > 0) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_reversal`);
      }
      
      // Signal 3: Current candle close > Fib candle high (breakout)
      if (currentClose > fibHigh * 1.02) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_breakout`);
      }
    }
  });
  
  // Analyze uptrend duration (consecutive green candles)
  let consecutiveUpCandles = 0;
  for (let i = sortedCandles.length - 1; i >= 0; i--) {
    if (parseFloat(sortedCandles[i][4]) > parseFloat(sortedCandles[i][1])) {
      consecutiveUpCandles++;
    } else {
      break;
    }
  }
  
  // Bonus: uptrend at Fibonacci durations (5, 8, 13 hours)
  if ([5, 8, 13, 21].includes(consecutiveUpCandles)) {
    fibScore += 4;
    fibReasons.push(`fib_uptrend_${consecutiveUpCandles}h`);
  } else if (consecutiveUpCandles > 3 && consecutiveUpCandles < 5) {
    fibScore += 2;
    fibReasons.push(`pre_fib_reversal_${consecutiveUpCandles}h`);
  }
  
  return { fibScore: Math.min(fibScore, 15), fibReasons };
}

// Analyze 4h candles for longer-term Fibonacci signals
function analyzeFib4h(candles4h) {
  let fib4hScore = 0;
  let fib4hReasons = [];
  
  if (!candles4h || candles4h.length < 5) return { fib4hScore: 0, fib4hReasons: [] };
  
  const sorted4h = candles4h.reverse();
  
  // Check 5-day (30 x 4h) and 8-day (48 x 4h approx with 21 candles = 84h = 3.5 days)
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

(async () => {
  console.log('=== Bybit Long Scanner (Fibonacci Time Enhanced) ===');
  console.log(`Time: ${new Date().toISOString()}\n`);
  
  const instruments = await pub('/v5/market/instruments-info', { 
    category: 'linear', 
    status: 'Trading',
    limit: 1000 
  });
  
  if (!instruments.result?.list) {
    console.error('Failed to fetch symbols');
    return;
  }
  
  const symbols = instruments.result.list
    .filter(i => i.symbol.endsWith('USDT') && !i.symbol.includes('USDC'))
    .map(i => i.symbol);
  
  console.log(`Scanning ${symbols.length} USDT perp symbols...\n`);
  
  const candidates = [];
  const BATCH_SIZE = 8;
  
  for (let i = 0; i < symbols.length; i += BATCH_SIZE) {
    const batch = symbols.slice(i, i + BATCH_SIZE);
    
    await Promise.all(batch.map(async (symbol) => {
      try {
        // 1. Ticker data
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
        const oi = parseFloat(ticker.openInterestValue) / 1e6;
        
        const pricePos = ((price - low24) / (high24 - low24) * 100);
        const range = ((high24 - low24) / low24 * 100);
        
        // Safety filters
        const MIN_VOLUME = 5;
        const MIN_FUNDING = -0.0001;
        const MAX_PRICE = 50;
        
        if (vol24 < MIN_VOLUME || price > MAX_PRICE || fund > MIN_FUNDING) {
          return;
        }
        
        // 2. Fetch 1h candles (55 for Fibonacci analysis)
        const k1hRes = await pub('/v5/market/kline', { 
          category: 'linear', 
          symbol, 
          interval: '60', 
          limit: '55'
        });
        const candles1h = k1hRes.result?.list || [];
        
        // 3. Fetch 4h candles (21 for longer-term)
        const k4hRes = await pub('/v5/market/kline', { 
          category: 'linear', 
          symbol, 
          interval: '240', 
          limit: '21'
        });
        const candles4h = k4hRes.result?.list || [];
        
        // Base score (existing logic)
        let score = 0;
        let reasons = [];
        
        if (chg24 < -10) { score += 15; reasons.push('crashed'); }
        else if (chg24 < -5) { score += 10; reasons.push('oversold'); }
        else if (chg24 < -2) { score += 5; reasons.push('falling'); }
        else if (chg24 > 5) { score -= 10; reasons.push('overbought'); }
        
        if (pricePos < 20) { score += 12; reasons.push('24h_bottom'); }
        else if (pricePos < 40) { score += 10; reasons.push('24h_lower'); }
        else if (pricePos > 80) { score -= 15; reasons.push('24h_top'); }
        else if (pricePos > 60) { score -= 10; reasons.push('24h_upper'); }
        
        if (fund < -0.001) { 
          const fundScore = Math.min(20, Math.abs(fund) * 10000);
          score += fundScore;
          reasons.push(`fund_neg_earn(${Math.abs(fund).toFixed(5)})`); 
        }
        else if (fund > 0.0001) { 
          score -= 15; 
          reasons.push('fund_pos_longPays'); 
        }
        
        if (vol24 > 100) { score += 5; reasons.push('vol_high'); }
        else if (vol24 > 50) { score += 3; reasons.push('vol_med'); }
        else if (vol24 > 20) { score += 2; reasons.push('vol_ok'); }
        
        if (pricePos < 10) { score += 3; reasons.push('extreme_bottom'); }
        
        // FIBONACCI TIME ANALYSIS (NEW)
        const { fibScore, fibReasons } = analyzeFibonacciTimeSignals(candles1h);
        const { fib4hScore, fib4hReasons } = analyzeFib4h(candles4h);
        
        score += fibScore + fib4hScore;
        reasons.push(...fibReasons, ...fib4hReasons);
        
        if (score >= 12) {
          candidates.push({
            symbol: symbol.replace('USDT',''),
            price: price.toFixed(price < 0.1 ? 6 : price < 10 ? 4 : 2),
            chg24: chg24.toFixed(2),
            fund: fund.toFixed(4),
            vol24: vol24.toFixed(0),
            oi: oi.toFixed(0),
            range: range.toFixed(1),
            pricePos: pricePos.toFixed(0),
            score,
            reasons: reasons.join(','),
            candles1h,
            candles4h,
            rawPrice: price
          });
        }
      } catch (e) {}
    }));
    
    if ((i + BATCH_SIZE) % 100 === 0 || i + BATCH_SIZE >= symbols.length) {
      console.log(`  ... ${Math.min(i + BATCH_SIZE, symbols.length)}/${symbols.length} done`);
    }
  }
  
  candidates.sort((a, b) => b.score - a.score);
  
  console.log(`\n=== TOP ${Math.min(candidates.length, 20)} Long Candidates (Fibonacci Enhanced) ===\n`);
  console.log('Rank | Symbol | Price | 24h% | Funding | Vol$M | OI$M | Range% | Pos% | Score | Reasons');
  console.log('-----|--------|-------|------|---------|-------|-------|--------|------|-------|--------');
  
  candidates.slice(0, 20).forEach((c, i) => {
    console.log(`${(i+1).toString().padStart(2)} | ${c.symbol.padEnd(6)} | $${c.price.padEnd(10)} | ${c.chg24.padStart(6)}% | ${c.fund}% | $${c.vol24.padStart(6)}M | $${c.oi.padStart(5)}M | ${c.range.padStart(5)}% | ${c.pricePos.padStart(3)}% | ${c.score.toString().padStart(3)} | ${c.reasons}`);
  });
  
  console.log(`\nTotal candidates: ${candidates.length} / ${symbols.length}\n`);
  
  if (candidates.length > 0) {
    console.log('=== TOP 5 Detail ===\n');
    
    for (let i = 0; i < Math.min(5, candidates.length); i++) {
      const c = candidates[i];
      const symbol = c.symbol + 'USDT';
      
      console.log(`\n--- ${c.symbol} Detail ---`);
      console.log(`Score: ${c.score} | Reasons: ${c.reasons}`);
      console.log(`Price: $${c.price} | 24h: ${c.chg24}% | Funding: ${c.fund}%`);
      
      // Display 4h candles
      if (c.candles4h && c.candles4h.length > 0) {
        console.log('\n4h candles (last 6):');
        c.candles4h.reverse().slice(-6).forEach(r => {
          const dt = new Date(parseInt(r[0])).toISOString().slice(5,16);
          const o = parseFloat(r[1]), h = parseFloat(r[2]), l = parseFloat(r[3]), cl = parseFloat(r[4]);
          const pct = ((cl-o)/o*100).toFixed(2);
          console.log(`  ${dt} O:$${o.toFixed(4)} H:$${h.toFixed(4)} L:$${l.toFixed(4)} C:$${cl.toFixed(4)} ${pct}%`);
        });
      }
      
      // Display 1h Fibonacci analysis
      if (c.candles1h && c.candles1h.length > 0) {
        console.log('\n1h Fibonacci signals (last 13 hours):');
        c.candles1h.reverse().slice(-13).forEach((r, idx) => {
          const dt = new Date(parseInt(r[0])).toISOString().slice(11,16);
          const o = parseFloat(r[1]), cl = parseFloat(r[4]);
          const pct = ((cl-o)/o*100).toFixed(2);
          const signal = cl > o ? '▲' : '▼';
          console.log(`  ${dt} ${signal} ${pct}%`);
        });
      }
      
      const price = c.rawPrice;
      console.log(`\nSuggested SL/TP (long, 2x):`);
      console.log(`  Entry: $${price.toFixed(price < 0.1 ? 6 : 4)}`);
      console.log(`  SL: $${(price * 0.97).toFixed(price < 0.1 ? 6 : 4)} (-3%)`);
      console.log(`  TP1: $${(price * 1.05).toFixed(price < 0.1 ? 6 : 4)} (+5%)`);
      console.log(`  TP2: $${(price * 1.10).toFixed(price < 0.1 ? 6 : 4)} (+10%)`);
    }
  }
  
  console.log('\n=== Done ===');
})().catch(e => console.error(e));
