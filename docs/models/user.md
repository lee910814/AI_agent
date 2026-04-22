# User

> 플랫폼 사용자 계정 — 인증 정보, 역할(RBAC), 크레딧 잔액을 관리한다

**파일 경로:** `backend/app/models/user.py`
**테이블명:** `users`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `login_id` | VARCHAR(30) | NOT NULL | — | 로그인 아이디 (유니크) |
| `nickname` | VARCHAR(50) | NOT NULL | — | 화면 표시 이름 (유니크) |
| `email_hash` | VARCHAR(64) | NULL | — | 이메일 SHA-256 해시 (원본 미저장) |
| `password_hash` | VARCHAR(128) | NULL | — | 비밀번호 해시 (소셜 로그인 시 NULL) |
| `role` | VARCHAR(20) | NOT NULL | 'user' | 권한 역할 (user / admin / superadmin) |
| `age_group` | VARCHAR(20) | NOT NULL | 'unverified' | 연령 인증 상태 (minor_safe / adult_verified / unverified) |
| `adult_verified_at` | TIMESTAMPTZ | NULL | — | 성인 인증 완료 시각 |
| `auth_method` | VARCHAR(20) | NULL | — | 인증 방식 (local / google / kakao 등) |
| `preferred_llm_model_id` | UUID | NULL | — | 선호 LLM 모델 FK → `llm_models.id` |
| `preferred_themes` | VARCHAR(30)[] | NULL | — | 관심 테마 태그 배열 |
| `credit_balance` | INTEGER | NOT NULL | 0 | 보유 플랫폼 크레딧 |
| `daily_token_limit` | INTEGER | NULL | — | 일일 토큰 사용 한도 (NULL이면 무제한) |
| `monthly_token_limit` | INTEGER | NULL | — | 월간 토큰 사용 한도 (NULL이면 무제한) |
| `last_credit_grant_at` | TIMESTAMPTZ | NULL | — | 마지막 크레딧 지급 시각 |
| `banned_until` | TIMESTAMPTZ | NULL | — | 제재 만료 시각 (NULL이면 정상 계정) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 계정 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 마지막 수정 시각 |

---

## 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `preferred_llm_model` | LLMModel | ManyToOne | 사용자가 선호하는 LLM 모델 |
| `community_post_likes` | CommunityPostLike | OneToMany | 사용자가 누른 좋아요 목록 |
| `community_post_dislikes` | CommunityPostDislike | OneToMany | 사용자가 누른 싫어요 목록 |

---

## 인덱스 / 제약 조건

```sql
-- 유니크 제약
UNIQUE (login_id)
UNIQUE (nickname)

-- CHECK 제약
CONSTRAINT ck_users_role
    CHECK (role IN ('user', 'admin', 'superadmin'))

CONSTRAINT ck_users_age_group
    CHECK (age_group IN ('minor_safe', 'adult_verified', 'unverified'))

-- FK
preferred_llm_model_id → llm_models.id
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
