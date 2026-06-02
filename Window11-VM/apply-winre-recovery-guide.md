# 복구 파티션 생성 + 기존 winre.wim 적용 가이드

이 문서는 이미 추출해 둔 `winre.wim`을 사용해 복구 파티션을 만들고, Windows RE를 다시 등록하는 절차를 정리한 고객 전달용 가이드입니다.

---

## 전제

- `winre.wim`은 이미 추출된 상태
- 대상 시스템은 Windows 11
- 관리자 권한 PowerShell 사용
- 필요 시 C:의 마지막 부분을 조금 줄여 복구 파티션 공간을 확보

---

## 결과물

### 스크립트
- `apply-winre-recovery.ps1`

### 역할
1. WinRE 비활성화
2. 시스템 디스크 확인
3. 필요 시 C: 축소
4. 복구 파티션 생성
5. `winre.wim` 복사
6. `reagentc /setreimage` 실행
7. `reagentc /enable` 실행
8. 복구 파티션 드라이브 문자 숨김

---

## 사용 방법

### 예시 1: 이미 충분한 여유 공간이 있는 경우

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\apply-winre-recovery.ps1 -WinReWimPath C:\Temp\WinRE\winre.wim
```

실행 시 확인 메시지가 나오며, 진행하려면 `YES`를 입력하면 됩니다.

### 예시 2: C:를 줄여가며 작업하는 경우

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\apply-winre-recovery.ps1 -WinReWimPath C:\Temp\WinRE\winre.wim -ShrinkOSDrive
```

---

## 기본 동작

복구 파티션은 일반적으로 C: 뒤, 디스크 마지막에 생성됩니다.

```text
[EFI] -> [MSR] -> [Windows(C:)] -> [Recovery]
```

복구 파티션 정보:
- GUID: `de94bba4-06d1-4d40-a16a-bfd50179d6ac`
- GPT 속성: `0x8000000000000001`
- 기본 크기: `1024MB`

---

## 적용 후 확인

```powershell
reagentc /info
Get-Partition | Format-Table DiskNumber, PartitionNumber, DriveLetter, Size, GptType
```

정상이라면 WinRE 상태가 활성화로 표시되고, 복구 파티션은 드라이브 문자 없이 숨겨집니다.

---

## 고객 전달용 짧은 설명

> 추출된 `winre.wim`을 사용해 Windows 11 복구 파티션을 다시 만들고 WinRE를 재등록하는 스크립트입니다. 관리자 권한 PowerShell에서 실행하면 C: 뒤쪽의 복구 파티션 생성, 이미지 복사, `reagentc` 등록, 드라이브 문자 숨김까지 자동으로 처리합니다.

---

## 주의사항

- BitLocker가 활성화되어 있으면 작업 전에 잠시 보호를 중지하는 것이 안전합니다.

```powershell
manage-bde -protectors -disable C:
```

- 시스템 디스크 번호가 0이 아닐 수도 있으므로 스크립트가 자동 감지합니다.
- `winre.wim` 경로가 올바른지 먼저 확인하세요.
