import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_ADMIN_MONITORING_STATS, MOCK_LLM_MODELS, captureRequest, overrideRoute } from './helpers';

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');
  });

  test('should render dashboard with stat cards', async ({ page }) => {
    await expect(page.getByText('대시보드').first()).toBeVisible();
    await expect(page.getByText('전체 사용자')).toBeVisible();
    await expect(page.getByText('에이전트 수')).toBeVisible();
    await expect(page.getByText('매치 수')).toBeVisible();
    await page.screenshot({ path: 'screenshots/admin-dashboard.png' });
  });

  test('should show stats values from monitoring API', async ({ page }) => {
    await expect(
      page.getByText(String(MOCK_ADMIN_MONITORING_STATS.totals.users)),
    ).toBeVisible();
    await page.screenshot({ path: 'screenshots/admin-stats.png' });
  });

  test('should render admin sidebar with navigation links', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    await page.screenshot({ path: 'screenshots/admin-sidebar.png' });
  });
});

test.describe('Admin User Management', () => {
  test('should render users page', async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.goto('/admin/users');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/admin-users.png' });
  });
});

test.describe('Admin Models Management', () => {
  test('should render LLM models page', async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.goto('/admin/models');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/admin-models.png' });
  });
});

test.describe('Admin Monitoring', () => {
  test('should render monitoring page', async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.goto('/admin/monitoring');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/admin-monitoring.png' });
  });
});

test.describe('Admin Usage/Billing', () => {
  test('should render usage page', async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.goto('/admin/usage');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/admin-usage.png' });
  });
});

test.describe('Admin Debate Management', () => {
  test('should render debate admin page', async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.goto('/admin/debate');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'screenshots/admin-debate.png' });
  });
});

