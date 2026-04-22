'use client';

import { ArrowLeft } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { AgentForm } from '@/components/debate/AgentForm';

export default function CreateAgentPage() {
  const router = useRouter();

  return (
    <div className="max-w-[700px] mx-auto py-6 px-4">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1 text-sm text-text-muted hover:text-text mb-4 bg-transparent border-none cursor-pointer p-0"
      >
        <ArrowLeft size={14} />
        뒤로가기
      </button>

      <h1 className="page-title mb-5">에이전트 생성</h1>
      <AgentForm />
    </div>
  );
}
