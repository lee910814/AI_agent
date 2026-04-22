# userStore

> HttpOnly 쿠키 기반 인증 및 로그인 사용자 정보를 관리하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/userStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `user` | `User \| null` | `null` | 현재 로그인 사용자 정보 |
| `token` | `string \| null` | `null` | 하위 호환성용 토큰 필드 (실제 인증은 쿠키 기반, 사용되지 않음) |
| `initialized` | `boolean` | `false` | `initialize()` 완료 여부 (로딩 게이트로 사용) |

### User 타입

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `string` | 사용자 UUID |
| `login_id` | `string` | 로그인 ID |
| `nickname` | `string` | 닉네임 |
| `email` | `string \| null` | 이메일 |
| `role` | `'user' \| 'admin' \| 'superadmin'` | 역할 |
| `ageGroup` | `string` | 연령대 |
| `adultVerifiedAt` | `string \| null` | 성인 인증 일시 |
| `preferredLlmModelId` | `string \| null` | 선호 LLM 모델 ID |
| `creditBalance` | `number` | 플랫폼 크레딧 잔액 |
| `subscriptionPlanKey` | `string \| null` | 구독 플랜 키 |
| `createdAt` | `string` | 가입 일시 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `setUser` | `user: User \| null` | 사용자 정보 직접 설정 |
| `setToken` | `token: string \| null` | localStorage에 토큰 저장/제거 (SSE Authorization 헤더용 보조 메커니즘) |
| `isAdultVerified` | — | `adultVerifiedAt != null` 여부 반환 |
| `isAdmin` | — | role이 `admin` 또는 `superadmin`인지 반환 |
| `isSuperAdmin` | — | role이 `superadmin`인지 반환 |
| `logout` | — | `/auth/logout` 호출 후 localStorage 토큰 제거, 사용자 상태 초기화 |
| `initialize` | — | `/auth/me` 호출로 쿠키 기반 세션 복원. 동시 호출 방지(pending 체크), 초기화 완료 시 `initialized: true` |

---

## initialize() 설계

`initialize()`는 클로저로 `pending` 변수를 캡처하여 동시에 여러 번 호출되어도 실제 API 호출은 한 번만 수행합니다.

```
첫 번째 호출 → pending = Promise 생성 → API 호출
두 번째 호출 → pending이 존재 → 동일 Promise 반환
완료 → pending = null, initialized = true
```

비로그인 상태(쿠키 없음 또는 만료)는 정상 케이스로 처리하며, 에러가 아닌 `{ user: null, initialized: true }`로 설정합니다.

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `app/layout.tsx` (또는 providers) | 앱 초기화 시 `initialize()` 호출 |
| `components/ui/Header.tsx` | 로그인 상태, 사용자 닉네임, 역할 표시 |
| `app/admin/**` | `isAdmin()` / `isSuperAdmin()` 접근 제어 |
| `hooks/useDebateStream.ts` | SSE 연결 시 localStorage 토큰 읽기 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-02-26 | `creditBalance`, `subscriptionPlanKey` 필드 추가 |
