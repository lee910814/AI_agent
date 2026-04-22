'use client';

import { useEffect, useState, useCallback } from 'react';
import { Plus, Pencil, Gem } from 'lucide-react';
import { api } from '@/lib/api';
import { DataTable } from '@/components/admin/DataTable';
import { toast } from '@/stores/toastStore';

type LLMModel = {
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
  total_requests: number;
  total_tokens: number;
  total_cost: number;
};

type ModelUsageStats = {
  llm_model_id: string;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
};

type FormData = {
  provider: string;
  model_id: string;
  display_name: string;
  input_cost_per_1m: string;
  output_cost_per_1m: string;
  max_context_length: string;
  is_adult_only: boolean;
  tier: string;
  credit_per_1k_tokens: string;
};

const EMPTY_FORM: FormData = {
  provider: 'openai',
  model_id: '',
  display_name: '',
  input_cost_per_1m: '',
  output_cost_per_1m: '',
  max_context_length: '',
  is_adult_only: false,
  tier: 'economy',
  credit_per_1k_tokens: '1',
};

const PROVIDERS = ['openai', 'anthropic', 'google', 'runpod'] as const;
const TIERS = [
  { value: 'economy', label: 'Economy' },
  { value: 'standard', label: 'Standard' },
  { value: 'premium', label: 'Premium' },
] as const;

