import { Page, Route } from '@playwright/test';

// -- Mock Data --------------------------------------------------------------

export const MOCK_TOKEN = 'mock-jwt-token-for-testing';

export const MOCK_USER = {
  id: 'user-001',
  login_id: 'testuser',
  nickname: '테스트유저',
  role: 'user' as const,
  age_group: 'adult',
  adult_verified_at: null,
  preferred_llm_model_id: null,
  credit_balance: 1000,
  subscription_plan_key: null,
};

export const MOCK_ADMIN_USER = {
  id: 'admin-001',
  login_id: 'admin',
  nickname: '관리자',
  role: 'superadmin' as const,
  age_group: 'adult',
  adult_verified_at: '2026-01-01T00:00:00Z',
  preferred_llm_model_id: null,
  credit_balance: 9999,
  subscription_plan_key: null,
};

export const MOCK_AGENTS = [
  {
    id: 'agent-001',
    name: '논리왕 Alpha',
    description: '논리적 추론을 기반으로 토론하는 에이전트',
    provider: 'openai',
    model_name: 'gpt-4.1',
    elo_rating: 1250,
    wins: 15,
    losses: 5,
    draws: 2,
    tier: 'gold',
    is_profile_public: true,
    is_active: true,
    is_connected: false,
    owner_id: 'user-001',
    owner_nickname: '테스트유저',
    image_url: null,
    use_platform_credits: false,
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'agent-002',
    name: '감성봇 Beta',
    description: '감성적 호소로 청중을 설득하는 에이전트',
    provider: 'anthropic',
    model_name: 'claude-sonnet-4-6',
    elo_rating: 1100,
    wins: 8,
    losses: 10,
    draws: 1,
    tier: 'silver',
    is_profile_public: true,
    is_active: true,
    is_connected: false,
    owner_id: 'user-001',
    owner_nickname: '테스트유저',
    image_url: null,
    use_platform_credits: false,
    created_at: '2026-01-02T00:00:00Z',
  },
];

export const MOCK_LOCAL_AGENT = {
  id: 'agent-local-1',
  name: 'My Local Agent',
  description: 'Test local agent',
  provider: 'local',
  model_name: 'custom',
  elo_rating: 1500,
  wins: 0,
  losses: 0,
  draws: 0,
  tier: 'iron',
  is_profile_public: true,
  is_active: true,
  is_connected: false,
  owner_id: 'user-001',
  owner_nickname: 'devuser',
  image_url: null,
  use_platform_credits: false,
  created_at: '2026-01-01T00:00:00Z',
};

export const MOCK_TOPICS = [
  {
    id: 'topic-001',
    title: '원자력 발전은 친환경 에너지인가?',
    description: '핵에너지의 환경적 영향을 토론합니다',
    mode: 'debate',
    status: 'open',
    max_turns: 6,
    turn_token_limit: 500,
    tools_enabled: true,
    creator_id: 'user-001',
    creator_nickname: '테스트유저',
    queue_count: 3,
    match_count: 12,
    scheduled_start_at: null,
    scheduled_end_at: null,
    created_at: '2026-01-10T00:00:00Z',
  },
  {
    id: 'topic-002',
    title: 'AI가 인간의 일자리를 대체할 것인가?',
    description: 'AI 기술 발전과 고용 시장의 변화',
    mode: 'persuasion',
    status: 'in_progress',
    max_turns: 8,
    turn_token_limit: 800,
    tools_enabled: false,
    creator_id: 'user-002',
    creator_nickname: '다른유저',
    queue_count: 1,
    match_count: 5,
    scheduled_start_at: null,
    scheduled_end_at: null,
    created_at: '2026-01-11T00:00:00Z',
  },
];

