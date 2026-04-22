'use client';

type Agent = {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  image_url?: string | null;
};

type Props = {
  agent: Agent | null;
  side: 'left' | 'right';
  isRevealing?: boolean;
};

const PROVIDER_BADGE: Record<string, string> = {
  openai: 'bg-green-500/20 text-green-400',
  anthropic: 'bg-orange-500/20 text-orange-400',
  google: 'bg-blue-500/20 text-blue-400',
  runpod: 'bg-purple-500/20 text-purple-400',
  local: 'bg-bg-hover text-text-muted',
};

export function AgentProfilePanel({ agent, side, isRevealing = false }: Props) {
  const ringColor = side === 'left' ? 'ring-blue-500/30' : 'ring-orange-500/30';
  const alignClass = side === 'left' ? 'items-start text-left' : 'items-end text-right';

  if (agent === null) {
    return (
      <div className={`flex flex-col ${alignClass} gap-3 w-full max-w-[160px] sm:max-w-[220px]`}>
        <div
          className={`w-full aspect-square max-w-[120px] sm:max-w-[160px] rounded-2xl border-2 border-dashed border-border
            ring-2 ${ringColor} flex items-center justify-center bg-bg-surface/50`}
        >
          {/* 펄스 애니메이션 */}
          <div className="relative flex items-center justify-center">
            <span className="animate-ping absolute inline-flex h-12 w-12 rounded-full bg-bg-hover opacity-30" />
            <span className="text-4xl">?</span>
          </div>
        </div>
        <p className="text-sm text-text-muted animate-pulse">상대를 찾는 중...</p>
      </div>
    );
  }

  const slideClass = isRevealing
    ? side === 'right'
      ? 'animate-slide-in'
      : 'animate-slide-in-left'
    : '';

  return (
    <div
      className={`flex flex-col ${alignClass} gap-3 w-full max-w-[160px] sm:max-w-[220px] ${slideClass}`}
    >
      {/* 아바타 */}
      <div
        className={`w-full aspect-square max-w-[120px] sm:max-w-[160px] rounded-2xl border-2 border-border
          ring-2 ${ringColor} overflow-hidden flex items-center justify-center bg-bg-surface text-6xl
          transition-all duration-700`}
      >
        {agent.image_url ? (
          <img src={agent.image_url} alt={agent.name} className="w-full h-full object-cover" />
        ) : (
          '🤖'
        )}
      </div>

      {/* 에이전트 정보 */}
      <div className={`flex flex-col ${alignClass} gap-1`}>
        <span className="text-base font-bold text-white truncate max-w-[140px] sm:max-w-[200px]">
          {agent.name}
        </span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full font-semibold self-start ${
            PROVIDER_BADGE[agent.provider] ?? 'bg-bg-hover text-text-muted'
          } ${side === 'right' ? 'self-end' : ''}`}
        >
          {agent.provider}
        </span>
        <span className="text-xs text-text-secondary truncate max-w-[140px] sm:max-w-[200px]">
          {agent.model_id}
        </span>
        <span className="text-sm font-mono font-bold text-yellow-400">ELO {agent.elo_rating}</span>
        <span className="text-xs text-text-muted">
          {agent.wins}승 {agent.losses}패 {agent.draws}무
        </span>
      </div>
    </div>
  );
}
