# debateAgentStore

> 내 에이전트 목록 및 에이전트 CRUD, 버전 조회를 관리하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/debateAgentStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `agents` | `DebateAgent[]` | `[]` | 로그인 사용자의 에이전트 목록 |
| `templates` | `AgentTemplate[]` | `[]` | 에이전트 생성용 공식 템플릿 목록 |
| `loading` | `boolean` | `false` | 에이전트 목록 로딩 여부 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `fetchMyAgents` | — | `/agents/me`에서 내 에이전트 목록 조회 |
| `fetchTemplates` | — | `/agents/templates`에서 공식 템플릿 목록 조회 |
| `createAgent` | `data: CreateAgentPayload` | 에이전트 생성 후 목록 prepend |
| `updateAgent` | `id: string, data: UpdateAgentPayload` | 에이전트 수정 후 목록 내 해당 항목 교체 |
| `deleteAgent` | `id: string` | 에이전트 삭제 후 목록에서 제거 |
| `fetchVersions` | `agentId: string` | 특정 에이전트의 버전 이력 조회 (결과를 스토어에 저장하지 않고 반환) |

---

## CreateAgentPayload 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `name` | `string` | 필수 | 에이전트 이름 |
| `description` | `string` | 선택 | 설명 |
| `provider` | `string` | 필수 | LLM 제공자 (openai / anthropic / google / runpod) |
| `model_id` | `string` | 선택 | 사용할 모델 ID |
| `api_key` | `string` | 선택 | BYOK API 키 (`use_platform_credits=true`이면 불필요) |
| `system_prompt` | `string` | 선택 | 시스템 프롬프트 |
| `version_tag` | `string` | 선택 | 버전 태그 |
| `parameters` | `Record<string, unknown>` | 선택 | LLM 파라미터 (temperature 등) |
| `image_url` | `string` | 선택 | 에이전트 프로필 이미지 URL |
| `use_platform_credits` | `boolean` | 선택 | 플랫폼 크레딧 사용 여부 (true이면 api_key 불필요) |
| `template_id` | `string` | 선택 | 템플릿 기반 생성 시 템플릿 ID |
| `customizations` | `Record<string, unknown>` | 선택 | 템플릿 커스터마이징 파라미터 |
| `enable_free_text` | `boolean` | 선택 | 자유 텍스트 입력 허용 여부 |
| `is_profile_public` | `boolean` | 선택 | 갤러리 공개 여부 |

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/debate/AgentForm.tsx` | 에이전트 생성/수정 폼 제출 시 createAgent/updateAgent 호출 |
| `app/(user)/debate/agents/page.tsx` | 내 에이전트 목록 표시, fetchMyAgents 호출 |
| `app/(user)/debate/page.tsx` | 큐 등록 시 에이전트 선택 목록 표시 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-02-26 | `use_platform_credits` 필드 추가 (플랫폼 크레딧 에이전트 기능) |
