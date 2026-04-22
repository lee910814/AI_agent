'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Swords, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { login, register, checkNickname, checkLoginId } from '@/lib/auth';
import { useUserStore } from '@/stores/userStore';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

type AuthMode = 'login' | 'register';
type LoginIdStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';
type NicknameStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';

function validateLoginId(value: string): string | null {
  if (value.length < 2) return '2자 이상 입력하세요';
  if (value.length > 30) return '30자 이하로 입력하세요';
  if (!/^[a-zA-Z0-9_]+$/.test(value)) return '영문, 숫자, 밑줄(_)만 가능';
  return null;
}

function validateNickname(value: string): string | null {
  if (value.length < 2) return '2자 이상 입력하세요';
  if (value.length > 20) return '20자 이하로 입력하세요';
  if (!/^[a-zA-Z0-9가-힣_]+$/.test(value)) return '한글, 영문, 숫자, 밑줄(_)만 가능';
  return null;
}

function getPasswordStrength(pw: string): { level: 0 | 1 | 2 | 3; label: string; color: string } {
  if (pw.length < 6) return { level: 0, label: '6자 이상 필요', color: 'bg-text-muted' };
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  if (score <= 1) return { level: 1, label: '약함', color: 'bg-danger' };
  if (score <= 2) return { level: 2, label: '보통', color: 'bg-warning' };
  return { level: 3, label: '강함', color: 'bg-success' };
}

