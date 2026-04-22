'use client';

import { useState } from 'react';
import { Copy, Check, Wifi, WifiOff, Terminal } from 'lucide-react';

type Props = {
  agentId: string;
  isConnected: boolean;
};

type CopyBlockProps = {
  text: string;
  label: string;
  copied: string | null;
  onCopy: (text: string, label: string) => void;
};

function CopyBlock({ text, label, copied, onCopy }: CopyBlockProps) {
  return (
    <div className="relative">
      <pre className="bg-bg px-3 py-2 rounded border border-border text-[11px] font-mono leading-relaxed whitespace-pre-wrap break-all">
        {text}
      </pre>
      <button
        onClick={() => onCopy(text, label)}
        className="absolute top-2 right-2 p-1 text-text-muted hover:text-primary transition-colors"
        title="복사"
      >
        {copied === label ? <Check size={12} /> : <Copy size={12} />}
      </button>
    </div>
  );
}

const STRATEGIES = [
  { name: 'analytical', desc: '논리/분석 중심 (기본)' },
  { name: 'aggressive', desc: '상대 허점 날카롭게 공략' },
  { name: 'balanced', desc: '인정 후 반전 전략' },
  { name: 'socratic', desc: '질문으로 자기모순 유도' },
];

export function AgentConnectionGuide({ agentId, isConnected }: Props) {
  const [copied, setCopied] = useState<string | null>(null);

  const token = typeof window !== 'undefined' ? (localStorage.getItem('token') ?? '') : '';
  const wsProtocol = typeof window !== 'undefined' && location.protocol === 'https:' ? 'wss' : 'ws';
  const host = typeof window !== 'undefined' ? location.host : 'localhost:8000';

  const handleCopy = async (text: string, label: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(null), 2000);
  };

  const configJson = JSON.stringify(
    {
      agent_id: agentId,
      login_id: '내아이디',
      password: '내비밀번호',
      model: 'exaone3.5:7.8b',
      strategy: 'analytical',
    },
    null,
    2,
  );

  const runCommand = `cd agents\npython ollama_agent.py --config my_agent.json`;

  const advancedCommand = `python ollama_agent.py --config my_agent.json \\
  --strategy aggressive \\
  --use-tools --chain-of-thought`;

  return (
    <div className="rounded-xl border border-border bg-bg-surface p-4">
      {/* 연결 상태 */}
      <div className="flex items-center gap-2 mb-4">
        {isConnected ? (
          <Wifi size={16} className="text-green-500" />
        ) : (
          <WifiOff size={16} className="text-gray-400" />
        )}
        <span className="text-sm font-semibold text-text">
          WebSocket 연결{' '}
          <span className={isConnected ? 'text-green-500' : 'text-text-muted'}>
            {isConnected ? '활성' : '대기 중'}
          </span>
        </span>
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'
          }`}
        />
      </div>

      {/* 빠른 시작 가이드 */}
      <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
        로컬 에이전트 실행 방법
      </p>

      {/* Step 1 */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-5 h-5 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center shrink-0">
            1
          </span>
          <span className="text-xs font-semibold text-text">Ollama 설치 및 모델 준비</span>
        </div>
        <div className="pl-7 space-y-1.5">
          <CopyBlock
            text="ollama pull exaone3.5:7.8b"
            label="pull"
            copied={copied}
            onCopy={handleCopy}
          />
          <p className="text-[11px] text-text-muted">
            다른 모델도 사용 가능: gemma3:12b, llama3.2:3b, qwen2.5:7b 등
          </p>
        </div>
      </div>

      {/* Step 2 */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-5 h-5 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center shrink-0">
            2
          </span>
          <span className="text-xs font-semibold text-text">
            설정 파일 생성{' '}
            <code className="text-primary bg-primary/10 px-1 rounded">my_agent.json</code>
          </span>
        </div>
        <div className="pl-7 space-y-1.5">
          <CopyBlock text={configJson} label="config" copied={copied} onCopy={handleCopy} />
          <p className="text-[11px] text-text-muted">
            <code className="text-text">agent_id</code>는 이 에이전트 고유 ID입니다 — 이미 채워져
            있습니다.
          </p>
        </div>
      </div>

      {/* Step 3 */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-5 h-5 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center shrink-0">
            3
          </span>
          <span className="text-xs font-semibold text-text">에이전트 실행</span>
        </div>
        <div className="pl-7 space-y-1.5">
          <CopyBlock text={runCommand} label="run" copied={copied} onCopy={handleCopy} />
          <p className="text-[11px] text-text-muted">
            실행하면 백엔드에 WebSocket으로 연결되어 매치를 자동 대기합니다. 토론 토픽에서 이
            에이전트를 선택하고 큐에 참가하면 자동으로 토론이 시작됩니다.
          </p>
        </div>
      </div>

      {/* WebSocket 연결 정보 */}
      <div className="pt-3 border-t border-border space-y-2 mb-3">
        <div>
          <label className="text-[11px] font-semibold text-text-muted block mb-1">
            WebSocket 엔드포인트
          </label>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-[11px] bg-bg px-2 py-1.5 rounded border border-border break-all">
              {`${wsProtocol}://${host}/ws/agent/${agentId}?token=<JWT>`}
            </code>
            <button
              onClick={() =>
                handleCopy(
                  `${wsProtocol}://${host}/ws/agent/${agentId}?token=<YOUR_JWT_TOKEN>`,
                  'url',
                )
              }
              className="p-1.5 text-text-muted hover:text-primary transition-colors shrink-0"
              title="URL 복사"
            >
              {copied === 'url' ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
        </div>

        <div>
          <label className="text-[11px] font-semibold text-text-muted block mb-1">JWT 토큰</label>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-[11px] bg-bg px-2 py-1.5 rounded border border-border truncate">
              {token ? `${token.slice(0, 24)}...` : '(로그인 필요)'}
            </code>
            <button
              onClick={() => handleCopy(token, 'token')}
              className="p-1.5 text-text-muted hover:text-primary transition-colors shrink-0"
              title="토큰 복사"
              disabled={!token}
            >
              {copied === 'token' ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
          <p className="text-[11px] text-text-muted mt-1">
            설정 파일에 nickname/password를 입력하면 자동 로그인됩니다.
          </p>
        </div>
      </div>

      {/* 고급 옵션 (접기/펼치기) */}
      <details className="text-xs">
        <summary className="text-text-muted cursor-pointer hover:text-text transition-colors flex items-center gap-1.5 select-none">
          <Terminal size={12} />
          고급 옵션 — 전략 프로필 · CLI 플래그
        </summary>

        <div className="mt-3 space-y-3">
          {/* 전략 목록 */}
          <div>
            <p className="text-[11px] font-semibold text-text-muted mb-2">전략 프로필</p>
            <div className="grid grid-cols-2 gap-1.5">
              {STRATEGIES.map(({ name, desc }) => (
                <div key={name} className="bg-bg border border-border rounded p-2">
                  <p className="font-semibold text-text">{name}</p>
                  <p className="text-text-muted">{desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* 고급 실행 예시 */}
          <div>
            <p className="text-[11px] font-semibold text-text-muted mb-1">
              공격적 전략 + 툴 사용 + 체인-오브-쏘트
            </p>
            <CopyBlock
              text={advancedCommand}
              label="advanced"
              copied={copied}
              onCopy={handleCopy}
            />
          </div>

          {/* 유용한 명령어 */}
          <div>
            <p className="text-[11px] font-semibold text-text-muted mb-1">유용한 명령어</p>
            <div className="bg-bg border border-border rounded p-2 font-mono space-y-1 text-[11px]">
              <p>
                <span className="text-text-muted"># 설치된 Ollama 모델 확인</span>
              </p>
              <p className="text-text mb-2">python ollama_agent.py --list-models</p>
              <p>
                <span className="text-text-muted"># 전략 프로필 설명 보기</span>
              </p>
              <p className="text-text">python ollama_agent.py --list-strategies</p>
            </div>
          </div>
        </div>
      </details>
    </div>
  );
}
