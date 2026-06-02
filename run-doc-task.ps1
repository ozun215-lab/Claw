$taskName = "Windows 11 QCOW2 Backing File 백업 관리 방안"
$query = "아래 내용을 바탕으로 전문적인 기술 문서를 작성하세요. PDF 출력에 적합한 Word 스타일 HTML 문서로 만들어주세요."
$instructions = @"
## 문서 제목
Windows 11 QCOW2 Backing File 백업 관리 방안

## 문서 형식 요구사항
- 전문 기술 문서 스타일 (Word 형식)
- 한국어로 작성
- 표지 포함 (제목, 버전 1.0, 날짜 2026-05-08)
- 목차 포함
- 각 섹션 번호 체계 유지
- 코드 블록은 고정폭 폰트 사용
- PDF 출력에 적합한 A4 레이아웃

## 1. 개요
QEMU/KVM 환경에서 qcow2의 Copy-on-Write(COW) 특성을 활용한 Windows 11 VM 백업 전략입니다.

핵심 목표:
- 마스터 이미지의 완전 불변성 보장
- Windows Update 전/후 백업본 각 1개 유지
- 3단계 롤백 체계로 유연한 복구 제공
- falloc 사전할당으로 overlay I/O 안정성 확보
- 압축 포맷으로 저장 공간 최소화

## 2. 핵심 아키텍처: 3계층 Backing Chain

구조:
  master.qcow2   [압축 qcow2, chmod 444, 영구 불변]
        ↑ backing
  backup.qcow2   [압축 qcow2, Update 확정 후 갱신, 1개 유지]
        ↑ backing
  overlay.qcow2  [falloc 사전할당, VM 실제 R/W]

  + pre-backup.qcow2 [압축 qcow2, Update 시작 전 overlay 스냅샷, 1개 유지]

각 계층 역할:
| 계층 | 파일 | 형식 | 역할 |
|------|------|------|------|
| L1 | master.qcow2 | 압축 qcow2 | 최초 설치 원본, 완전 초기화용 |
| L2 | backup.qcow2 | 압축 qcow2 | 최신 Update 적용본, 1개만 유지 |
| L3 | overlay.qcow2 | falloc qcow2 | VM 운용 레이어, 언제든 폐기 가능 |
| snap | pre-backup.qcow2 | 압축 qcow2 | Update 직전 overlay 스냅샷 |

COW 동작 원리:
- 읽기: overlay에 없는 블록 → backup → master 순으로 fallback
- 쓰기: 무조건 최상위 overlay에만 발생 → 하위 이미지는 자동 보호

## 3. 파일 구조

  /vm/win11/
  ├── master.qcow2          # L1 압축 RO  — 최초 설치 원본
  ├── backup.qcow2          # L2 압축 RW  — 최신 Update 확정본
  ├── overlay.qcow2         # L3 falloc   — VM 운용 레이어
  ├── pre-backup.qcow2      # 압축 snap   — Update 직전 스냅샷 (1개)
  └── scripts/
      ├── init.sh
      ├── vm-pre-update.sh
      ├── vm-update-commit.sh
      ├── vm-rollback.sh
      └── status.sh

## 4. 포맷 전략

| 파일 | 형식 | 이유 |
|------|------|------|
| master.qcow2 | 압축 qcow2 (-c) | 불변 원본, 저장 공간 최소화 |
| overlay.qcow2 | falloc 사전할당 | 런타임 공간 부족 방지, I/O 안정성 |
| backup.qcow2 | 압축 qcow2 | delta 압축 보관, 크기 최소화 |
| pre-backup.qcow2 | 압축 qcow2 | Update 직전 delta만 압축 보관 |

falloc의 역할: posix_fallocate()로 디스크 공간을 미리 예약하여 VM 운영 중 "No space left on device" 차단, 런타임 클러스터 할당 오버헤드 제거

