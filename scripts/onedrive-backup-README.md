# OneDrive 백업 스크립트

## 파일
- `scripts/onedrive-backup.ps1`
- `scripts/install-onedrive-backup-task.ps1`

## 기본 동작
- 원본: `D:\Claw\workspace`
- 대상: OneDrive 아래 `Claw-backups\YYYY-MM-DD`
- 로그: `Claw-backups\logs`
- 기본 실행: 매일 20:00
- 기본 복사 방식: 안전한 일반 복사(`/E`), 삭제 동작 없음
- 미러(`/MIR`)는 사용하지 않음

## 수동 실행
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\onedrive-backup.ps1
```

## 설치
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-onedrive-backup-task.ps1
```

## 옵션
예: 대상 폴더를 직접 지정
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\onedrive-backup.ps1 -DestinationRoot "$env:OneDrive\Backups"
```

미러 방식은 더 이상 사용하지 않음. 백업은 단순 복사로 유지.

## 제외 폴더
기본 제외:
- `.git`
- `node_modules`
- `dist`
- `build`
- `coverage`
- `.next`
- `.cache`
- `tmp`
- `temp`
- `out`
- `bin`
- `obj`

원하면 제외 목록을 줄이거나 늘릴 수 있음.
