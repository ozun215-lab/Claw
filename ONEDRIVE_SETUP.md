# OneDrive 동기화 설정 가이드

## 📋 사무실 PC (이곳)에서 설정

### Step 1: OneDrive 시작
1. **Windows 시작 버튼** 클릭
2. 검색창에 `OneDrive` 입력
3. **Microsoft OneDrive** 실행
   - 아직 로그인 안 했으면: 대표님 계정(zunn@eactive.co.kr) 로그인

### Step 2: OneDrive 폴더 추가
1. **OneDrive 폴더 위치 확인**
   ```
   기본 경로: C:\Users\zunn\OneDrive
   ```

2. **동기화할 폴더 설정**
   - OneDrive 시스템 트레이 아이콘 (화면 오른쪽 아래) 우클릭
   - **설정** 클릭
   - **계정** 탭 → **폴더 선택** 버튼
   
   ![OneDrive Settings 이미지 설명]
   - 체크박스 중 필요한 것만 선택
   - **다음** → **동기화 시작**

### Step 3: Bybit 폴더 동기화 추가
1. **OneDrive 폴더 열기**
   ```
   C:\Users\zunn\OneDrive
   ```

2. **새 폴더 생성**
   - 우클릭 → 새로 만들기 → 폴더
   - 폴더명: `Bybit_Trading`

3. **사무실의 파일 복사**
   ```powershell
   # PowerShell 열기 (관리자 권한)
   
   # Step 1: 원드라이브 폴더로 이동
   cd C:\Users\zunn\OneDrive\Bybit_Trading
   
   # Step 2: 사무실 파일 모두 복사
   Copy-Item D:\Claw\workspace\*.js .
   Copy-Item D:\Claw\workspace\.env.bybit .
   Copy-Item D:\Claw\workspace\MEMORY.md .
   
   # Step 3: 복사 확인
   Get-ChildItem
   ```

4. **동기화 대기**
   - 파일이 OneDrive 클라우드로 업로드 대기 중
   - 상태: OneDrive 아이콘 → 파란 원 (동기화 중)

---

## 🏠 집의 PC에서 설정

### Step 1: OneDrive 설치 및 로그인
1. **Windows 시작** → **Microsoft Store** 열기
2. 검색: `OneDrive`
3. **Microsoft OneDrive** 설치 (대부분 이미 설치됨)
4. 실행 후 **대표님 계정 로그인**
   ```
   이메일: zunn@eactive.co.kr
   비밀번호: [Windows 계정 비밀번호]
   ```

### Step 2: 폴더 동기화 대기
1. OneDrive 아이콘 확인 (화면 오른쪽 아래)
   - **파란 원**: 동기화 중 🔄
   - **흰 체크마크**: 완료 ✅

2. **자동 동기화 완료**
   ```
   C:\Users\zunn\OneDrive\Bybit_Trading\
   ```
   여기에 모든 파일이 자동으로 다운로드됨

### Step 3: 집의 워크스페이스 업데이트
```powershell
# PowerShell 열기

# Step 1: OneDrive에서 파일 복사
Copy-Item C:\Users\zunn\OneDrive\Bybit_Trading\*.js D:\Claw\workspace\

# Step 2: 기존 Node 프로세스 종료
taskkill /PID <기존_NODE_PID> /F

# 또는 모든 node 종료:
taskkill /IM node.exe /F

# Step 3: 새 봇 시작
cd D:\Claw\workspace
node trading_dashboard.js    # 터미널 1
node auto_scan.js            # 터미널 2
node telegram_alert_bot.js   # 터미널 3
```

---

## 🔄 지속적인 동기화

### 사무실 PC에서:
```powershell
# 파일 수정 후 자동 동기화
# OneDrive가 자동으로 변경사항 감지 → 클라우드 업로드
```

### 집 PC에서:
```powershell
# 주기적으로 다시 다운로드
Copy-Item C:\Users\zunn\OneDrive\Bybit_Trading\*.js D:\Claw\workspace\ -Force

# 또는 OneDrive 폴더를 직접 사용 (심링크)
New-Item -ItemType SymbolicLink -Path D:\Claw\workspace\remote -Target C:\Users\zunn\OneDrive\Bybit_Trading
```

---

## ⚙️ OneDrive 자동 동기화 설정

### 사무실 PC:
```powershell
# OneDrive 설정 열기
& "C:\Program Files\Microsoft OneDrive\OneDrive.exe" /shell:apicall ShellExecuteW Shell.Application CreateObject Shell.Application InvokeVerb Open "shell:syncenginefolder"

# 또는 수동으로:
# 화면 오른쪽 아래 OneDrive 아이콘 → 설정 ⚙️
# → 자동 저장 → 모든 동기화 옵션 활성화
```

---

## 🎯 최종 확인 체크리스트

### ✅ 사무실 PC
- [ ] OneDrive 로그인 (zunn@eactive.co.kr)
- [ ] C:\Users\zunn\OneDrive\Bybit_Trading 폴더 생성
- [ ] 모든 .js 파일 복사
- [ ] .env.bybit 복사
- [ ] OneDrive 동기화 완료 (파란 아이콘 → 흰 체크)

### ✅ 집 PC
- [ ] OneDrive 로그인 (같은 계정)
- [ ] C:\Users\zunn\OneDrive\Bybit_Trading 폴더 확인
- [ ] 파일이 모두 다운로드됨
- [ ] D:\Claw\workspace에 복사
- [ ] Node 프로세스 재시작

---

## 🔗 OneDrive 웹 접속

언제 어디서나 파일 확인:
```
https://onedrive.live.com/
```

브라우저에서 zunn@eactive.co.kr 로그인 후 Bybit_Trading 폴더 확인 가능

---

**완료되면 "완료" 말씀해주세요!** ✅
