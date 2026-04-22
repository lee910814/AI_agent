'use client';

import { useEffect, useState } from 'react';

/**
 * MSW(Mock Service Worker) 초기화 컴포넌트.
 * NEXT_PUBLIC_API_MOCK=true 일 때만 활성화되며, worker 준비 전까지 렌더링을 지연시킨다.
 */
export function MSWProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(process.env.NEXT_PUBLIC_API_MOCK !== 'true');

  useEffect(() => {
    if (process.env.NEXT_PUBLIC_API_MOCK !== 'true') return;

    import('../mocks/browser').then(({ worker }) => {
      worker
        .start({
          onUnhandledRequest: 'bypass', // 핸들러 없는 요청은 그대로 통과
        })
        .then(() => setReady(true));
    });
  }, []);

  if (!ready) return null;

  return <>{children}</>;
}
