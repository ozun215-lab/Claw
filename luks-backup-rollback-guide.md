# Debian LUKS Multi-Disk Single Passphrase - Backup & Rollback Guide
# 데비안 LUKS 다중디스크 단일 암호 구성 - 백업 및 롤백 가이드
# 작성: 2026-08-03
# 적용 대상: 루트 파티션 LUKS 암호화 + 추가 디스크 LUKS 결합 구성

================================================================================
PRE-FLIGHT CHECKLIST (적용 전 필수 확인)
================================================================================

□ 1. 시스템 백업 완료 여부
   - 중요 데이터 외부 백업 확인
   - 현재 /etc/crypttab, /etc/fstab 내용 기록

□ 2. 현재 설정 스냅샷 촬영
   cp /etc/crypttab /etc/crypttab.backup.$(date +%Y%m%d_%H%M%S)
   cp /etc/fstab /etc/fstab.backup.$(date +%Y%m%d_%H%M%S)

□ 3. Live USB/Rescue 미디어 준비
   - Debian Live USB 또는 SystemRescueCD 준비
   - 부팅 테스트 완료

□ 4. root 권한 확인
   whoami  # root 출력 확인

================================================================================
STEP 0: 현재 설정 백업 (필수)
================================================================================

# 1. crypttab 백업
BACKUP_CRYPTTAB="/etc/crypttab.backup.$(date +%Y%m%d_%H%M%S)"
cp /etc/crypttab "$BACKUP_CRYPTTAB"
echo "crypttab backed up to: $BACKUP_CRYPTTAB"

# 2. fstab 백업
BACKUP_FSTAB="/etc/fstab.backup.$(date +%Y%m%d_%H%M%S)"
cp /etc/fstab "$BACKUP_FSTAB"
echo "fstab backed up to: $BACKUP_FSTAB"

# 3. 현재 blkid 상태 기록
blkid > /root/blkid-$(date +%Y%m%d_%H%M%S).txt

# 4. 현재 마운트 상태 기록
mount > /root/mount-$(date +%Y%m%d_%H%M%S).txt

# 5. 현재 cryptsetup 상태 기록 (있는 경우)
cryptsetup status sdb_crypt 2>/dev/null >> /root/crypt-status-$(date +%Y%m%d_%H%M%S).txt || true

================================================================================
STEP 1-3: 디스크 암호화 (원본 가이드와 동일)
================================================================================

# Step 1: 추가 디스크 암호화 및 열기
# 주의: 동일한 암호 사용 필수!
cryptsetup luksFormat /dev/sdb
cryptsetup luksOpen /dev/sdb sdb_crypt

# Step 2: 파일 시스템 생성 및 마운트 준비
mkfs.ext4 /dev/mapper/sdb_crypt
mkdir -p /mnt/secure_data
mount /dev/mapper/sdb_crypt /mnt/secure_data

# Step 3: UUID 확인
blkid /dev/sdb
# 출력된 UUID 기록 (예: UUID="1234abcd-56ef-78gh-90ij-1234567890ab")
SDB_UUID="1234abcd-56ef-78gh-90ij-1234567890ab"  # 실제 UUID로 교체

================================================================================
STEP 4: 수정된 crypttab & fstab 설정
================================================================================

# 4-1. crypttab 설정 (수정됨 - keyscript 이름 및 identifier 추가)
# 형식: <target> <source> <keyfile> <options>
# <keyfile> 필드: 동일한 identifier 사용 (예: group1)
# <options>: luks,keyscript=decrypt_keyctl

cat >> /etc/crypttab << EOF
# 추가 디스크 - LUKS 단일 암호 캐싱 (decrypt_keyctl 사용)
sdb_crypt UUID=${SDB_UUID} group1 luks,keyscript=decrypt_keyctl
EOF

# 4-2. fstab 설정
cat >> /etc/fstab << EOF
# 추가 디스크 마운트
/dev/mapper/sdb_crypt /mnt/secure_data ext4 defaults 0 2
EOF

# 4-3. 설정 검증
echo "=== /etc/crypttab ==="
cat /etc/crypttab
echo ""
echo "=== /etc/fstab ==="
cat /etc/fstab

================================================================================
STEP 5: initramfs 업데이트 및 검증
================================================================================

# 5-1. initramfs 업데이트
update-initramfs -u -k all

# 5-2. 업데이트 결과 확인 (에러 체크)
# "cryptsetup: WARNING" 메시지 유무 확인
# "update-initramfs: Generating..." 성공 메시지 확인

# 5-3. initramfs에 keyctl 포함 확인
lsinitramfs /boot/initrd.img-$(uname -r) | grep -E "(keyctl|decrypt_keyctl)" || {
    echo "WARNING: keyctl 또는 decrypt_keyctl이 initramfs에 없을 수 있습니다"
    echo "cryptsetup-initramfs 패키지 설치 확인: apt-get install cryptsetup-initramfs"
}

================================================================================
STEP 6: 안전한 재부팅 절차 (롤백 준비 포함)
================================================================================

# 6-1. 현재 세션 유지, 새로운 SSH 세션 열기 (권장)
# 터미널 1: 현재 세션 (롤백용)
# 터미널 2: 모니터링용 새 세션

# 6-2. 재부팅 전 최종 확인 체크리스트
echo "재부팅 전 확인사항:"
echo "□ /etc/crypttab 구문 오류 없음"
echo "□ /etc/fstab 구문 오류 없음"
echo "□ update-initramfs 성공 완료"
echo "□ 백업 파일 존재: $BACKUP_CRYPTTAB, $BACKUP_FSTAB"
echo "□ Live USB 준비 완료"

