# Bybit 거래용 API 키 생성 가이드

> 작성일: 2026-06-06
> 용도: Claw에서 Bybit 자동 거래/주문 수정용 키 발급
> 대상: 박영준 (zunn@eactive.co.kr)

---

## ⚠️ 보안 원칙

1. **출금(Withdraw) 권한 절대 부여 금지** — 키가 유출돼도 자금은 안전
2. **IP 화이트리스트 필수** — 가장 강력한 보호막
3. **기존 읽기 전용 키는 그대로 유지** — 새 거래 키와 분리해서 사용
4. **2FA(OTP) 활성화 필수**

---

## 📋 단계별 생성 과정

### 1. Bybit API 관리 페이지 접속

👉 https://www.bybit.com/app/user/api-management

또는: 우측 상단 프로필 아이콘 → **Account & Security** → **API Management**

### 2. "Create New Key" 클릭

- 키 타입: **System-generated API Keys** 선택
- (Third-party는 외부 봇 연동용이라 다름)

### 3. 키 용도 선택

- **API Transaction** 선택 (HFT 아니어도 OK)
- Name: `Claw-Trading` (알아볼 수 있는 이름)

### 4. 권한 설정 ⭐ 가장 중요

#### ✅ 켜야 할 것

| 카테고리 | 권한 | 용도 |
|---|---|---|
| **Contract** | Orders | 선물 주문 생성/수정/취소 |
| **Contract** | Positions | 포지션 조회 및 SL/TP 수정 |
| **Contract** | Execution | 체결 내역 조회 |
| **Spot Trading** | Trade | 스팟 거래 (사용 시) |
| **Wallet** | Account Transfer | 선물↔현물 자금 이동 (필요 시) |
| **Read** | All | 잔고, 시세, 주문 조회 |

#### ❌ 절대 켜지 말 것

| 권한 | 이유 |
|---|---|
| **Withdraw** | 출금 권한 — 유출 시 자금 탈취 가능 |
| **Sub-Account Transfer** | 사용 안 하면 끄기 |
| **NFT, Earn 등** | 사용 안 하면 전부 끄기 |

### 5. IP 제한 설정 ⭐ 매우 중요

#### 현재 IP 확인 방법

**브라우저:**
```
https://api.ipify.org
```

**PowerShell:**
```powershell
(Invoke-WebRequest https://api.ipify.org).Content
```

#### 입력

- 확인된 IP를 **IP Restriction** 칸에 입력
- 여러 IP면 쉼표(,)로 구분
- 동적 IP 환경이면 ISP가 부여하는 대역대 입력 고려

> 💡 **IP 제한 없이 키 발급 시 만료기간이 90일로 강제 단축됩니다.**
> 보안과 편의 모두를 위해 IP 제한 거는 게 좋아요.

### 6. 2FA 인증

- Google Authenticator OTP 입력
- 이메일 인증 코드 입력

### 7. 키 발급 및 저장 ⚠️ 한 번만 표시됨

- **API Key**: 항상 다시 볼 수 있음
- **API Secret**: 발급 화면에서만 표시 — 사라지면 재발급 필요

발급 즉시 안전한 곳에 저장.

---

## 💾 Claw 환경에 저장

`D:\Claw\workspace\.env.bybit` 파일에 추가:

```env
# 기존 읽기 전용 키 (모니터링/조회용 유지)
BYBIT_API_KEY=<기존 읽기 전용>
BYBIT_API_SECRET=<기존>

# 새 거래용 키
BYBIT_TRADE_API_KEY=<새 거래용 키>
BYBIT_TRADE_API_SECRET=<새 거래용 시크릿>
```

---

## 🧪 발급 후 검증 절차

새 키 발급 후 안전 테스트 권장:

1. **권한 확인** — 잔고 조회 (Read 권한)
2. **주문 수정 테스트** — 기존 SL 주문의 가격을 1센트 살짝 수정 (실제 거래 발생 안 함)
3. **원복** — 원래 가격으로 되돌림
4. ✅ 통과 시 본격 사용

---

## 🛡️ 추가 보안 권장사항

- **키 발급 후 30일마다 IP 확인** — IP 바뀌면 갱신
- **사용 안 하는 거래소 권한 정기 점검** — `Trade Settings` 페이지에서
- **이상 거래 알림 활성화** — Bybit 알림 설정
- **API 키 사용 로그 정기 확인** — `API Management` 페이지 하단

---

## 📞 문제 발생 시

- API 키 유출 의심: **즉시 Bybit 페이지에서 키 Delete**
- 출금 권한 실수로 켰음: **삭제 후 재발급**
- 사용량 한도 초과: Bybit 기본 한도는 충분, IP 화이트리스트로 분당 600회

---

## 🔗 참고 링크

- Bybit API 관리: https://www.bybit.com/app/user/api-management
- Bybit API V5 문서: https://bybit-exchange.github.io/docs/v5/intro
- 권한 상세 설명: https://www.bybit.com/help-center/article/Bybit-API-Permissions

---

_작성: Nova (Claw AI Assistant) ✨_
