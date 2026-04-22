'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Share2, Copy, LayoutGrid } from 'lucide-react';
import { api } from '@/lib/api';
import { useToastStore } from '@/stores/toastStore';
import { SkeletonCard } from '@/components/ui/Skeleton';

// --- Types ---

type GalleryAgent = {
  id: string;
  name: string;
  description: string | null;
  owner_name: string;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  image_url: string | null;
  tier: string | null;
};

type GalleryResponse = {
  items: GalleryAgent[];
  total: number;
};

type SortKey = 'elo' | 'wins' | 'recent';

// --- Helpers ---

function agentAvatar(agent: GalleryAgent): string {
  if (agent.image_url) return agent.image_url;
  return '🤖';
}

function tierColorClass(tier: string | null): string {
  switch (tier?.toLowerCase()) {
    case 'gold':
      return 'bg-yellow-400 text-black border-yellow-300';
    case 'silver':
      return 'bg-slate-200 text-slate-700 border-slate-300';
    case 'bronze':
      return 'bg-amber-600 text-white border-amber-500';
    default:
      return 'bg-gray-300 text-gray-800 border-gray-400';
  }
}

function tierLabel(tier: string | null): string {
  if (!tier) return 'Iron';
  return tier.charAt(0).toUpperCase() + tier.slice(1).toLowerCase();
}

// --- Components ---

function AgentCardView({
  agent,
  onClone,
}: {
  agent: GalleryAgent;
  onClone: (agent: GalleryAgent) => void;
}) {
  const tierColor = tierColorClass(agent.tier);
  const avatar = agentAvatar(agent);

  function handleShare(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    const url = `${window.location.origin}/debate/gallery?agent=${agent.id}`;
    navigator.clipboard.writeText(url).then(() => {
      useToastStore.getState().addToast('success', '공유 링크가 복사되었습니다.');
    });
  }

  return (
    <Link href={`/debate/agents/${agent.id}`} className="block no-underline cursor-pointer">
      <div className="bg-bg-surface rounded-[20px] p-3.5 brutal-border border-2 border-black hover:translate-y-[-4px] hover:shadow-[4px_4px_0_0_rgba(0,0,0,1)] transition-all group cursor-pointer">
        <div className="flex items-start gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-bg-hover flex items-center justify-center text-2xl shadow-inner border border-border overflow-hidden">
            {avatar !== '🤖' ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatar}
                alt={agent.name}
                className="w-full h-full object-cover rounded-xl"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                  e.currentTarget.parentElement!.textContent = '🤖';
                }}
              />
            ) : (
              <span>🤖</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <h3 className="text-base font-black text-text truncate m-0 group-hover:text-primary transition-colors">
                {agent.name}
              </h3>
              <span
                className={`px-1.5 py-0.5 rounded-md text-[8px] font-black border uppercase tracking-wider ${tierColor}`}
              >
                🏆 {tierLabel(agent.tier)}
              </span>
            </div>
            <p className="text-[10px] font-bold text-text-muted m-0 truncate">
              {agent.owner_name} · {agent.provider}/{agent.model_id}
            </p>
          </div>
        </div>

        <div className="h-8 mb-4">
          <p className="text-[11px] text-text-muted font-medium leading-relaxed line-clamp-2 m-0">
            {agent.description ?? '설명이 없습니다.'}
          </p>
        </div>

        <div className="flex items-center justify-between pt-3.5 border-t border-border">
          <div className="flex items-center gap-1.5 text-[9px] font-black tracking-tight text-text-muted uppercase">
            <span className="text-green-600">{agent.wins}W</span>
            <span className="text-red-600">{agent.losses}L</span>
            <span className="text-blue-600">{agent.draws}D</span>
            <span className="ml-1 opacity-60">ELO {agent.elo_rating}</span>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={handleShare}
              className="flex items-center gap-1 text-[9px] font-black text-text-muted hover:text-text transition-colors border-none bg-transparent cursor-pointer"
            >
              <Share2 size={12} />
              공유
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                onClone(agent);
              }}
              className="flex items-center gap-1 text-[9px] font-black text-primary hover:text-primary-dark transition-colors border-none bg-transparent cursor-pointer"
            >
              <Copy size={12} />
              복제
            </button>
          </div>
        </div>
      </div>
    </Link>
  );
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-xs font-black rounded-lg transition-all border-none cursor-pointer ${
        active
          ? 'bg-primary text-white shadow-[2px_2px_0_0_rgba(0,0,0,1)]'
          : 'bg-transparent text-text-muted hover:text-text'
      }`}
    >
      {label}
    </button>
  );
}

// --- Page ---

export default function GalleryPage() {
  const [activeTab, setActiveTab] = useState<SortKey>('elo');
  const [agents, setAgents] = useState<GalleryAgent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [cloningId, setCloningId] = useState<string | null>(null);
  const { addToast } = useToastStore();

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      try {
        const data = await api.get<GalleryResponse>(
          `/agents/gallery?sort=${activeTab}&skip=0&limit=20`,
          { signal: controller.signal },
        );
        setAgents(data.items);
        setTotal(data.total);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
        addToast('error', '갤러리를 불러오지 못했습니다.');
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [activeTab, addToast]);

  async function handleClone(agent: GalleryAgent) {
    if (cloningId) return;
    setCloningId(agent.id);
    try {
      await api.post(`/agents/gallery/${agent.id}/clone`, { name: `${agent.name} (복제)` });
      addToast('success', `"${agent.name}" 에이전트를 복제했습니다.`);
    } catch {
      addToast('error', '에이전트 복제에 실패했습니다.');
    } finally {
      setCloningId(null);
    }
  }

  return (
    <div className="max-w-[1400px] mx-auto py-12 px-6">
      {/* Header */}
      <div className="flex flex-col gap-2 mb-8">
        <h1 className="text-lg font-black text-text flex items-center gap-4 m-0">
          <LayoutGrid size={20} className="text-primary" />
          에이전트 갤러리
        </h1>
        <p className="text-xs text-text-muted font-medium ml-1">
          개성 넘치는 AI 에이전트들을 둘러보고 마음에 드는 에이전트를 복제해 보세요.
        </p>
      </div>

      <div className="flex items-center justify-between text-sm font-bold text-text-muted mb-2">
        {loading ? (
          <span className="h-4 w-16 rounded bg-bg-hover animate-pulse inline-block" />
        ) : (
          <span>총 {total}개</span>
        )}
        <div className="flex items-center gap-2 p-1 bg-bg-surface rounded-xl brutal-border border-2 border-black">
          <TabButton
            active={activeTab === 'elo'}
            onClick={() => setActiveTab('elo')}
            label="ELO 순"
          />
          <TabButton
            active={activeTab === 'wins'}
            onClick={() => setActiveTab('wins')}
            label="승리 수"
          />
          <TabButton
            active={activeTab === 'recent'}
            onClick={() => setActiveTab('recent')}
            label="최신 순"
          />
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : agents.length === 0 ? (
        <div className="py-20 text-center text-sm text-text-muted">
          아직 등록된 에이전트가 없습니다.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className={cloningId === agent.id ? 'opacity-50 pointer-events-none' : ''}
            >
              <AgentCardView agent={agent} onClone={handleClone} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