export const MOCK_MATCHES = [
  {
    id: 'match-001',
    topic_id: 'topic-001',
    topic_title: '원자력 발전은 친환경 에너지인가?',
    status: 'in_progress' as const,
    agent_a: {
      id: 'agent-001',
      name: '논리왕 Alpha',
      provider: 'openai',
      model_id: 'gpt-4.1',
      elo_rating: 1250,
      image_url: null,
    },
    agent_b: {
      id: 'agent-002',
      name: '감성봇 Beta',
      provider: 'anthropic',
      model_id: 'claude-sonnet-4-6',
      elo_rating: 1100,
      image_url: null,
    },
    winner_id: null,
    score_a: 0,
    score_b: 0,
    penalty_a: 0,
    penalty_b: 0,
    is_featured: true,
    match_type: 'ranked' as const,
    series_id: null,
    turn_count: 3,
    started_at: '2026-01-15T10:00:00Z',
    finished_at: null,
    created_at: '2026-01-15T10:00:00Z',
    elo_a_before: null,
    elo_b_before: null,
    elo_a_after: null,
    elo_b_after: null,
    viewers: 5,
  },
  {
    id: 'match-002',
    topic_id: 'topic-002',
    topic_title: 'AI가 인간의 일자리를 대체할 것인가?',
    status: 'completed' as const,
    agent_a: {
      id: 'agent-001',
      name: '논리왕 Alpha',
      provider: 'openai',
      model_id: 'gpt-4.1',
      elo_rating: 1250,
      image_url: null,
    },
    agent_b: {
      id: 'agent-002',
      name: '감성봇 Beta',
      provider: 'anthropic',
      model_id: 'claude-sonnet-4-6',
      elo_rating: 1100,
      image_url: null,
    },
    winner_id: 'agent-001',
    score_a: 75,
    score_b: 60,
    penalty_a: 5,
    penalty_b: 10,
    is_featured: false,
    match_type: 'ranked' as const,
    series_id: null,
    turn_count: 6,
    started_at: '2026-01-14T09:00:00Z',
    finished_at: '2026-01-14T09:30:00Z',
    created_at: '2026-01-14T09:00:00Z',
    elo_a_before: 1230,
    elo_b_before: 1120,
    elo_a_after: 1250,
    elo_b_after: 1100,
    viewers: 0,
  },
];

export const MOCK_TURN_LOGS = [
  {
    id: 'turn-001',
    match_id: 'match-001',
    turn_number: 1,
    speaker: 'agent_a',
    agent_id: 'agent-001',
    action: 'claim',
    claim: '원자력 발전은 탄소 배출이 거의 없어 기후 변화 대응에 효과적인 에너지원입니다.',
    evidence: null,
    tool_used: null,
    tool_result: null,
    penalties: null,
    penalty_total: 0,
    human_suspicion_score: 0,
    response_time_ms: null,
    input_tokens: 100,
    output_tokens: 50,
    review_result: { logic_score: 8, violations: [], feedback: '논리적', blocked: false },
    is_blocked: false,
    created_at: '2026-01-15T10:01:00Z',
  },
  {
    id: 'turn-002',
    match_id: 'match-001',
    turn_number: 2,
    speaker: 'agent_b',
    agent_id: 'agent-002',
    action: 'rebuttal',
    claim: '핵폐기물 처리 문제와 안전 위험을 고려하면 진정한 친환경이라 보기 어렵습니다.',
    evidence: null,
    tool_used: null,
    tool_result: null,
    penalties: null,
    penalty_total: 0,
    human_suspicion_score: 0,
    response_time_ms: null,
    input_tokens: 120,
    output_tokens: 60,
    review_result: { logic_score: 7, violations: [], feedback: '좋음', blocked: false },
    is_blocked: false,
    created_at: '2026-01-15T10:02:00Z',
  },
];

export const MOCK_RANKING = MOCK_AGENTS.map((a, i) => ({ ...a, rank: i + 1 }));

export const MOCK_SEASONS = [
  {
    id: 'season-001',
    season_number: 1,
    title: 'Season 1',
    status: 'active',
    start_at: '2026-01-01T00:00:00Z',
    end_at: '2026-03-31T00:00:00Z',
  },
];

export const MOCK_TOURNAMENTS = [
  {
    id: 'tournament-001',
    name: '3월 챔피언십',
    status: 'in_progress',
    max_participants: 8,
    current_participants: 6,
    created_at: '2026-03-01T00:00:00Z',
  },
];

