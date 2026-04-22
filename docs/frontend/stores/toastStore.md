# toastStore

> 최대 3개 토스트 알림을 4초 자동 제거로 관리하는 Zustand 스토어

**파일 경로:** `frontend/src/stores/toastStore.ts`
**최종 수정일:** 2026-03-24

---

## 상태 (State)

| 필드 | 타입 | 초기값 | 설명 |
|---|---|---|---|
| `toasts` | `Toast[]` | `[]` | 현재 표시 중인 토스트 목록 (최대 3개) |

### Toast 타입

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | `string` | UUID 또는 fallback ID (`Date.now()-random`) |
| `type` | `'success' \| 'error' \| 'info'` | 토스트 유형 |
| `message` | `string` | 표시할 메시지 |

---

## 액션 (Actions)

| 액션명 | 파라미터 | 설명 |
|---|---|---|
| `addToast` | `type: ToastType, message: string` | 토스트 추가. 최신 3개만 유지 (`toasts.slice(-2)`에 신규 추가). 4초 후 자동 제거 |
| `removeToast` | `id: string` | 특정 토스트 즉시 제거 |

---

## 컴포넌트 외부 사용 — toast 헬퍼

스토어 직접 접근 없이 어디서든 토스트를 띄울 수 있는 편의 객체가 export됩니다.

```typescript
import { toast } from '@/stores/toastStore';

toast.success('저장되었습니다.');
toast.error('오류가 발생했습니다.');
toast.info('업데이트가 있습니다.');
```

---

## 주요 사용처

| 파일 | 사용 목적 |
|---|---|
| `components/ui/ToastContainer.tsx` | toasts 배열 구독 및 렌더링 |
| API 에러 핸들러, 폼 제출 콜백 등 | `toast.success()` / `toast.error()` 직접 호출 |

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
