const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

// Fibonacci sequence for time-based analysis
const FIB_SEQUENCE = [5, 8, 13, 21, 34, 55];

// Analyze 1h candles for Fibonacci time reversal signals (SHORT version)
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
      
      // Signal 1: Price at Fib time was in uptrend, now recovering downward
      if (fibHigh > currentClose && (fibHigh - currentClose) / fibHigh > 0.02) {
        fibScore += 3;
        fibReasons.push(`fib_${fib}h_decline`);
      }
      
      // Signal 2: Fib candle was green, current is red (reversal)
      const fibChange = parseFloat(fibCandle[4]) - parseFloat(fibCandle[1]);
      const currentChange = currentClose - currentOpen;
      if (fibChange > 0 && currentChange < 0) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_reversal`);
      }
      
      // Signal 3: Current candle close < Fib candle low (breakdown)
      if (currentClose < fibLow * 0.98) {
        fibScore += 2;
        fibReasons.push(`fib_${fib}h_breakdown`);
      }
    }
  });
  
  // Analyze downtrend duration (consecutive red candles)
  let consecutiveDownCandles = 0;
  for (let i = sortedCandles.length - 1; i >= 0; i--) {
    if (parseFloat(sortedCandles[i][4]) < parseFloat(sortedCandles[i][1])) {
      consecutiveDownCandles++;
    } else {
      break;
    }
  }
  
  // Bonus: downtrend at Fibonacci durations
  if ([5, 8, 13, 21].includes(consecutiveDownCandles)) {
    fibScore += 4;
    fibReasons.push(`fib_downtrend_${consecutiveDownCandles}h`);
  } else if (consecutiveDownCandles > 3 && consecutiveDownCandles < 5) {
    fibScore += 2;
    fibReasons.push(`pre_fib_reversal_${consecutiveDownCandles}h`);
  }
  
  return { fibScore: Math.min(fibScore, 15), fibReasons };
}

// Analyze 4h candles for longer-term Fibonacci signals (SHORT)
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

(async () => {
  console.log('=== Bybit Short Scanner (Fibonacci Time Enhanced) ===');
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
        
        let score = 0;
        let reasons = [];
        
        if (chg24 > 5) { score -= 10; reasons.push('overbought'); }
        else if (chg24 > 2) { score -= 5; reasons.push('rising'); }
        else if (chg24 < -5) { score += 10; reasons.push('oversold_bounce'); }
        else if (chg24 < -2) { score += 5; reasons.push('falling'); }
        
        if (pricePos > 80) { score += 20; reasons.push('24h_top'); }
        else if (pricePos > 60) { score += 15; reasons.push('24h_upper'); }
        else if (pricePos < 20) { score -= 15; reasons.push('24h_bottom'); }
        else if (pricePos < 40) { score -= 10; reasons.push('24h_lower'); }
        
        if (fund > 0.05) { score += 15; reasons.push('fund_pos_shortEarns'); }
        else if (fund > 0.01) { score += 10; reasons.push('fund_pos_shortEarns'); }
        else if (fund < -0.1) { score -= 20; reasons.push('fund_neg_shortPays!'); }
        else if (fund < -0.03) { score -= 10; reasons.push('fund_neg_shortPays'); }
        
        if (vol24 > 100) { score += 5; reasons.push('vol_high'); }
        else if (vol24 > 50) { score += 3; reasons.push('vol_med'); }
        else if (vol24 < 1) { score -= 5; reasons.push('vol_low'); }
        
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
        
        // FIBONACCI TIME ANALYSIS (SHORT VERSION)
        const { fibScore, fibReasons } = analyzeFibonacciTimeSignalsShort(candles1h);
        const { fib4hScore, fib4hReasons } = analyzeFib4hShort(candles4h);
        
        score += fibScore + fib4hScore;
        reasons.push(...fibReasons, ...fib4hReasons);
        
        if (score >= 10) {
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
  
  console.log(`\n=== TOP ${Math.min(candidates.length, 20)} Short Candidates (Fibonacci Enhanced) ===\n`);
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
      
      if (c.candles4h && c.candles4h.length > 0) {
        console.log('\n4h candles (last 6):');
        c.candles4h.reverse().slice(-6).forEach(r => {
          const dt = new Date(parseInt(r[0])).toISOString().slice(5,16);
          const o = parseFloat(r[1]), h = parseFloat(r[2]), l = parseFloat(r[3]), cl = parseFloat(r[4]);
          const pct = ((cl-o)/o*100).toFixed(2);
          console.log(`  ${dt} O:$${o.toFixed(4)} H:$${h.toFixed(4)} L:$${l.toFixed(4)} C:$${cl.toFixed(4)} ${pct}%`);
        });
      }
      
      if (c.candles1h && c.candles1h.length > 0) {
        console.log('\n1h Fibonacci signals (last 13 hours):');
        c.candles1h.reverse().slice(-13).forEach((r, idx) => {
          const dt = new Date(parseInt(r[0])).toISOString().slice(11,16);
          const o = parseFloat(r[1]), cl = parseFloat(r[4]);
          const pct = ((cl-o)/o*100).toFixed(2);
          const signal = cl < o ? '▼' : '▲';
          console.log(`  ${dt} ${signal} ${pct}%`);
        });
      }
      
      const price = c.rawPrice;
      console.log(`\nSuggested SL/TP (short, 2x):`);
      console.log(`  Entry: $${price.toFixed(price < 0.1 ? 6 : 4)}`);
      console.log(`  SL: $${(price * 1.03).toFixed(price < 0.1 ? 6 : 4)} (+3%)`);
      console.log(`  TP1: $${(price * 0.95).toFixed(price < 0.1 ? 6 : 4)} (-5%)`);
      console.log(`  TP2: $${(price * 0.90).toFixed(price < 0.1 ? 6 : 4)} (-10%)`);
    }
  }
  
  console.log('\n=== Done ===');
})().catch(e => console.error(e));
