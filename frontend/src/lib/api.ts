/**
 * API 클라이언트. 모든 백엔드 요청은 이 모듈을 통해 수행한다.
 * - 자동으로 JWT 토큰을 Authorization 헤더에 첨부
 * - 에러 응답을 ApiError로 변환
 */
const BASE_URL = '/api';

/** 백엔드 에러 응답을 표현하는 커스텀 에러. status, code, message, body를 포함. */
class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public body: unknown = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** 공통 fetch 래퍼. HttpOnly 쿠키로 자동 인증 + 에러 변환. */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    // 쿠키를 자동으로 포함 (HttpOnly 쿠키 기반 인증)
    credentials: 'include',
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    // 401 → 세션 만료. 로그인 페이지가 아닌 경우에만 이동 (무한 루프 방지)
    if (
      response.status === 401 &&
      typeof window !== 'undefined' &&
      window.location.pathname !== '/login'
    ) {
      // 다른 기기 로그인으로 세션이 교체된 경우 사유를 저장해 로그인 페이지에서 표시
      if (response.headers.get('X-Error-Code') === 'AUTH_SESSION_REPLACED') {
        sessionStorage.setItem('auth_redirect_reason', 'session_replaced');
      }
      window.location.href = '/login';
    }
    throw new ApiError(
      response.status,
      body.error_code ?? 'UNKNOWN_ERROR',
      body.detail ?? 'An error occurred',
      body,
    );
  }

  // 204 No Content 등 본문이 없는 응답 처리
  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }

  return response.json();
}

type RequestOptions = { signal?: AbortSignal };

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { signal: options?.signal }),
  post: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
      signal: options?.signal,
    }),
  put: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
      signal: options?.signal,
    }),
  patch: <T>(path: string, data?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
      signal: options?.signal,
    }),
  delete: <T>(path: string, options?: RequestOptions) =>
    request<T>(path, { method: 'DELETE', signal: options?.signal }),
  upload: <T>(path: string, file: File, fieldName = 'file') => {
    const formData = new FormData();
    formData.append(fieldName, file);
    return request<T>(path, { method: 'POST', body: formData });
  },
};

export { ApiError };

// ── 쿼리 스트링 빌더 ─────────────────────────────────────────────────────────
/** 객체를 URL 쿼리 스트링으로 변환. undefined 값은 제외. */
function buildQuery(params?: Record<string, string | number | boolean | undefined>): string {
  if (!params) return '';
  const entries = Object.entries(params).filter(([, v]) => v !== undefined);
  if (entries.length === 0) return '';
  return (
    '?' +
    entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&')
  );
}

// ── Follow API ────────────────────────────────────────────────────────────────
export type FollowResponse = {
  id: string;
  target_type: 'user' | 'agent';
  target_id: string;
  target_name: string;
  target_image_url: string | null;
  created_at: string;
};

export type FollowListResponse = {
  items: FollowResponse[];
  total: number;
};

export const followTarget = (targetType: 'user' | 'agent', targetId: string) =>
  api.post<FollowResponse>('/follows', { target_type: targetType, target_id: targetId });

export const unfollowTarget = (targetType: 'user' | 'agent', targetId: string) =>
  api.delete<void>(`/follows/${targetType}/${targetId}`);

export const getFollowing = (params?: { target_type?: string; offset?: number; limit?: number }) =>
  api.get<FollowListResponse>(`/follows/following${buildQuery(params)}`);

// ── Notification API ──────────────────────────────────────────────────────────
export type NotificationResponse = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
};

export type NotificationListResponse = {
  items: NotificationResponse[];
  total: number;
  unread_count: number;
};

export const getNotifications = (params?: {
  offset?: number;
  limit?: number;
  unread_only?: boolean;
}) => api.get<NotificationListResponse>(`/notifications${buildQuery(params)}`);

export const getUnreadCount = () => api.get<{ count: number }>('/notifications/unread-count');

export const markNotificationRead = (id: string) => api.put<void>(`/notifications/${id}/read`, {});

export const markAllNotificationsRead = () => api.put<void>('/notifications/read-all', {});

// ── Community API ──────────────────────────────────────────────────────────────
export type CommunityPostResponse = {
  id: string;
  agent_id: string;
  agent_name: string;
  agent_image_url: string | null;
  agent_tier: string | null;
  agent_model: string | null;
  content: string;
  match_id: string | null;
  match_result: {
    result: 'win' | 'lose' | 'draw';
    score_mine: number;
    score_opp: number;
    elo_before: number;
    elo_after: number;
    elo_delta: number;
    opponent_name: string;
    topic: string;
  } | null;
  likes_count: number;
  dislikes_count: number;
  is_liked: boolean;
  is_disliked: boolean;
  created_at: string;
};

export type CommunityFeedResponse = {
  items: CommunityPostResponse[];
  total: number;
  has_more: boolean;
};

export type LikeToggleResponse = {
  liked: boolean;
  likes_count: number;
};

export const fetchCommunityFeed = (params?: {
  tab?: 'all' | 'following';
  offset?: number;
  limit?: number;
}) => api.get<CommunityFeedResponse>(`/community/feed${buildQuery(params)}`);

export const toggleCommunityLike = (postId: string) =>
  api.post<LikeToggleResponse>(`/community/${postId}/like`);

export type DislikeToggleResponse = { disliked: boolean; dislikes_count: number };
export const toggleCommunityDislike = (postId: string) =>
  api.post<DislikeToggleResponse>(`/community/${postId}/dislike`);

export type HotTopicItem = {
  id: string;
  title: string;
  match_count: number;
};

export type MyCommunityStatsResponse = {
  tier: string;
  total_score: number;
  likes_given: number;
  follows_given: number;
  next_tier: string | null;
  next_tier_score: number | null;
};

export const fetchHotTopics = () => api.get<HotTopicItem[]>('/community/hot-topics');

export const fetchMyCommunityStats = () => api.get<MyCommunityStatsResponse>('/community/my-stats');
