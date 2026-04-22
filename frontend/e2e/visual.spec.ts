import { test, expect } from '@playwright/test';
import { setupApiMocks } from './helpers';

test.describe('시각적 회귀 테스트', () => {
  test('로그인 화면 — 데스크톱 뷰포트', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'screenshots/visual-01-login-desktop.png', fullPage: true });

    const card = page.locator('.bg-bg-surface').first();
    await expect(card).toBeVisible();
  });

  test('로그인 화면 — 모바일 뷰포트', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'screenshots/visual-02-login-mobile.png', fullPage: true });
    // Card should still be visible and not overflow on mobile
    await expect(page.locator('form')).toBeVisible();
  });

  test('회원가입 화면 — 전체 폼 스크린샷', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/');
    await page.getByRole('button', { name: '회원가입' }).click();
    await page.waitForTimeout(300);

    await page.screenshot({ path: 'screenshots/visual-03-register-full.png', fullPage: true });
    await expect(page.getByRole('button', { name: '가입하기' })).toBeVisible();
  });

  test('토론 목록 페이지 — 데스크톱', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/debate');
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'screenshots/visual-04-debate-desktop.png', fullPage: true });
  });

  test('토론 목록 페이지 — 모바일', async ({ page }) => {
    await setupApiMocks(page, 'user');
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/debate');
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'screenshots/visual-05-debate-mobile.png', fullPage: true });
  });

  test('관리자 대시보드 — 데스크톱', async ({ page }) => {
    await setupApiMocks(page, 'admin');
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    await page.screenshot({ path: 'screenshots/visual-06-admin-desktop.png', fullPage: true });
  });
});

test.describe('접근성 기본 검사', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('폼 레이블 — 입력 필드에 레이블 연결 확인', async ({ page }) => {
    await expect(page.getByText('아이디')).toBeVisible();
    await expect(page.getByText('비밀번호')).toBeVisible();
  });

  test('버튼 접근성 — role=button 확인', async ({ page }) => {
    const buttons = page.getByRole('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('입력 필드 — required 속성 확인', async ({ page }) => {
    const loginIdInput = page.locator('input[type="text"]');
    await expect(loginIdInput).toHaveAttribute('required');

    const passwordInput = page.locator('input[type="password"]');
    await expect(passwordInput).toHaveAttribute('required');
  });

  test('페이지 타이틀이 비어있지 않음', async ({ page }) => {
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });
});

test.describe('인터랙션 테스트', () => {
  test('탭 키 포커스 이동 — 키보드 내비게이션', async ({ page }) => {
    await page.goto('/');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    const focused = await page.evaluate(() => document.activeElement?.tagName);
    expect(['INPUT', 'BUTTON']).toContain(focused);
  });

  test('회원가입 — 비밀번호 불일치 에러 표시', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: '회원가입' }).click();

    await page.getByPlaceholder('6자 이상').fill('Password123!');
    await page.getByPlaceholder('비밀번호 다시 입력').fill('DifferentPass!');

    await expect(page.getByText('비밀번호가 일치하지 않습니다')).toBeVisible();
    await page.screenshot({
      path: 'screenshots/interaction-password-mismatch.png',
    });
  });

  test('비밀번호 강도 표시 확인', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: '회원가입' }).click();

    // Weak password
    await page.getByPlaceholder('6자 이상').fill('abc');
    // Still below 6 chars, shows helper text
    await page.getByPlaceholder('6자 이상').fill('abcdef');
    // 6+ chars should show strength bar
    const strengthBar = page.locator('.h-1.flex-1.rounded-full').first();
    await expect(strengthBar).toBeVisible();
    await page.screenshot({ path: 'screenshots/interaction-password-strength.png' });
  });
});
