'use client';

import { X, BookOpen } from 'lucide-react';
import type { GuideSection } from '@/data/guideContent';

type Props = {
  open: boolean;
  onClose: () => void;
  sections: GuideSection[];
  title?: string;
};

export function HelpDrawer({ open, onClose, sections, title = '도움말' }: Props) {
  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-[90]" onClick={onClose} />

      {/* Drawer */}
      <aside className="fixed top-0 right-0 h-full w-[360px] max-w-[90vw] bg-bg-surface border-l border-border z-[91] flex flex-col animate-slide-in">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <BookOpen size={18} className="text-primary" />
            <h2 className="text-base font-semibold m-0">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 bg-transparent border-none cursor-pointer text-text-muted hover:text-text transition-colors"
            aria-label="닫기"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {sections.map((section, i) => (
            <div key={i}>
              <h3 className="text-sm font-semibold text-primary m-0 mb-1.5">{section.title}</h3>
              <p className="text-sm text-text-secondary m-0 leading-relaxed">{section.body}</p>
            </div>
          ))}

          {sections.length === 0 && (
            <p className="text-sm text-text-muted text-center py-8">
              이 화면의 도움말이 준비 중입니다.
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border">
          <p className="text-[11px] text-text-muted m-0 text-center">
            배너가 다시 보이게 하려면 브라우저 캐시를 초기화하세요.
          </p>
        </div>
      </aside>
    </>
  );
}
