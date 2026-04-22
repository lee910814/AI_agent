/** 확인/취소 다이얼로그. 위험 동작 전 사용자 확인용. ESC로 닫기 지원. */
'use client';

import { memo, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';

type Props = {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'default';
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export const ConfirmDialog = memo(function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = '확인',
  cancelLabel = '취소',
  variant = 'default',
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onCancel}
    >
      <div
        className="bg-bg-surface rounded-xl p-6 w-full max-w-[400px] mx-4 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 mb-4">
          {variant === 'danger' && (
            <div className="w-10 h-10 rounded-full bg-danger/15 flex items-center justify-center flex-shrink-0">
              <AlertTriangle size={20} className="text-danger" />
            </div>
          )}
          <h3 className="text-lg font-semibold text-text m-0">{title}</h3>
        </div>
        <p className="text-sm text-text-secondary mb-6 leading-relaxed">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            disabled={loading}
            className="py-2 px-4 rounded-lg text-sm bg-transparent border border-border text-text-secondary hover:bg-bg-hover cursor-pointer disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`py-2 px-4 rounded-lg text-sm text-white border-none cursor-pointer disabled:opacity-50 ${
              variant === 'danger'
                ? 'bg-danger hover:bg-danger/80'
                : 'bg-primary hover:bg-primary/80'
            }`}
          >
            {loading ? '처리 중...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
});
