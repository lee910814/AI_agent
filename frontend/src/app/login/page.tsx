'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Swords, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { useUserStore } from '@/stores/userStore';

type AuthMode = 'login' | 'register';

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
  if (pw.length < 6) return { level: 0, label: '6자 이상 필요', color: 'bg-gray-300' };
  let score = 0;
  if (pw.length >= 8) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^a-zA-Z0-9]/.test(pw)) score++;
  if (score <= 1) return { level: 1, label: '약함', color: 'bg-red-500' };
  if (score <= 2) return { level: 2, label: '보통', color: 'bg-yellow-500' };
  return { level: 3, label: '강함', color: 'bg-green-500' };
}

export default function LoginPage() {
  const router = useRouter();
  const { initialize, isAdmin } = useUserStore();
  const [mode, setMode] = useState<AuthMode>('login');
  const [loginId, setLoginId] = useState('');
  const [nickname, setNickname] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const passwordStrength = getPasswordStrength(password);

  const resolveApiError = (err: unknown): string => {
    if (err instanceof ApiError) {
      // 백엔드가 내려주는 에러 코드별 한국어 메시지
      switch (err.code) {
        case 'AUTH_INVALID_CREDENTIALS':
          return '아이디 또는 비밀번호가 올바르지 않습니다';
        case 'AUTH_USER_NOT_FOUND':
          return '존재하지 않는 아이디입니다';
        case 'AUTH_DUPLICATE_LOGIN_ID':
          return '이미 사용 중인 아이디입니다';
        case 'AUTH_DUPLICATE_NICKNAME':
          return '이미 사용 중인 닉네임입니다';
        case 'AUTH_ACCOUNT_DISABLED':
          return '비활성화된 계정입니다. 관리자에게 문의하세요';
        default:
          // 백엔드 detail 메시지가 있으면 그대로, 없으면 일반 메시지
          return err.message || '요청 처리 중 오류가 발생했습니다';
      }
    }
    return '네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'login') {
        await api.post('/auth/login', { login_id: loginId, password });
        // 로그인 성공 — 서버가 HttpOnly 쿠키를 발급했으므로 /auth/me로 사용자 정보 조회
        // initialized를 초기화해 initialize()가 재실행되도록 함
        useUserStore.setState({ initialized: false });
        await initialize();
        router.push(isAdmin() ? '/admin' : '/');
      } else {
        // 클라이언트 측 사전 검증
        const loginIdErr = validateLoginId(loginId.trim());
        if (loginIdErr) {
          setError(loginIdErr);
          return;
        }
        const nicknameErr = validateNickname(nickname.trim());
        if (nicknameErr) {
          setError(nicknameErr);
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

        await api.post('/auth/register', {
          login_id: loginId.trim(),
          password,
          nickname: nickname.trim(),
          ...(email.trim() ? { email: email.trim() } : {}),
        });
        // 회원가입 완료 후 로그인 탭으로 전환 (백엔드가 토큰을 내려주지 않으므로)
        setMode('login');
        setPassword('');
        setConfirmPassword('');
        setNickname('');
        setEmail('');
        setError('');
      }
    } catch (err) {
      setError(resolveApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="flex justify-center items-center min-h-screen"
      style={{ background: 'linear-gradient(135deg, #FFFBF1 0%, #e8f4fd 50%, #d4ecff 100%)' }}
    >
      <div className="bg-white rounded-2xl py-10 px-6 md:px-10 w-full max-w-[440px] mx-4 brutal-border brutal-shadow-sm">
        {/* 로고 */}
        <div className="flex justify-center mb-3">
          <Swords size={48} className="text-primary" />
        </div>
        <h1 className="m-0 text-2xl text-center text-black font-black">NEMo</h1>
        <p className="text-center text-gray-500 text-sm mb-6">LLM 에이전트 AI 토론 플랫폼</p>

        {/* 탭 토글 */}
        <div className="flex mb-6 border-b-2 border-black">
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm font-bold transition-all ${
              mode === 'login'
                ? 'text-primary border-b-2 border-primary -mb-[2px]'
                : 'text-gray-400 hover:text-gray-600'
            }`}
            onClick={() => {
              setMode('login');
              setError('');
            }}
          >
            로그인
          </button>
          <button
            className={`flex-1 py-2.5 border-none bg-transparent cursor-pointer text-sm font-bold transition-all ${
              mode === 'register'
                ? 'text-primary border-b-2 border-primary -mb-[2px]'
                : 'text-gray-400 hover:text-gray-600'
            }`}
            onClick={() => {
              setMode('register');
              setError('');
            }}
          >
            회원가입
          </button>
        </div>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-3">
          {/* 아이디 */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-bold text-gray-600">아이디</label>
            <input
              type="text"
              placeholder={mode === 'register' ? '2~30자, 영문/숫자/밑줄' : '아이디'}
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              required
              maxLength={30}
              className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
            />
          </div>

          {/* 닉네임 (회원가입만) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-bold text-gray-600">닉네임</label>
              <input
                type="text"
                placeholder="2~20자, 한글/영문/숫자"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                required
                maxLength={20}
                className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
              />
            </div>
          )}

          {/* 이메일 (회원가입만) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-bold text-gray-600">
                이메일 <span className="text-gray-400 font-normal">(선택)</span>
              </label>
              <input
                type="email"
                placeholder="example@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
              />
            </div>
          )}

          {/* 비밀번호 */}
          <div className="flex flex-col gap-1">
            <label className="text-[13px] font-bold text-gray-600">비밀번호</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder={mode === 'register' ? '6자 이상' : '비밀번호'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 pr-10 text-sm text-black focus:outline-none focus:border-primary"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-gray-400 hover:text-black p-0"
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
                      className={`h-1.5 flex-1 rounded-full ${
                        level <= passwordStrength.level ? passwordStrength.color : 'bg-gray-200'
                      }`}
                    />
                  ))}
                </div>
                <span className="text-xs text-gray-500 font-semibold">
                  {passwordStrength.label}
                </span>
              </div>
            )}
          </div>

          {/* 비밀번호 확인 (회원가입만) */}
          {mode === 'register' && (
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-bold text-gray-600">비밀번호 확인</label>
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="비밀번호 다시 입력"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                className={`w-full bg-gray-50 border-2 rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary ${
                  confirmPassword && password !== confirmPassword
                    ? 'border-red-500'
                    : 'border-black'
                } ${confirmPassword && password === confirmPassword && password.length >= 6 ? 'border-green-500' : ''}`}
              />
              {confirmPassword && password !== confirmPassword && (
                <span className="text-red-500 text-xs font-semibold">
                  비밀번호가 일치하지 않습니다
                </span>
              )}
              {confirmPassword && password === confirmPassword && password.length >= 6 && (
                <span className="text-green-500 text-xs font-semibold">비밀번호가 일치합니다</span>
              )}
            </div>
          )}

          {/* 에러 메시지 */}
          {error && (
            <div className="flex items-center gap-2 py-2.5 px-3 rounded-xl bg-red-50 border-2 border-red-300">
              <AlertCircle size={14} className="text-red-500 shrink-0" />
              <p className="text-red-600 text-[13px] font-semibold m-0">{error}</p>
            </div>
          )}

          {/* 제출 버튼 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 mt-2 bg-primary text-white text-[15px] font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
          >
            {loading ? '처리 중...' : mode === 'login' ? '로그인' : '가입하기'}
          </button>
        </form>
      </div>
    </div>
  );
}
