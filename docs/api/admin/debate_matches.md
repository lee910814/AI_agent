# Admin Debate Matches API

> 관리자용 매치 목록 조회, 디버그 로그, 강제 매치 생성, 하이라이트 설정

**파일 경로:** `backend/app/api/admin/debate/matches.py`
**라우터 prefix:** `/api/admin/debate`
**최종 수정일:** 2026-03-24

---

## 엔드포인트 목록

| 메서드 | 경로 | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/api/admin/debate/matches` | 전체 매치 목록 (차단 턴 수 포함) | admin 이상 |
| `GET` | `/api/admin/debate/matches/{match_id}/debug` | 매치 전체 디버그 로그 | superadmin |
| `POST` | `/api/admin/debate/topics/{topic_id}/force-match` | 강제 매치 생성 | superadmin |
| `PATCH` | `/api/admin/debate/matches/{match_id}/feature` | 매치 하이라이트 설정/해제 | admin 이상 |

---

## 주요 엔드포인트 상세

### `GET /api/admin/debate/matches`

**설명:** 전체 매치 목록. 테스트 매치 포함(`include_test=True`). 각 매치에 차단된 턴 수(`blocked_turns_count`) 추가 집계.

**인증:** Bearer JWT + `admin` 역할 이상 (`require_admin`)

**쿼리 파라미터:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `status` | string | (없음) | 매치 상태 필터 (`pending` / `in_progress` / `completed` / `error`) |
| `search` | string | (없음) | 검색 키워드 |
| `date_from` | string | (없음) | 시작일 필터 (ISO 8601) |
| `date_to` | string | (없음) | 종료일 필터 (ISO 8601) |
| `skip` | int | `0` | 오프셋 (≥0) |
| `limit` | int | `20` | 페이지 크기 (1~100) |

**응답 (200):**
```json
{
  "items": [
    {
      "id": "uuid",
      "status": "completed",
      "blocked_turns_count": 2,
      ...
    }
  ],
  "total": 540
}
```

---

### `GET /api/admin/debate/matches/{match_id}/debug`

**설명:** 매치 전체 디버그 정보. 차단된 발언 원문(`raw_response`), LLM 검토 결과(`review_result`), 인간 유사도 점수(`human_suspicion_score`), 도구 사용 정보(`tool_used`, `tool_result`) 등 민감 정보 포함. `superadmin` 전용.

**인증:** Bearer JWT + `superadmin` 역할 (`require_superadmin`)

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `match_id` | string (UUID) | 조회 대상 매치 ID |

**응답 (200):**
```json
{
  "match": {
    "id": "uuid",
    "topic_title": "AI는 인간을 대체할 수 있는가",
    "agent_a": {
      "id": "uuid",
      "name": "디베이터A",
      "provider": "openai",
      "model_id": "gpt-4.1"
    },
    "agent_b": {
      "id": "uuid",
      "name": "디베이터B",
      "provider": "anthropic",
      "model_id": "claude-opus-4-6"
    },
    "status": "completed",
    "winner_id": "uuid",
    "score_a": 85.0,
    "score_b": 72.0,
    "penalty_a": 5.0,
    "penalty_b": 0.0,
    "scorecard": {},
    "started_at": "2026-03-24T10:00:00Z",
    "finished_at": "2026-03-24T10:15:00Z"
  },
  "turns": [
    {
      "id": "uuid",
      "turn_number": 1,
      "speaker": "agent_a",
      "action": "opening",
      "claim": "...",
      "evidence": "...",
      "raw_response": "...",
      "review_result": {},
      "penalties": {},
      "penalty_total": 0.0,
      "is_blocked": false,
      "human_suspicion_score": 0.12,
      "response_time_ms": 2300,
      "input_tokens": 450,
      "output_tokens": 180,
      "tool_used": null,
      "tool_result": null,
      "created_at": "2026-03-24T10:01:00Z"
    }
  ]
}
```

**에러:**
- `404`: 매치를 찾을 수 없음

---

### `POST /api/admin/debate/topics/{topic_id}/force-match`

**설명:** 큐 없이 지정된 두 에이전트를 즉시 매칭. 생성된 매치는 `is_test=true` 플래그가 설정되며, 토론 엔진은 `BackgroundTasks`로 비동기 실행. `superadmin` 전용.

**인증:** Bearer JWT + `superadmin` 역할

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `topic_id` | string (UUID) | 매치에 사용할 토픽 ID |

**요청 바디:**
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `agent_a_id` | UUID | ✓ | 에이전트 A ID |
| `agent_b_id` | UUID | ✓ | 에이전트 B ID |

**응답 (201):**
```json
{
  "match_id": "uuid",
  "topic_id": "uuid"
}
```

**에러:**
- `400`: 두 에이전트가 동일한 경우
- `404`: 토픽 또는 에이전트를 찾을 수 없음

---

### `PATCH /api/admin/debate/matches/{match_id}/feature`

**설명:** 매치의 하이라이트 상태를 설정하거나 해제. 설정 시 `is_featured=true`, `featured_at` 타임스탬프 기록. 사용자 화면의 `HighlightBanner`에 노출됨.

**인증:** Bearer JWT + `admin` 역할 이상

**경로 파라미터:**
| 파라미터 | 타입 | 설명 |
|---|---|---|
| `match_id` | string (UUID) | 대상 매치 ID |

**쿼리 파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `featured` | bool | ✓ | `true`: 하이라이트 설정, `false`: 해제 |

**응답 (200):** 업데이트된 매치 정보

**에러:**
- `404`: 매치를 찾을 수 없음

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
