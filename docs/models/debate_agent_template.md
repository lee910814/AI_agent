# DebateAgentTemplate

> 관리자가 제공하는 미리 정의된 에이전트 기반 설정 — 사용자는 커스터마이징 값만 입력해 에이전트를 생성한다

**파일 경로:** `backend/app/models/debate_agent_template.py`
**테이블명:** `debate_agent_templates`
**최종 수정일:** 2026-03-24

---

## 컬럼 정의

| 컬럼명 | 타입 | Nullable | 기본값 | 설명 |
|---|---|---|---|---|
| `id` | UUID | NOT NULL | gen_random_uuid() | PK |
| `slug` | VARCHAR(50) | NOT NULL | — | URL 친화적 식별자 (유니크, 예: "logical-debater") |
| `display_name` | VARCHAR(100) | NOT NULL | — | 화면 표시 이름 |
| `description` | TEXT | NULL | — | 템플릿 설명 |
| `icon` | VARCHAR(50) | NULL | — | 아이콘 식별자 문자열 |
| `base_system_prompt` | TEXT | NOT NULL | — | 코어 시스템 프롬프트 (`{customization_block}` 플레이스홀더 포함) |
| `customization_schema` | JSONB | NOT NULL | '{}' | 커스터마이징 항목 정의 (sliders, selects, free_text) |
| `default_values` | JSONB | NOT NULL | '{}' | 커스터마이징 기본값 flat dict |
| `sort_order` | INTEGER | NOT NULL | 0 | 목록 표시 순서 |
| `is_active` | BOOLEAN | NOT NULL | true | 활성 여부 (비활성 시 신규 생성 불가) |
| `created_at` | TIMESTAMPTZ | NOT NULL | now() | 생성 시각 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | now() | 마지막 수정 시각 |

---

## 관계 (Relationships)

이 모델에서 직접 정의된 relationship 없음.
역방향으로 `DebateAgent.template`이 이 모델을 참조한다.

---

## 인덱스 / 제약 조건

```sql
UNIQUE (slug)
```

---

## 비고

- `customization_schema` JSONB 구조 예시:
  ```json
  {
    "sliders": [{"key": "aggression", "label": "공격성", "min": 1, "max": 5}],
    "selects": [{"key": "tone", "label": "말투", "options": ["formal", "casual"]}],
    "free_text": [{"key": "background", "label": "배경 설정"}]
  }
  ```
- `base_system_prompt`의 `{customization_block}` 위치에 사용자 커스터마이징 값이 삽입된다

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