## 5. 초기 세팅 (init.sh)

  #!/bin/bash
  set -euo pipefail
  
  BASE_DIR="/vm/win11"
  SRC="${1:?사용법: init.sh <원본이미지.qcow2>}"
  MASTER="$BASE_DIR/master.qcow2"
  BACKUP="$BASE_DIR/backup.qcow2"
  OVERLAY="$BASE_DIR/overlay.qcow2"
  LOG="/var/log/vm-backup.log"
  STAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  log() { echo "[$STAMP] $*" | tee -a "$LOG"; }
  
  mkdir -p "$BASE_DIR"
  log "=== 초기화 ==="
  
  # L1: 원본 → 압축 마스터 봉인
  log "[1/4] 압축 마스터 생성..."
  qemu-img convert -f qcow2 -O qcow2 -c "$SRC" "$MASTER"
  chmod 444 "$MASTER"
  log "  master : $(du -sh "$MASTER" | cut -f1) (압축, RO)"
  
  # L2: backup 생성
  log "[2/4] backup 생성..."
  qemu-img create -f qcow2 -b "$MASTER" -F qcow2 "$BACKUP"
  log "  backup : $(du -sh "$BACKUP" | cut -f1)"
  
  # L3: falloc overlay 생성
  log "[3/4] falloc overlay 생성..."
  qemu-img create -f qcow2 -b "$BACKUP" -F qcow2 -o preallocation=falloc "$OVERLAY"
  log "  overlay: $(du -sh "$OVERLAY" | cut -f1) (falloc)"
  
  # 체인 검증
  log "[4/4] 체인 검증..."
  qemu-img info --backing-chain "$OVERLAY" | tee -a "$LOG"
  log "✓ 초기화 완료"

libvirt XML 설정:
  <disk type='file' device='disk'>
    <source file='/vm/win11/overlay.qcow2'/>
    <target dev='vda' bus='virtio'/>
  </disk>

## 6. Windows Update 전 백업 (vm-pre-update.sh)

  #!/bin/bash
  set -euo pipefail
  
  VM_NAME="win11"
  BASE_DIR="/vm/win11"
  MASTER="$BASE_DIR/master.qcow2"
  BACKUP="$BASE_DIR/backup.qcow2"
  OVERLAY="$BASE_DIR/overlay.qcow2"
  PRE_BACKUP="$BASE_DIR/pre-backup.qcow2"
  PRE_BACKUP_TMP="$BASE_DIR/pre-backup.tmp.qcow2"
  LOG="/var/log/vm-backup.log"
  STAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  log() { echo "[$STAMP] $*" | tee -a "$LOG"; }
  log "=== Update 전 백업 시작 ==="
  
  # 1. VM 종료 (graceful → forced)
  if virsh domstate "$VM_NAME" 2>/dev/null | grep -q running; then
    log "[1/5] VM 종료 중 (최대 3분)..."
    virsh shutdown "$VM_NAME" || true
    for i in $(seq 1 36); do
      sleep 5
      virsh domstate "$VM_NAME" 2>/dev/null | grep -q "shut off" && break
      if [ "$i" -eq 36 ]; then
        log "  타임아웃 → 강제 종료"
        virsh destroy "$VM_NAME"; sleep 3
      fi
    done
  fi
  
  # 2. overlay 무결성 검사
  log "[2/5] overlay 무결성 검사..."
  qemu-img check "$OVERLAY" && log "  overlay OK"
  
  # 3. overlay → pre-backup 압축 변환 (1개 덮어씀)
  log "[3/5] overlay → 압축 pre-backup 변환..."
  qemu-img convert -f qcow2 -O qcow2 -c -B "$BACKUP" "$OVERLAY" "$PRE_BACKUP_TMP"
  qemu-img rebase -u -b "$BACKUP" -F qcow2 "$PRE_BACKUP_TMP"
  qemu-img check "$PRE_BACKUP_TMP" && log "  pre-backup 무결성 OK"
  mv "$PRE_BACKUP_TMP" "$PRE_BACKUP"
  log "  pre-backup : $(du -sh "$PRE_BACKUP" | cut -f1) (압축 delta)"
  
  # 4. overlay falloc 재생성 (새 thin 레이어)
  log "[4/5] overlay falloc 재생성..."
  rm -f "$OVERLAY"
  qemu-img create -f qcow2 -b "$BACKUP" -F qcow2 -o preallocation=falloc "$OVERLAY"
  log "  overlay 재생성: $(du -sh "$OVERLAY" | cut -f1) (falloc)"
  
  # 5. 체인 검증
  log "[5/5] 체인 검증..."
  qemu-img info --backing-chain "$OVERLAY" | tee -a "$LOG"
  log "✓ Update 전 백업 완료"
  log "  다음 단계: virsh start $VM_NAME → Windows Update → vm-update-commit.sh"
  log "  문제 발생: vm-rollback.sh pre"

