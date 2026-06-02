const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const gskMain = path.join(
  process.env.APPDATA,
  'Genspark Claw',
  'bundled-resources',
  'openclaw',
  'node_modules',
  '@genspark',
  'cli',
  'dist',
  'index.js'
);

const instrFile = path.join(os.tmpdir(), 'vm-backup-instr.txt');
const instructions = fs.readFileSync(instrFile, 'utf8');

const taskName = "Win11 QCOW2 Backup Debian11";
const query = "Debian 11 backports libvirt 환경 기준, Windows 11 QCOW2 Backing File 백업 관리 방안을 한국어 전문 기술 문서로 작성하세요. 표지(제목/버전/날짜), 목차, 각 섹션을 포함하고 PDF 출력에 적합한 A4 Word 스타일로 구성하세요.";
const outFile = 'D:\\Claw\\workspace\\win11-qcow2-backup-debian11.docx';

console.log('gsk main:', gskMain);

// spawn node with the script directly as the process
const args = [
  'task', 'docs',
  '--task_name', taskName,
  '--query', query,
  '--instructions', instructions,
  '-o', outFile
];

// Require the CLI module and patch argv
process.argv = [process.execPath, gskMain, ...args];

try {
  require(gskMain);
} catch(e) {
  console.error('require error:', e.message);
}
