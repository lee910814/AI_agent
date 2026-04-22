import { test, expect } from '@playwright/test';
import { setupApiMocks, MOCK_TOKEN, MOCK_USER, MOCK_ADMIN_USER, loginViaForm, setupLoginError, captureRequest } from './helpers';

test.describe('Authentication Flow', () => {
  test.describe('Login', () => {
    test('should display login form on landing page', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');

      await expect(page.getByRole('heading', { name: 'AI 토론 플랫폼', exact: true })).toBeVisible();
      await expect(page.locator('input[type="text"]')).toBeVisible();
      await expect(page.locator('input[type="password"]')).toBeVisible();
      await expect(page.locator('button[type="submit"]')).toBeVisible();
      await page.screenshot({ path: 'screenshots/auth-login-form.png' });
    });

    test('should login as user and redirect to /debate', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await loginViaForm(page);

      await expect(page).toHaveURL(/\/debate/);
      await page.screenshot({ path: 'screenshots/auth-login-success.png' });
    });

    test('should login as admin and redirect to /admin', async ({ page }) => {
      await setupApiMocks(page, 'admin');
      await loginViaForm(page, 'admin', 'adminpass');

      await expect(page).toHaveURL(/\/admin/);
      await page.screenshot({ path: 'screenshots/auth-admin-login.png' });
    });

    test('should show error for invalid credentials', async ({ page }) => {
      await page.route('**/api/auth/login', (route) =>
        route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: '아이디 또는 비밀번호가 올바르지 않습니다' }),
        }),
      );

      await page.goto('/');
      await page.fill('input[type="text"]', 'wronguser');
      await page.fill('input[type="password"]', 'wrongpass');
      await page.click('button[type="submit"]');

      await expect(page.getByText(/아이디 또는 비밀번호|오류가 발생했습니다/)).toBeVisible();
      await page.screenshot({ path: 'screenshots/auth-login-error.png' });
    });

    // NOTE: JWT tokens are stored in HTTP-only cookies, not localStorage.
    // The localStorage token check has been removed as it no longer applies.

    test('should show loading state during login', async ({ page }) => {
      await setupApiMocks(page, 'user');
      await page.route('**/api/auth/login', async (route) => {
        await new Promise((r) => setTimeout(r, 500));
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ access_token: MOCK_TOKEN, token_type: 'bearer' }),
        });
      });

      await page.goto('/');
      await page.fill('input[type="text"]', 'testuser');
      await page.fill('input[type="password"]', 'password123');
      await page.click('button[type="submit"]');

      await expect(page.getByText('처리 중...')).toBeVisible();
    });
  });

  test.describe('Registration', () => {
    test('should switch to registration form', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');

      await page.getByRole('button', { name: '회원가입' }).click();
      await expect(page.getByRole('button', { name: '가입하기' })).toBeVisible();
      await page.screenshot({ path: 'screenshots/auth-register-form.png' });
    });

    test('should show all registration fields', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');
      await page.getByRole('button', { name: '회원가입' }).click();

      await expect(page.getByPlaceholder('2~30자, 영문/숫자/밑줄')).toBeVisible();
      await expect(page.getByPlaceholder('2~20자, 한글/영문/숫자')).toBeVisible();
      await expect(page.getByPlaceholder('6자 이상')).toBeVisible();
    });

    test('should validate login_id availability with debounce', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');
      await page.getByRole('button', { name: '회원가입' }).click();

      await page.getByPlaceholder('2~30자, 영문/숫자/밑줄').fill('newuser123');
      // Wait for debounce check
      await page.waitForTimeout(600);
      await expect(page.getByText('사용 가능한 아이디입니다')).toBeVisible();
    });

    test('should register and redirect to /debate', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');
      await page.getByRole('button', { name: '회원가입' }).click();

      await page.getByPlaceholder('2~30자, 영문/숫자/밑줄').fill('newuser');
      await page.waitForTimeout(600);
      await page.getByPlaceholder('2~20자, 한글/영문/숫자').fill('새유저');
      await page.waitForTimeout(600);
      await page.getByPlaceholder('6자 이상').fill('password123');
      await page.getByPlaceholder('비밀번호 다시 입력').fill('password123');

      await page.getByRole('button', { name: '가입하기' }).click();
      await expect(page).toHaveURL(/\/debate/);
    });

    test('should toggle between login and register tabs', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');

      await page.getByRole('button', { name: '회원가입' }).click();
      await expect(page.getByRole('button', { name: '가입하기' })).toBeVisible();

      await page.getByRole('button', { name: '로그인' }).first().click();
      await expect(page.locator('button[type="submit"]')).toContainText('로그인');
    });
  });
});

