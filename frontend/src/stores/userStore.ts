/**
 * 사용자 인증/상태 스토어. HttpOnly 쿠키 기반 인증.
 * initialize()로 페이지 로드 시 /auth/me로 사용자 정보 조회 (쿠키 자동 전송).
 */
import { create } from 'zustand';
import { api } from '@/lib/api';

type User = {
  id: string;
  login_id: string;
  nickname: string;
  email: string | null;
  role: 'user' | 'admin' | 'superadmin';
  ageGroup: string;
  adultVerifiedAt: string | null;
  preferredLlmModelId: string | null;
  creditBalance: number;
  subscriptionPlanKey: string | null;
  createdAt: string;
};

type UserState = {
  user: User | null;
  token: string | null; // 하위 호환성 유지 (실제로 사용되지 않음 — 쿠키 기반 인증)
  initialized: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void; // 하위 호환성 유지 (no-op)
  isAdultVerified: () => boolean;
  isAdmin: () => boolean;
  isSuperAdmin: () => boolean;
  logout: () => Promise<void>;
  initialize: () => Promise<void>;
};

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  token: null,
  initialized: false,
  setUser: (user) => set({ user }),
  // SSE Authorization 헤더 전송을 위해 localStorage에도 저장 (쿠키는 POST SSE에서 불안정)
  setToken: (token) => {
    if (typeof window !== 'undefined') {
      if (token) localStorage.setItem('token', token);
      else localStorage.removeItem('token');
    }
    set({ token });
  },
  isAdultVerified: () => get().user?.adultVerifiedAt != null,
  isAdmin: () => ['admin', 'superadmin'].includes(get().user?.role ?? ''),
  isSuperAdmin: () => get().user?.role === 'superadmin',
  logout: async () => {
    try {
      // 서버 측 쿠키 삭제 + 토큰 블랙리스트 등록
      await api.post('/auth/logout');
    } catch {
      // 네트워크 오류 등 무시 — 클라이언트 상태는 항상 초기화
    }
    if (typeof window !== 'undefined') localStorage.removeItem('token');
    set({ user: null, token: null });
  },
  initialize: (() => {
    let pending: Promise<void> | null = null;
    return () => {
      if (get().initialized) return Promise.resolve();
      if (pending) return pending;
      pending = (async () => {
        try {
          // 쿠키가 유효하면 자동으로 인증됨 (credentials: 'include' in api.ts)
          const data = await api.get<{
            id: string;
            login_id: string;
            nickname: string;
            email: string | null;
            role: 'user' | 'admin' | 'superadmin';
            age_group: string;
            adult_verified_at: string | null;
            preferred_llm_model_id: string | null;
            credit_balance?: number;
            subscription_plan_key?: string | null;
            created_at: string;
          }>('/auth/me');
          set({
            user: {
              id: data.id,
              login_id: data.login_id,
              nickname: data.nickname,
              email: data.email ?? null,
              role: data.role,
              ageGroup: data.age_group,
              adultVerifiedAt: data.adult_verified_at,
              preferredLlmModelId: data.preferred_llm_model_id,
              creditBalance: data.credit_balance ?? 0,
              subscriptionPlanKey: data.subscription_plan_key ?? null,
              createdAt: data.created_at,
            },
            initialized: true,
          });
        } catch {
          // 미인증 상태 (쿠키 없음 또는 만료) — 정상적인 비로그인 상태
          set({ user: null, token: null, initialized: true });
        } finally {
          pending = null;
        }
      })();
      return pending;
    };
  })(),
}));