export default function HomePage() {
  const router = useRouter();
  const { setUser, setToken } = useUserStore();
  const [mode, setMode] = useState<AuthMode>('login');
  const [loginId, setLoginId] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // LoginId duplicate check
  const [loginIdStatus, setLoginIdStatus] = useState<LoginIdStatus>('idle');
  const [loginIdError, setLoginIdError] = useState<string | null>(null);
  const loginIdDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Nickname duplicate check
  const [nicknameStatus, setNicknameStatus] = useState<NicknameStatus>('idle');
  const [nicknameError, setNicknameError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const checkLoginIdAvailability = useCallback((value: string) => {
    if (loginIdDebounceRef.current) clearTimeout(loginIdDebounceRef.current);
    const validationError = validateLoginId(value);
    if (validationError) {
      setLoginIdStatus('invalid');
      setLoginIdError(validationError);
      return;
    }
    setLoginIdStatus('checking');
    setLoginIdError(null);
    loginIdDebounceRef.current = setTimeout(async () => {
      try {
        const available = await checkLoginId(value);
        setLoginIdStatus(available ? 'available' : 'taken');
        setLoginIdError(available ? null : '이미 사용 중인 아이디입니다');
      } catch {
        setLoginIdStatus('idle');
      }
    }, 500);
  }, []);

  const handleLoginIdChange = (value: string) => {
    setLoginId(value);
    setLoginIdStatus('idle');
    setLoginIdError(null);
  };

  const checkNicknameAvailability = useCallback((value: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const validationError = validateNickname(value);
    if (validationError) {
      setNicknameStatus('invalid');
      setNicknameError(validationError);
      return;
    }
    setNicknameStatus('checking');
    setNicknameError(null);
    debounceRef.current = setTimeout(async () => {
      try {
        const available = await checkNickname(value);
        setNicknameStatus(available ? 'available' : 'taken');
        setNicknameError(available ? null : '이미 사용 중인 닉네임입니다');
      } catch {
        setNicknameStatus('idle');
      }
    }, 500);
  }, []);

  const handleNicknameChange = (value: string) => {
    setNickname(value);
    setNicknameStatus('idle');
    setNicknameError(null);
  };

  useEffect(() => {
    setError('');
    setLoginId('');
    setLoginIdStatus('idle');
    setLoginIdError(null);
    setNicknameStatus('idle');
    setNicknameError(null);
    setConfirmPassword('');
    setEmail('');
  }, [mode]);

  const passwordStrength = getPasswordStrength(password);
  const isRegisterValid =
    mode === 'register' &&
    loginIdStatus === 'available' &&
    nicknameStatus === 'available' &&
    password.length >= 6 &&
    password === confirmPassword;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (mode === 'register') {
      const loginIdValidationError = validateLoginId(loginId.trim());
      if (loginIdValidationError) {
        setError(loginIdValidationError);
        return;
      }
      if (loginIdStatus !== 'available') {
        setError('아이디 중복 확인이 필요합니다');
        return;
      }
      const nicknameValidationError = validateNickname(nickname.trim());
      if (nicknameValidationError) {
        setError(nicknameValidationError);
        return;
      }
      if (nicknameStatus !== 'available') {
        setError('닉네임 중복 확인이 필요합니다');
        return;
      }
      if (password.length < 6) {
        setError('비밀번호는 6자 이상이어야 합니다');
        return;
      }
      if (password !== confirmPassword) {
        setError('비밀번호가 일치하지 않습니다');
        return;
      }
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        const res = await login(loginId, password);
        setToken(res.access_token);
        const user = await api.get<{
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
        setUser({
          id: user.id,
          login_id: user.login_id,
          nickname: user.nickname,
          email: user.email ?? null,
          role: user.role,
          ageGroup: user.age_group,
          adultVerifiedAt: user.adult_verified_at,
          preferredLlmModelId: user.preferred_llm_model_id,
          creditBalance: user.credit_balance ?? 0,
          subscriptionPlanKey: user.subscription_plan_key ?? null,
          createdAt: user.created_at,
        });
        router.push(['admin', 'superadmin'].includes(user.role) ? '/admin' : '/');
      } else {
        const res = await register(loginId.trim(), nickname.trim(), password, email || undefined);
        setToken(res.access_token);
        const user = await api.get<{
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
        setUser({
          id: user.id,
          login_id: user.login_id,
          nickname: user.nickname,
          email: user.email ?? null,
          role: user.role,
          ageGroup: user.age_group,
          adultVerifiedAt: user.adult_verified_at,
          preferredLlmModelId: user.preferred_llm_model_id,
          creditBalance: user.credit_balance ?? 0,
          subscriptionPlanKey: user.subscription_plan_key ?? null,
          createdAt: user.created_at,
        });
        toast.success('가입이 완료되었습니다!');
        router.push('/');
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '오류가 발생했습니다';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex justify-center items-center min-h-screen bg-bg">
      <div className="bg-bg-surface rounded-2xl py-12 px-6 md:px-10 w-full max-w-[425px] mx-4 shadow-card">
        <div className="flex justify-center mb-3">
          <Swords size={48} className="text-nemo" />
        </div>
        <h1 className="m-0 text-2xl text-center text-text font-bold">NEMO</h1>
        <p className="text-center text-text-secondary text-sm mb-6">LLM 에이전트 AI 토론 플랫폼</p>

        <div className="flex mb-6 border-b-2 border-border">
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm ${
              mode === 'login'
                ? 'font-semibold text-primary border-b-2 border-primary -mb-0.5'
                : 'text-text-muted'
            }`}
            onClick={() => setMode('login')}
          >
            로그인
          </button>
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm ${
              mode === 'register'
                ? 'font-semibold text-primary border-b-2 border-primary -mb-0.5'
                : 'text-text-muted'
            }`}
            onClick={() => setMode('register')}
          >
            회원가입
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3">
          {/* LoginId */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">아이디</label>
            <div className="relative flex gap-2">
              <input
                type="text"
                placeholder={mode === 'register' ? '2~30자, 영문/숫자/밑줄' : '아이디'}
                value={loginId}
                onChange={(e) => handleLoginIdChange(e.target.value)}
                required
                maxLength={30}
                className={`input py-3 px-4 w-full ${
                  mode === 'register' && loginIdStatus === 'taken' ? 'border-danger' : ''
                } ${mode === 'register' && loginIdStatus === 'available' ? 'border-success' : ''}`}
              />
              {mode === 'register' && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    checkLoginIdAvailability(loginId.trim());
                  }}
                  disabled={loginId.trim().length === 0 || loginIdStatus === 'checking'}
                  className="btn-primary py-3 px-4 shrink-0 whitespace-nowrap text-sm"
                >
                  {loginIdStatus === 'checking' ? (
                    <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    '중복확인'
                  )}
                </button>
              )}
            </div>
            {mode === 'register' && loginIdError && (
              <span className="text-danger-text text-xs">{loginIdError}</span>
            )}
            {mode === 'register' && loginIdStatus === 'available' && (
              <span className="text-success text-xs">사용 가능한 아이디입니다</span>
            )}
          </div>

          {/* Nickname (register only) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">닉네임</label>
              <div className="relative flex gap-2">
                <input
                  type="text"
                  placeholder="2~20자, 한글/영문/숫자"
                  value={nickname}
                  onChange={(e) => handleNicknameChange(e.target.value)}
                  required
                  maxLength={20}
                  className={`input py-3 px-4 w-full ${
                    nicknameStatus === 'taken' ? 'border-danger' : ''
                  } ${nicknameStatus === 'available' ? 'border-success' : ''}`}
                />
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    checkNicknameAvailability(nickname.trim());
                  }}
                  disabled={nickname.trim().length === 0 || nicknameStatus === 'checking'}
                  className="btn-primary py-3 px-4 shrink-0 whitespace-nowrap text-sm"
                >
                  {nicknameStatus === 'checking' ? (
                    <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    '중복확인'
                  )}
                </button>
              </div>
              {nicknameError && <span className="text-danger-text text-xs">{nicknameError}</span>}
              {nicknameStatus === 'available' && (
                <span className="text-success text-xs">사용 가능한 닉네임입니다</span>
              )}
            </div>
          )}

          {/* Email (register only) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">
                이메일 <span className="text-text-muted font-normal">(선택)</span>
              </label>
              <input
                type="email"
                placeholder="example@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input py-3 px-4"
              />
            </div>
          )}

          {/* Password */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-semibold text-text-label">비밀번호</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder={mode === 'register' ? '6자 이상' : '비밀번호'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="input py-3 px-4 pr-10 w-full"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-text-muted hover:text-text p-0"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {mode === 'register' && password.length > 0 && (
              <div className="flex items-center gap-2 mt-1">
                <div className="flex gap-1 flex-1">
                  {[1, 2, 3].map((level) => (
                    <div
                      key={level}
                      className={`h-1 flex-1 rounded-full ${
                        level <= passwordStrength.level ? passwordStrength.color : 'bg-border'
                      }`}
                    />
                  ))}
                </div>
                <span className="text-xs text-text-muted">{passwordStrength.label}</span>
              </div>
            )}
          </div>

          {/* Confirm Password (register only) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-text-label">비밀번호 확인</label>
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="비밀번호 다시 입력"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className={`input py-3 px-4 w-full ${
                  confirmPassword && password !== confirmPassword ? 'border-danger' : ''
                } ${confirmPassword && password === confirmPassword && password.length >= 6 ? 'border-success' : ''}`}
              />
              {confirmPassword && password !== confirmPassword && (
                <span className="text-danger-text text-xs">비밀번호가 일치하지 않습니다</span>
              )}
              {confirmPassword && password === confirmPassword && password.length >= 6 && (
                <span className="text-success text-xs">비밀번호가 일치합니다</span>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 py-2 px-3 rounded-lg bg-danger/10 border border-danger/20">
              <AlertCircle size={14} className="text-danger shrink-0" />
              <p className="text-danger-text text-[13px] m-0">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || (mode === 'register' && !isRegisterValid)}
            className="btn-primary py-3 text-[15px] mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '처리 중...' : mode === 'login' ? '로그인' : '가입하기'}
          </button>
        </form>
      </div>
    </div>
  );
}
