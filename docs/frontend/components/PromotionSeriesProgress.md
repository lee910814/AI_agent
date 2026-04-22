# PromotionSeriesProgress

> 승급전/강등전 시리즈의 현재 진행 상태를 원형 슬롯으로 시각화하는 컴포넌트

**파일 경로:** `frontend/src/components/debate/PromotionSeriesProgress.tsx`
**최종 수정일:** 2026-03-24

---

## Props

| Prop | 타입 | 필수 | 설명 |
|---|---|---|---|
| `series` | `PromotionSeries` | 필수 | 승급전/강등전 시리즈 데이터 |

---

## PromotionSeries 타입 (주요 필드)

| 필드 | 타입 | 설명 |
|---|---|---|
| `series_type` | `'promotion' \| 'demotion'` | 시리즈 종류 |
| `from_tier` | `string` | 현재 티어 |
| `to_tier` | `string` | 목표 티어 |
| `current_wins` | `number` | 현재 승리 수 |
| `current_losses` | `number` | 현재 패배 수 |
| `status` | `'in_progress' \| 'won' \| 'lost' \| 'expired'` | 시리즈 상태 |

---

## 주요 기능

### 슬롯 구성

- **승급전** (`series_type === 'promotion'`): 3슬롯 (3판 2선승제)
- **강등전** (`series_type === 'demotion'`): 1슬롯 (1판 필승)

각 슬롯은 `current_wins`와 `current_losses` 기준으로 상태가 결정됩니다.

| 슬롯 상태 | 색상 | 의미 |
|---|---|---|
| `win` | 초록색 채움 | 승리 |
| `loss` | 빨간색 채움 | 패배 |
| `pending` | 회색 테두리만 | 미결 |

### 레이블 및 결과 텍스트

| 조건 | 표시 텍스트 |
|---|---|
| 승급전 진행 중/완료 | `{from_tier} → {to_tier} 승급전` |
| 강등전 진행 중/완료 | `{from_tier} 강등전` |
| `status === 'won'` (승급전) | 승급 성공! (초록) |
| `status === 'won'` (강등전) | 강등전 생존! (초록) |
| `status === 'lost'` (승급전) | 승급 실패 (빨강) |
| `status === 'lost'` (강등전) | 강등 확정 (빨강) |
| `status === 'expired'` | 시리즈 만료 (회색) |

---

## 사용 예시

```tsx
{activeSeries && (
  <PromotionSeriesProgress series={activeSeries} />
)}
```

---

## 변경 이력

| 날짜 | 변경 내용 |
|---|---|
| 2026-03-24 | 신규 문서 작성 |
| 2026-03-03 | 신규 생성 (승급전/강등전 시스템) |
