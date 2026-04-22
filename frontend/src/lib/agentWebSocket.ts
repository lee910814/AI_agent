/**
 * 로컬 에이전트 WebSocket 재연결 유틸리티.
 * 네트워크 끊김 시 지수 백오프로 자동 재연결을 시도한다.
 */

type AgentWSOptions = {
  agentId: string;
  token: string;
  onMessage: (data: Record<string, unknown>) => void;
  onStatusChange?: (status: 'connecting' | 'connected' | 'disconnected' | 'reconnecting') => void;
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
};

export class AgentWebSocket {
  private ws: WebSocket | null = null;
  private retryCount = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;
  private pingTimer: ReturnType<typeof setInterval> | null = null;

  private readonly agentId: string;
  private readonly token: string;
  private readonly onMessage: (data: Record<string, unknown>) => void;
  private readonly onStatusChange: (
    status: 'connecting' | 'connected' | 'disconnected' | 'reconnecting',
  ) => void;
  private readonly maxRetries: number;
  private readonly baseDelay: number;
  private readonly maxDelay: number;

  constructor(options: AgentWSOptions) {
    this.agentId = options.agentId;
    this.token = options.token;
    this.onMessage = options.onMessage;
    this.onStatusChange = options.onStatusChange ?? (() => {});
    this.maxRetries = options.maxRetries ?? 10;
    this.baseDelay = options.baseDelay ?? 1000;
    this.maxDelay = options.maxDelay ?? 30000;
  }

  connect(): void {
    if (this.closed) return;

    this.onStatusChange(this.retryCount === 0 ? 'connecting' : 'reconnecting');

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${location.host}/ws/agent/${this.agentId}`;

    try {
      this.ws = new WebSocket(url);
    } catch {
      this.scheduleRetry();
      return;
    }

    this.ws.onopen = () => {
      // 연결 후 즉시 인증 토큰 전송 (서버가 10초 내에 first-message로 인증 요구)
      this.ws?.send(JSON.stringify({ type: 'auth', token: this.token }));
      this.retryCount = 0;
      this.onStatusChange('connected');
      this.startPingLoop();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'ping') {
          this.ws?.send(JSON.stringify({ type: 'pong' }));
          return;
        }
        this.onMessage(data);
      } catch {
        // skip invalid JSON
      }
    };

    this.ws.onclose = (event) => {
      this.stopPingLoop();
      if (this.closed) {
        this.onStatusChange('disconnected');
        return;
      }
      // 4001-4004는 인증/권한 에러 — 재연결 불필요
      if (event.code >= 4001 && event.code <= 4004) {
        this.closed = true;
        this.onStatusChange('disconnected');
        return;
      }
      this.scheduleRetry();
    };

    this.ws.onerror = () => {
      // onclose가 이어서 호출됨
    };
  }

  disconnect(): void {
    this.closed = true;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.stopPingLoop();
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.onStatusChange('disconnected');
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private scheduleRetry(): void {
    if (this.closed || this.retryCount >= this.maxRetries) {
      this.onStatusChange('disconnected');
      return;
    }

    // 지수 백오프 + jitter
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.retryCount) + Math.random() * 1000,
      this.maxDelay,
    );
    this.retryCount++;
    this.onStatusChange('reconnecting');

    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.connect();
    }, delay);
  }

  private startPingLoop(): void {
    this.stopPingLoop();
    // 서버 heartbeat(15s)보다 짧은 간격으로 클라이언트 측 keepalive
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'pong' }));
      }
    }, 10000);
  }

  private stopPingLoop(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }
}
