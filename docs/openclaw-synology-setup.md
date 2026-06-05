# OpenClaw 시놀로지 NAS 설치 가이드

**대상 NAS**: Synology DS1520+ (Intel Celeron J4125, 8GB RAM, DSM 7.2+)
**대상 사용자**: 박영준 (대표님)
**작성일**: 2026-06-05

---

## 📋 사전 준비

### 필수 확인 사항

| 항목 | 확인 방법 |
|------|----------|
| DSM 버전 | 제어판 > 정보 센터 (7.2 이상 권장) |
| Container Manager 설치 | 패키지 센터에서 검색 |
| SSH 활성화 | 제어판 > 터미널 및 SNMP > SSH 서비스 |
| 관리자 계정 | admin 그룹 권한 필요 |
| 여유 공간 | volume1에 10GB 이상 |

---

## 1단계: Container Manager 설치

### 1-1. 패키지 센터 접속
1. DSM 로그인
2. **메인 메뉴 > 패키지 센터**
3. 검색창에 **"Container Manager"** 입력

### 1-2. 설치
- 설치 버튼 클릭
- 약관 동의
- 설치 완료까지 1-2분 대기

> ⚠️ 구 버전 DSM은 **"Docker"** 패키지명을 사용합니다. 둘 다 동일하게 작동합니다.

---

## 2단계: SSH 활성화

### 2-1. 제어판 설정
1. **제어판 > 터미널 및 SNMP**
2. **터미널** 탭 선택
3. **"SSH 서비스 활성화"** 체크
4. 포트: 22 (또는 원하는 포트로 변경)
5. **적용**

### 2-2. 보안 권장사항
- SSH 포트는 외부 노출하지 말 것 (내부 네트워크만)
- 강력한 비밀번호 또는 SSH 키 사용
- root 로그인 비활성화 유지

---

## 3단계: 디렉토리 구조 준비

### 3-1. File Station에서 폴더 생성

위치: `/volume1/docker/openclaw/`

```
/volume1/docker/openclaw/
├── workspace/        # 작업공간 (메모리, 설정 파일)
├── config/           # OpenClaw 설정
├── logs/             # 로그
└── data/             # 영구 데이터
```

### 3-2. SSH로 생성 (대안)

```bash
ssh admin@<NAS-IP>
sudo mkdir -p /volume1/docker/openclaw/{workspace,config,logs,data}
sudo chown -R admin:users /volume1/docker/openclaw
```

---

## 4단계: 현재 PC 데이터 백업

### 4-1. 이전할 파일 목록

PC 위치: `D:\Claw\workspace\`

```
필수:
├── IDENTITY.md
├── USER.md
├── SOUL.md
├── AGENTS.md
├── TOOLS.md
├── HEARTBEAT.md
├── MEMORY.md            # (있다면)
├── memory/              # 폴더 전체
├── .env.bybit           # API 키
└── docs/                # 문서

선택:
├── TODO.md
└── 기타 작업 파일
```

### 4-2. 백업 방법

#### 옵션 A: 압축 파일로 전송 (추천)
```powershell
# PC에서 압축
Compress-Archive -Path "D:\Claw\workspace\*" -DestinationPath "D:\openclaw-backup.zip"
```

#### 옵션 B: NAS에 직접 복사
1. File Station 접속
2. `/volume1/docker/openclaw/workspace/`로 이동
3. PC에서 드래그앤드롭

---

## 5단계: OpenClaw Docker 컨테이너 실행

### 방법 A: Container Manager GUI

#### 5-A-1. 이미지 다운로드
1. **Container Manager 실행**
2. 왼쪽 **"레지스트리"** 클릭
3. 검색: **"openclaw"** 
4. 공식 이미지 선택 후 **다운로드**
5. 태그: `latest`

#### 5-A-2. 컨테이너 생성
1. **"이미지"** 탭으로 이동
2. openclaw 이미지 선택 > **실행**
3. 컨테이너 이름: `openclaw`
4. **자동 재시작**: ✅ 활성화

#### 5-A-3. 포트 설정
- 컨테이너 포트: `3000` → 로컬 포트: `3000`
- (필요 시 다른 포트도 추가)

#### 5-A-4. 볼륨 마운트
| 호스트 경로 | 컨테이너 경로 |
|------------|--------------|
| `/volume1/docker/openclaw/workspace` | `/app/workspace` |
| `/volume1/docker/openclaw/config` | `/app/config` |
| `/volume1/docker/openclaw/data` | `/app/data` |

#### 5-A-5. 환경 변수
```
BYBIT_API_KEY=<API 키>
BYBIT_API_SECRET=<Secret>
TELEGRAM_BOT_TOKEN=<텔레그램 토큰>
TZ=Asia/Seoul
```

#### 5-A-6. 적용 및 시작
- **적용** 클릭
- 컨테이너 자동 시작

---

### 방법 B: SSH + Docker CLI

#### 5-B-1. Docker Compose 파일 작성

`/volume1/docker/openclaw/docker-compose.yml`:

```yaml
version: '3.8'

