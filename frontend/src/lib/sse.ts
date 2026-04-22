type SSEOptions = {
  onMessage: (data: string) => void;
  onError?: (error: unknown) => void;
  onClose?: () => void;
};

/**
 * POST 기반 SSE 연결. fetch + ReadableStream 사용.
 * EventSource(GET 전용)를 대체하여 Authorization 헤더와 JSON body를 지원한다.
 */
export function connectSSE(
  url: string,
  body: Record<string, unknown>,
  options: SSEOptions,
): () => void {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(url, {
        method: 'POST',
        // 쿠키 기반 인증 — credentials 없으면 HttpOnly 쿠키가 전송되지 않아 401 발생
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        options.onError?.(new Error(`SSE request failed: ${response.status}`));
        options.onClose?.();
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        options.onClose?.();
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        // 마지막 줄은 아직 불완전할 수 있으므로 버퍼에 유지
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const payload = trimmed.slice(6);
            if (payload === '[DONE]') {
              options.onClose?.();
              return;
            }
            options.onMessage(payload);
          }
        }
      }

      options.onClose?.();
    } catch (err) {
      if (controller.signal.aborted) return;
      options.onError?.(err);
      options.onClose?.();
    }
  })();

  return () => {
    controller.abort();
  };
}
