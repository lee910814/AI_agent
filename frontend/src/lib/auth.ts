/**
 * 인증 관련 API 호출 함수. 로그인, 회원가입, 아이디/닉네임 중복 확인, 성인인증 요청.
 */
import { api } from './api';

type LoginResponse = {
  access_token: string;
  token_type: string;
};

/** 로그인 → JWT 토큰 반환. */
export async function login(loginId: string, password: string): Promise<LoginResponse> {
  return api.post<LoginResponse>('/auth/login', { login_id: loginId, password });
}

/** 회원가입 → 자동 로그인 (JWT 토큰 반환). */
export async function register(
  loginId: string,
  nickname: string,
  password: string,
  email?: string,
): Promise<LoginResponse> {
  return api.post<LoginResponse>('/auth/register', {
    login_id: loginId,
    nickname,
    password,
    email: email || null,
  });
}

/** 아이디 중복 확인. 사용 가능하면 true. */
export async function checkLoginId(loginId: string): Promise<boolean> {
  const res = await api.get<{ available: boolean }>(
    `/auth/check-login-id?login_id=${encodeURIComponent(loginId)}`,
  );
  return res.available;
}

/** 닉네임 중복 확인. 사용 가능하면 true. */
export async function checkNickname(nickname: string): Promise<boolean> {
  const res = await api.get<{ available: boolean }>(
    `/auth/check-nickname?nickname=${encodeURIComponent(nickname)}`,
  );
  return res.available;
}

/** 성인인증 요청 (본인확인 방법 전달). */
export async function requestAdultVerification(method: string): Promise<void> {
  await api.post('/auth/adult-verify', { method });
}