# 6-3. 안전한 재부팅
# 주의: -f 플래그 없이 일반 reboot 사용
reboot

================================================================================
STEP 7: 부팅 후 검증 절차
================================================================================

# 7-1. 부팅 시 암호 입력 횟수 확인
# 기대: 루트 파티션 암호 1회 입력 후 자동 진행
# 비정상: 추가 디스크 암호 추가 요청

# 7-2. 디스크 상태 확인
cryptsetup status sdb_crypt
# 기대: active, type: LUKS1 또는 LUKS2

# 7-3. 마운트 상태 확인
mount | grep secure_data
# 기대: /dev/mapper/sdb_crypt on /mnt/secure_data

# 7-4. 파일 시스템 정상 접근 확인
touch /mnt/secure_data/test_file && rm /mnt/secure_data/test_file

# 7-5. keyring 캐시 상태 확인 (선택)
keyctl show @u 2>/dev/null | grep cryptsetup

================================================================================
ROLLBACK PROCEDURES (롤백 절차)
================================================================================

# 시나리오 A: 부팅 실패 (암호 입력 후 멈춤/에러)
# -------------------------------------------------
# 1. Live USB로 부팅
# 2. 루트 파티션 복호화 및 마운트
#    cryptsetup luksOpen /dev/sda1 sda_crypt
#    mount /dev/mapper/sda_crypt /mnt
# 3. chroot 진입
#    mount --bind /dev /mnt/dev
#    mount --bind /proc /mnt/proc
#    mount --bind /sys /mnt/sys
#    chroot /mnt
# 4. 백업 복원
#    cp /etc/crypttab.backup.YYYYMMDD_HHMMSS /etc/crypttab
#    cp /etc/fstab.backup.YYYYMMDD_HHMMSS /etc/fstab
# 5. initramfs 재생성
#    update-initramfs -u -k all
# 6. 재부팅

# 시나리오 B: 부팅은 되지만 추가 디스크 마운트 실패
# -------------------------------------------------
# 1. 현재 시스템에서 crypttab/fstab 수정
# 2. 수동 마운트로 임시 복구
    mount /dev/mapper/sdb_crypt /mnt/secure_data
# 3. 설정 수정 후 initramfs 업데이트

# 시나리오 C: 완전 롤백 (원상 복구)
# -------------------------------------------------
ROLLBACK_CRYPTTAB="/etc/crypttab.backup.20260803_175300"  # 실제 백업 파일명으로 교체
ROLLBACK_FSTAB="/etc/fstab.backup.20260803_175300"        # 실제 백업 파일명으로 교체

cp "$ROLLBACK_CRYPTTAB" /etc/crypttab
cp "$ROLLBACK_FSTAB" /etc/fstab
update-initramfs -u -k all

# 추가 디스크 암호화 제거 (필요시)
# cryptsetup luksClose sdb_crypt
# 주의: 실제 데이터 삭제 전 백업 필수!

================================================================================
TROUBLESHOOTING (문제 해결)
================================================================================

# 문제 1: "decrypt_keyctl: command not found"
# 해결: cryptsetup-initramfs 패키지 설치
apt-get install cryptsetup-initramfs

# 문제 2: "keyctl: command not found"
# 해결: keyutils 패키지 설치
apt-get install keyutils

# 문제 3: 캐싱이 작동하지 않음 (암호 여러번 요청)
# 확인: crypttab의 <keyfile> 필드가 동일한 identifier인지 확인
# 확인: 두 디스크의 암호가 실제로 동일한지 확인
# 확인: initramfs 업데이트 후 재부팅했는지 확인

# 문제 4: 추가 디스크가 initramfs에서 열리지 않음
# 확인: crypttab에 initramfs 옵션 필요시 추가
# sdb_crypt UUID=... group1 luks,initramfs,keyscript=decrypt_keyctl

# 문제 5: 마운트 실패 (fstab 오류)
# 확인: /dev/mapper/sdb_crypt가 실제 존재하는지
ls -la /dev/mapper/sdb_crypt
# 없다면 cryptsetup luksOpen으로 수동 열기

================================================================================
SECURITY NOTES (보안 참고)
================================================================================

# 1. 암호 캐싱은 메모리에서만 이루어짐 (디스크에 저장되지 않음)
# 2. 캐시 타임아웃: 60초 (변경 불가)
# 3. 스왑 사용 시 cryptoswap 권장 (암호가 스왑에 기록될 위험)
# 4. 키링 정리 (민감한 환경에서)
keyctl clear @u

# 5. 백업 파일 보안
# 백업 파일도 민감 정보 포함 가능, 안전한 위치 저장 또는 삭제
shred -u /etc/crypttab.backup.*  # 필요시 안전 삭제
shred -u /etc/fstab.backup.*      # 필요시 안전 삭제

================================================================================
REFERENCES
================================================================================

# Debian Cryptsetup Keyctl README
# https://cryptsetup-team.pages.debian.net/cryptsetup/README.keyctl.html

# decrypt_keyctl 소스코드
# /lib/cryptsetup/scripts/decrypt_keyctl

# man pages
# man 5 crypttab
# man 8 cryptsetup
# man 1 keyctl

================================================================================
END OF GUIDE
================================================================================
