'use client';

import { useEffect, useState } from 'react';
import { Trophy, Zap, Brain, ChevronRight, Cpu, DollarSign } from 'lucide-react';
import { api } from '@/lib/api';
import { useToastStore } from '@/stores/toastStore';

type LLMModelResponse = {
  id: string;
  provider: string;
  model_id: string;
  display_name: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  max_context_length: number;
  is_adult_only: boolean;
  is_active: boolean;
  tier: string;
  credit_per_1k_tokens: number;
  created_at: string;
};

/** provider 문자열을 UI 표시용 색상 클래스로 변환 */
function providerColor(provider: string): string {
  switch (provider.toLowerCase()) {
    case 'openai':
      return 'bg-emerald-500';
    case 'anthropic':
      return 'bg-orange-500';
    case 'google':
      return 'bg-blue-500';
    case 'runpod':
      return 'bg-purple-500';
    default:
      return 'bg-gray-500';
  }
}

/** provider 문자열을 이모지 로고로 변환 */
function providerLogo(provider: string): string {
  switch (provider.toLowerCase()) {
    case 'openai':
      return '🟢';
    case 'anthropic':
      return '🟠';
    case 'google':
      return '🔵';
    case 'runpod':
      return '🟣';
    default:
      return '⚫';
  }
}

/** 백엔드 tier 값을 UI 등급 배지 색상으로 변환 */
function tierBadgeColor(tier: string): string {
  switch (tier.toLowerCase()) {
    case 'premium':
      return 'bg-yellow-400 text-black';
    case 'standard':
      return 'bg-blue-500 text-white';
    case 'economy':
      return 'bg-green-500 text-white';
    default:
      return 'bg-gray-400 text-white';
  }
}

/** 비용(USD/1M) → 1K 토큰 기준 표시 문자열 */
function formatCostPer1k(costPer1m: number): string {
  if (costPer1m === 0) return '무료';
  const per1k = costPer1m / 1000;
  return `$${per1k.toFixed(4)}`;
}

