'use client';

import { useState } from 'react';
import { Share2, Check, Twitter } from 'lucide-react';

type Props = { url: string; title?: string };

export function ShareButton({ url, title = 'AI 토론' }: Props) {
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* fallback */
    }
    setOpen(false);
  };

  const handleTwitter = () => {
    const text = encodeURIComponent(title);
    const encodedUrl = encodeURIComponent(url);
    window.open(`https://twitter.com/intent/tweet?text=${text}&url=${encodedUrl}`, '_blank');
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-surface border border-border text-sm text-text-muted hover:text-text transition-colors"
      >
        <Share2 size={14} />
        공유
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-20 bg-bg-surface border border-border rounded-xl shadow-lg min-w-[150px] py-1">
            <button
              type="button"
              onClick={handleCopy}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-bg text-text-muted hover:text-text transition-colors"
            >
              {copied ? <Check size={14} className="text-green-400" /> : <Share2 size={14} />}
              {copied ? '복사됨!' : '링크 복사'}
            </button>
            <button
              type="button"
              onClick={handleTwitter}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-bg text-text-muted hover:text-text transition-colors"
            >
              <Twitter size={14} />
              트위터
            </button>
          </div>
        </>
      )}
    </div>
  );
}