## 7. Windows Update 후 확정 (vm-update-commit.sh)

  #!/bin/bash
  set -euo pipefail
  
  VM_NAME="win11"
  BASE_DIR="/vm/win11"
  MASTER="$BASE_DIR/master.qcow2"
  BACKUP="$BASE_DIR/backup.qcow2"
  BACKUP_TMP="$BASE_DIR/backup.tmp.qcow2"
  OVERLAY="$BASE_DIR/overlay.qcow2"
  PRE_BACKUP="$BASE_DIR/pre-backup.qcow2"
  LOG="/var/log/vm-backup.log"
  STAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  log() { echo "[$STAMP] $*" | tee -a "$LOG"; }
  log "=== Update Commit 시작 ==="
  
  # 1. VM 종료
  if virsh domstate "$VM_NAME" 2>/dev/null | grep -q running; then
    log "[1/6] VM 종료 중..."
    virsh shutdown "$VM_NAME" || true
    for i in $(seq 1 36); do
      sleep 5
      virsh domstate "$VM_NAME" 2>/dev/null | grep -q "shut off" && break
      if [ "$i" -eq 36 ]; then
        log "  타임아웃 → 강제 종료"
        virsh destroy "$VM_NAME"; sleep 3
      fi
    done
  fi
  
  # 2. 무결성 검사
  log "[2/6] 무결성 검사..."
  qemu-img check "$OVERLAY" && log "  overlay OK"
  qemu-img check "$BACKUP"  && log "  backup  OK"
  
  # 3. overlay → backup 커밋 (master는 절대 변경 없음)
  log "[3/6] overlay → backup 커밋..."
  qemu-img commit "$OVERLAY"
  log "  커밋 완료 (master 불변 유지)"
  
  # 4. backup 압축 재변환
  log "[4/6] backup 압축 최적화..."
  qemu-img convert -f qcow2 -O qcow2 -c -B "$MASTER" "$BACKUP" "$BACKUP_TMP"
  mv "$BACKUP_TMP" "$BACKUP"
  qemu-img rebase -u -b "$MASTER" -F qcow2 "$BACKUP"
  log "  backup 압축: $(du -sh "$BACKUP" | cut -f1)"
  
  # 5. overlay falloc 재생성
  log "[5/6] overlay falloc 재생성..."
  rm -f "$OVERLAY"
  qemu-img create -f qcow2 -b "$BACKUP" -F qcow2 -o preallocation=falloc "$OVERLAY"
  log "  overlay 재생성: $(du -sh "$OVERLAY" | cut -f1)"
  
  # 6. 최종 검증 후 VM 시작
  log "[6/6] 체인 검증..."
  qemu-img info --backing-chain "$OVERLAY" | tee -a "$LOG"
  virsh start "$VM_NAME"
  log "✓ Commit 완료. VM 시작됨."

## 8. 3단계 롤백 (vm-rollback.sh)

롤백 모드:
- pre    → Update 시작 직전 상태 (pre-backup 복원)
- backup → 최신 Update 확정 시점 (overlay 재생성)
- master → 최초 설치 시점 (완전 초기화)

  #!/bin/bash
  set -euo pipefail
  
  VM_NAME="win11"
  BASE_DIR="/vm/win11"
  MASTER="$BASE_DIR/master.qcow2"
  BACKUP="$BASE_DIR/backup.qcow2"
  OVERLAY="$BASE_DIR/overlay.qcow2"
  PRE_BACKUP="$BASE_DIR/pre-backup.qcow2"
  LOG="/var/log/vm-backup.log"
  MODE="${1:-pre}"
  STAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  log() { echo "[$STAMP] $*" | tee -a "$LOG"; }
  
  case "$MODE" in
    pre|backup|master) ;;
    *) echo "사용법: $0 [pre|backup|master]"; exit 1 ;;
  esac
  
  read -p "계속하시겠습니까? (yes/no): " YN
  [ "$YN" != "yes" ] && echo "취소." && exit 0
  
  virsh destroy "$VM_NAME" 2>/dev/null || true
  sleep 3
  
  case "$MODE" in
    pre)
      log "[ROLLBACK:pre] pre-backup → falloc overlay 복원..."
      [ ! -f "$PRE_BACKUP" ] && echo "오류: pre-backup 없음" && exit 1
      rm -f "$OVERLAY"
      qemu-img convert -f qcow2 -O qcow2 -B "$BACKUP" \
        -o preallocation=falloc "$PRE_BACKUP" "$OVERLAY"
      qemu-img rebase -u -b "$BACKUP" -F qcow2 "$OVERLAY"
      log "  복원 완료: Update 시작 직전 상태"
      ;;
    backup)
      log "[ROLLBACK:backup] overlay falloc 재생성..."
      rm -f "$OVERLAY"
      qemu-img create -f qcow2 -b "$BACKUP" -F qcow2 \
        -o preallocation=falloc "$OVERLAY"
      log "  복원 완료: 최신 Update 확정 시점"
      ;;
    master)
      log "[ROLLBACK:master] backup + overlay 완전 초기화..."
      rm -f "$OVERLAY" "$PRE_BACKUP"
      qemu-img create -f qcow2 -b "$MASTER" -F qcow2 "$BACKUP"
      qemu-img create -f qcow2 -b "$BACKUP" -F qcow2 \
        -o preallocation=falloc "$OVERLAY"
      log "  복원 완료: 최초 설치 시점"
      ;;
  esac
  
  qemu-img check "$OVERLAY" && log "  overlay 무결성 OK"
  qemu-img info --backing-chain "$OVERLAY" | tee -a "$LOG"
  log "✓ 롤백 완료."
  echo ""
  echo "  virsh start $VM_NAME"

