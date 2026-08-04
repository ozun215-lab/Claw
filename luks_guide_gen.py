import os, sys
sys.stdout.reconfigure(encoding='utf-8')

html = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Debian LUKS 다중 디스크 단일 암호 구성 가이드</title>
<style>
@page {
    size: A4;
    margin: 2.2cm 2.5cm 2.8cm 2.5cm;
    @bottom-right { content: counter(page) " / " counter(pages); font-size: 9pt; color: #888; }
    @top-left { content: "Debian LUKS Multi-Disk Guide"; font-size: 8pt; color: #aaa; }
}
* { box-sizing: border-box; }
body {
    font-family: "Malgun Gothic","맑은 고딕","Noto Sans KR",sans-serif;
    font-size: 10.5pt; line-height: 1.75; color: #1e2a38; background: #fff;
}

/* ── 커버 ─────────────────────────────── */
.cover {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: #fff; padding: 60px 40px; border-radius: 8px;
    margin-bottom: 40px; page-break-after: always;
}
.cover .badge {
    display: inline-block; background: rgba(255,255,255,0.15);
    padding: 4px 14px; border-radius: 20px; font-size: 9pt;
    letter-spacing: 1px; text-transform: uppercase; margin-bottom: 20px;
}
.cover h1 {
    font-size: 28pt; margin: 0 0 8px 0; border: none;
    color: #e2f0ff; font-weight: 700; letter-spacing: -0.5px;
}
.cover .subtitle {
    font-size: 14pt; color: #a8c8e8; margin-bottom: 30px; font-weight: 300;
}
.cover .meta { font-size: 9pt; color: #7fa8c8; line-height: 2; margin-top: 30px; }
.cover .meta span { color: #c8e0f0; font-weight: 600; }

/* ── 목차 ─────────────────────────────── */
.toc {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 25px 30px; margin-bottom: 35px; page-break-after: always;
}
.toc h2 { font-size: 14pt; color: #2d3748; margin: 0 0 18px 0; border: none; background: none; padding: 0; }
.toc ol { margin: 0; padding-left: 22px; }
.toc li { padding: 5px 0; font-size: 10pt; color: #4a5568; border-bottom: 1px dashed #e2e8f0; }
.toc li:last-child { border: none; }
.toc .toc-step { color: #3182ce; font-weight: 600; }
.toc .toc-sub { font-size: 9pt; color: #718096; margin-left: 10px; }

/* ── 섹션 헤더 ─────────────────────────── */
h2 {
    font-size: 15pt; font-weight: 700; color: #fff;
    background: linear-gradient(90deg, #2b6cb0 0%, #3182ce 100%);
    padding: 12px 20px; border-radius: 6px;
    margin: 35px 0 18px 0; page-break-after: avoid;
    display: flex; align-items: center; gap: 10px;
}
h2 .step-num {
    background: rgba(255,255,255,0.25); border-radius: 50%;
    width: 28px; height: 28px; display: inline-flex;
    align-items: center; justify-content: center;
    font-size: 11pt; font-weight: 700; flex-shrink: 0;
}
h3 {
    font-size: 11.5pt; color: #2d3748; font-weight: 700;
    border-left: 4px solid #48bb78; padding: 6px 12px;
    margin: 22px 0 10px 0; background: #f0fff4; border-radius: 0 4px 4px 0;
    page-break-after: avoid;
}
h4 {
    font-size: 10.5pt; color: #553c9a; font-weight: 700;
    margin: 18px 0 8px 0; page-break-after: avoid;
}

/* ── 알림 박스 ─────────────────────────── */
.box {
    border-radius: 6px; padding: 14px 18px; margin: 16px 0;
    font-size: 10pt; line-height: 1.65; page-break-inside: avoid;
}
.box-icon { font-size: 16pt; margin-right: 8px; vertical-align: middle; }
.danger  { background: #fff5f5; border-left: 5px solid #e53e3e; color: #742a2a; }
.warning { background: #fffbeb; border-left: 5px solid #d69e2e; color: #744210; }
.info    { background: #ebf8ff; border-left: 5px solid #3182ce; color: #1a365d; }
.success { background: #f0fff4; border-left: 5px solid #38a169; color: #1c4532; }
.note    { background: #faf5ff; border-left: 5px solid #805ad5; color: #322659; }

/* ── 코드 블록 ─────────────────────────── */
.code-block {
    background: #1e2a38; border-radius: 6px;
    margin: 14px 0; overflow: hidden; page-break-inside: avoid;
}
.code-label {
    background: #0f1923; padding: 6px 14px;
    font-size: 8pt; color: #64b5f6; font-family: monospace;
    letter-spacing: 0.5px; display: flex; align-items: center; gap: 8px;
}
.code-label::before { content: "●"; color: #ef5350; }
.code-label::after  { content: "●"; color: #ffca28; }
code.block {
    display: block; background: none; color: #e8f4f8;
    padding: 14px 18px; font-family: "Consolas","Courier New",monospace;
    font-size: 9pt; line-height: 1.6; white-space: pre; overflow-x: auto;
}
.comment { color: #78909c; }
.cmd     { color: #80deea; }
.param   { color: #a5d6a7; }
.str     { color: #ffcc80; }
.warn-c  { color: #ef9a9a; }

/* ── 인라인 코드 ─────────────────────────── */
code:not(.block) {
    background: #edf2f7; color: #c53030; padding: 2px 6px;
    border-radius: 3px; font-family: "Consolas","Courier New",monospace;
    font-size: 9pt; border: 1px solid #e2e8f0;
}

/* ── 표 ────────────────────────────────── */
table {
    width: 100%; border-collapse: collapse; margin: 16px 0;
    font-size: 10pt; page-break-inside: avoid; box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    border-radius: 6px; overflow: hidden;
}
th {
    background: linear-gradient(135deg, #434190, #553c9a);
    color: #fff; padding: 11px 14px; text-align: left;
    font-size: 9.5pt; font-weight: 600; letter-spacing: 0.3px;
}
td { padding: 10px 14px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr:nth-child(even) td { background: #f7fafc; }
td.label { font-weight: 600; color: #2d3748; white-space: nowrap; }
td.ok    { color: #276749; font-weight: 600; }
td.err   { color: #c53030; font-weight: 600; }

/* ── 체크리스트 ─────────────────────────── */
.checklist { list-style: none; padding: 0; margin: 12px 0; }
.checklist li {
    padding: 8px 12px 8px 40px; position: relative;
    border-bottom: 1px solid #e8edf2; font-size: 10pt;
}
.checklist li:last-child { border: none; }
.checklist li::before {
    content: "☐"; position: absolute; left: 12px;
    color: #3182ce; font-size: 14pt; line-height: 1;
}
.checklist li strong { color: #2d3748; }

/* ── 롤백 시나리오 카드 ───────────────────── */
.scenario-card {
    border: 1px solid #e2e8f0; border-radius: 8px;
    margin: 18px 0; overflow: hidden; page-break-inside: avoid;
}
.scenario-header {
    padding: 12px 18px; font-weight: 700; font-size: 11pt; color: #fff;
}
.scenario-a .scenario-header { background: #e53e3e; }
.scenario-b .scenario-header { background: #d69e2e; }
.scenario-c .scenario-header { background: #3182ce; }
.scenario-body { padding: 16px 18px; }
.scenario-steps { counter-reset: step; list-style: none; padding: 0; margin: 0; }
.scenario-steps li {
    counter-increment: step; padding: 8px 12px 8px 42px;
    position: relative; border-bottom: 1px solid #f0f4f8; font-size: 10pt;
}
.scenario-steps li:last-child { border: none; }
.scenario-steps li::before {
    content: counter(step); position: absolute; left: 10px;
    background: #2b6cb0; color: #fff; border-radius: 50%;
    width: 22px; height: 22px; display: flex; align-items: center;
    justify-content: center; font-size: 9pt; font-weight: 700;
}

/* ── 문제 해결 카드 ─────────────────────── */
.trouble-card {
    border: 1px solid #e2e8f0; border-radius: 6px;
    margin: 14px 0; page-break-inside: avoid;
}
.trouble-q {
    background: #f7fafc; padding: 10px 16px;
    font-weight: 600; color: #2d3748; font-size: 10pt;
    border-bottom: 1px solid #e2e8f0;
}
.trouble-q::before { content: "Q. "; color: #e53e3e; font-weight: 700; }
.trouble-a {
    padding: 12px 16px; font-size: 10pt;
}
.trouble-a::before { content: "A. "; color: #38a169; font-weight: 700; }

/* ── 기타 ───────────────────────────────── */
p { margin: 8px 0 10px 0; }
ul, ol { padding-left: 24px; margin: 10px 0; }
li { margin: 6px 0; }
hr { border: none; border-top: 2px solid #e2e8f0; margin: 30px 0; }
.page-break { page-break-before: always; }
.highlight { background: #fefcbf; padding: 1px 4px; border-radius: 2px; }
.diff-old { color: #c53030; text-decoration: line-through; background: #fff5f5; padding: 1px 4px; border-radius: 2px; }
.diff-new { color: #276749; background: #f0fff4; padding: 1px 4px; border-radius: 2px; }
</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════
     COVER
═══════════════════════════════════════════════ -->
<div class="cover">
  <div class="badge">Debian Security Guide</div>
  <h1>LUKS 다중 디스크<br>단일 암호 구성 가이드</h1>
  <div class="subtitle">Single Passphrase Multi-Disk Configuration<br>with Backup &amp; Rollback Procedures</div>
  <div class="meta">
    작성일: <span>2026-08-03</span><br>
    대상 OS: <span>Debian GNU/Linux (Bookworm 이상)</span><br>
    구성 목적: <span>루트 파티션 해제 시 추가 디스크 자동 해제 및 마운트</span><br>
    핵심 도구: <span>cryptsetup / decrypt_keyctl / initramfs</span><br>
    버전: <span>v2.0 (검증 및 보완 완료)</span>
  </div>
</div>

<!-- ═══════════════════════════════════════════════
     목차
═══════════════════════════════════════════════ -->
<div class="toc">
  <h2>📋 목차</h2>
  <ol>
    <li><span class="toc-step">Pre-flight Checklist</span> <span class="toc-sub">— 적용 전 필수 확인</span></li>
    <li><span class="toc-step">Step 0: 현재 설정 백업</span> <span class="toc-sub">— crypttab / fstab / blkid 스냅샷</span></li>
    <li><span class="toc-step">Step 1: 추가 디스크 암호화</span> <span class="toc-sub">— luksFormat &amp; luksOpen</span></li>
    <li><span class="toc-step">Step 2: 파일 시스템 생성</span> <span class="toc-sub">— mkfs.ext4 &amp; 마운트 테스트</span></li>
    <li><span class="toc-step">Step 3: UUID 확인</span> <span class="toc-sub">— 장치명 변경 대응</span></li>
    <li><span class="toc-step">Step 4: crypttab &amp; fstab 수정</span> <span class="toc-sub">— decrypt_keyctl 적용 (보완사항 반영)</span></li>
    <li><span class="toc-step">Step 5: initramfs 업데이트</span> <span class="toc-sub">— 부팅 이미지 재생성</span></li>
    <li><span class="toc-step">Step 6: 재부팅 및 검증</span> <span class="toc-sub">— 단일 암호 입력 확인</span></li>
    <li><span class="toc-step">롤백 절차</span> <span class="toc-sub">— 시나리오 A/B/C</span></li>
    <li><span class="toc-step">문제 해결 (Troubleshooting)</span> <span class="toc-sub">— 빈번한 오류 5종</span></li>
    <li><span class="toc-step">보안 고려사항</span> <span class="toc-sub">— 캐시 타임아웃, cryptoswap</span></li>
  </ol>
</div>

<!-- ═══════════════════════════════════════════════
     개요
═══════════════════════════════════════════════ -->
<h2><span class="step-num">✦</span> 개요 및 동작 원리</h2>

<p>루트 파티션이 LUKS로 암호화된 Debian 시스템에서, 추가 디스크 역시 LUKS 암호화되어 있을 때 부팅마다 암호를 두 번 입력해야 하는 불편함이 생깁니다.</p>
<p>본 가이드는 <code>decrypt_keyctl</code> 스크립트를 활용하여 <strong>루트 파티션 해제 시 입력한 암호를 Linux 커널 키링(keyring)에 캐싱</strong>하고, 추가 디스크 해제 시 이를 재사용하는 방법을 다룹니다.</p>

<table>
  <tr><th>구성 요소</th><th>역할</th><th>위치</th></tr>
  <tr><td class="label">decrypt_keyctl</td><td>암호 캐싱 keyscript</td><td><code>/lib/cryptsetup/scripts/decrypt_keyctl</code></td></tr>
  <tr><td class="label">Linux keyring</td><td>메모리 내 암호 임시 저장 (60초)</td><td>커널 내부 (<code>@u</code> keyring)</td></tr>
  <tr><td class="label">/etc/crypttab</td><td>LUKS 볼륨 자동 해제 설정</td><td><code>/etc/crypttab</code></td></tr>
  <tr><td class="label">initramfs</td><td>부팅 초기 단계 실행 환경</td><td><code>/boot/initrd.img-*</code></td></tr>
</table>

<div class="box warning">
  <span class="box-icon">⚠️</span>
  <strong>원본 가이드의 오류 사항 (보완 완료)</strong><br>
  원본에서 사용된 <span class="diff-old">keyscript=decrypt_key_script</span>는 <strong>존재하지 않는 스크립트명</strong>입니다.<br>
  정확한 이름은 <span class="diff-new">keyscript=decrypt_keyctl</span>이며, 세 번째 필드(keyfile)에도 <code>none</code>이 아닌 <strong>그룹 identifier</strong>를 지정해야 캐싱이 동작합니다.
</div>

<!-- ═══════════════════════════════════════════════
     PRE-FLIGHT
═══════════════════════════════════════════════ -->
<div class="page-break"></div>
<h2><span class="step-num">0</span> Pre-flight Checklist — 적용 전 필수 확인</h2>

<div class="box danger">
  <span class="box-icon">🚨</span>
  <strong>이 섹션을 건너뛰지 마십시오.</strong> LUKS 설정 오류 시 시스템이 부팅 불가 상태가 될 수 있습니다. Live USB 없이 복구는 불가능합니다.
</div>

<ul class="checklist">
  <li><strong>중요 데이터 외부 백업 완료</strong> — NAS, 외장 드라이브, 원격 스토리지</li>
  <li><strong>Live USB 또는 SystemRescueCD 준비</strong> — 반드시 사전 부팅 테스트 완료</li>
  <li><strong>root 권한 확인</strong> — <code>whoami</code> 명령 실행 시 <code>root</code> 출력 확인</li>
  <li><strong>추가 디스크 장치명 확인</strong> — <code>lsblk</code> 또는 <code>fdisk -l</code>로 <code>/dev/sdb</code> 확인</li>
  <li><strong>cryptsetup-initramfs 패키지 설치 확인</strong> — <code>dpkg -l | grep cryptsetup-initramfs</code></li>
  <li><strong>keyutils 패키지 설치 확인</strong> — <code>dpkg -l | grep keyutils</code></li>
  <li><strong>decrypt_keyctl 스크립트 존재 확인</strong> — <code>ls /lib/cryptsetup/scripts/decrypt_keyctl</code></li>
  <li><strong>SSH 이중 세션 준비 (원격 서버인 경우)</strong> — 터미널 1: 작업용 / 터미널 2: 비상용</li>
</ul>

<div class="code-block">
  <div class="code-label">bash — 사전 환경 확인 스크립트</div>
  <code class="block"><span class="comment"># 패키지 확인 및 설치</span>
<span class="cmd">dpkg -l | grep -E "cryptsetup|keyutils"</span>
<span class="cmd">apt-get install -y cryptsetup cryptsetup-initramfs keyutils</span>

<span class="comment"># decrypt_keyctl 스크립트 확인</span>
<span class="cmd">ls -la /lib/cryptsetup/scripts/decrypt_keyctl</span>

<span class="comment"># 커널 키링 지원 확인</span>
<span class="cmd">grep CONFIG_KEYS /boot/config-$(uname -r)</span>
<span class="comment"># CONFIG_KEYS=y 출력되면 정상</span></code>
</div>

<!-- ═══════════════════════════════════════════════
     STEP 0: 백업
═══════════════════════════════════════════════ -->
<h2><span class="step-num">↗</span> Step 0 — 현재 설정 백업 (필수)</h2>

<p>모든 설정 변경 전, 현재 상태를 타임스탬프가 포함된 파일로 보존합니다.</p>

<div class="code-block">
  <div class="code-label">bash — 자동 백업 스크립트</div>
  <code class="block"><span class="comment"># 타임스탬프 변수 설정</span>
<span class="param">TS=$(date +%Y%m%d_%H%M%S)</span>

<span class="comment"># 핵심 설정 파일 백업</span>
<span class="cmd">cp /etc/crypttab /etc/crypttab.backup.${TS}</span>
<span class="cmd">cp /etc/fstab    /etc/fstab.backup.${TS}</span>

<span class="comment"># 현재 블록 장치 및 마운트 상태 기록</span>
<span class="cmd">blkid  > /root/blkid_${TS}.txt</span>
<span class="cmd">lsblk  > /root/lsblk_${TS}.txt</span>
<span class="cmd">mount  > /root/mount_${TS}.txt</span>

<span class="comment"># 백업 확인</span>
<span class="cmd">ls -la /etc/crypttab.backup.* /etc/fstab.backup.*</span>
echo <span class="str">"✅ 백업 완료: /etc/crypttab.backup.${TS}"</span>
echo <span class="str">"✅ 백업 완료: /etc/fstab.backup.${TS}"</span></code>
</div>

<div class="box info">
  <span class="box-icon">💡</span>
  백업 파일의 타임스탬프를 반드시 기록해 두십시오. 롤백 시 정확한 파일명이 필요합니다.<br>
  예: <code>/etc/crypttab.backup.20260803_180000</code>
</div>

<!-- ═══════════════════════════════════════════════
     STEP 1
═══════════════════════════════════════════════ -->
<div class="page-break"></div>
<h2><span class="step-num">1</span> Step 1 — 추가 디스크 암호화</h2>

<div class="box danger">
  <span class="box-icon">🚨</span>
  <strong>반드시 루트 파티션과 동일한 암호를 사용하십시오.</strong> 암호가 다르면 캐싱이 무의미하며, 부팅 시 추가 암호 입력 창이 나타납니다.
</div>

<div class="code-block">
  <div class="code-label">bash — LUKS 포맷 및 열기</div>
  <code class="block"><span class="comment"># 1-1. 대상 디스크 최종 확인 (sdb인지 재확인)</span>
<span class="cmd">lsblk /dev/sdb</span>

<span class="comment"># 1-2. LUKS 포맷 (기존 데이터 모두 삭제됨 — 주의!)</span>
<span class="warn-c">cryptsetup luksFormat /dev/sdb</span>
<span class="comment"># 프롬프트: YES 입력 후 루트 파티션과 동일한 암호 입력</span>

<span class="comment"># 1-3. 매퍼에 연결 (장치명: sdb_crypt)</span>
<span class="cmd">cryptsetup luksOpen /dev/sdb sdb_crypt</span>

<span class="comment"># 1-4. 정상 연결 확인</span>
<span class="cmd">ls -la /dev/mapper/sdb_crypt</span></code>
</div>

<!-- ═══════════════════════════════════════════════
     STEP 2
═══════════════════════════════════════════════ -->
<h2><span class="step-num">2</span> Step 2 — 파일 시스템 생성 및 마운트 테스트</h2>

<div class="code-block">
  <div class="code-label">bash — ext4 생성 및 임시 마운트</div>
  <code class="block"><span class="comment"># 2-1. ext4 파일 시스템 생성</span>
<span class="cmd">mkfs.ext4 /dev/mapper/sdb_crypt</span>

<span class="comment"># 2-2. 마운트 포인트 생성</span>
<span class="cmd">mkdir -p /mnt/secure_data</span>

<span class="comment"># 2-3. 임시 마운트 (정상 작동 확인)</span>
<span class="cmd">mount /dev/mapper/sdb_crypt /mnt/secure_data</span>

<span class="comment"># 2-4. 읽기/쓰기 테스트</span>
<span class="cmd">touch /mnt/secure_data/test_file &amp;&amp; rm /mnt/secure_data/test_file</span>
echo <span class="str">"✅ 마운트 및 쓰기 정상"</span>

<span class="comment"># 2-5. 임시 마운트 해제 (이후 fstab으로 영구 마운트 처리)</span>
<span class="cmd">umount /mnt/secure_data</span></code>
</div>

<!-- ═══════════════════════════════════════════════
     STEP 3
═══════════════════════════════════════════════ -->
<h2><span class="step-num">3</span> Step 3 — LUKS UUID 확인</h2>

<p>장치명(<code>/dev/sdb</code>)은 부팅마다 변경될 수 있습니다. UUID를 사용하면 장치 순서와 무관하게 안정적으로 식별합니다.</p>

<div class="code-block">
  <div class="code-label">bash — UUID 조회</div>
  <code class="block"><span class="cmd">blkid /dev/sdb</span>
<span class="comment"># 출력 예시:</span>
<span class="comment"># /dev/sdb: UUID="1234abcd-56ef-78gh-90ij-1234567890ab" TYPE="crypto_LUKS"</span>
<span class="comment">#                 ↑ 이 값을 복사합니다 (TYPE="crypto_LUKS" 옆의 UUID)</span>

<span class="comment"># 변수로 저장 (이후 단계에서 재사용)</span>
<span class="param">SDB_UUID=$(blkid -s UUID -o value /dev/sdb)</span>
echo <span class="str">"UUID: ${SDB_UUID}"</span></code>
</div>

<div class="box warning">
  <span class="box-icon">⚠️</span>
  <code>TYPE="ext4"</code>가 아닌 <code>TYPE="crypto_LUKS"</code> 옆의 UUID를 사용해야 합니다. LUKS 헤더의 UUID이며, 내부 파일 시스템 UUID와 다릅니다.
</div>

<!-- ═══════════════════════════════════════════════
     STEP 4
═══════════════════════════════════════════════ -->
<div class="page-break"></div>
<h2><span class="step-num">4</span> Step 4 — crypttab &amp; fstab 수정 ★핵심★</h2>

<div class="box danger">
  <span class="box-icon">🔴</span>
  <strong>원본 가이드의 오류 2가지가 이 단계에서 수정됩니다.</strong> 아래 내용을 정확히 따르십시오.
</div>

<h3>오류 수정 비교</h3>

<table>
  <tr><th>항목</th><th>원본 (오류)</th><th>수정 (정확)</th></tr>
  <tr>
    <td class="label">keyscript 이름</td>
    <td class="err"><code>decrypt_key_script</code> ✗</td>
    <td class="ok"><code>decrypt_keyctl</code> ✓</td>
  </tr>
  <tr>
    <td class="label">crypttab 3번째 필드</td>
    <td class="err"><code>none</code> (캐싱 안 됨)</td>
    <td class="ok"><code>group1</code> (그룹 identifier)</td>
  </tr>
</table>

<div class="box note">
  <span class="box-icon">📌</span>
  <strong>crypttab 형식:</strong> <code>&lt;target&gt; &lt;source&gt; &lt;keyfile&gt; &lt;options&gt;</code><br>
  <code>decrypt_keyctl</code>은 <strong>세 번째 필드(keyfile)를 그룹 identifier로 사용</strong>합니다.<br>
  동일한 identifier를 가진 볼륨은 첫 번째 암호 입력 후 60초 내 캐시된 암호로 자동 해제됩니다.
</div>

<h3>4-1. /etc/crypttab 수정</h3>

<div class="code-block">
  <div class="code-label">/etc/crypttab — 추가 내용</div>
  <code class="block"><span class="comment"># 추가 디스크 항목 추가 (SDB_UUID 변수 사용)</span>
cat >> /etc/crypttab << EOF
<span class="comment"># 추가 디스크 — decrypt_keyctl로 암호 캐싱</span>
sdb_crypt UUID=<span class="str">${SDB_UUID}</span> <span class="param">group1</span> luks,keyscript=<span class="param">decrypt_keyctl</span>
EOF

<span class="comment"># 결과 확인</span>
<span class="cmd">cat /etc/crypttab</span></code>
</div>

<div class="box info">
  <span class="box-icon">💡</span>
  <strong>group1</strong>은 임의의 이름입니다. 세 번째 필드가 비어있거나 <code>none</code>이면 캐싱이 작동하지 않습니다.<br>
  디스크가 3개 이상일 경우 모두 동일한 identifier(예: <code>group1</code>)를 지정하면 함께 캐싱됩니다.
</div>

<h3>4-2. /etc/fstab 수정</h3>

<div class="code-block">
  <div class="code-label">/etc/fstab — 추가 내용</div>
  <code class="block"><span class="comment"># 추가 디스크 자동 마운트 항목 추가</span>
cat >> /etc/fstab << EOF
<span class="comment"># 추가 디스크 자동 마운트</span>
/dev/mapper/sdb_crypt  /mnt/secure_data  ext4  defaults  0 2
EOF

<span class="comment"># fstab 구문 검사 (오류 시 재부팅 전 수정 필수)</span>
<span class="cmd">findmnt --verify --verbose</span></code>
</div>

<!-- ═══════════════════════════════════════════════
     STEP 5
═══════════════════════════════════════════════ -->
<h2><span class="step-num">5</span> Step 5 — initramfs 업데이트</h2>

<p>변경된 crypttab 설정과 <code>decrypt_keyctl</code> 스크립트를 부팅 초기 이미지에 반영합니다. <strong>이 단계를 생략하면 부팅 시 추가 암호 입력 창이 나타납니다.</strong></p>

<div class="code-block">
  <div class="code-label">bash — initramfs 업데이트 및 검증</div>
  <code class="block"><span class="comment"># 5-1. 모든 커널의 initramfs 업데이트</span>
<span class="cmd">update-initramfs -u -k all</span>
<span class="comment"># "update-initramfs: Generating /boot/initrd.img-X.X.X" 메시지 확인</span>

<span class="comment"># 5-2. decrypt_keyctl이 initramfs에 포함됐는지 확인</span>
<span class="cmd">lsinitramfs /boot/initrd.img-$(uname -r) | grep -E "decrypt_keyctl|keyctl"</span>
<span class="comment"># scripts/local-top/decrypt_keyctl 등이 출력되어야 정상</span>

<span class="comment"># 5-3. crypttab이 initramfs에 포함됐는지 확인</span>
<span class="cmd">lsinitramfs /boot/initrd.img-$(uname -r) | grep crypttab</span></code>
</div>

<div class="box warning">
  <span class="box-icon">⚠️</span>
  <code>lsinitramfs</code> 결과에 <code>decrypt_keyctl</code>이 없다면, <code>cryptsetup-initramfs</code> 패키지가 올바르게 설치되지 않은 것입니다.<br>
  <code>apt-get install --reinstall cryptsetup-initramfs</code> 실행 후 initramfs를 다시 업데이트하십시오.
</div>

<!-- ═══════════════════════════════════════════════
     STEP 6
═══════════════════════════════════════════════ -->
<div class="page-break"></div>
<h2><span class="step-num">6</span> Step 6 — 재부팅 및 검증</h2>

<h3>6-1. 재부팅 전 최종 체크리스트</h3>

<ul class="checklist">
  <li><strong>/etc/crypttab</strong> — <code>sdb_crypt UUID=... group1 luks,keyscript=decrypt_keyctl</code> 형식 확인</li>
  <li><strong>/etc/fstab</strong> — <code>/dev/mapper/sdb_crypt /mnt/secure_data ext4 defaults 0 2</code> 확인</li>
  <li><strong>initramfs 업데이트</strong> — <code>update-initramfs -u -k all</code> 오류 없이 완료</li>
  <li><strong>decrypt_keyctl 포함 확인</strong> — <code>lsinitramfs</code>로 포함 여부 확인</li>
  <li><strong>백업 파일 존재</strong> — <code>ls /etc/crypttab.backup.*</code> 확인</li>
  <li><strong>Live USB 준비</strong> — 부팅 가능한 복구 미디어 수중 확보</li>
</ul>

<div class="code-block">
  <div class="code-label">bash — 안전한 재부팅</div>
  <code class="block"><span class="comment"># 강제 플래그(-f) 없이 안전하게 재부팅</span>
<span class="cmd">reboot</span></code>
</div>

<h3>6-2. 부팅 후 검증</h3>

<div class="code-block">
  <div class="code-label">bash — 재부팅 후 상태 확인</div>
  <code class="block"><span class="comment"># 암호화 볼륨 상태 확인</span>
<span class="cmd">cryptsetup status sdb_crypt</span>
<span class="comment"># 기대 출력: type: LUKS1 or LUKS2 / status: active</span>

<span class="comment"># 마운트 상태 확인</span>
<span class="cmd">mount | grep secure_data</span>
<span class="comment"># 기대 출력: /dev/mapper/sdb_crypt on /mnt/secure_data type ext4</span>

<span class="comment"># 파일 시스템 쓰기 테스트</span>
<span class="cmd">touch /mnt/secure_data/test &amp;&amp; rm /mnt/secure_data/test &amp;&amp; echo "✅ 정상"</span>

<span class="comment"># (선택) 키링 캐시 확인</span>
<span class="cmd">keyctl show @u | grep cryptsetup</span></code>
</div>

<table>
  <tr><th>확인 항목</th><th>기대 결과</th><th>비정상 상태</th></tr>
  <tr><td>부팅 시 암호 입력 횟수</td><td class="ok">1회</td><td class="err">2회 이상</td></tr>
  <tr><td>cryptsetup status</td><td class="ok">active</td><td class="err">inactive / 오류</td></tr>
  <tr><td>마운트 확인</td><td class="ok">/mnt/secure_data 마운트됨</td><td class="err">마운트 없음</td></tr>
  <tr><td>쓰기 테스트</td><td class="ok">성공</td><td class="err">Permission denied / 오류</td></tr>
</table>

<!-- ═══════════════════════════════════════════════
     ROLLBACK
═══════════════════════════════════════════════ -->
<div class="page-break"></div>
<h2><span class="step-num">↩</span> 롤백 절차</h2>

<div class="box warning">
  <span class="box-icon">⚠️</span>
  시나리오 A(부팅 실패) 발생 시 <strong>Live USB가 반드시 필요</strong>합니다. Pre-flight에서 준비하지 않았다면 다른 컴퓨터로 즉시 제작하십시오.
</div>

<div class="scenario-card scenario-a">
  <div class="scenario-header">🔴 시나리오 A — 부팅 실패 (암호 입력 후 멈춤 또는 패닉)</div>
  <div class="scenario-body">
    <ol class="scenario-steps">
      <li>Debian Live USB로 부팅</li>
      <li>루트 파티션 복호화: <code>cryptsetup luksOpen /dev/sda1 sda_crypt</code></li>
      <li>마운트: <code>mount /dev/mapper/sda_crypt /mnt</code></li>
      <li>chroot 준비: <code>mount --bind /dev /mnt/dev &amp;&amp; mount --bind /proc /mnt/proc &amp;&amp; mount --bind /sys /mnt/sys</code></li>
      <li>chroot 진입: <code>chroot /mnt</code></li>
      <li>백업 복원: <code>cp /etc/crypttab.backup.YYYYMMDD_HHMMSS /etc/crypttab</code></li>
      <li>fstab 복원: <code>cp /etc/fstab.backup.YYYYMMDD_HHMMSS /etc/fstab</code></li>
      <li>initramfs 재생성: <code>update-initramfs -u -k all</code></li>
      <li>chroot 종료 후 재부팅: <code>exit &amp;&amp; reboot</code></li>
    </ol>
  </div>
</div>

<div class="scenario-card scenario-b">
  <div class="scenario-header">🟡 시나리오 B — 부팅 성공, 추가 디스크 마운트 실패</div>
  <div class="scenario-body">
    <ol class="scenario-steps">
      <li>수동으로 볼륨 열기: <code>cryptsetup luksOpen /dev/sdb sdb_crypt</code></li>
      <li>수동 마운트: <code>mount /dev/mapper/sdb_crypt /mnt/secure_data</code></li>
      <li>/etc/crypttab 확인: 3번째 필드가 <code>none</code>이 아닌 그룹 identifier인지 점검</li>
      <li>/etc/fstab 확인: 경로 및 옵션 오타 점검</li>
      <li>설정 수정 후 <code>update-initramfs -u -k all</code> 재실행</li>
      <li>재부팅하여 자동 마운트 확인</li>
    </ol>
  </div>
</div>

<div class="scenario-card scenario-c">
  <div class="scenario-header">🔵 시나리오 C — 완전 롤백 (구성 전 원상 복구)</div>
  <div class="scenario-body">
    <ol class="scenario-steps">
      <li>crypttab 복원: <code>cp /etc/crypttab.backup.YYYYMMDD_HHMMSS /etc/crypttab</code></li>
      <li>fstab 복원: <code>cp /etc/fstab.backup.YYYYMMDD_HHMMSS /etc/fstab</code></li>
      <li>initramfs 재생성: <code>update-initramfs -u -k all</code></li>
      <li>추가 디스크 볼륨 닫기: <code>umount /mnt/secure_data &amp;&amp; cryptsetup luksClose sdb_crypt</code></li>
      <li>재부팅하여 정상 복구 확인</li>
    </ol>
    <div class="box warning" style="margin-top:12px;">
      <span class="box-icon">⚠️</span>
      추가 디스크 LUKS 포맷을 제거(<code>wipefs -a /dev/sdb</code>)할 경우 내부 데이터가 모두 삭제됩니다. 반드시 사전 백업 후 진행하십시오.
    </div>
  </div>
</div>

<!-- ═══════════════════════════════════════════════
     TROUBLESHOOTING
═══════════════════════════════════════════════ -->
<div class="page-break"></div>
<h2><span class="step-num">?</span> 문제 해결 (Troubleshooting)</h2>

<div class="trouble-card">
  <div class="trouble-q">부팅 시 추가 디스크 암호를 한 번 더 묻는다</div>
  <div class="trouble-a">
    <code>/etc/crypttab</code>의 세 번째 필드가 <code>none</code>이거나 비어 있는지 확인합니다.<br>
    <code>group1</code>과 같은 identifier로 수정 후 <code>update-initramfs -u -k all</code>을 다시 실행합니다.<br>
    또한 두 디스크의 암호가 실제로 동일한지 재확인하십시오.
  </div>
</div>

<div class="trouble-card">
  <div class="trouble-q">decrypt_keyctl: command not found</div>
  <div class="trouble-a">
    <code>apt-get install --reinstall cryptsetup-initramfs</code> 후 <code>update-initramfs -u -k all</code>을 실행합니다.<br>
    스크립트 경로: <code>/lib/cryptsetup/scripts/decrypt_keyctl</code>
  </div>
</div>

<div class="trouble-card">
  <div class="trouble-q">keyctl: command not found</div>
  <div class="trouble-a">
    <code>apt-get install keyutils</code>를 실행합니다.<br>
    커널 설정 확인: <code>grep CONFIG_KEYS /boot/config-$(uname -r)</code> → <code>CONFIG_KEYS=y</code> 필요
  </div>
</div>

<div class="trouble-card">
  <div class="trouble-q">update-initramfs 실행 시 cryptsetup WARNING 메시지</div>
  <div class="trouble-a">
    <code>/etc/crypttab</code>에 <code>initramfs</code> 옵션 추가를 고려합니다:<br>
    <code>sdb_crypt UUID=... group1 luks,initramfs,keyscript=decrypt_keyctl</code><br>
    이 옵션은 해당 볼륨을 initramfs 단계에서 처리하도록 명시합니다.
  </div>
</div>

<div class="trouble-card">
  <div class="trouble-q">재부팅 후 /mnt/secure_data가 마운트되지 않음</div>
  <div class="trouble-a">
    <code>systemctl status systemd-cryptsetup@sdb_crypt.service</code>로 서비스 상태 확인.<br>
    <code>journalctl -xb | grep sdb_crypt</code>로 오류 로그 확인.<br>
    <code>/dev/mapper/sdb_crypt</code>가 존재하면 <code>mount /mnt/secure_data</code>로 수동 마운트 후 fstab 재점검.
  </div>
</div>

<!-- ═══════════════════════════════════════════════
     SECURITY
═══════════════════════════════════════════════ -->
<h2><span class="step-num">🔒</span> 보안 고려사항</h2>

<table>
  <tr><th>항목</th><th>내용</th><th>권장 조치</th></tr>
  <tr>
    <td class="label">암호 캐싱 방식</td>
    <td>Linux 커널 keyring(@u)에 메모리 저장</td>
    <td>디스크에 기록되지 않아 안전</td>
  </tr>
  <tr>
    <td class="label">캐시 타임아웃</td>
    <td>60초 (변경 불가)</td>
    <td>부팅 절차가 60초 초과 시 캐싱 실패 가능</td>
  </tr>
  <tr>
    <td class="label">스왑 파티션</td>
    <td>암호가 스왑에 기록될 위험</td>
    <td>cryptoswap 사용 강력 권장</td>
  </tr>
  <tr>
    <td class="label">백업 파일 보안</td>
    <td>crypttab/fstab 백업에 민감 정보 포함 가능</td>
    <td><code>shred -u /etc/crypttab.backup.*</code></td>
  </tr>
  <tr>
    <td class="label">키링 정리</td>
    <td>부팅 완료 후 메모리에 캐시 잔존</td>
    <td><code>keyctl clear @u</code> (필요시)</td>
  </tr>
</table>

<div class="box success">
  <span class="box-icon">✅</span>
  <strong>구성 완료 기준</strong><br>
  시스템 재부팅 시 암호 입력 창이 <strong>1회</strong>만 나타나고, 루트 파티션 및 추가 디스크(<code>/mnt/secure_data</code>)가 모두 자동 마운트되면 구성이 성공적으로 완료된 것입니다.
</div>

<hr>
<p style="text-align:center; font-size:9pt; color:#aaa;">
  Debian LUKS Multi-Disk Single Passphrase Guide v2.0 &nbsp;|&nbsp; 2026-08-03 &nbsp;|&nbsp; Internal Use Only
</p>

</body>
</html>
"""

out = r'D:\\Claw\\workspace\\luks_guide_final.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"OK: {out}  ({os.path.getsize(out):,} bytes)")
