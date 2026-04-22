'use client';

import { HelpCircle } from 'lucide-react';

type Props = {
  onClick: () => void;
};

export function HelpButton({ onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-6 right-6 z-[80] w-11 h-11 rounded-full bg-primary text-white border-none cursor-pointer shadow-glow flex items-center justify-center hover:bg-primary-dark transition-colors"
      aria-label="도움말 열기"
    >
      <HelpCircle size={22} />
    </button>
  );
}