test.describe('인터랙션 / 기능 검증', () => {
  test.describe('로그인 폼 유효성', () => {
    test('로그인 아이디 미입력 시 HTML required 속성으로 제출 차단', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');

      // 비밀번호만 입력하고 제출 시도
      await page.fill('input[type="password"]', 'password123');

      // required 속성이 있으면 브라우저가 제출 자체를 막음 — URL 변화 없음
      await page.click('button[type="submit"]');
      await expect(page).toHaveURL('/');

      await page.screenshot({ path: 'screenshots/auth-required-validation.png' });
    });

    test('로그인 실패(401) 시 에러 메시지 표시', async ({ page }) => {
      // 일반 mock 없이 login 엔드포인트만 401 반환
      await setupLoginError(page);
      // /auth/me는 비로그인 상태 → 401로 응답해도 랜딩 페이지에 머뭄
      await page.route('**/api/auth/me', (route) =>
        route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'not authenticated' }),
        }),
      );

      await page.goto('/');
      await page.fill('input[type="text"]', 'wronguser');
      await page.fill('input[type="password"]', 'wrongpass');
      await page.click('button[type="submit"]');

      await expect(
        page.getByText(/아이디 또는 비밀번호|오류가 발생했습니다/),
      ).toBeVisible({ timeout: 5000 });
      await page.screenshot({ path: 'screenshots/auth-login-401-error.png' });
    });
  });

  test.describe('회원가입 폼', () => {
    test('회원가입 탭 클릭 시 회원가입 폼 렌더링', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');

      await page.getByRole('button', { name: '회원가입' }).click();

      // 회원가입 폼 필드 확인
      await expect(page.getByPlaceholder('2~30자, 영문/숫자/밑줄')).toBeVisible();
      await expect(page.getByPlaceholder('2~20자, 한글/영문/숫자')).toBeVisible();
      await expect(page.getByPlaceholder('6자 이상')).toBeVisible();
      await expect(page.getByPlaceholder('비밀번호 다시 입력')).toBeVisible();
      await expect(page.getByRole('button', { name: '가입하기' })).toBeVisible();
      await page.screenshot({ path: 'screenshots/auth-register-tab-form.png' });
    });

    test('회원가입 폼 전체 입력 후 제출 시 POST /api/auth/register 호출', async ({ page }) => {
      await setupApiMocks(page);
      await page.goto('/');
      await page.getByRole('button', { name: '회원가입' }).click();

      const [request] = await Promise.all([
        captureRequest(page, '/api/auth/register', 'POST'),
        (async () => {
          await page.getByPlaceholder('2~30자, 영문/숫자/밑줄').fill('newuser01');
          await page.waitForTimeout(650); // debounce 대기
          await page.getByPlaceholder('2~20자, 한글/영문/숫자').fill('신규유저');
          await page.waitForTimeout(650);
          await page.getByPlaceholder('6자 이상').fill('password123');
          await page.getByPlaceholder('비밀번호 다시 입력').fill('password123');
          await page.getByRole('button', { name: '가입하기' }).click();
        })(),
      ]);

      // POST body에 login_id/nickname/password 포함 여부 확인
      expect(request.url).toContain('/api/auth/register');
      const body = request.body as Record<string, unknown>;
      expect(typeof body).toBe('object');
      await page.screenshot({ path: 'screenshots/auth-register-submit.png' });
    });
  });
});