## 9. 상태 조회 (status.sh)

  #!/bin/bash
  BASE_DIR="/vm/win11"
  echo "========================================"
  echo "  VM 이미지 상태"
  echo "========================================"
  for KEY in master backup pre-backup overlay; do
    FILE="$BASE_DIR/$KEY.qcow2"
    echo ""
    echo "[$KEY]"
    if [ -f "$FILE" ]; then
      qemu-img info "$FILE" | grep -E "virtual size|disk size|backing file|prealloc"
      echo "  파일크기 : $(du -sh "$FILE" | cut -f1)"
      echo "  수정일시 : $(stat -c '%y' "$FILE" | cut -d'.' -f1)"
    else
      echo "  (없음)"
    fi
  done
  echo ""
  echo "[backing chain]"
  qemu-img info --backing-chain "$BASE_DIR/overlay.qcow2" | grep -E "^image|backing file"
  echo ""
  echo "[최근 로그]"
  tail -5 /var/log/vm-backup.log 2>/dev/null || echo "  로그 없음"
  echo "========================================"

## 10. 운영 라이프사이클

단계 1. 초기화
  init.sh 실행
  → master(압축 RO) → backup(압축) → overlay(falloc)

단계 2. 평상시 운영
  overlay에 변경 누적
  master / backup 불변 유지

단계 3. Windows Update 사이클
  [전] vm-pre-update.sh
    → overlay → pre-backup (압축 delta, 1개 덮어씀)
    → overlay falloc 재생성 (새 레이어)
  
  [진행] virsh start win11 → Windows Update → VM 종료
  
  [후] vm-update-commit.sh
    → check (overlay + backup 무결성)
    → commit overlay → backup
    → backup 압축 재변환
    → overlay falloc 재생성
    → VM 시작

단계 4. 문제 발생 시 롤백
  경미한 문제 : vm-rollback.sh pre    → Update 직전 복구
  중간 문제   : vm-rollback.sh backup → Update 확정 시점
  완전 초기화 : vm-rollback.sh master → 최초 설치 시점

## 11. Quick Reference

| 상황 | 명령어 |
|------|--------|
| 최초 세팅 | bash scripts/init.sh win11-source.qcow2 |
| Update 전 백업 | bash scripts/vm-pre-update.sh |
| Update 후 확정 | bash scripts/vm-update-commit.sh |
| Update 실패 롤백 | bash scripts/vm-rollback.sh pre |
| Update 확정 후 롤백 | bash scripts/vm-rollback.sh backup |
| 완전 초기화 | bash scripts/vm-rollback.sh master |
| 상태 조회 | bash scripts/status.sh |
| 체인 확인 | qemu-img info --backing-chain /vm/win11/overlay.qcow2 |
| VM 시작 | virsh start win11 |
| VM 중지 | virsh shutdown win11 |
| VM 상태 | virsh domstate win11 |

## 12. 보호 규칙

| 규칙 | 이유 |
|------|------|
| master에 commit 절대 금지 | chmod 444 물리 차단, 오염 시 최초 설치본 영구 손실 |
| VM 실행 중 commit 금지 | 디스크 손상 위험, shut off 확인 후 실행 |
| commit 전 check 강제 실행 | 손상 overlay 커밋 차단 |
| backing 경로 절대경로 유지 | rebase -u 후 반드시 재확인 |
| pre-backup backing = backup | overlay backing = backup (체인 일관성) |
| graceful → forced 순서 준수 | 데이터 무결성 우선, 타임아웃 후 강제 종료 |

## 13. 파일 크기 예시 (60GB 가상 디스크 기준)

| 파일 | 방식 | 예상 크기 |
|------|------|----------|
| master.qcow2 | 압축 qcow2 | 15~20 GB |
| backup.qcow2 | 압축 qcow2 | 15~22 GB |
| pre-backup.qcow2 | 압축 delta | 1~3 GB |
| overlay.qcow2 | falloc 사전할당 | ~60 GB (공간 예약) |
| 합계 | | 91~105 GB |
"@

& gsk task docs `
  --task_name $taskName `
  --query $query `
  --instructions $instructions `
  -o "D:\Claw\workspace\win11-qcow2-backup-guide-final.docx"
