/**
 * MSW mock handlers — 백엔드 없이 프론트 개발 시 사용.
 * NEXT_PUBLIC_API_MOCK=true 환경변수가 설정된 경우에만 활성화됨.
 */
import { http, HttpResponse } from 'msw';

const MOCK_USER = {
  id: '00000001-0000-0000-0000-000000000003',
  login_id: 'user1',
  nickname: '테스트유저',
  role: 'user' as const,
  age_group: 'adult_verified',
  adult_verified_at: '2025-01-01T00:00:00Z',
  preferred_llm_model_id: null,
  credit_balance: 500,
  subscription_plan_key: null,
};

export const handlers = [
  // 인증
  http.get('/api/auth/me', () => HttpResponse.json(MOCK_USER)),

  http.post('/api/auth/login', () =>
    HttpResponse.json({ access_token: 'mock-token', token_type: 'bearer' }),
  ),

  http.post('/api/auth/register', () =>
    HttpResponse.json({ access_token: 'mock-token', token_type: 'bearer' }),
  ),

  http.post('/api/auth/logout', () => new HttpResponse(null, { status: 204 })),

  http.get('/api/auth/check-login-id', () => HttpResponse.json({ available: true })),

  http.get('/api/auth/check-nickname', () => HttpResponse.json({ available: true })),

  http.post('/api/auth/adult-verify', () => new HttpResponse(null, { status: 204 })),

  // 피처 플래그 — 전체 활성화
  http.get('/api/features', () =>
    HttpResponse.json({
      chat: true,
      community: true,
      character_chats: true,
      character_pages: true,
      debate: true,
      favorites: true,
      relationships: true,
      pending_posts: true,
      mypage: true,
      notifications: true,
    }),
  ),

  // 채팅 세션
  http.get('/api/sessions', () => HttpResponse.json({ items: [], total: 0 })),
  http.post('/api/sessions', () =>
    HttpResponse.json({ id: 'mock-session-1', title: '새 채팅' }, { status: 201 }),
  ),
  http.get('/api/sessions/:id/messages', () => HttpResponse.json({ items: [], total: 0 })),

  // LLM 모델
  http.get('/api/models', () =>
    HttpResponse.json([
      {
        id: 'model-1',
        display_name: 'GPT-4o (Mock)',
        provider: 'openai',
        tier: 'premium',
        is_active: true,
        is_adult_only: false,
      },
    ]),
  ),

  // 사용량
  http.get('/api/usage/me', () =>
    HttpResponse.json({
      today_tokens: 1200,
      month_tokens: 45000,
      today_cost: 0.012,
      month_cost: 0.45,
    }),
  ),

  // 사용자 정보
  http.get('/api/users/me', () => HttpResponse.json(MOCK_USER)),
  http.patch('/api/users/me', () => HttpResponse.json(MOCK_USER)),

  // 알림
  http.get('/api/notifications', () => HttpResponse.json({ items: [], total: 0, unread: 0 })),

  // 커뮤니티
  http.get('/api/boards', () => HttpResponse.json([])),
  http.get('/api/boards/:boardId/posts', () => HttpResponse.json({ items: [], total: 0 })),

  // 로어북
  http.get('/api/lorebook', () => HttpResponse.json({ items: [], total: 0 })),

  // 토론
  http.get('/api/debate/topics', () => HttpResponse.json({ items: [], total: 0 })),
  http.get('/api/debate/agents', () => HttpResponse.json({ items: [], total: 0 })),
  http.get('/api/debate/matches', () => HttpResponse.json({ items: [], total: 0 })),
  http.get('/api/debate/ranking', () => HttpResponse.json({ items: [], total: 0 })),

  // 에이전트
  http.get('/api/agents/me', () => HttpResponse.json([])),
  http.get('/api/agents/templates', () => HttpResponse.json([])),
  http.post('/api/agents', async ({ request }) => {
    const data = await request
      .clone()
      .json()
      .catch(() => ({}));
    return HttpResponse.json(
      { id: 'mock-agent-1', ...(data as object), elo_rating: 1200 },
      { status: 201 },
    );
  }),
  http.put('/api/agents/:id', async ({ request }) => {
    const data = await request
      .clone()
      .json()
      .catch(() => ({}));
    return HttpResponse.json({ id: 'mock-agent-1', ...(data as object), elo_rating: 1200 });
  }),
  http.delete('/api/agents/:id', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/agents/:id/versions', () => HttpResponse.json([])),

  // 캐릭터 페이지
  http.get('/api/character-pages', () => HttpResponse.json({ items: [], total: 0 })),

  // 즐겨찾기
  http.get('/api/favorites', () => HttpResponse.json({ items: [], total: 0 })),

  // 크레딧
  http.get('/api/credits/balance', () => HttpResponse.json({ balance: 500 })),
];