export const MOCK_LLM_MODELS = [
  {
    id: 'model-001',
    provider: 'openai',
    model_name: 'gpt-4.1',
    display_name: 'GPT-4.1',
    is_active: true,
    input_cost_per_1m: 2.0,
    output_cost_per_1m: 8.0,
    credit_per_1k_tokens: 4,
  },
  {
    id: 'model-002',
    provider: 'anthropic',
    model_name: 'claude-sonnet-4-6',
    display_name: 'Claude Sonnet 4.6',
    is_active: true,
    input_cost_per_1m: 3.0,
    output_cost_per_1m: 15.0,
    credit_per_1k_tokens: 6,
  },
];

export const MOCK_USAGE_ME = {
  total_input_tokens: 125000,
  total_output_tokens: 45000,
  total_cost: 1.23,
  daily_input_tokens: 5000,
  daily_output_tokens: 1800,
  daily_cost: 0.05,
  monthly_input_tokens: 80000,
  monthly_output_tokens: 30000,
  monthly_cost: 0.82,
  by_model: [
    {
      model_name: 'gpt-4.1',
      provider: 'openai',
      tier: 'standard',
      credit_per_1k_tokens: 4,
      input_cost_per_1m: 2.0,
      output_cost_per_1m: 8.0,
      input_tokens: 80000,
      output_tokens: 30000,
      cost: 0.82,
      request_count: 40,
      daily_input_tokens: 3000,
      daily_output_tokens: 1000,
      daily_cost: 0.03,
      daily_request_count: 5,
      monthly_input_tokens: 50000,
      monthly_output_tokens: 20000,
      monthly_cost: 0.5,
      monthly_request_count: 25,
    },
  ],
};

export const MOCK_ADMIN_MONITORING_STATS = {
  totals: { users: 42, agents: 150, matches: 380 },
  weekly: { new_users: 7 },
};

export const MOCK_ADMIN_USERS = [
  {
    id: 'user-001',
    login_id: 'testuser',
    nickname: '테스트유저',
    role: 'user',
    created_at: '2026-01-01T00:00:00Z',
    last_login_at: '2026-03-09T08:00:00Z',
  },
  {
    id: 'admin-001',
    login_id: 'admin',
    nickname: '관리자',
    role: 'superadmin',
    created_at: '2025-12-01T00:00:00Z',
    last_login_at: '2026-03-09T09:00:00Z',
  },
];

// -- Setup Helpers ----------------------------------------------------------

/**
 * 토론 플랫폼 전체 API mock 등록.
 *
 * Playwright route 우선순위: 마지막 등록 route가 가장 높은 우선순위를 가짐.
 * broad(광범위) 패턴을 먼저 등록하고, specific(구체적) 패턴을 나중에 등록한다.
 * 예: broad(agents) 먼저 등록, specific(agents/ranking) 나중 등록
 */
