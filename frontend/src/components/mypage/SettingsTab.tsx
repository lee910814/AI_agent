/** 마이페이지 설정 탭. LLM 모델 목록 표시. */
'use client';

import { useEffect, useState } from 'react';
import { Bot } from 'lucide-react';
import { api } from '@/lib/api';
import { toast } from '@/stores/toastStore';

type LLMModel = {
  id: string;
  display_name: string;
  provider: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  max_context_length: number;
  is_adult_only: boolean;
  is_active: boolean;
  tier?: string;
  credit_per_1k_tokens: number;
};

export function SettingsTab() {
  const [models, setModels] = useState<LLMModel[]>([]);

  useEffect(() => {
    api
      .get<LLMModel[]>('/models')
      .then(setModels)
      .catch(() => toast.error('모델 목록을 불러오지 못했습니다'));
  }, []);

  return (
    <>
      <section className="card p-6">
        <h2 className="section-title flex items-center gap-2">
          <Bot size={20} className="text-primary" />
          LLM 모델 정보
        </h2>
        <p className="text-text-secondary text-sm mb-4">
          현재 플랫폼에서 지원하는 AI 모델 목록입니다.
        </p>
        <div className="flex flex-col gap-3">
          {models
            .filter((m) => m.is_active)
            .map((model) => (
              <div
                key={model.id}
                className="p-4 rounded-xl border-2 border-border bg-bg-surface transition-colors duration-200"
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[15px] font-semibold">{model.display_name}</span>
                  <span className="text-xs text-text-muted uppercase">{model.provider}</span>
                </div>
                <div className="flex gap-4 text-[13px] text-text-secondary mb-1">
                  <span>입력: ${model.input_cost_per_1m}/1M</span>
                  <span>출력: ${model.output_cost_per_1m}/1M</span>
                </div>
                <div className="text-xs text-text-muted">
                  컨텍스트: {(model.max_context_length / 1000).toFixed(0)}K
                  {model.is_adult_only && ' | 성인전용'}
                  {' | '}
                  {model.credit_per_1k_tokens}석/1K토큰
                </div>
              </div>
            ))}
        </div>
      </section>
    </>
  );
}