function ModelListSkeleton() {
  return (
    <div className="flex flex-col gap-2 animate-pulse">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="w-full flex items-center gap-3 px-3 py-3 rounded-xl bg-gray-100 border-2 border-transparent"
        >
          <div className="w-6 h-6 rounded bg-gray-200 shrink-0" />
          <div className="w-9 h-9 rounded-lg bg-gray-200 shrink-0" />
          <div className="flex-1">
            <div className="h-3 w-2/3 rounded bg-gray-200 mb-1.5" />
            <div className="h-2.5 w-1/2 rounded bg-gray-200" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ModelDetailSkeleton() {
  return (
    <div className="bg-white rounded-xl brutal-border brutal-shadow-sm overflow-hidden animate-pulse">
      <div className="bg-gray-200 px-6 py-5 h-28" />
      <div className="grid grid-cols-2 md:grid-cols-4 border-b-2 border-black/10">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="p-4 text-center border-r border-black/10 last:border-r-0">
            <div className="h-5 w-1/2 rounded bg-gray-200 mx-auto mb-1" />
            <div className="h-3 w-2/3 rounded bg-gray-200 mx-auto" />
          </div>
        ))}
      </div>
      <div className="p-5">
        <div className="h-3 w-1/4 rounded bg-gray-200 mb-3" />
        <div className="grid grid-cols-3 gap-3 mb-5">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-14 rounded-xl bg-gray-100" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function AIProfilePage() {
  const [models, setModels] = useState<LLMModelResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { addToast } = useToastStore();

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      try {
        const data = await api.get<LLMModelResponse[]>('/models', { signal: controller.signal });
        // is_active인 모델만 표시, created_at 기준 최신순 정렬
        const active = data.filter((m) => m.is_active);
        setModels(active);
        if (active.length > 0) {
          setSelectedId(active[0].id);
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
        addToast('error', '모델 목록을 불러오지 못했습니다.');
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [addToast]);

  const selectedModel = models.find((m) => m.id === selectedId) ?? null;

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* 페이지 타이틀 */}
      <div className="flex items-center gap-2 mb-5">
        <Brain size={24} className="text-primary" />
        <h1 className="text-2xl font-black text-black m-0">AI Profile</h1>
      </div>
      <p className="text-sm text-gray-500 mb-6 -mt-2">
        토론에 사용되는 LLM 모델들의 등록 정보와 스펙을 확인하세요.
      </p>

      {/* 2컬럼 그리드 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* ─── 왼쪽: LLM 모델 목록 ─── */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-xl brutal-border brutal-shadow-sm p-4">
            <h2 className="text-sm font-black text-black flex items-center gap-2 mb-4">
              <Trophy size={16} className="text-yellow-500" />
              등록된 LLM 모델
            </h2>

            {loading ? (
              <ModelListSkeleton />
            ) : models.length === 0 ? (
              <div className="py-10 text-center text-sm text-gray-400">
                사용 가능한 모델이 없습니다.
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {models.map((model, idx) => {
                  const isSelected = selectedId === model.id;
                  return (
                    <button
                      key={model.id}
                      onClick={() => setSelectedId(model.id)}
                      className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl border-2 text-left cursor-pointer transition-all ${
                        isSelected
                          ? 'border-primary bg-primary/5 shadow-md'
                          : 'border-transparent bg-gray-50 hover:bg-gray-100 hover:border-gray-200'
                      }`}
                    >
                      {/* 순위 */}
                      <span
                        className={`text-xs font-black w-6 text-center shrink-0 ${
                          idx === 0
                            ? 'text-yellow-500'
                            : idx === 1
                              ? 'text-gray-400'
                              : idx === 2
                                ? 'text-amber-600'
                                : 'text-gray-400'
                        }`}
                      >
                        {idx < 3 ? <Trophy size={14} className="mx-auto" /> : `#${idx + 1}`}
                      </span>

                      {/* 모델 로고 */}
                      <div
                        className={`w-9 h-9 rounded-lg ${providerColor(model.provider)} flex items-center justify-center text-white text-sm font-bold shrink-0`}
                      >
                        {providerLogo(model.provider)}
                      </div>

                      {/* 모델 정보 */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-bold text-black truncate">
                            {model.display_name}
                          </span>
                          <span
                            className={`text-[10px] font-black px-1.5 py-0.5 rounded ${tierBadgeColor(model.tier)}`}
                          >
                            {model.tier.toUpperCase()}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[11px] text-gray-400 capitalize">
                            {model.provider}
                          </span>
                          <span className="text-[11px] text-gray-300">·</span>
                          <span className="text-[11px] text-gray-400">{model.model_id}</span>
                        </div>
                      </div>

                      {/* 화살표 */}
                      <ChevronRight
                        size={16}
                        className={`shrink-0 ${isSelected ? 'text-primary' : 'text-gray-300'}`}
                      />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* ─── 오른쪽: 선택된 모델 상세 정보 ─── */}
        <div className="lg:col-span-3">
          {loading ? (
            <ModelDetailSkeleton />
          ) : selectedModel === null ? (
            <div className="bg-white rounded-xl brutal-border brutal-shadow-sm p-10 text-center text-sm text-gray-400">
              모델을 선택하면 상세 정보를 확인할 수 있습니다.
            </div>
          ) : (
            <div className="bg-white rounded-xl brutal-border brutal-shadow-sm overflow-hidden sticky top-4">
              {/* 모델 헤더 */}
              <div className={`${providerColor(selectedModel.provider)} px-6 py-5 text-white`}>
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-3xl">{providerLogo(selectedModel.provider)}</span>
                  <div>
                    <h2 className="text-xl font-black m-0">{selectedModel.display_name}</h2>
                    <p className="text-white/70 text-sm capitalize">{selectedModel.provider}</p>
                  </div>
                  <span
                    className={`ml-auto text-sm font-black px-3 py-1 rounded-lg ${tierBadgeColor(selectedModel.tier)}`}
                  >
                    {selectedModel.tier.toUpperCase()} Tier
                  </span>
                </div>
                <p className="text-white/80 text-sm leading-relaxed m-0">
                  모델 ID: <span className="font-mono font-bold">{selectedModel.model_id}</span>
                </p>
              </div>

              {/* 핵심 지표 그리드 */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-0 border-b-2 border-black/10">
                <div className="p-4 text-center border-r border-black/10">
                  <div className="flex items-center justify-center gap-1 text-primary mb-1">
                    <DollarSign size={14} />
                  </div>
                  <p className="text-lg font-black text-black m-0">
                    {formatCostPer1k(selectedModel.input_cost_per_1m)}
                  </p>
                  <p className="text-[11px] text-gray-400 m-0">입력 (1K 토큰)</p>
                </div>
                <div className="p-4 text-center border-r border-black/10">
                  <div className="flex items-center justify-center gap-1 text-blue-500 mb-1">
                    <DollarSign size={14} />
                  </div>
                  <p className="text-lg font-black text-black m-0">
                    {formatCostPer1k(selectedModel.output_cost_per_1m)}
                  </p>
                  <p className="text-[11px] text-gray-400 m-0">출력 (1K 토큰)</p>
                </div>
                <div className="p-4 text-center border-r border-black/10">
                  <div className="flex items-center justify-center gap-1 text-yellow-500 mb-1">
                    <Cpu size={14} />
                  </div>
                  <p className="text-lg font-black text-black m-0">
                    {selectedModel.max_context_length.toLocaleString()}
                  </p>
                  <p className="text-[11px] text-gray-400 m-0">최대 컨텍스트</p>
                </div>
                <div className="p-4 text-center">
                  <div className="flex items-center justify-center gap-1 text-green-500 mb-1">
                    <Zap size={14} />
                  </div>
                  <p className="text-lg font-black text-black m-0">
                    {selectedModel.credit_per_1k_tokens}
                  </p>
                  <p className="text-[11px] text-gray-400 m-0">크레딧/1K</p>
                </div>
              </div>

              {/* 스펙 정보 */}
              <div className="p-5">
                <h3 className="text-sm font-black text-black mb-3">📋 모델 스펙</h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3 border border-gray-100">
                    <span className="text-[12px] text-gray-500 font-semibold">Provider</span>
                    <span className="text-sm font-bold text-black capitalize">
                      {selectedModel.provider}
                    </span>
                  </div>
                  <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3 border border-gray-100">
                    <span className="text-[12px] text-gray-500 font-semibold">Model ID</span>
                    <span className="text-sm font-bold text-black font-mono">
                      {selectedModel.model_id}
                    </span>
                  </div>
                  <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3 border border-gray-100">
                    <span className="text-[12px] text-gray-500 font-semibold">성인 전용</span>
                    <span
                      className={`text-sm font-bold ${selectedModel.is_adult_only ? 'text-red-500' : 'text-gray-400'}`}
                    >
                      {selectedModel.is_adult_only ? '예' : '아니오'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between bg-gray-50 rounded-xl px-4 py-3 border border-gray-100">
                    <span className="text-[12px] text-gray-500 font-semibold">상태</span>
                    <span
                      className={`text-sm font-bold ${selectedModel.is_active ? 'text-green-600' : 'text-gray-400'}`}
                    >
                      {selectedModel.is_active ? '활성' : '비활성'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