export async function setupApiMocks(page: Page, role: 'user' | 'admin' = 'user') {
  const mockUser = role === 'admin' ? MOCK_ADMIN_USER : MOCK_USER;

  // window.fetch 패치로 /auth/me 요청을 항상 모킹 (page.route보다 확실)
  await page.addInitScript(
    ({ user }) => {
      const realFetch = window.fetch;
      window.fetch = function (url, ...args) {
        const urlStr = typeof url === 'string' ? url : (url as Request)?.url ?? '';
        if (urlStr.includes('/api/auth/me') || urlStr.endsWith('/auth/me')) {
          return Promise.resolve(
            new Response(JSON.stringify(user), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        }
        return realFetch(url, ...args);
      };
    },
    { user: mockUser },
  );

  // -- 1단계: 광범위 catch-all 패턴 (낮은 우선순위) --------------------------

  // Admin catch-all (가장 낮은 우선순위 - 아무것도 매치 안 될 때 fallback)
  await page.route('**/api/admin/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    });
  });

  // Broad agent routes
  await page.route('**/api/agents/**', async (route: Route) => {
    const method = route.request().method();
    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...MOCK_AGENTS[0], id: 'agent-new' }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_AGENTS[0]),
      });
    }
  });

  // Use pathname predicate to match /api/agents with/without query params
  await page.route(
    (url) => url.pathname === '/api/agents',
    async (route: Route) => {
      const method = route.request().method();
      if (method === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ ...MOCK_AGENTS[0], id: 'agent-new' }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ items: MOCK_AGENTS, total: MOCK_AGENTS.length }),
        });
      }
    },
  );

  // Broad match routes
  await page.route('**/api/matches/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_MATCHES[0]),
    });
  });

  await page.route(
    (url) => url.pathname === '/api/matches',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_MATCHES, total: MOCK_MATCHES.length }),
      });
    },
  );

  // Broad usage routes
  await page.route('**/api/usage/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    });
  });

  // Broad topic routes — use pathname predicate to match with/without query params
  await page.route(
    (url) => url.pathname === '/api/topics',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_TOPICS, total: MOCK_TOPICS.length }),
      });
    },
  );

  await page.route('**/api/topics/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_TOPICS[0]),
    });
  });

  // Broad models routes
  await page.route('**/api/models/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_LLM_MODELS[0]),
    });
  });

  await page.route(
    (url) => url.pathname === '/api/models',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_LLM_MODELS, total: MOCK_LLM_MODELS.length }),
      });
    },
  );

  // Broad tournament/season routes
  await page.route('**/api/tournaments/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_TOURNAMENTS[0]),
    });
  });

  await page.route(
    (url) => url.pathname === '/api/tournaments',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_TOURNAMENTS, total: MOCK_TOURNAMENTS.length }),
      });
    },
  );

  await page.route('**/api/seasons/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_SEASONS[0]),
    });
  });

  await page.route(
    (url) => url.pathname === '/api/seasons',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_SEASONS, total: MOCK_SEASONS.length }),
      });
    },
  );

  // Health
  await page.route('**/api/health', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok' }),
    });
  });

  // Uploads
  await page.route('**/api/uploads/**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ url: '/uploads/test.png' }),
    });
  });

  // -- 2단계: 구체적 패턴 (높은 우선순위) ------------------------------------

  // Admin specific routes
  await page.route('**/api/admin/monitoring/stats', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ADMIN_MONITORING_STATS),
    });
  });

  await page.route('**/api/admin/users', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: MOCK_ADMIN_USERS, total: MOCK_ADMIN_USERS.length }),
    });
  });

  await page.route('**/api/admin/models', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: MOCK_LLM_MODELS, total: MOCK_LLM_MODELS.length }),
    });
  });

  await page.route('**/api/admin/usage', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USAGE_ME),
    });
  });

  await page.route('**/api/admin/matches', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: MOCK_MATCHES, total: MOCK_MATCHES.length }),
    });
  });

  await page.route('**/api/admin/agents', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: MOCK_AGENTS, total: MOCK_AGENTS.length }),
    });
  });

  // Agents specific routes
  await page.route('**/api/agents/templates', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/agents/me', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_AGENTS),
    });
  });

  await page.route('**/api/agents/gallery', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: MOCK_AGENTS, total: MOCK_AGENTS.length }),
    });
  });

  // fetchRanking expects RankingEntry[] directly (not wrapped)
  await page.route(
    (url) => url.pathname === '/api/agents/ranking',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_RANKING),
      });
    },
  );

  await page.route('**/api/agents/season/current', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ season: MOCK_SEASONS[0] }),
    });
  });

  // Match specific routes
  await page.route(
    (url) => url.pathname === '/api/matches/featured',
    async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_MATCHES, total: MOCK_MATCHES.length }),
      });
    },
  );

  await page.route(/\/api\/matches\/[^/?]+\/stream/, async (route: Route) => {
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' });
  });

  await page.route(/\/api\/matches\/[^/?]+\/turns/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_TURN_LOGS),
    });
  });

  await page.route(/\/api\/matches\/[^/?]+\/viewers/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ count: 5 }),
    });
  });

  await page.route(/\/api\/matches\/[^/?]+\/predictions/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(null),
    });
  });

  // Usage specific routes
  await page.route('**/api/usage/me', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USAGE_ME),
    });
  });

  // Topics specific routes
  await page.route('**/api/topics/popular', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_TOPICS),
    });
  });

  // -- 3단계: Auth routes (항상 정확하게 동작해야 함) -------------------------

  await page.route('**/api/auth/check-login-id', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ available: true }),
    });
  });

  await page.route('**/api/auth/check-nickname', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ available: true }),
    });
  });

  await page.route('**/api/auth/logout', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'logged out' }),
    });
  });

  await page.route('**/api/auth/register', async (route: Route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: MOCK_TOKEN, token_type: 'bearer' }),
    });
  });

  await page.route('**/api/auth/login', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ access_token: MOCK_TOKEN, token_type: 'bearer' }),
    });
  });

  // /auth/me: 최우선 - 모든 페이지 초기화에 사용됨
  await page.route('**/api/auth/me', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockUser),
    });
  });
}

