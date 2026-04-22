/** 토스트 알림 컨테이너. 화면 우상단에 알림을 오버레이로 표시. */
'use client';

import { useToastStore } from '@/stores/toastStore';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';

const iconMap = {
  success: <CheckCircle size={18} className="text-success shrink-0" />,
  error: <XCircle size={18} className="text-danger shrink-0" />,
  info: <Info size={18} className="text-primary shrink-0" />,
};

const borderMap = {
  success: 'border-l-success',
  error: 'border-l-danger',
  info: 'border-l-primary',
};

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[200] flex flex-col gap-2 w-[340px]">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-3 bg-bg-surface border border-border border-l-4 ${borderMap[t.type]} rounded-lg p-3 shadow-card animate-slide-in`}
        >
          {iconMap[t.type]}
          <p className="text-sm text-text flex-1 m-0 leading-5">{t.message}</p>
          <button
            onClick={() => removeToast(t.id)}
            className="text-text-muted hover:text-text bg-transparent border-none cursor-pointer p-0 shrink-0"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
