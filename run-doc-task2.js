const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const gsk = path.join(
  process.env.APPDATA,
  'Genspark Claw',
  'bundled-resources',
  'openclaw',
  'node_modules',
  '.bin',
  'gsk.cmd'
);

const taskName = "Win11 QCOW2 Backup Debian11";
const query = "Debian 11 backports libvirt 환경 기준, Windows 11 QCOW2 Backing File 백업 관리 방안을 한국어 전문 기술 문서로 작성하세요. 표지(제목/버전/날짜), 목차, 각 섹션을 포함하고 PDF 출력에 적합한 A4 Word 스타일로 구성하세요.";

const instrFile = path.join(os.tmpdir(), 'vm-backup-instr.txt');
const instructions = fs.readFileSync(instrFile, 'utf8');

console.log('gsk path:', gsk);
console.log('instructions length:', instructions.length);

try {
  const result = execFileSync('cmd', [
    '/c', gsk,
    'task', 'docs',
    '--task_name', taskName,
    '--query', query,
    '--instructions', instructions,
    '-o', 'D:\\Claw\\workspace\\win11-qcow2-backup-debian11.docx'
  ], {
    encoding: 'utf8',
    maxBuffer: 100 * 1024 * 1024,
    timeout: 290000,
    windowsHide: true,
    env: { ...process.env }
  });
  console.log('SUCCESS');
  console.log(result.slice(0, 2000));
} catch (e) {
  console.error('ERROR:', e.message.slice(0, 500));
  if (e.stdout) console.log('STDOUT:', e.stdout.slice(0, 2000));
  if (e.stderr) console.error('STDERR:', e.stderr.slice(0, 1000));
}
