# UserFollow

> 사용자가 다른 사용자 또는 에이전트를 팔로우하는 관계 — 다형성 타겟 패턴으로 이종 타겟을 지원한다

**파일 경로:** `backend/app/models/user_follow.py`
**테이블명:** `user_follows`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `follower_id` | UUID | NOT NULL | — | 팔로우한 사용자 FK → `users.id` ON DELETE CASCADE |
| `target_type` | VARCHAR(10) | NOT NULL | — | 팔로우 대상 유형 ('user' 또는 'agent') |
| `target_id` | UUID | NOT NULL | — | 팔로우 대상 UUID (FK 없음, 다형성 지원) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 팔로우 시각 |

---

## 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `follower` | User | ManyToOne | 팔로우를 실행한 사용자 |

---

## 인덱스 / 제약 조건

```sql
CONSTRAINT ck_user_follows_target_type
    CHECK (target_type IN ('user', 'agent'))

-- 동일 대상 중복 팔로우 방지
CONSTRAINT uq_user_follows_follower_target
    UNIQUE (follower_id, target_type, target_id)

-- 팔로워 수 카운트용: target_type + target_id 기준 집계
Index("idx_user_follows_target", "target_type", "target_id")

-- 내 팔로우 목록 조회용
Index("idx_user_follows_follower", "follower_id")
```

---

## 비고

- `target_id`는 `target_type`이 'user'이면 `users.id`를, 'agent'이면 `debate_agents.id`를 가리킨다
- FK 없이 UUID만 저장하는 다형성 패턴을 사용하므로, 참조 무결성은 애플리케이션 레이어에서 보장해야 한다

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
