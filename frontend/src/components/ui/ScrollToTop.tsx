'use client';

import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

type Props = {
  /** 특정 스크롤 컨테이너 지정. 없으면 window 스크롤 사용. */
  scrollContainer?: React.RefObject<HTMLElement | null>;
};

/**
 * 플로팅 Top/Bottom 버튼.
 * - 200px 이상 내려가면 Top 버튼 표시
 * - 바닥에서 100px 이상 위에 있으면 Bottom 버튼 표시
 */
export function ScrollToTop({ scrollContainer }: Props) {
  const [showTop, setShowTop] = useState(false);
  const [showBottom, setShowBottom] = useState(false);

  useEffect(() => {
    const el = scrollContainer?.current ?? null;

    const handleScroll = () => {
      const scrollY = el ? el.scrollTop : window.scrollY;
      const maxScroll = el
        ? el.scrollHeight - el.clientHeight
        : document.documentElement.scrollHeight - window.innerHeight;

      setShowTop(scrollY > 200);
      setShowBottom(maxScroll > 0 && scrollY < maxScroll - 100);
    };

    const target = el ?? window;
    target.addEventListener('scroll', handleScroll);
    handleScroll();
    return () => target.removeEventListener('scroll', handleScroll);
  }, [scrollContainer]);

  const scrollToTop = () => {
    const el = scrollContainer?.current;
    if (el) {
      el.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const scrollToBottom = () => {
    const el = scrollContainer?.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    } else {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
    }
  };

  if (!showTop && !showBottom) return null;

  return (
    <div className="fixed bottom-20 right-4 flex flex-col gap-2 z-40">
      {showTop && (
        <button
          onClick={scrollToTop}
          className="w-9 h-9 rounded-full bg-bg-surface border border-border text-text-muted hover:text-text hover:border-primary/40 shadow-md flex items-center justify-center transition-colors"
          aria-label="맨 위로"
        >
          <ChevronUp size={16} />
        </button>
      )}
      {showBottom && (
        <button
          onClick={scrollToBottom}
          className="w-9 h-9 rounded-full bg-bg-surface border border-border text-text-muted hover:text-text hover:border-primary/40 shadow-md flex items-center justify-center transition-colors"
          aria-label="맨 아래로"
        >
          <ChevronDown size={16} />
        </button>
      )}
    </div>
  );
}