/**
 * 로그인 폼을 통한 인증 (login 페이지에서만 사용).
 * setupApiMocks 호출 후 사용할 것.
 */
export async function loginViaForm(
  page: Page,
  loginId = 'testuser',
  password = 'password123',
) {
  await page.goto('/');
  await page.fill('input[type="text"]', loginId);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
}

// -- 에러/상태별 Mock 헬퍼 ---------------------------------------------------

/**
 * 특정 엔드포인트가 지정한 HTTP 상태 코드와 바디를 반환하도록 override한다.
 * page.route는 마지막 등록이 우선순위가 높으므로 setupApiMocks 이후에 호출해야 한다.
 */
export async function overrideRoute(
  page: Page,
  urlPattern: string | RegExp,
  status: number,
  body: unknown,
): Promise<void> {
  await page.route(urlPattern, async (route: Route) => {
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

/**
 * POST /api/auth/login이 401을 반환하도록 설정한다.
 * setupApiMocks 없이 단독으로 사용 가능.
 */
export async function setupLoginError(page: Page): Promise<void> {
  await page.route('**/api/auth/login', async (route: Route) => {
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '아이디 또는 비밀번호가 올바르지 않습니다' }),
    });
  });
}

/**
 * navigator.clipboard.writeText를 가로채어 마지막으로 기록된 텍스트를 반환한다.
 * page.goto 이전에 호출해야 initScript가 적용된다.
 * 클립보드에 쓰인 텍스트는 반환된 Promise가 resolve될 때 확인할 수 있다.
 *
 * 사용 예:
 *   const getText = await mockClipboard(page);
 *   await page.click('공유 버튼');
 *   const text = await getText();
 */
export async function mockClipboard(
  page: Page,
): Promise<() => Promise<string>> {
  await page.addInitScript(() => {
    let _written = '';
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: (text: string) => {
          _written = text;
          return Promise.resolve();
        },
        readText: () => Promise.resolve(_written),
      },
      configurable: true,
    });
  });

  return async () => {
    return page.evaluate(() => navigator.clipboard.readText());
  };
}

/**
 * 특정 URL 패턴과 HTTP 메서드에 맞는 첫 번째 요청을 가로채어
 * url, body, query params를 반환한다.
 *
 * Promise.all([captureRequest(...), page.click(...)]) 패턴으로 사용한다.
 */
export async function captureRequest(
  page: Page,
  urlPattern: string | RegExp,
  method: string,
): Promise<{ url: string; body: unknown; params: Record<string, string> }> {
  return new Promise((resolve) => {
    page.on('request', (req) => {
      const urlStr = req.url();
      const methodMatch = req.method().toUpperCase() === method.toUpperCase();
      const urlMatch =
        typeof urlPattern === 'string'
          ? urlStr.includes(urlPattern)
          : urlPattern.test(urlStr);

      if (methodMatch && urlMatch) {
        let body: unknown = null;
        try {
          body = req.postDataJSON();
        } catch {
          // body가 없는 요청 (GET 등)
        }

        const url = new URL(urlStr);
        const params: Record<string, string> = {};
        url.searchParams.forEach((value, key) => {
          params[key] = value;
        });

        resolve({ url: urlStr, body, params });
      }
    });
  });
}
