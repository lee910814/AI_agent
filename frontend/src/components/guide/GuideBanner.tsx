'use client';

import { useState, useEffect } from 'react';
import { X, Lightbulb } from 'lucide-react';

type Props = {
  pathname: string;
  text: string;
};

const STORAGE_KEY = 'guide_banner_dismissed';

function getDismissed(): Record<string, boolean> {
  if (typeof window === 'undefined') return {};
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
  } catch {
    return {};
  }
}

function setDismissed(pathname: string) {
  const current = getDismissed();
  current[pathname] = true;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
}

export function GuideBanner({ pathname, text }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const dismissed = getDismissed();
    setVisible(!dismissed[pathname]);
  }, [pathname]);

  if (!visible) return null;

  const handleDismiss = () => {
    setDismissed(pathname);
    setVisible(false);
  };

  return (
    <div className="flex items-center gap-3 px-4 py-3 mb-4 rounded-lg bg-primary/10 border border-primary/30 animate-[fade-in_0.3s_ease-out]">
      <Lightbulb size={18} className="text-primary flex-shrink-0" />
      <p className="flex-1 text-sm text-text-secondary m-0">{text}</p>
      <button
        onClick={handleDismiss}
        className="flex-shrink-0 p-1 bg-transparent border-none cursor-pointer text-text-muted hover:text-text transition-colors"
        aria-label="배너 닫기"
      >
        <X size={16} />
      </button>
    </div>
  );
}
