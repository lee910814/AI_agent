# UserCommunityStats

> 사용자별 커뮤니티 활동량 집계 — 좋아요·팔로우 수를 합산해 활동 티어(Bronze~Diamond)를 산정한다

**파일 경로:** `backend/app/models/user_community_stats.py`
**테이블명:** `user_community_stats`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | uuid4() | PK |
| `user_id` | UUID | NOT NULL | — | 사용자 FK → `users.id` ON DELETE CASCADE (인덱스 포함) |
| `total_score` | INTEGER | NOT NULL | 0 | 활동 총 점수 |
| `tier` | VARCHAR(20) | NOT NULL | 'Bronze' | 활동 티어 (Bronze / Silver / Gold / Diamond 등) |
| `likes_given` | INTEGER | NOT NULL | 0 | 누른 좋아요 총 횟수 |
| `follows_given` | INTEGER | NOT NULL | 0 | 팔로우한 총 횟수 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 마지막 갱신 시각 (onupdate 자동 갱신) |

---

## 관계 (Relationships)

이 모델에서 직접 정의된 relationship 없음.

---

## 인덱스 / 제약 조건

```sql
-- 사용자당 1행 보장
CONSTRAINT uq_user_community_stats_user_id
    UNIQUE (user_id)

-- user_id 단독 인덱스 (index=True 옵션으로 자동 생성)
Index on user_id
```

---

## 비고

- 활동 발생 시마다 비동기로 업데이트되는 집계 테이블
- `updated_at`은 `onupdate=func.now()` 설정으로 레코드 변경 시 자동 갱신

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
