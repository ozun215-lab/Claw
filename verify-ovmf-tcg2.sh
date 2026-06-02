#!/bin/bash
###############################################################################
# verify-ovmf-tcg2.sh
# OVMF 펌웨어 파일의 TCG2(TPM) 모듈 포함 여부 검증 스크립트
#
# 용도:
#   - 신규 호스트 vTPM 사용 가능 여부 사전 검증
#   - OVMF 패키지 업데이트 후 회귀 검증
#   - 다수 호스트 일괄 진단
#
# 의존성:
#   apt install python3-virt-firmware python3-importlib-resources
#
# 사용법:
#   sudo ./verify-ovmf-tcg2.sh                   # 기본 경로 검사
#   sudo ./verify-ovmf-tcg2.sh /path/to/OVMF/    # 특정 경로 검사
#   sudo ./verify-ovmf-tcg2.sh -v                # 상세 모드
#   sudo ./verify-ovmf-tcg2.sh -j                # JSON 출력
#
# 작성일: 2026-05-19
# 참조: INFRA-VM-OVMF-005 v4
###############################################################################

set -euo pipefail

# ── 기본 설정 ────────────────────────────────────────────────────────────────
OVMF_DIR="${1:-/usr/share/OVMF}"
VERBOSE=0
JSON_OUTPUT=0
EXIT_CODE=0

# Tcg2 모듈 패턴 (정정된 패턴 — v4 기준)
TCG2_PATTERN="name=Tcg2(Pei|Dxe|ConfigPei|ConfigDxe)"
TPM_PATTERN="name=.*Tcg|name=.*Tpm"

# ── 색상 ─────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[0;33m'
    BLU='\033[0;34m'; CYN='\033[0;36m'; BLD='\033[1m'; NC='\033[0m'
else
    RED=''; GRN=''; YEL=''; BLU=''; CYN=''; BLD=''; NC=''
fi

# ── 옵션 처리 ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose) VERBOSE=1; shift ;;
        -j|--json)    JSON_OUTPUT=1; shift ;;
        -h|--help)
            head -25 "$0" | tail -23 | sed 's/^# \?//'
            exit 0
            ;;
        -*) echo "Unknown option: $1" >&2; exit 1 ;;
        *)  OVMF_DIR="$1"; shift ;;
    esac
done

# ── 의존성 검증 ──────────────────────────────────────────────────────────────
check_deps() {
    local missing=()

    if ! command -v virt-fw-dump &>/dev/null; then
        missing+=("python3-virt-firmware")
    fi

    if ! python3 -c "import importlib_resources" 2>/dev/null; then
        missing+=("python3-importlib-resources")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}[ERROR]${NC} 필수 패키지 누락:"
        for pkg in "${missing[@]}"; do
            echo "  - $pkg"
        done
        echo
        echo "설치 명령:"
        echo "  apt install -y ${missing[*]}"
        exit 2
    fi
}

# ── OVMF 디렉토리 검증 ───────────────────────────────────────────────────────
check_dir() {
    if [[ ! -d "$OVMF_DIR" ]]; then
        echo -e "${RED}[ERROR]${NC} OVMF 디렉토리 없음: $OVMF_DIR"
        exit 3
    fi

    local count
    count=$(find "$OVMF_DIR" -maxdepth 1 -name "OVMF_CODE*.fd" 2>/dev/null | wc -l)
    if [[ $count -eq 0 ]]; then
        echo -e "${RED}[ERROR]${NC} OVMF_CODE*.fd 파일이 없음: $OVMF_DIR"
        exit 4
    fi
}

# ── 단일 파일 검증 ───────────────────────────────────────────────────────────
verify_file() {
    local file="$1"
    local fname tcg2_count is_link link_target real_path sha256_short
    local secboot=0 status=""

    fname=$(basename "$file")

    # 심볼릭 링크 확인
    if [[ -L "$file" ]]; then
        link_target=$(readlink "$file")
        real_path=$(readlink -f "$file")
        is_link=1
    else
        link_target=""
        real_path="$file"
        is_link=0
    fi

    # 해시 (앞 8자만)
    sha256_short=$(sha256sum "$real_path" 2>/dev/null | cut -c1-8)

    # Tcg2 모듈 개수
    tcg2_count=$(virt-fw-dump --input "$file" 2>&1 \
        | grep -cE "$TCG2_PATTERN" || true)

    # Secure Boot 추정 (파일명 기반)
    if [[ "$fname" == *secboot* ]] || [[ "$fname" == *.ms.fd ]] || [[ "$fname" == *snakeoil* ]]; then
        secboot=1
    fi

    # 상태 판정
    if [[ $tcg2_count -ge 3 ]]; then
        status="OK"
    elif [[ $tcg2_count -ge 1 ]]; then
        status="PARTIAL"
        EXIT_CODE=1
    else
        status="MISSING"
        EXIT_CODE=1
    fi

    # JSON 출력
    if [[ $JSON_OUTPUT -eq 1 ]]; then
        cat <<EOF
  {
    "file": "$fname",
    "real_path": "$real_path",
    "is_symlink": $is_link,
    "link_target": "$link_target",
    "sha256_prefix": "$sha256_short",
    "tcg2_modules": $tcg2_count,
    "secure_boot_capable": $([ $secboot -eq 1 ] && echo true || echo false),
    "status": "$status"
  }
EOF
        return
    fi

    # 텍스트 출력
    local status_color
    case "$status" in
        OK)      status_color="$GRN" ;;
        PARTIAL) status_color="$YEL" ;;
        MISSING) status_color="$RED" ;;
    esac

    local link_note=""
    if [[ $is_link -eq 1 ]]; then
        link_note=" -> ${link_target}"
    fi

    local sb_mark
    [[ $secboot -eq 1 ]] && sb_mark="${GRN}SB✔${NC}" || sb_mark="${YEL}SB✘${NC}"

    printf "  ${BLD}%-45s${NC} ${CYN}%s${NC} Tcg2:%d %b  [${status_color}%s${NC}]%s\n" \
        "$fname" \
        "$sha256_short" \
        "$tcg2_count" \
        "$sb_mark" \
        "$status" \
        "$link_note"

    # 상세 모드
    if [[ $VERBOSE -eq 1 && $tcg2_count -gt 0 ]]; then
        echo "    └─ 포함 모듈:"
        virt-fw-dump --input "$file" 2>&1 \
            | grep -iE "name=.*Tcg|name=.*Tpm" \
            | sed -E 's/.*name=([^ ]+).*/      • \1/' \
            | sort -u
    fi
}

