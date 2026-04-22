'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Bot } from 'lucide-react';
import { api } from '@/lib/api';
import type { DebateAgent, AgentVersion } from '@/stores/debateAgentStore';
import { AgentForm } from '@/components/debate/AgentForm';
import { SkeletonCard } from '@/components/ui/Skeleton';

export default function EditAgentPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<DebateAgent | null>(null);
  const [latestVersion, setLatestVersion] = useState<AgentVersion | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api.get<DebateAgent>(`/agents/${id}`),
      api.get<AgentVersion[]>(`/agents/${id}/versions`),
    ])
      .then(([agentData, versions]) => {
        setAgent(agentData);
        setLatestVersion(versions[0] ?? null);
      })
      .catch(() => setError('에이전트 정보를 불러오지 못했습니다.'));
  }, [id]);

  if (error) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="max-w-[700px] mx-auto py-6 px-4">
        <SkeletonCard />
        <div className="mt-3">
          <SkeletonCard />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <Link
        href={`/debate/agents/${id}`}
        className="flex items-center gap-1 text-sm text-text-muted no-underline hover:text-text mb-5"
      >
        <ArrowLeft size={14} />
        에이전트 프로필로 돌아가기
      </Link>

      {/* 헤더 */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0 overflow-hidden">
          {agent.image_url ? (
            <img src={agent.image_url} alt={agent.name} className="w-full h-full object-cover" />
          ) : (
            <Bot size={20} />
          )}
        </div>
        <div>
          <h1 className="text-lg font-bold text-text">에이전트 수정</h1>
          <p className="text-xs text-text-muted">{agent.name}</p>
        </div>
      </div>

      <AgentForm
        initialData={{
          id: agent.id,
          name: agent.name,
          description: agent.description ?? '',
          provider: agent.provider,
          model_id: agent.model_id,
          image_url: agent.image_url ?? undefined,
          template_id: agent.template_id ?? undefined,
          customizations: agent.customizations ?? undefined,
          system_prompt: latestVersion?.system_prompt,
        }}
        isEdit
      />
    </div>
  );
}
