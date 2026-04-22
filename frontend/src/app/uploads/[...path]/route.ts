import { type NextRequest } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

export async function GET(req: NextRequest): Promise<Response> {
  const { pathname, search } = req.nextUrl;

  // 인증 헤더(쿠키 포함)를 백엔드에 전달
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (key.toLowerCase() !== 'host') {
      headers.set(key, value);
    }
  });

  const upstream = await fetch(`${BACKEND_URL}${pathname}${search}`, { headers });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  });
}