export default function AdminModelsPage() {
  const [models, setModels] = useState<LLMModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const [modelsRes, statsRes] = await Promise.all([
        api.get<{
          items: Omit<LLMModel, 'total_requests' | 'total_tokens' | 'total_cost'>[];
          total: number;
        }>('/admin/models'),
        api
          .get<ModelUsageStats[]>('/admin/models/usage-stats')
          .catch(() => [] as ModelUsageStats[]),
      ]);

      const statsMap = new Map(statsRes.map((s: ModelUsageStats) => [s.llm_model_id, s]));

      const merged = (modelsRes.items ?? []).map((m) => {
        const stats = statsMap.get(m.id);
        return {
          ...m,
          total_requests: stats?.total_requests ?? 0,
          total_tokens: (stats?.total_input_tokens ?? 0) + (stats?.total_output_tokens ?? 0),
          total_cost: stats?.total_cost ?? 0,
        };
      });
      setModels(merged);
    } catch {
      // handled
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const toggleActive = async (id: string, current: boolean) => {
    try {
      await api.put(`/admin/models/${id}`, { is_active: !current });
      fetchModels();
    } catch {
      toast.error('모델 상태 변경에 실패했습니다');
    }
  };

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (model: LLMModel) => {
    setEditingId(model.id);
    setForm({
      provider: model.provider,
      model_id: model.model_id,
      display_name: model.display_name,
      input_cost_per_1m: String(model.input_cost_per_1m),
      output_cost_per_1m: String(model.output_cost_per_1m),
      max_context_length: String(model.max_context_length),
      is_adult_only: model.is_adult_only,
      tier: model.tier,
      credit_per_1k_tokens: String(model.credit_per_1k_tokens),
    });
    setModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;

    const payload = {
      provider: form.provider,
      model_id: form.model_id,
      display_name: form.display_name,
      input_cost_per_1m: parseFloat(form.input_cost_per_1m),
      output_cost_per_1m: parseFloat(form.output_cost_per_1m),
      max_context_length: parseInt(form.max_context_length, 10),
      is_adult_only: form.is_adult_only,
      tier: form.tier,
      credit_per_1k_tokens: parseInt(form.credit_per_1k_tokens, 10),
    };

    if (isNaN(payload.input_cost_per_1m) || isNaN(payload.output_cost_per_1m)) {
      toast.error('비용을 올바르게 입력해주세요');
      return;
    }
    if (isNaN(payload.max_context_length) || payload.max_context_length <= 0) {
      toast.error('컨텍스트 길이를 올바르게 입력해주세요');
      return;
    }
    if (isNaN(payload.credit_per_1k_tokens) || payload.credit_per_1k_tokens < 1) {
      toast.error('크레딧 비용은 1 이상이어야 합니다');
      return;
    }

    setSubmitting(true);
    try {
      if (editingId) {
        await api.put(`/admin/models/${editingId}`, payload);
        toast.success('모델이 수정되었습니다');
      } else {
        await api.post('/admin/models', payload);
        toast.success('모델이 등록되었습니다');
      }
      setModalOpen(false);
      fetchModels();
    } catch {
      toast.error(editingId ? '모델 수정에 실패했습니다' : '모델 등록에 실패했습니다');
    } finally {
      setSubmitting(false);
    }
  };

  const updateField = (field: keyof FormData, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const columns = [
    { key: 'display_name' as const, label: '모델명' },
    { key: 'provider' as const, label: 'Provider' },
    { key: 'model_id' as const, label: 'Model ID' },
    {
      key: 'tier' as const,
      label: '티어',
      render: (val: unknown) => {
        const tier = String(val);
        const colors: Record<string, string> = {
          economy: 'bg-success/20 text-success',
          standard: 'bg-warning/20 text-warning',
          premium: 'bg-error/20 text-error',
        };
        return (
          <span className={`py-0.5 px-2 rounded-badge text-xs font-semibold ${colors[tier] ?? ''}`}>
            {tier}
          </span>
        );
      },
    },
    {
      key: 'credit_per_1k_tokens' as const,
      label: '크레딧/1K',
      render: (val: unknown) => (
        <span className="inline-flex items-center gap-1 font-semibold">
          <Gem size={12} className="text-primary" />
          {Number(val)}석
        </span>
      ),
    },
    {
      key: 'input_cost_per_1m' as const,
      label: '입력 비용',
      render: (val: unknown) => `$${Number(val).toFixed(2)}`,
    },
    {
      key: 'output_cost_per_1m' as const,
      label: '출력 비용',
      render: (val: unknown) => `$${Number(val).toFixed(2)}`,
    },
    {
      key: 'max_context_length' as const,
      label: '컨텍스트',
      render: (val: unknown) => `${(Number(val) / 1000).toFixed(0)}K`,
    },
    {
      key: 'total_requests' as const,
      label: '총 요청',
      render: (val: unknown) => Number(val).toLocaleString(),
    },
    {
      key: 'total_tokens' as const,
      label: '총 토큰',
      render: (val: unknown) => {
        const n = Number(val);
        if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
        if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
        return String(n);
      },
    },
    {
      key: 'total_cost' as const,
      label: '총 비용',
      render: (val: unknown) => `$${Number(val).toFixed(2)}`,
    },
    {
      key: 'is_adult_only' as const,
      label: '성인전용',
      render: (val: unknown) => (val ? '예' : '-'),
    },
    {
      key: 'is_active' as const,
      label: '상태',
      render: (_: unknown, row: LLMModel) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleActive(row.id, row.is_active);
          }}
          className={`py-1 px-3 min-w-[4rem] text-center rounded-badge border-none text-white text-xs font-semibold cursor-pointer ${
            row.is_active ? 'bg-success' : 'bg-text-muted'
          }`}
        >
          {row.is_active ? '활성' : '비활성'}
        </button>
      ),
    },
    {
      key: 'id' as const,
      label: '',
      render: (_: unknown, row: LLMModel) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            openEdit(row);
          }}
          className="p-1.5 rounded-lg bg-transparent border-none text-text-muted hover:text-primary hover:bg-bg-hover cursor-pointer transition-colors"
          title="수정"
        >
          <Pencil size={14} />
        </button>
      ),
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="page-title mb-0">LLM 모델 관리</h1>
        <button onClick={openCreate} className="btn-primary flex items-center gap-1.5 text-sm">
          <Plus size={16} />
          모델 추가
        </button>
      </div>

      <div className="card">
        <DataTable columns={columns} data={models} loading={loading} />
      </div>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={() => setModalOpen(false)}
        >
          <div
            className="bg-bg-surface rounded-2xl shadow-lg w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <h2 className="text-lg font-bold text-text mb-4">
                {editingId ? '모델 수정' : '모델 추가'}
              </h2>
              <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-text-muted">Provider</label>
                    <select
                      value={form.provider}
                      onChange={(e) => updateField('provider', e.target.value)}
                      className="input text-sm"
                    >
                      {PROVIDERS.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-text-muted">Model ID</label>
                    <input
                      type="text"
                      value={form.model_id}
                      onChange={(e) => updateField('model_id', e.target.value)}
                      placeholder="gpt-4o"
                      required
                      className="input text-sm"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-text-muted">표시 이름</label>
                  <input
                    type="text"
                    value={form.display_name}
                    onChange={(e) => updateField('display_name', e.target.value)}
                    placeholder="GPT-4o"
                    required
                    className="input text-sm"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-text-muted">티어</label>
                    <select
                      value={form.tier}
                      onChange={(e) => updateField('tier', e.target.value)}
                      className="input text-sm"
                    >
                      {TIERS.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-text-muted">크레딧/1K 토큰</label>
                    <div className="relative">
                      <input
                        type="number"
                        min="1"
                        value={form.credit_per_1k_tokens}
                        onChange={(e) => updateField('credit_per_1k_tokens', e.target.value)}
                        required
                        className="input text-sm pr-8"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-text-muted">
                        석
                      </span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-text-muted">
                      입력 비용 ($/1M tokens)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.input_cost_per_1m}
                      onChange={(e) => updateField('input_cost_per_1m', e.target.value)}
                      placeholder="2.50"
                      required
                      className="input text-sm"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-text-muted">
                      출력 비용 ($/1M tokens)
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.output_cost_per_1m}
                      onChange={(e) => updateField('output_cost_per_1m', e.target.value)}
                      placeholder="10.00"
                      required
                      className="input text-sm"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-xs font-semibold text-text-muted">
                    최대 컨텍스트 길이 (토큰)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={form.max_context_length}
                    onChange={(e) => updateField('max_context_length', e.target.value)}
                    placeholder="128000"
                    required
                    className="input text-sm"
                  />
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_adult_only}
                    onChange={(e) => updateField('is_adult_only', e.target.checked)}
                    className="w-4 h-4 accent-primary"
                  />
                  <span className="text-sm text-text">성인전용 모델</span>
                </label>

                <div className="flex justify-end gap-2 mt-2">
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    className="btn-secondary text-sm px-4 py-2"
                  >
                    취소
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="btn-primary text-sm px-4 py-2"
                  >
                    {submitting ? '저장 중...' : editingId ? '수정' : '등록'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
