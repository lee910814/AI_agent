/**
 * 백엔드 프록시 — 모든 /api/** 요청을 FastAPI로 전달.
 * Next.js rewrites()는 SSE 스트리밍을 버퍼링하므로 App Router API Route로 대체.
 */
import { type NextRequest } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

async function proxy(req: NextRequest): Promise<Response> {
  const { pathname, search } = req.nextUrl;
  const targetUrl = `${BACKEND_URL}${pathname}${search}`;

  // 요청 헤더 복사 (host 제외)
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (key.toLowerCase() !== 'host') {
      headers.set(key, value);
    }
  });
  // gzip 압축 비활성화 — Node.js fetch가 gzip 블록 단위로 버퍼링하면 SSE가 지연됨
  headers.set('accept-encoding', 'identity');

  // 요청 바디 읽기 (스트리밍 없이 버퍼로)
  let body: ArrayBuffer | undefined;
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    body = await req.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: body && body.byteLength > 0 ? body : undefined,
      // SSE 스트림 버퍼링 방지 — Next.js fetch 캐시가 body를 소비하면 "한번에 출력" 현상 발생
      cache: 'no-store',
    });
  } catch {
    // 백엔드 연결 실패 (ECONNREFUSED 등) — 503으로 반환하여 클라이언트가 graceful하게 처리 가능
    return new Response(JSON.stringify({ detail: 'Backend unavailable' }), {
      status: 503,
      headers: { 'content-type': 'application/json' },
    });
  }

  // 응답 헤더 복사
  const responseHeaders = new Headers(upstream.headers);

  // SSE 등 스트리밍 응답: body를 그대로 파이핑
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