# ── 헤더 출력 ────────────────────────────────────────────────────────────────
print_header() {
    [[ $JSON_OUTPUT -eq 1 ]] && return

    echo
    echo -e "${BLD}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLD}  OVMF TCG2(TPM) 모듈 검증 — verify-ovmf-tcg2.sh${NC}"
    echo -e "${BLD}═══════════════════════════════════════════════════════════════════════${NC}"
    echo -e "  검사 경로 : ${CYN}${OVMF_DIR}${NC}"
    echo -e "  호스트   : ${CYN}$(hostname)${NC}"
    echo -e "  실행 시각 : ${CYN}$(date -Iseconds)${NC}"
    echo
    echo -e "  ${BLD}판정 기준:${NC}"
    echo -e "    ${GRN}OK${NC}       — Tcg2 모듈 3개 이상 (vTPM 정상 지원)"
    echo -e "    ${YEL}PARTIAL${NC}  — Tcg2 모듈 1~2개 (불완전)"
    echo -e "    ${RED}MISSING${NC}  — Tcg2 모듈 0개 (vTPM 미지원)"
    echo
    echo -e "${BLD}───────────────────────────────────────────────────────────────────────${NC}"
}

# ── 결과 요약 ────────────────────────────────────────────────────────────────
print_summary() {
    [[ $JSON_OUTPUT -eq 1 ]] && return

    echo
    echo -e "${BLD}───────────────────────────────────────────────────────────────────────${NC}"
    if [[ $EXIT_CODE -eq 0 ]]; then
        echo -e "  ${GRN}${BLD}✅ 검증 통과${NC} — 검사된 모든 펌웨어가 vTPM 지원"
    else
        echo -e "  ${RED}${BLD}❌ 검증 실패${NC} — 일부 펌웨어가 vTPM 미지원 또는 불완전"
        echo
        echo -e "  ${YEL}권장 조치:${NC}"
        echo -e "    1. virt-firmware 패키지 재설치"
        echo -e "       ${CYN}apt install --reinstall ovmf python3-virt-firmware${NC}"
        echo -e "    2. 다른 OVMF 변종 사용 (OK 판정된 파일)"
        echo -e "    3. INFRA-VM-OVMF-005 v4 문서 참조"
    fi
    echo -e "${BLD}═══════════════════════════════════════════════════════════════════════${NC}"
    echo

    # 권장 사용 OVMF 안내
    echo -e "  ${BLD}🪟 Windows 11 + Secure Boot + vTPM 권장 구성:${NC}"
    echo -e "    loader  : ${CYN}${OVMF_DIR}/OVMF_CODE_4M.ms.fd${NC}"
    echo -e "    nvram   : ${CYN}${OVMF_DIR}/OVMF_VARS_4M.ms.fd${NC}"
    echo -e "    machine : ${CYN}pc-q35-9.0${NC} (이상)"
    echo -e "    tpm     : ${CYN}tpm-crb${NC} + emulator"
    echo -e "    smm     : ${CYN}on${NC}"
    echo
}

# ── 메인 ─────────────────────────────────────────────────────────────────────
main() {
    check_deps
    check_dir
    print_header

    [[ $JSON_OUTPUT -eq 1 ]] && echo '['

    local first=1
    while IFS= read -r -d '' file; do
        if [[ $JSON_OUTPUT -eq 1 ]]; then
            [[ $first -eq 0 ]] && echo ','
            first=0
        fi
        verify_file "$file"
    done < <(find "$OVMF_DIR" -maxdepth 1 -name "OVMF_CODE*.fd" -print0 | sort -z)

    [[ $JSON_OUTPUT -eq 1 ]] && echo && echo ']'

    print_summary
    exit $EXIT_CODE
}

main "$@"
