@echo off
chcp 65001 >nul
setlocal

echo ================================================
echo  virtio 드라이버 자동 설치 (수동 트리거)
echo ================================================
echo.

:: PowerShell 실행 정책 해제
powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force" >nul 2>&1

:: virtio-win ISO 드라이브 자동 감지 (D: ~ H: 순서로 검색)
set VIRTIO_DRIVE=

for %%d in (D E F G H I) do (
    if exist "%%d:\viostor\w11\amd64\viostor.inf" (
        set VIRTIO_DRIVE=%%d:\
        goto :found
    )
)

echo [오류] virtio-win ISO를 찾을 수 없습니다.
echo.
echo  다음을 확인하세요:
echo   1. virtio-win.iso가 VM에 마운트되어 있는지
echo   2. 드라이브 문자가 D: ~ I: 범위 내에 있는지
echo   3. E:\viostor\w11\amd64\viostor.inf 경로 존재 여부
echo.
pause
exit /b 1

:found
echo [정보] virtio-win ISO 감지됨: %VIRTIO_DRIVE%
echo.

:: install-virtio.ps1 경로 확인
set PS_SCRIPT=%~dp0install-virtio.ps1

if not exist "%PS_SCRIPT%" (
    echo [오류] install-virtio.ps1을 찾을 수 없습니다.
    echo  경로: %PS_SCRIPT%
    echo  이 .bat 파일과 같은 폴더에 install-virtio.ps1이 있어야 합니다.
    pause
    exit /b 1
)

echo [정보] 스크립트 실행: %PS_SCRIPT%
echo [정보] 드라이버 경로: %VIRTIO_DRIVE%
echo.

:: PowerShell 스크립트 실행
powershell -ExecutionPolicy Bypass ^
    -File "%PS_SCRIPT%" ^
    -VirtioPath "%VIRTIO_DRIVE%"

echo.
echo ================================================
echo  완료. 창을 닫아도 됩니다.
echo ================================================
pause
endlocal
