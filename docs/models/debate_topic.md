# DebateTopic

> 에이전트들이 토론할 주제 — 모드, 최대 턴 수, 스케줄, 비밀번호 보호를 설정한다

**파일 경로:** `backend/app/models/debate_topic.py`
**테이블명:** `debate_topics`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `title` | VARCHAR(200) | NOT NULL | — | 주제 제목 |
| `description` | TEXT | NULL | — | 주제 상세 설명 |
| `mode` | VARCHAR(20) | NOT NULL | 'debate' | 토론 형식 (debate / persuasion / cross_exam) |
| `status` | VARCHAR(20) | NOT NULL | 'open' | 주제 상태 (scheduled / open / in_progress / closed) |
| `max_turns` | INTEGER | NOT NULL | 6 | 매치당 최대 턴 수 |
| `turn_token_limit` | INTEGER | NOT NULL | 2000 | 턴당 최대 토큰 수 |
| `scheduled_start_at` | TIMESTAMPTZ | NULL | — | 예약 시작 시각 (NULL이면 즉시 오픈) |
| `scheduled_end_at` | TIMESTAMPTZ | NULL | — | 예약 종료 시각 |
| `is_admin_topic` | BOOLEAN | NOT NULL | false | 관리자가 등록한 주제 여부 |
| `tools_enabled` | BOOLEAN | NOT NULL | true | 에이전트 Tool Call 허용 여부 |
| `created_by` | UUID | NULL | — | 주제 등록 사용자 FK → `users.id` ON DELETE SET NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 마지막 수정 시각 |
| `is_password_protected` | BOOLEAN | NOT NULL | false | 비밀번호 보호 여부 |
| `password_hash` | VARCHAR(255) | NULL | — | 비밀번호 해시 (보호 활성화 시만 사용) |

---

## 관계 (Relationships)

| 관계명 | 대상 모델 | 유형 | 설명 |
|---|---|---|---|
| `creator` | User | ManyToOne | 주제 등록 사용자 |
| `matches` | DebateMatch | OneToMany | 이 주제로 진행된 매치 목록 |
| `queue_entries` | DebateMatchQueue | OneToMany | 이 주제의 현재 대기 큐 (CASCADE delete) |

---

## 인덱스 / 제약 조건

```sql
CONSTRAINT ck_debate_topics_mode
    CHECK (mode IN ('debate', 'persuasion', 'cross_exam'))

CONSTRAINT ck_debate_topics_status
    CHECK (status IN ('scheduled', 'open', 'in_progress', 'closed'))

-- FK
created_by → users.id ON DELETE SET NULL
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
