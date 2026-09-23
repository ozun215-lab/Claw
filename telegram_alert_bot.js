#!/usr/bin/env node
/**
 * Telegram Alert Bot for Bybit Trading
 * 진입 포지션과 후보를 구분하여 알림 발송
 */

const https = require('https');

// Configuration
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '';
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID || '';
const DASHBOARD_URL = 'http://localhost:3000/api/dashboard';

let lastUpdate = {
  longCount: 0,
  shortCount: 0,
  positionCount: 0
};

async function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : require('http');
    client.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

async function sendTelegramMessage(message) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) {
    console.log('⚠️  Telegram not configured. Skipping message.');
    return;
  }

  return new Promise((resolve, reject) => {
    const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;
    const postData = JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text: message,
      parse_mode: 'HTML'
    });

    const options = {
      hostname: 'api.telegram.org',
      path: `/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const result = JSON.parse(data);
          if (result.ok) {
            console.log(`✅ Message sent to Telegram`);
            resolve();
          } else {
            console.log(`❌ Telegram error: ${result.description}`);
            reject(result.description);
          }
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

async function checkAndNotify() {
  try {
    const data = await fetchJSON(DASHBOARD_URL);
    const longCount = data.longCandidates.length;
    const shortCount = data.shortCandidates.length;
    const positionCount = data.positions.length;

    let messages = [];

    // 📈 New Long Candidates (후보 - TP 제외)
    if (longCount > lastUpdate.longCount) {
      const newCount = longCount - lastUpdate.longCount;
      const topLongs = data.longCandidates.slice(0, 3);
      let msg = `🟢 <b>새로운 롱 후보</b> +${newCount}개\n\n`;
      topLongs.forEach((c, i) => {
        const sl = (parseFloat(c.price) * 0.97).toFixed(c.price < 0.1 ? 6 : 4);
        msg += `${i + 1}. <b>${c.symbol}</b> (${c.score}점)\n`;
        msg += `   📍 진입: $${c.price}\n`;
        msg += `   🛑 SL: $${sl}\n`;
        msg += `   📈 24h: ${c.chg24}% | 펀딩: ${c.fund}%\n\n`;
      });
      messages.push(msg.trim());
    }

    // 📉 New Short Candidates (후보 - TP 제외)
    if (shortCount > lastUpdate.shortCount) {
      const newCount = shortCount - lastUpdate.shortCount;
      const topShorts = data.shortCandidates.slice(0, 3);
      let msg = `🔴 <b>새로운 숏 후보</b> +${newCount}개\n\n`;
      topShorts.forEach((c, i) => {
        const sl = (parseFloat(c.price) * 1.03).toFixed(c.price < 0.1 ? 6 : 4);
        msg += `${i + 1}. <b>${c.symbol}</b> (${c.score}점)\n`;
        msg += `   📍 진입: $${c.price}\n`;
        msg += `   🛑 SL: $${sl}\n`;
        msg += `   📈 24h: ${c.chg24}% | 펀딩: ${c.fund}%\n\n`;
      });
      messages.push(msg.trim());
    }

    // 💼 New Position
    if (positionCount > lastUpdate.positionCount) {
      const newPositions = data.positions.slice(-1)[0];
      messages.push(
        `💼 <b>새로운 포지션 진입</b>\n` +
        `심볼: <b>${newPositions.symbol}</b> (${newPositions.direction})\n` +
        `진입가: $${newPositions.entryPrice}\n` +
        `🛑 SL: $${newPositions.sl}\n` +
        `✅ TP1: $${newPositions.tp1}\n` +
        `✅ TP2: $${newPositions.tp2}`
      );
    }

    // 💼 Position Closed
    if (positionCount < lastUpdate.positionCount) {
      messages.push(
        `🏁 <b>포지션 종료</b>\n` +
        `진입 포지션: ${positionCount}개 (${lastUpdate.positionCount - positionCount}개 종료)`
      );
    }

    // Send notifications
    for (const msg of messages) {
      await sendTelegramMessage(msg);
      await new Promise(r => setTimeout(r, 500)); // Rate limit
    }

    // Update last state
    lastUpdate = { longCount, shortCount, positionCount };

  } catch (e) {
    console.error(`❌ Error checking dashboard: ${e.message}`);
  }
}

// Periodic check (every 5 minutes)
async function startMonitoring() {
  console.log(`
╔════════════════════════════════════════════════════════════╗
║         📱 Telegram Alert Bot - Started                    ║
╚════════════════════════════════════════════════════════════╝

🔧 설정:
   BOT_TOKEN: ${TELEGRAM_BOT_TOKEN ? '✅ 설정됨' : '❌ 미설정'}
   CHAT_ID: ${TELEGRAM_CHAT_ID ? '✅ 설정됨' : '❌ 미설정'}

📊 모니터링 대상:
   - 🟢 롱 후보 변화
   - 🔴 숏 후보 변화
   - 💼 포지션 진입/종료

⏰ 체크 주기: 5분

설정 방법:
  export TELEGRAM_BOT_TOKEN=<YOUR_BOT_TOKEN>
  export TELEGRAM_CHAT_ID=<YOUR_CHAT_ID>

`);

  // Initial check
  await checkAndNotify();

  // Periodic check every 5 minutes
  setInterval(checkAndNotify, 5 * 60 * 1000);
}

startMonitoring().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});

process.on('SIGINT', () => {
  console.log('\n🛑 Telegram bot stopped');
  process.exit(0);
});
