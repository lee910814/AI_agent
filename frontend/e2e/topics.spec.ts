import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_TOPICS, MOCK_AGENTS, captureRequest, overrideRoute } from './helpers';

/**
 * /debate/topics/[id] 페이지 기능 테스트.
 * topic.status === 'open' 이고 agents.length > 0 일 때 참가 폼이 표시됨.
 */
test.describe('Topic Detail Page', () => {
  test('토픽 제목과 기본 정보 렌더링', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/topics/topic-001');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(MOCK_TOPICS[0].title)).toBeVisible();
    await page.screenshot({ path: 'screenshots/topic-detail-basic.png' });
  });

  test('에이전트 목록이 있을 때 참가 드롭다운 표시', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/topics/topic-001');
    await page.waitForLoadState('networkidle');

    // topic.status=open, agents.length>0 → 참가 폼 표시
    await expect(page.getByText('토론 참가')).toBeVisible();

    const agentSelect = page.locator('select').first();
    await expect(agentSelect).toBeVisible();
    await page.screenshot({ path: 'screenshots/topic-detail-join-form.png' });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test('에이전트 선택 드롭다운에 내 에이전트 목록 표시', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/topics/topic-001');
    await page.waitForLoadState('networkidle');

    const agentSelect = page.locator('select').first();
    await expect(agentSelect).toBeVisible();

    // 에이전트 이름이 옵션으로 포함되어야 함
    await expect(agentSelect).toContainText(MOCK_AGENTS[0].name);
    await expect(agentSelect).toContainText(MOCK_AGENTS[1].name);
    await page.screenshot({ path: 'screenshots/topic-detail-agent-options.png' });
  });

  test('에이전트 선택 후 참가 버튼 클릭 시 POST /api/topics/{id}/queue 요청 발생', async ({
    page,
  }) => {
    await setupApiMocks(page, 'user');

    // queue status: not_in_queue
    await overrideRoute(
      page,
      /\/api\/topics\/[^/?]+\/queue\/status/,
      200,
      { status: 'not_in_queue' },
    );

    // join queue mock — 실제 API는 /topics/{id}/join 엔드포인트 호출
    await overrideRoute(
      page,
      /\/api\/topics\/[^/?]+\/join$/,
      200,
      { status: 'queued', match_id: null },
    );

    await page.goto('/debate/topics/topic-001');
    await page.waitForLoadState('networkidle');

    const agentSelect = page.locator('select').first();
    await agentSelect.selectOption(MOCK_AGENTS[0].id);

    // queue status 조회 완료 대기
    await page.waitForTimeout(500);

    const joinBtn = page.locator('button').filter({ hasText: '참가' }).first();
    await expect(joinBtn).toBeVisible();

    const [request] = await Promise.all([
      captureRequest(page, /\/api\/topics\/[^/?]+\/join/, 'POST'),
      joinBtn.click(),
    ]);

    expect(request.url).toContain('/join');
    await page.screenshot({ path: 'screenshots/topic-detail-join-request.png' });
  });

  test('409 응답 시 충돌 UI(기존 대기 취소 후 참가 버튼) 표시', async ({ page }) => {
    await setupApiMocks(page, 'user');

    // queue status 정상
    await overrideRoute(
      page,
      /\/api\/topics\/[^/?]+\/queue\/status/,
      200,
      { status: 'not_in_queue' },
    );

    // join → 409 충돌 반환 — 실제 API는 /topics/{id}/join 엔드포인트 호출
    await overrideRoute(
      page,
      /\/api\/topics\/[^/?]+\/join$/,
      409,
      {
        detail: '이미 다른 토픽에 대기 중입니다',
        message: '이미 다른 토픽에 대기 중입니다',
        existing_topic_id: 'topic-002',
      },
    );

    // 기존 토픽 제목 조회 mock
    await overrideRoute(page, '**/api/topics/topic-002', 200, {
      ...MOCK_TOPICS[1],
      id: 'topic-002',
    });

    await page.goto('/debate/topics/topic-001');
    await page.waitForLoadState('networkidle');

    const agentSelect = page.locator('select').first();
    await agentSelect.selectOption(MOCK_AGENTS[0].id);
    await page.waitForTimeout(300);

    const joinBtn = page.locator('button').filter({ hasText: '참가' }).first();
    await joinBtn.click();

    // 충돌 UI: "기존 대기 취소 후 참가" 버튼 표시 (ApiError 409 처리)
    await expect(
      page.locator('button').filter({ hasText: '기존 대기 취소 후 참가' }),
    ).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: 'screenshots/topic-detail-409-conflict-ui.png' });
  });

  test('이미 대기 중인 에이전트 선택 시 경고 메시지 표시', async ({ page }) => {
    await setupApiMocks(page, 'user');

    // 에이전트가 이미 다른 토픽 대기 중
    await overrideRoute(
      page,
      /\/api\/topics\/[^/?]+\/queue\/status/,
      200,
      { status: 'queued', joined_at: '2026-03-09T10:00:00Z' },
    );

    await page.goto('/debate/topics/topic-001');
    await page.waitForLoadState('networkidle');

    const agentSelect = page.locator('select').first();
    await agentSelect.selectOption(MOCK_AGENTS[0].id);

    // 상태 조회 완료 대기
    await page.waitForTimeout(500);

    await expect(
      page.getByText(/다른 토픽 대기 중|기존 대기가 취소/),
    ).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: 'screenshots/topic-detail-already-queued.png' });
  });
});
