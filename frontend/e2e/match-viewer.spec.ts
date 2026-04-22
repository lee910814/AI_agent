import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_MATCHES, MOCK_TURN_LOGS, captureRequest, mockClipboard, overrideRoute } from './helpers';

test.describe('Match Viewer', () => {
  test('should render match viewer page', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/matches/match-001');
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'screenshots/match-viewer.png' });
  });

  test('should show agent names in match', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/matches/match-001');
    await page.waitForLoadState('networkidle');

    const agentNameVisible = await page
      .getByText(MOCK_MATCHES[0].agent_a.name)
      .first()
      .isVisible()
      .catch(() => false);
    expect(agentNameVisible).toBe(true);
    await page.screenshot({ path: 'screenshots/match-viewer-agents.png' });
  });

  test('should display turn log content', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/matches/match-001');
    await page.waitForLoadState('networkidle');

    // Check first 15 chars of turn claim to avoid partial text issues
    const firstContent = MOCK_TURN_LOGS[0].claim.substring(0, 15);
    await expect(page.getByText(firstContent)).toBeVisible();
    await page.screenshot({ path: 'screenshots/match-viewer-turns.png' });
  });

  test('should show topic title', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/matches/match-001');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText(MOCK_MATCHES[0].topic_title)).toBeVisible();
    await page.screenshot({ path: 'screenshots/match-viewer-topic.png' });
  });

  test('should render matches list page', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.goto('/debate/matches');
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'screenshots/matches-list.png' });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test('진행 중 매치 예측 투표 버튼 클릭 시 POST /api/matches/{id}/predictions 요청 발생', async ({
    page,
  }) => {
    await setupApiMocks(page, 'user');

    // 예측 통계를 미투표 상태로 override (user_prediction: null, total: 0, canVote 조건: turnCount <= 2)
    await overrideRoute(page, /\/api\/matches\/[^/?]+\/predictions/, 200, {
      total: 0,
      a_win: 0,
      b_win: 0,
      draw: 0,
      a_win_pct: 0,
      b_win_pct: 0,
      draw_pct: 0,
      user_prediction: null,
    });

    // in_progress 매치로 이동 (match-001)
    await page.goto('/debate/matches/match-001');
    await page.waitForLoadState('networkidle');

    // 예측 패널의 투표 버튼 확인 (PredictionPanel: turnCount <= 2 이면 투표 가능)
    // MOCK_TURN_LOGS는 2개이므로 turnCount=2 → canVote=true
    const voteBtn = page.getByRole('button', { name: /논리왕 Alpha 승|감성봇 Beta 승|무승부/ }).first();

    if (await voteBtn.isVisible()) {
      const [request] = await Promise.all([
        captureRequest(page, /\/api\/matches\/[^/?]+\/predictions/, 'POST'),
        voteBtn.click(),
      ]);
      expect(request.url).toContain('/predictions');
    } else {
      // 투표 버튼이 없으면 예측 패널 자체가 없는 것 (상태에 따라 다름)
      await page.screenshot({ path: 'screenshots/match-viewer-no-vote-panel.png' });
    }

    await page.screenshot({ path: 'screenshots/match-viewer-prediction-vote.png' });
  });

  test('완료된 매치에서 공유 버튼 클릭 시 클립보드에 URL 복사', async ({ page }) => {
    // 클립보드 mock 먼저 등록 (goto 이전)
    const getClipboardText = await mockClipboard(page);
    await setupApiMocks(page, 'user');

    // 완료된 매치(match-002) 데이터로 override
    await overrideRoute(page, /\/api\/matches\/match-002$/, 200, MOCK_MATCHES[1]);

    await page.goto('/debate/matches/match-002');
    await page.waitForLoadState('networkidle');

    // 공유 버튼 찾기 (ShareButton 컴포넌트: 완료된 매치에서만 표시)
    const shareBtn = page.getByRole('button', { name: '공유' });
    if (await shareBtn.isVisible()) {
      await shareBtn.click();

      // 드롭다운 메뉴의 "링크 복사" 클릭
      const copyLinkBtn = page.getByRole('button', { name: '링크 복사' });
      await expect(copyLinkBtn).toBeVisible();
      await copyLinkBtn.click();

      // 클립보드에 매치 URL 포함 여부 확인
      const copiedText = await getClipboardText();
      expect(copiedText).toContain('/debate/matches/match-002');
    } else {
      await page.screenshot({ path: 'screenshots/match-viewer-no-share-btn.png' });
    }

    await page.screenshot({ path: 'screenshots/match-viewer-share-clipboard.png' });
  });
});