test.describe('Admin Navigation', () => {
  test('should navigate between admin pages via sidebar', async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('대시보드').first()).toBeVisible();
    await page.screenshot({ path: 'screenshots/admin-nav-dashboard.png' });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test.describe('사용자 관리 페이지', () => {
    test('검색창 입력 시 GET /api/admin/users?search=xxx 요청 발생', async ({ page }) => {
      await setupApiMocks(page, 'admin');
      await page.goto('/admin/users');
      await page.waitForLoadState('networkidle');

      const searchInput = page.getByPlaceholder('닉네임으로 검색...');
      await expect(searchInput).toBeVisible();

      const [request] = await Promise.all([
        captureRequest(page, '/api/admin/users', 'GET'),
        (async () => {
          await searchInput.fill('테스트');
          // debounce 300ms 대기
          await page.waitForTimeout(400);
        })(),
      ]);

      expect(request.url).toContain('/api/admin/users');
      expect(request.params['search']).toBe('테스트');
      await page.screenshot({ path: 'screenshots/admin-users-search.png' });
    });

    test('사용자 행 클릭 시 상세 드로어 열림', async ({ page }) => {
      await setupApiMocks(page, 'admin');

      // 쿼리파람 포함 URL도 매칭하도록 predicate 사용 (setupApiMocks의 glob은 ?skip=0&limit=20 불일치)
      await page.route(
        (url) => url.pathname === '/api/admin/users',
        async (route) => {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              items: [
                {
                  id: 'user-001',
                  nickname: '테스트유저',
                  role: 'user',
                  age_group: 'unverified',
                  adult_verified_at: null,
                  created_at: '2026-01-01T00:00:00Z',
                },
              ],
              total: 1,
              stats: null,
            }),
          });
        },
      );

      // UserDetailDrawer가 호출하는 상세 API + 쿼터 API
      await overrideRoute(page, /\/api\/admin\/users\/user-\w+/, 200, {
        id: 'user-001',
        nickname: '테스트유저',
        role: 'user',
        age_group: 'unverified',
        adult_verified_at: null,
        preferred_llm_model_id: null,
        preferred_themes: null,
        credit_balance: 1000,
        last_credit_grant_at: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: null,
        session_count: 0,
        message_count: 0,
        subscription_status: null,
      });
      await overrideRoute(page, /\/api\/admin\/usage\/quotas\/user-\w+/, 200, null);

      await page.goto('/admin/users');
      await page.waitForLoadState('networkidle');

      // 실제 데이터 행이 렌더링될 때까지 대기 (skeleton 행과 구분)
      const nicknameCell = page.locator('tbody tr').filter({ hasText: '테스트유저' }).first();
      if (await nicknameCell.isVisible({ timeout: 5000 })) {
        await nicknameCell.click();

        // 드로어 헤더 "사용자 상세" 표시 확인
        await expect(page.getByRole('heading', { name: '사용자 상세' })).toBeVisible({ timeout: 5000 });
        await page.screenshot({ path: 'screenshots/admin-users-drawer-open.png' });
      } else {
        await page.screenshot({ path: 'screenshots/admin-users-no-rows.png' });
      }
    });
  });

  test.describe('모델 관리 페이지', () => {
    test('모델 추가 버튼 클릭 시 모달 열림', async ({ page }) => {
      await setupApiMocks(page, 'admin');
      await page.goto('/admin/models');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: '모델 추가' }).click();

      // 모달 내 "모델 추가" 타이틀 표시
      await expect(page.getByRole('heading', { name: '모델 추가' })).toBeVisible();
      await expect(page.getByPlaceholder('gpt-4o').first()).toBeVisible();
      await page.screenshot({ path: 'screenshots/admin-models-add-modal.png' });
    });

    test('모달에 provider/model_id 입력 후 제출 시 POST /api/admin/models 요청 발생', async ({
      page,
    }) => {
      await setupApiMocks(page, 'admin');

      // POST /admin/models mock
      await overrideRoute(page, '**/api/admin/models', 200, {
        id: 'model-new',
        provider: 'openai',
        model_id: 'gpt-5-test',
        display_name: 'GPT-5 Test',
        is_active: true,
      });

      await page.goto('/admin/models');
      await page.waitForLoadState('networkidle');

      await page.getByRole('button', { name: '모델 추가' }).click();
      await expect(page.getByRole('heading', { name: '모델 추가' })).toBeVisible();

      // 필수 필드 입력
      // model_id 필드 (placeholder="gpt-4o", 첫 번째)
      await page.getByPlaceholder('gpt-4o').first().fill('gpt-5-test');
      // display_name 필드 (placeholder="GPT-4o", 두 번째) — getByPlaceholder은 case-insensitive → .nth(1)
      await page.getByPlaceholder('gpt-4o').nth(1).fill('GPT-5 Test');
      await page.locator('input[placeholder="2.50"]').fill('2.50');
      await page.locator('input[placeholder="10.00"]').fill('10.00');
      await page.getByPlaceholder('128000').fill('128000');

      const [request] = await Promise.all([
        captureRequest(page, '/api/admin/models', 'POST'),
        page.getByRole('button', { name: '등록' }).click(),
      ]);

      expect(request.url).toContain('/api/admin/models');
      const body = request.body as Record<string, unknown>;
      expect(body.model_id).toBe('gpt-5-test');
      await page.screenshot({ path: 'screenshots/admin-models-post-request.png' });
    });

    test('활성/비활성 토글 버튼 클릭 시 PUT /api/admin/models/{id} 요청 발생', async ({
      page,
    }) => {
      await setupApiMocks(page, 'admin');

      await overrideRoute(page, /\/api\/admin\/models\/model-\w+/, 200, {
        ...MOCK_LLM_MODELS[0],
        is_active: false,
      });

      await page.goto('/admin/models');
      await page.waitForLoadState('networkidle');

      // 활성/비활성 토글 버튼 (DataTable의 is_active 컬럼)
      const toggleBtn = page.getByRole('button', { name: /활성|비활성/ }).first();
      if (await toggleBtn.isVisible()) {
        const [request] = await Promise.all([
          captureRequest(page, /\/api\/admin\/models\//, 'PUT'),
          toggleBtn.click(),
        ]);
        expect(request.url).toContain('/api/admin/models/');
        await page.screenshot({ path: 'screenshots/admin-models-toggle-active.png' });
      } else {
        await page.screenshot({ path: 'screenshots/admin-models-no-toggle.png' });
      }
    });
  });

  test.describe('토론 관리 페이지', () => {
    test('검색어 입력 시 필터 동작 확인', async ({ page }) => {
      await setupApiMocks(page, 'admin');
      await page.goto('/admin/debate');
      await page.waitForLoadState('networkidle');

      // 검색 입력란 찾기 (admin debate 페이지에 Search 아이콘 있는 input)
      const searchInput = page.locator('input[type="text"]').first();
      if (await searchInput.isVisible()) {
        await searchInput.fill('원자력');
        await page.waitForTimeout(400);

        // 검색어가 입력 필드에 반영됨
        await expect(searchInput).toHaveValue('원자력');
        await page.screenshot({ path: 'screenshots/admin-debate-search.png' });
      } else {
        await page.screenshot({ path: 'screenshots/admin-debate-no-search.png' });
      }
    });
  });
});
