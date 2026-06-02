# 설치 미디어에서 winre.wim 추출하는 방법

이 문서는 Windows 11 설치 미디어에서 `winre.wim`을 추출해, 복구 파티션에 다시 넣고 `reagentc`로 등록하는 절차를 정리한 고객 전달용 가이드입니다.

---

## 개요

Windows 시스템에 `winre.wim`이 없더라도, 설치 미디어의 `install.wim` 또는 `install.esd` 안에서 복구 이미지를 추출할 수 있습니다.

이 방식은 다음 상황에 유용합니다.
- 현재 시스템에 `C:\Windows\System32\Recovery\winre.wim`이 없음
- 복구 파티션이 삭제되었음
- 새 복구 파티션을 만들고 WinRE를 다시 연결해야 함

---

## 준비물

- Windows 11 설치 ISO 또는 마운트된 설치 미디어
- 관리자 권한 PowerShell
- 아래 스크립트: `winre-extract.ps1`

---

## 스크립트 역할

`winre-extract.ps1`는 다음 작업을 자동으로 수행합니다.

1. 설치 미디어의 `sources\install.wim` 또는 `sources\install.esd` 확인
2. `install.esd`만 있으면 WIM으로 변환
3. 대상 이미지를 읽기 전용으로 마운트
4. 마운트된 이미지 내부에서 `winre.wim` 탐색
5. `winre.wim`을 출력 폴더로 복사
6. 임시 마운트 해제

---

## 추출 방법

### 1) 스크립트 실행

관리자 PowerShell에서:

```powershell
.\winre-extract.ps1 -SourceRoot D:\ -ImageIndex 1 -OutputDir C:\Temp\WinRE
```

- `D:\` 는 설치 ISO가 마운트된 드라이브로 바꾸세요.
- `-ImageIndex` 는 필요한 Windows 에디션 인덱스로 바꿀 수 있습니다.
- `-OutputDir` 는 추출 결과 저장 위치입니다.

### 2) 추출 결과 확인

성공하면 다음 파일이 생성됩니다.

```text
C:\Temp\WinRE\winre.wim
```

---

## 대상 PC에 적용하는 방법

복구 파티션이 이미 존재한다고 가정하면 다음 순서로 적용합니다.

### 1) 복구 파티션에 복사

```powershell
New-Item -ItemType Directory -Path R:\Recovery\WindowsRE -Force | Out-Null
Copy-Item C:\Temp\WinRE\winre.wim R:\Recovery\WindowsRE\winre.wim -Force
```

### 2) WinRE 경로 등록

```powershell
reagentc /setreimage /path R:\Recovery\WindowsRE /target C:\Windows
```

### 3) WinRE 활성화

```powershell
reagentc /enable
reagentc /info
```

### 4) 복구 파티션 드라이브 문자 제거

```powershell
diskpart
select volume R
remove letter=R
exit
```

---

## 고객 전달용 요약 문구

> Windows 11 설치 미디어에서 `winre.wim`을 추출한 뒤, 복구 파티션에 복사하고 `reagentc`로 재등록하면 복구 환경을 다시 활성화할 수 있습니다. 시스템에 `winre.wim`이 없어도 설치 미디어 기반으로 복구 이미지를 복원할 수 있습니다.

---

## 주의사항

- 관리자 권한이 필요합니다.
- `install.esd`만 있는 경우에는 먼저 WIM으로 변환합니다.
- 추출한 `winre.wim`은 가능한 한 동일한 Windows 11 계열에서 사용하세요.
- BitLocker가 켜져 있으면 작업 전 보호를 일시 중지하는 것이 안전합니다.

```powershell
manage-bde -protectors -disable C:
```
