# DebateTournamentService

> 토너먼트 생성·참가 등록·라운드 진행·조회를 담당하는 서비스 계층

**파일 경로:** `backend/app/services/debate/tournament_service.py`
**최종 수정일:** 2026-03-12

---

## 모듈 목적

토너먼트 전체 생명주기를 관리한다.

- **생성** — 제목·토픽·대진표 크기 설정 후 `"registration"` 상태로 생성
- **참가 등록** — `WITH FOR UPDATE` 행 잠금으로 동시 요청 시 정원 초과 방지, 씨드 번호 자동 부여
- **라운드 진행** — 현재 라운드 전체 완료 시 승자끼리 다음 라운드 매치 자동 생성. 최종 1명 남으면 토너먼트 종료
- **조회** — 단건 상세(참가 에이전트 목록 포함) 및 목록 페이지네이션

---

## 주요 상수

없음

---

## 클래스: DebateTournamentService

### 생성자

```python
def __init__(self, db: AsyncSession)
```

| 파라미터 | 타입 | 설명 |
|---|---|---|
| `db` | `AsyncSession` | SQLAlchemy 비동기 세션. FastAPI `Depends(get_db)`로 주입 |

### 메서드

| 메서드 | 시그니처 | 역할 |
|---|---|---|
| `create_tournament` | `(title: str, topic_id: str, bracket_size: int, created_by: uuid.UUID) -> DebateTournament` | 토너먼트 생성. 초기 `status`는 `"registration"` |
| `join_tournament` | `(tournament_id: str, agent_id: str, user: User) -> DebateTournamentEntry` | 참가 등록. 토너먼트 행 `WITH FOR UPDATE` 잠금 → 상태·정원·중복 순서로 검증. 씨드는 현재 참가자 수 + 1 |
| `advance_round` | `(tournament_id: str) -> None` | 현재 라운드 전체 완료 확인 → 승자끼리 다음 라운드 매치 생성. 1명 남으면 토너먼트 종료 처리 |
| `get_tournament` | `(tournament_id: str) -> dict \| None` | 토너먼트 상세 + 참가 에이전트 목록 (seed ASC). 미존재 시 `None` |
| `list_tournaments` | `(skip: int = 0, limit: int = 20) -> tuple[list, int]` | 토너먼트 목록 (created_at DESC) + 총 개수 |

---

## 의존 모듈

| 모듈 | 경로 | 용도 |
|---|---|---|
| `DebateAgent` | `app.models.debate_agent` | 참가 에이전트 이름·이미지 조회 (`get_tournament`) |
| `DebateMatch` | `app.models.debate_match` | 다음 라운드 매치 INSERT (`advance_round`) |
| `DebateTournament` | `app.models.debate_tournament` | 토너먼트 ORM 모델 |
| `DebateTournamentEntry` | `app.models.debate_tournament` | 토너먼트 참가 항목 ORM 모델 |
| `User` | `app.models.user` | 참가 요청자 타입 힌트 |

---

## 호출 흐름

### 참가 등록 검증 순서 (`join_tournament`)

```
1. DebateTournament SELECT ... WITH FOR UPDATE (행 잠금)
2. status == "registration" 확인 → 아니면 ValueError
3. 현재 DebateTournamentEntry 개수 재확인 (잠금 후) → bracket_size 초과 시 ValueError
4. 동일 agent_id 중복 참가 확인 → ValueError("DUPLICATE")
5. seed = current_count + 1 → DebateTournamentEntry INSERT
```

### 라운드 진행 흐름 (`advance_round`)

```
advance_round(tournament_id)
  → DebateTournament 조회. status != "in_progress"이면 즉시 return
  → 현재 라운드 매치 목록 조회
  → 미완료(status != "completed") 매치 존재 시 즉시 return (아직 진행 중)
  → 승자 수집:
      ├─ winner_id 있으면 winner_id
      └─ 무승부(winner_id=None, status="completed")이면 agent_a_id 진출
  → len(winners) == 1:
      → t.winner_agent_id = winners[0]
      → t.status = "completed", t.finished_at = now(UTC)
      → commit → 토너먼트 종료 로그
  → len(winners) > 1:
      → pairs: (winners[0], winners[1]), (winners[2], winners[3]), ...
      → DebateMatch INSERT (tournament_round = current_round + 1)
      → t.current_round += 1
      → commit → 다음 라운드 진행 로그
```

### 전체 API 호출 흐름

```
API 라우터 (api/debate_tournaments.py)
  → DebateTournamentService.create_tournament()    # POST /tournaments
  → DebateTournamentService.join_tournament()      # POST /tournaments/{id}/join
  → DebateTournamentService.get_tournament()       # GET  /tournaments/{id}
  → DebateTournamentService.list_tournaments()     # GET  /tournaments

API 라우터 또는 관리자 액션
  → DebateTournamentService.advance_round()        # POST /admin/tournaments/{id}/advance
```

### `get_tournament` 반환 dict 구조

```python
{
    "id": str,
    "title": str,
    "topic_id": str,
    "status": str,                  # "registration" | "in_progress" | "completed"
    "bracket_size": int,
    "current_round": int,
    "winner_agent_id": str | None,
    "started_at": datetime | None,
    "finished_at": datetime | None,
    "created_at": datetime,
    "entries": [
        {
            "id": str,
            "agent_id": str,
            "agent_name": str,
            "agent_image_url": str | None,
            "seed": int,
            "eliminated_at": datetime | None,
            "eliminated_round": int | None,
        },
        ...
    ]
}
```

---

## 에러 처리

| 상황 | 예외 | HTTP 변환 |
|---|---|---|
| 토너먼트 미존재 (`join_tournament`) | `ValueError("Tournament not found")` | 404 |
| 참가 신청 기간 아님 | `ValueError("참가 신청 기간이 아닙니다")` | 400 |
| 정원 초과 | `ValueError("참가 정원이 가득 찼습니다")` | 400 |
| 중복 참가 | `ValueError("DUPLICATE")` | 409 |

예외 → HTTP 상태코드 변환은 `api/debate_tournaments.py` 라우터가 담당한다.

`advance_round`는 조용한 실패 정책을 따른다. 토너먼트 미존재 또는 `in_progress` 아닌 상태이면 예외 없이 즉시 `return`한다.

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-12 | 레퍼런스 형식에 맞춰 전면 재작성. 클래스 섹션 구조화, advance_round 흐름 다이어그램 추가, get_tournament 반환 구조 통합, 에러 처리 HTTP 코드 명시 |
| 2026-03-11 | 실제 코드 기반으로 초기 재작성 |
