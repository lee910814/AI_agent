/** 마이페이지 프로필 탭. 사용자 정보 표시 + 비밀번호 변경 폼. */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { User, Lock, Calendar, Shield, Mail, IdCard, Eye, EyeOff, UserX } from 'lucide-react';
import { useUserStore } from '@/stores/userStore';
import { useToastStore } from '@/stores/toastStore';
import { api, ApiError } from '@/lib/api';

const AGE_GROUP_LABELS: Record<string, { label: string; color: string }> = {
  unverified: { label: '미인증', color: 'bg-text-muted' },
  minor_safe: { label: '청소년', color: 'bg-warning' },
  adult_verified: { label: '성인인증', color: 'bg-success' },
};

const ROLE_LABELS: Record<string, string> = {
  user: '일반 사용자',
  admin: '관리자',
  superadmin: '슈퍼관리자',
};

export function ProfileTab() {
  const { user, logout } = useUserStore();
  const { addToast } = useToastStore();
  const router = useRouter();

  // 비밀번호 변경 폼 상태
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordChanged, setPasswordChanged] = useState(false);

  // 회원탈퇴 상태
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) return;
    if (newPassword.length < 6) return;

    setPasswordLoading(true);
    try {
      await api.put('/auth/me/password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordChanged(true);
      addToast('success', '비밀번호가 변경되었습니다.');
      setShowPasswordForm(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordChanged(false);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : '비밀번호 변경에 실패했습니다.';
      addToast('error', message);
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeleteLoading(true);
    try {
      await api.delete('/auth/me');
      addToast('success', '회원탈퇴가 완료되었습니다.');
      logout();
      router.push('/login');
    } catch (err) {
      const message = err instanceof ApiError ? err.message : '회원탈퇴에 실패했습니다.';
      addToast('error', message);
      setShowDeleteConfirm(false);
    } finally {
      setDeleteLoading(false);
    }
  };

  // 비밀번호 강도 체크
  const getStrength = (pw: string) => {
    if (pw.length < 6) return { level: 0, label: '6자 이상 필요', color: 'bg-text-muted' };
    let score = 0;
    if (pw.length >= 8) score++;
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
    if (/\d/.test(pw)) score++;
    if (/[^a-zA-Z0-9]/.test(pw)) score++;
    if (score <= 1) return { level: 1, label: '약함', color: 'bg-red-500' };
    if (score <= 2) return { level: 2, label: '보통', color: 'bg-yellow-500' };
    return { level: 3, label: '강함', color: 'bg-green-500' };
  };

  const strength = getStrength(newPassword);

  if (!user) {
    return (
      <div className="bg-white rounded-xl p-6 brutal-border brutal-shadow-sm animate-pulse">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-gray-200 brutal-border" />
          <div className="flex-1 flex flex-col gap-2">
            <div className="h-5 w-32 bg-gray-200 rounded" />
            <div className="h-4 w-20 bg-gray-100 rounded" />
          </div>
        </div>
        <div className="flex flex-col gap-3 border-t-2 border-black/10 pt-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-4 bg-gray-100 rounded w-3/4" />
          ))}
        </div>
      </div>
    );
  }

  const ageInfo = AGE_GROUP_LABELS[user.ageGroup] ?? {
    label: user.ageGroup,
    color: 'bg-text-muted',
  };

  return (
    <>
      {/* 사용자 정보 카드 */}
      <div className="bg-white rounded-xl p-6 mb-5 brutal-border brutal-shadow-sm">
        {/* 헤더: 아바타 + 닉네임 */}
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary text-2xl font-black brutal-border">
            {user.nickname.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="m-0 text-xl font-black text-black">{user.nickname}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-500 font-semibold uppercase">
                {ROLE_LABELS[user.role] ?? user.role}
              </span>
              <span
                className={`text-[10px] font-bold text-white px-2 py-0.5 rounded-full ${ageInfo.color}`}
              >
                {ageInfo.label}
              </span>
            </div>
          </div>
        </div>

        {/* 상세 정보 */}
        <div className="flex flex-col gap-3 border-t-2 border-black/10 pt-4">
          <div className="flex items-center gap-3">
            <IdCard size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">아이디</span>
            <span className="text-sm text-black font-medium">{user.login_id}</span>
          </div>
          <div className="flex items-center gap-3">
            <User size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">닉네임</span>
            <span className="text-sm text-black font-medium">{user.nickname}</span>
          </div>
          {user.email && (
            <div className="flex items-center gap-3">
              <Mail size={16} className="text-gray-400 shrink-0" />
              <span className="text-sm text-gray-500 w-24 font-semibold">이메일</span>
              <span className="text-sm text-black font-medium">{user.email}</span>
            </div>
          )}
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">역할</span>
            <span className="text-sm text-black font-medium">
              {ROLE_LABELS[user.role] ?? user.role}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <Shield size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">연령 상태</span>
            <span className="text-sm text-black font-medium">{ageInfo.label}</span>
            {user.adultVerifiedAt && (
              <span className="text-xs text-gray-400">
                ({new Date(user.adultVerifiedAt).toLocaleDateString('ko-KR')} 인증)
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Calendar size={16} className="text-gray-400 shrink-0" />
            <span className="text-sm text-gray-500 w-24 font-semibold">가입일</span>
            <span className="text-sm text-black font-medium">
              {new Date(user.createdAt).toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </span>
          </div>
        </div>
      </div>

      {/* 비밀번호 변경 카드 */}
      <div className="bg-white rounded-xl p-6 mb-5 brutal-border brutal-shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-black text-black flex items-center gap-2 m-0">
            <Lock size={18} className="text-gray-400" />
            비밀번호 변경
          </h2>
          {!showPasswordForm && (
            <button
              onClick={() => setShowPasswordForm(true)}
              className="px-4 py-2 bg-white text-black text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer"
            >
              변경하기
            </button>
          )}
        </div>

        {showPasswordForm ? (
          <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
            {/* 현재 비밀번호 */}
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-gray-500">현재 비밀번호</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary"
                  placeholder="현재 비밀번호 입력"
                />
              </div>
            </div>

            {/* 새 비밀번호 */}
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-gray-500">새 비밀번호</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full bg-gray-50 border-2 border-black rounded-xl px-4 py-3 pr-10 text-sm text-black focus:outline-none focus:border-primary"
                  placeholder="6자 이상 입력"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-gray-400 hover:text-black p-0"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {newPassword.length > 0 && (
                <div className="flex items-center gap-2 mt-1">
                  <div className="flex gap-1 flex-1">
                    {[1, 2, 3].map((level) => (
                      <div
                        key={level}
                        className={`h-1.5 flex-1 rounded-full ${
                          level <= strength.level ? strength.color : 'bg-gray-200'
                        }`}
                      />
                    ))}
                  </div>
                  <span className="text-xs text-gray-500 font-semibold">{strength.label}</span>
                </div>
              )}
            </div>

            {/* 새 비밀번호 확인 */}
            <div className="flex flex-col gap-1">
              <label className="text-[13px] font-semibold text-gray-500">새 비밀번호 확인</label>
              <input
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
                className={`w-full bg-gray-50 border-2 rounded-xl px-4 py-3 text-sm text-black focus:outline-none focus:border-primary ${
                  confirmPassword && newPassword !== confirmPassword
                    ? 'border-red-500'
                    : 'border-black'
                } ${confirmPassword && newPassword === confirmPassword && newPassword.length >= 6 ? 'border-green-500' : ''}`}
                placeholder="새 비밀번호 다시 입력"
              />
              {confirmPassword && newPassword !== confirmPassword && (
                <span className="text-red-500 text-xs font-semibold">
                  비밀번호가 일치하지 않습니다
                </span>
              )}
              {confirmPassword && newPassword === confirmPassword && newPassword.length >= 6 && (
                <span className="text-green-500 text-xs font-semibold">비밀번호가 일치합니다</span>
              )}
            </div>

            {passwordChanged && (
              <div className="py-2 px-3 rounded-xl bg-green-50 border-2 border-green-500 text-green-600 text-sm font-semibold text-center">
                ✅ 비밀번호가 변경되었습니다
              </div>
            )}

            <div className="flex gap-2 mt-2">
              <button
                type="submit"
                disabled={
                  !currentPassword ||
                  newPassword.length < 6 ||
                  newPassword !== confirmPassword ||
                  passwordLoading
                }
                className="flex-1 py-3 bg-primary text-white text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
              >
                {passwordLoading ? '변경 중...' : '비밀번호 변경'}
              </button>
              <button
                type="button"
                disabled={passwordLoading}
                onClick={() => {
                  setShowPasswordForm(false);
                  setCurrentPassword('');
                  setNewPassword('');
                  setConfirmPassword('');
                }}
                className="flex-1 py-3 bg-white text-black text-sm font-black rounded-xl brutal-border hover:bg-gray-50 transition-all cursor-pointer disabled:opacity-50"
              >
                취소
              </button>
            </div>
          </form>
        ) : (
          <p className="text-sm text-gray-500 m-0">보안을 위해 주기적으로 비밀번호를 변경하세요.</p>
        )}
      </div>

      {/* 회원탈퇴 카드 */}
      <div className="bg-white rounded-xl p-6 brutal-border brutal-shadow-sm border-red-200">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-black text-red-500 flex items-center gap-2 m-0">
            <UserX size={18} />
            회원탈퇴
          </h2>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="px-4 py-2 bg-white text-red-500 text-sm font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer"
          >
            탈퇴하기
          </button>
        </div>
        <p className="text-sm text-gray-500 m-0">
          탈퇴 시 모든 데이터가 삭제되며 복구할 수 없습니다.
        </p>
      </div>

      {/* 회원탈퇴 확인 모달 */}
      {showDeleteConfirm && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setShowDeleteConfirm(false)}
        >
          <div
            className="bg-white brutal-border brutal-shadow-lg w-full max-w-sm p-8 animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center text-red-500 brutal-border border-red-200">
                <UserX size={32} />
              </div>
            </div>
            <h3 className="text-xl font-black text-center text-black mb-2">
              정말 탈퇴하시겠습니까?
            </h3>
            <p className="text-sm font-bold text-center text-gray-500 mb-8">
              모든 데이터가 삭제되며 복구할 수 없습니다.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={handleDeleteAccount}
                disabled={deleteLoading}
                className="w-full py-4 bg-red-500 text-white font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer border-none disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
              >
                {deleteLoading ? '처리 중...' : '회원탈퇴'}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleteLoading}
                className="w-full py-4 bg-white text-black font-black rounded-xl brutal-border brutal-shadow-sm hover:translate-y-[-2px] transition-all cursor-pointer border-none"
              >
                취소
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