services:
  openclaw:
    image: openclaw/openclaw:latest
    container_name: openclaw
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - /volume1/docker/openclaw/workspace:/app/workspace
      - /volume1/docker/openclaw/config:/app/config
      - /volume1/docker/openclaw/data:/app/data
      - /volume1/docker/openclaw/logs:/app/logs
    environment:
      - TZ=Asia/Seoul
      - BYBIT_API_KEY=${BYBIT_API_KEY}
      - BYBIT_API_SECRET=${BYBIT_API_SECRET}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    env_file:
      - .env
```

#### 5-B-2. 환경 변수 파일

`/volume1/docker/openclaw/.env`:

```bash
BYBIT_API_KEY=CyErJOsy4I3XKZKbzO
BYBIT_API_SECRET=<secret>
TELEGRAM_BOT_TOKEN=<your_token>
```

#### 5-B-3. 실행

```bash
cd /volume1/docker/openclaw
sudo docker-compose up -d
```

#### 5-B-4. 로그 확인

```bash
sudo docker logs -f openclaw
```

---

## 6단계: 텔레그램 봇 연동 확인

### 6-1. 봇 응답 테스트
- 텔레그램 앱에서 봇과 대화
- "현황 업데이트" 입력
- Bybit API 연동 응답 확인

### 6-2. 응답 없을 시 체크리스트
| 체크 | 확인 사항 |
|------|----------|
| 컨테이너 실행 중? | `docker ps` |
| 로그에 에러? | `docker logs openclaw` |
| 토큰 정확? | .env 파일 확인 |
| 봇이 외부 인터넷 접속? | NAS 방화벽 확인 |

---

## 7단계: 기존 PC OpenClaw 종료

⚠️ **중요**: NAS에서 정상 동작 확인 후 진행

### 7-1. PC OpenClaw 종료
```powershell
# 작업 관리자 또는
openclaw gateway stop
```

### 7-2. 자동 시작 비활성화
- 시작 프로그램에서 OpenClaw 제거
- 또는 서비스 비활성화

### 7-3. 데이터 보존
- PC의 `D:\Claw\workspace` 폴더는 백업으로 유지
- 삭제하지 말고 보관

---

## 8단계: 외부 접근 설정 (선택)

### 8-1. QuickConnect 사용
- DSM > 제어판 > 외부 액세스 > QuickConnect
- 외부에서 NAS 접속 가능

### 8-2. 텔레그램만 사용 시
- 외부 접근 불필요
- 텔레그램 봇은 NAS에서 폴링 방식으로 동작

### 8-3. 웹 인터페이스 외부 접근 (고급)
- 리버스 프록시 설정 (Synology DSM 기본 지원)
- HTTPS 인증서 (Let's Encrypt)

---

## 🔧 문제 해결

### 컨테이너가 즉시 종료됨
```bash
sudo docker logs openclaw
```
- 환경 변수 누락 확인
- 볼륨 권한 확인

### 권한 오류
```bash
sudo chown -R 1000:1000 /volume1/docker/openclaw
```

### 메모리 부족
- Container Manager > 컨테이너 > 리소스
- 메모리 제한 설정 (예: 2GB)

### 네트워크 문제
- NAS 방화벽 확인
- 포트 충돌 확인 (`netstat -tlnp`)

---

## 📊 운영 체크리스트

### 일일 점검
- [ ] 컨테이너 실행 상태 (Container Manager)
- [ ] 텔레그램 봇 응답 확인
- [ ] 로그 에러 확인

### 주간 점검
- [ ] 워크스페이스 백업
- [ ] 디스크 사용량 확인
- [ ] DSM 업데이트 확인

### 월간 점검
- [ ] OpenClaw 이미지 업데이트
- [ ] 보안 패치 적용
- [ ] 백업 데이터 검증

---

## 🎯 최종 확인 사항

설치 완료 후 텔레그램에서 아래 명령으로 정상 동작 확인:

```
대표님 안녕하세요
```

응답이 비서체 + Nova 페르소나로 오면 성공입니다.

---

## 📞 추가 지원

설치 중 문제 발생 시:
- 로그 캡처 후 공유
- 정확한 에러 메시지 전달
- 단계별 진행 상황 보고

대표님 트레이딩 보조 활동 지속을 위해 안정적인 24/7 환경 구축이 목표입니다. ✨
