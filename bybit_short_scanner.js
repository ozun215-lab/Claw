const BASE_URL = 'https://api.bybit.com';

async function pub(endpoint, params = {}) {
  const qs = Object.keys(params).map(k => `${k}=${params[k]}`).join('&');
  const res = await fetch(`${BASE_URL}${endpoint}${qs ? '?' + qs : ''}`);
  return res.json();
}

(async () => {
  console.log('=== Bybit Short Scanner ===');
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
  const BATCH_SIZE = 10;
  
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
        
        if (fund < -0.05) { score += 15; reasons.push('funding_neg_big'); }
        else if (fund < -0.01) { score += 10; reasons.push('funding_neg'); }
        else if (fund > 0.05) { score -= 10; reasons.push('funding_pos_big'); }
        
        if (vol24 > 100) { score += 5; reasons.push('vol_high'); }
        else if (vol24 > 50) { score += 3; reasons.push('vol_med'); }
        else if (vol24 < 1) { score -= 5; reasons.push('vol_low'); }
        
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
            reasons: reasons.join(',')
          });
        }
      } catch (e) {}
    }));
    
    if ((i + BATCH_SIZE) % 100 === 0 || i + BATCH_SIZE >= symbols.length) {
      console.log(`  ... ${Math.min(i + BATCH_SIZE, symbols.length)}/${symbols.length} done`);
    }
  }
  
  candidates.sort((a, b) => b.score - a.score);
  
  console.log(`\n=== TOP ${Math.min(candidates.length, 20)} Short Candidates ===\n`);
  console.log('Rank | Symbol | Price | 24h% | Funding | Vol$M | OI$M | Range% | Pos% | Score | Reasons');
  console.log('-----|--------|-------|------|---------|-------|-------|--------|------|-------|--------');
  
  candidates.slice(0, 20).forEach((c, i) => {
    const chgEmoji = parseFloat(c.chg24) > 0 ? 'UP' : 'DN';
    const fundEmoji = parseFloat(c.fund) < 0 ? 'NEG' : 'POS';
    console.log(`${(i+1).toString().padStart(2)} | ${c.symbol.padEnd(6)} | $${c.price.padEnd(10)} | ${c.chg24.padStart(6)}% ${chgEmoji} | ${c.fund}% ${fundEmoji} | $${c.vol24.padStart(6)}M | $${c.oi.padStart(5)}M | ${c.range.padStart(5)}% | ${c.pricePos.padStart(3)}% | ${c.score.toString().padStart(3)} | ${c.reasons}`);
  });
  
  console.log(`\nTotal candidates: ${candidates.length} / ${symbols.length}\n`);
  
  // Detailed analysis TOP 5
  if (candidates.length > 0) {
    console.log('=== TOP 5 Detail ===\n');
    
    for (let i = 0; i < Math.min(5, candidates.length); i++) {
      const c = candidates[i];
      const symbol = c.symbol + 'USDT';
      
      const k4 = await pub('/v5/market/kline', { 
        category: 'linear', 
        symbol, 
        interval: '240', 
        limit: '6' 
      });
      
      console.log(`\n--- ${c.symbol} Detail ---`);
      console.log(`Score: ${c.score} | Reasons: ${c.reasons}`);
      console.log(`Price: $${c.price} | 24h: ${c.chg24}% | Funding: ${c.fund}%`);
      
      if (k4.result?.list) {
        console.log('\n4h candles:');
        k4.result.list.reverse().forEach(r => {
          const dt = new Date(parseInt(r[0])).toISOString().slice(11,16);
          const o = parseFloat(r[1]), h = parseFloat(r[2]), l = parseFloat(r[3]), cl = parseFloat(r[4]);
          const pct = ((cl-o)/o*100).toFixed(2);
          const em = parseFloat(pct) > 0 ? 'RED' : 'GREEN';
          console.log(`  ${dt} O:$${o.toFixed(4)} H:$${h.toFixed(4)} L:$${l.toFixed(4)} C:$${cl.toFixed(4)} ${pct}% ${em}`);
        });
      }
      
      const price = parseFloat(c.price);
      console.log(`\nSuggested SL/TP (short, 2x):`);
      console.log(`  Entry: $${price.toFixed(4)}`);
      console.log(`  SL: $${(price * 1.03).toFixed(4)} (+3%)`);
      console.log(`  TP1: $${(price * 0.95).toFixed(4)} (-5%)`);
      console.log(`  TP2: $${(price * 0.90).toFixed(4)} (-10%)`);
    }
  }
  
  console.log('\n=== Done ===');
})().catch(e => console.error(e));
