# Windows 11 복구 파티션 재생성 요약

## 목적
이미 추출해 둔 `winre.wim`을 사용해 **C: 뒤쪽(디스크 마지막)** 에 복구 파티션을 만들고 WinRE를 다시 등록합니다.

---

## 준비물
- 관리자 권한 PowerShell
- 추출된 `winre.wim`
- 대상 Windows 11 시스템

---

## 사용 방법

### 1) 스크립트 실행
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\apply-winre-recovery.ps1 -WinReWimPath C:\Temp\WinRE\winre.wim
```

필요하면 C:를 줄이며 진행:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\apply-winre-recovery.ps1 -WinReWimPath C:\Temp\WinRE\winre.wim -ShrinkOSDrive
```

실행 중 `YES`를 입력해야 계속 진행됩니다.

---

## 스크립트가 하는 일
1. WinRE 비활성화
2. 시스템 디스크 확인
3. 필요 시 C: 마지막 공간 확보
4. **C: 뒤쪽에 복구 파티션 생성**
5. `winre.wim` 복사
6. `reagentc /setreimage` 등록
7. `reagentc /enable` 활성화
8. 복구 파티션 드라이브 문자 숨김

---

## 복구 파티션 정보
- 위치: **C: 뒤, 디스크 마지막**
- 크기: 기본 1024MB
- GUID: `de94bba4-06d1-4d40-a16a-bfd50179d6ac`
- GPT 속성: `0x8000000000000001`

---

## 정상 확인
```powershell
reagentc /info
Get-Partition | Format-Table DiskNumber, PartitionNumber, DriveLetter, Size, GptType
```

복구 파티션은 드라이브 문자 없이 숨겨지고, WinRE 상태는 활성화로 표시되어야 합니다.

---

## 주의사항
- BitLocker가 켜져 있으면 작업 전 잠시 보호를 중지하는 것이 안전합니다.

```powershell
manage-bde -protectors -disable C:
```

- 이미 복구 파티션이 있으면 스크립트가 중단됩니다.
- `winre.wim` 경로가 올바른지 먼저 확인하세요.

---

## 고객용 한 줄 설명
> 이 스크립트는 추출된 `winre.wim`을 이용해 Windows 11의 복구 파티션을 C: 뒤쪽에 다시 만들고, WinRE를 자동으로 재등록합니다.
