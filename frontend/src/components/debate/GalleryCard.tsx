'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Link2, Check } from 'lucide-react';
import { TierBadge } from './TierBadge';

type GalleryEntry = {
  id: string;
  name: string;
  description: string | null;
  provider: string;
  model_id: string;
  image_url: string | null;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  tier: string;
  owner_nickname: string;
};

type Props = { entry: GalleryEntry; onClone: (id: string, name: string) => Promise<void> };

export function GalleryCard({ entry, onClone }: Props) {
  const [cloning, setCloning] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [newName, setNewName] = useState(`${entry.name} (복제)`);
  const [copied, setCopied] = useState(false);

  const handleShare = async () => {
    const url = `${window.location.origin}/debate/agents/${entry.id}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClone = async () => {
    setCloning(true);
    try {
      await onClone(entry.id, newName);
      setShowModal(false);
    } finally {
      setCloning(false);
    }
  };

  return (
    <div className="bg-bg-surface border border-border rounded-xl p-5 flex flex-col gap-4 hover:border-primary/30 transition-colors">
      <Link
        href={`/debate/agents/${entry.id}`}
        className="flex items-start gap-3 no-underline hover:opacity-80 transition-opacity"
      >
        {entry.image_url ? (
          <img
            src={entry.image_url}
            alt={entry.name}
            className="w-11 h-11 rounded-lg object-cover shrink-0"
          />
        ) : (
          <div className="w-11 h-11 rounded-lg bg-primary/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
            {entry.name[0]}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-text text-sm truncate">{entry.name}</span>
            <TierBadge tier={entry.tier} />
          </div>
          <div className="text-xs text-text-muted mt-0.5">
            {entry.owner_nickname} · {entry.provider}
          </div>
        </div>
      </Link>

      {entry.description && (
        <p className="text-sm text-text-muted line-clamp-2">{entry.description}</p>
      )}

      <div className="flex items-center justify-between text-xs">
        <div className="flex gap-2 text-text-muted">
          <span className="text-green-400">{entry.wins}W</span>
          <span className="text-red-400">{entry.losses}L</span>
          <span>{entry.draws}D</span>
          <span className="font-semibold text-text">ELO {entry.elo_rating}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleShare}
            title="링크 복사"
            className="flex items-center gap-1 text-text-muted hover:text-text transition-colors"
          >
            {copied ? <Check size={13} className="text-green-400" /> : <Link2 size={13} />}
            <span className="text-xs">{copied ? '복사됨' : '공유'}</span>
          </button>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="text-primary hover:underline text-xs"
          >
            복제
          </button>
        </div>
      </div>

      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setShowModal(false)}
        >
          <div
            className="bg-bg-surface border border-border rounded-2xl p-6 w-80"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="font-semibold text-text mb-3">에이전트 복제</h3>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-text mb-4"
              placeholder="새 이름"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="flex-1 py-2 rounded-lg border border-border text-sm text-text-muted hover:text-text"
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleClone}
                disabled={cloning || !newName.trim()}
                className="flex-1 py-2 rounded-lg bg-primary text-white text-sm disabled:opacity-50"
              >
                {cloning ? '복제 중...' : '복제'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export type { GalleryEntry };
