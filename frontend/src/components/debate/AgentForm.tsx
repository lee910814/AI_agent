'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Camera, CheckCircle2, Coins, Loader2, X, XCircle } from 'lucide-react';
import { useDebateAgentStore } from '@/stores/debateAgentStore';
import type { AgentTemplate, CreateAgentPayload } from '@/stores/debateAgentStore';
import { useToastStore } from '@/stores/toastStore';
import { api } from '@/lib/api';
import { TemplateCard } from './TemplateCard';
import { TemplateCustomizer } from './TemplateCustomizer';

type Props = {
  initialData?: Partial<CreateAgentPayload> & {
    id?: string;
    image_url?: string;
    name_changed_at?: string | null;
    is_system_prompt_public?: boolean;
    is_profile_public?: boolean;
    use_platform_credits?: boolean;
  };
  isEdit?: boolean;
};

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google' },
  { value: 'runpod', label: 'RunPod' },
  { value: 'local', label: '로컬 에이전트' },
];

const MODEL_OPTIONS: Record<string, { value: string; label: string; ctx: string }[]> = {
  openai: [
    // ── GPT-5 계열 (최신) ──────────────────────────
    { value: 'gpt-5.2', label: '★ GPT-5.2', ctx: '400K' },
    { value: 'gpt-5.2-pro', label: '★ GPT-5.2 Pro', ctx: '400K' },
    { value: 'gpt-5.1', label: 'GPT-5.1', ctx: '200K' },
    { value: 'gpt-5', label: 'GPT-5', ctx: '128K' },
    { value: 'gpt-5-mini', label: 'GPT-5 Mini', ctx: '128K' },
    // ── GPT-4.1 / 4o ──────────────────────────────
    { value: 'gpt-4.1', label: 'GPT-4.1', ctx: '1M' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini', ctx: '1M' },
    { value: 'gpt-4.1-nano', label: 'GPT-4.1 Nano', ctx: '1M' },
    { value: 'gpt-4o', label: 'GPT-4o', ctx: '128K' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini', ctx: '128K' },
    // ── 추론 모델 ─────────────────────────────────
    { value: 'o3', label: 'o3  (추론)', ctx: '200K' },
    { value: 'o3-pro', label: 'o3 Pro  (추론)', ctx: '200K' },
    { value: 'o4-mini', label: 'o4-mini  (추론)', ctx: '200K' },
  ],
  anthropic: [
    { value: 'claude-opus-4-6', label: '★ Claude Opus 4.6', ctx: '200K' },
    { value: 'claude-sonnet-4-6', label: '★ Claude Sonnet 4.6', ctx: '200K' },
    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5', ctx: '200K' },
    { value: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5', ctx: '200K' },
    { value: 'claude-opus-4-5', label: 'Claude Opus 4.5', ctx: '200K' },
  ],
  google: [
    // ── Gemini 3 계열 (최신, Preview) ─────────────
    { value: 'gemini-3.1-pro-preview', label: '★ Gemini 3.1 Pro Preview', ctx: '1M' },
    { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash Preview', ctx: '1M' },
    // ── Gemini 2.5 계열 (안정) ────────────────────
    { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro', ctx: '1M' },
    { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash', ctx: '1M' },
    { value: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash-Lite', ctx: '1M' },
  ],
  runpod: [
    {
      value: 'meta-llama/Meta-Llama-3.1-70B-Instruct',
      label: 'Llama 3.1 70B Instruct',
      ctx: '128K',
    },
    { value: 'meta-llama/Llama-3.3-70B-Instruct', label: 'Llama 3.3 70B Instruct', ctx: '128K' },
    { value: 'mistralai/Mixtral-8x7B-Instruct-v0.1', label: 'Mixtral 8x7B Instruct', ctx: '32K' },
    { value: 'Qwen/Qwen2.5-72B-Instruct', label: 'Qwen 2.5 72B Instruct', ctx: '128K' },
  ],
  local: [],
};

const BYOK_PROVIDERS = ['openai', 'anthropic', 'google'];

type ApiModel = {
  id: string;
  provider: string;
  model_id: string;
  display_name: string;
  max_context_length: number;
  is_active: boolean;
  tier: string;
};

function formatCtx(maxContextLength: number): string {
  if (maxContextLength >= 1_000_000) {
    return `${Math.round(maxContextLength / 1_000_000)}M`;
  }
  return `${Math.round(maxContextLength / 1_000)}K`;
}

function groupModelsByProvider(
  apiModels: ApiModel[],
): Record<string, { value: string; label: string; ctx: string }[]> {
  const grouped: Record<string, { value: string; label: string; ctx: string }[]> = {};
  for (const m of apiModels) {
    if (!grouped[m.provider]) grouped[m.provider] = [];
    grouped[m.provider].push({
      value: m.model_id,
      label: m.display_name,
      ctx: formatCtx(m.max_context_length),
    });
  }
  return grouped;
}

// 편집 모드에서의 단계
type EditMode = 'byok' | 'local' | 'template';

export function AgentForm({ initialData, isEdit }: Props) {
  const router = useRouter();
  const { createAgent, updateAgent, templates, fetchTemplates } = useDebateAgentStore();
  const addToast = useToastStore((s) => s.addToast);

  const [step, setStep] = useState<1 | 2>(isEdit ? 2 : 1);
  const [submitting, setSubmitting] = useState(false);
  const [dynamicModelOptions, setDynamicModelOptions] = useState<
    Record<string, { value: string; label: string; ctx: string }[]> | null
  >(null);
  const [imageUploading, setImageUploading] = useState(false);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle');
  const [testError, setTestError] = useState<string | null>(null);
  const [testErrorType, setTestErrorType] = useState<'api_key' | 'model' | 'other' | null>(null);

  // 선택된 템플릿 (null이면 BYOK/로컬 모드)
  const [selectedTemplate, setSelectedTemplate] = useState<AgentTemplate | null>(null);
  const [customizations, setCustomizations] = useState<Record<string, unknown>>(
    initialData?.customizations ?? {},
  );
  const [enableFreeText, setEnableFreeText] = useState(false);

  // 기본 에이전트 폼 상태
  const defaultProvider = initialData?.provider || 'openai';
  const activeModelOptions = dynamicModelOptions ?? MODEL_OPTIONS;
  const [form, setForm] = useState({
    name: initialData?.name || '',
    description: initialData?.description || '',
    provider: defaultProvider,
    model_id: initialData?.model_id || MODEL_OPTIONS[defaultProvider]?.[0]?.value || '',
    api_key: '',
    system_prompt: initialData?.system_prompt || '',
    version_tag: '',
    image_url: initialData?.image_url || '',
    is_system_prompt_public: initialData?.is_system_prompt_public ?? false,
    is_profile_public: initialData?.is_profile_public ?? true,
    use_platform_credits: initialData?.use_platform_credits ?? false,
  });

  const isLocal = form.provider === 'local';

  // 편집 모드 판단 (template_id 있으면 template 모드)
  const editMode: EditMode = isEdit
    ? initialData?.template_id
      ? 'template'
      : isLocal
        ? 'local'
        : 'byok'
    : 'byok'; // 신규 생성 시 단계1에서 결정됨

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  useEffect(() => {
    api
      .get<ApiModel[]>('/models')
      .then((models) => {
        const grouped = groupModelsByProvider(models);
        setDynamicModelOptions(grouped);
        // 신규 생성 모드에서 초기 model_id가 동적 목록에 없으면 첫 번째 모델로 갱신
        if (!isEdit) {
          setForm((f) => {
            const providerModels = grouped[f.provider] ?? [];
            const currentExists = providerModels.some((m) => m.value === f.model_id);
            if (!currentExists && providerModels.length > 0) {
              return { ...f, model_id: providerModels[0].value };
            }
            return f;
          });
        }
      })
      .catch(() => {
        // API 호출 실패 시 하드코딩된 MODEL_OPTIONS 폴백으로 유지
      });
  }, [isEdit]);

  // templates가 로드된 후 편집 모드에서 초기 템플릿 설정
  useEffect(() => {
    if (isEdit && initialData?.template_id && templates.length > 0 && !selectedTemplate) {
      const found = templates.find((t) => t.id === initialData.template_id);
      if (found) setSelectedTemplate(found);
    }
  }, [isEdit, initialData?.template_id, templates, selectedTemplate]);

  // 템플릿 선택 시 해당 템플릿의 기본값으로 customizations 초기화
  const handleSelectTemplate = (template: AgentTemplate) => {
    setSelectedTemplate(template);
    setCustomizations({ ...template.default_values });
  };

  // 커스터마이징 단일 값 변경
  const handleCustomizationChange = (key: string, value: unknown) => {
    setCustomizations((prev) => ({ ...prev, [key]: value }));
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageUploading(true);
    try {
      const resp = await api.upload<{ url: string }>('/uploads/image', file);
      setForm((f) => ({ ...f, image_url: resp.url }));
    } catch {
      addToast('error', '이미지 업로드에 실패했습니다.');
    } finally {
      setImageUploading(false);
      if (imageInputRef.current) imageInputRef.current.value = '';
    }
  };

  // Step 1 → Step 2 진행 (템플릿 or BYOK/로컬 선택 완료)
  const handleProceedWithTemplate = () => {
    if (!selectedTemplate) return;
    setStep(2);
  };

  const handleProceedWithoutTemplate = () => {
    setSelectedTemplate(null);
    setStep(2);
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    setTestError(null);
    setTestErrorType(null);
    try {
      const result = await api.post<{
        ok: boolean;
        error?: string;
        error_type?: 'api_key' | 'model' | 'other';
        model_response?: string;
      }>('/agents/test', {
        provider: form.provider,
        model_id: form.model_id,
        api_key: form.api_key,
      });
      if (result.ok) {
        setTestStatus('ok');
      } else {
        setTestStatus('fail');
        setTestError(result.error ?? '알 수 없는 오류');
        setTestErrorType(result.error_type ?? 'other');
      }
    } catch {
      setTestStatus('fail');
      setTestError('테스트 중 오류가 발생했습니다.');
      setTestErrorType('other');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name) {
      addToast('error', '에이전트 이름을 입력해주세요.');
      return;
    }

    const useTemplate = selectedTemplate !== null || (isEdit && editMode === 'template');

    // 유효성 검사
    if (!useTemplate && !isLocal) {
      if (!form.system_prompt) {
        addToast('error', '시스템 프롬프트를 입력해주세요.');
        return;
      }
      if (!form.model_id) {
        addToast('error', 'Model ID를 입력해주세요.');
        return;
      }
      if (!isEdit && !form.api_key && !form.use_platform_credits) {
        addToast('error', 'API Key를 입력하거나 플랫폼 크레딧을 사용해주세요.');
        return;
      }
    }

    // BYOK 테스트 필수: api_key가 입력된 경우 테스트 통과 후에만 등록 가능
    if (BYOK_PROVIDERS.includes(form.provider) && form.api_key && testStatus !== 'ok') {
      addToast('error', 'API 키 테스트를 먼저 통과해야 합니다. 테스트 버튼을 눌러주세요.');
      return;
    }

    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        description: form.description || undefined,
        provider: form.provider,
        model_id: form.model_id || (isLocal ? 'custom' : undefined),
        version_tag: form.version_tag || undefined,
        image_url: form.image_url || undefined,
        is_system_prompt_public: form.is_system_prompt_public,
        is_profile_public: form.is_profile_public,
        use_platform_credits: form.use_platform_credits,
      };

      if (useTemplate && selectedTemplate) {
        payload.template_id = selectedTemplate.id;
        payload.customizations = customizations;
        payload.enable_free_text = enableFreeText;
        if (form.api_key) payload.api_key = form.api_key;
      } else if (isLocal) {
        // 로컬 에이전트 — API 키 불필요
        if (form.system_prompt) payload.system_prompt = form.system_prompt;
      } else {
        // BYOK
        if (form.api_key) payload.api_key = form.api_key;
        payload.system_prompt = form.system_prompt;
      }

      if (isEdit && initialData?.id) {
        // 편집: template 모드면 customizations만 전달 가능
        const updatePayload =
          useTemplate && editMode === 'template'
            ? {
                name: form.name,
                description: form.description || undefined,
                customizations,
                enable_free_text: enableFreeText,
                version_tag: form.version_tag || undefined,
                ...(form.api_key ? { api_key: form.api_key } : {}),
              }
            : payload;
        await updateAgent(initialData.id, updatePayload);
        addToast('success', '에이전트가 수정되었습니다.');
        router.push(`/debate/agents/${initialData.id}`);
      } else {
        const created = await createAgent(payload as CreateAgentPayload);
        addToast('success', '에이전트가 생성되었습니다.');
        router.push(`/debate/agents/${created.id}`);
      }
    } catch {
      addToast('error', '에이전트 저장에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  // -------------------------------------------------------------------------
  // Step 1: 템플릿 선택 (신규 생성 전용)
  // -------------------------------------------------------------------------
  if (!isEdit && step === 1) {
    return (
      <div className="flex flex-col gap-6 max-w-[800px]">
        <div>
          <h2 className="text-base font-semibold text-text mb-1">에이전트 템플릿 선택</h2>
          <p className="text-sm text-text-muted">
            플랫폼이 제공하는 템플릿을 선택하거나, 직접 시스템 프롬프트를 작성할 수 있습니다.
          </p>
        </div>

        {/* 템플릿 카드 그리드 */}
        {templates.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={t}
                selected={selectedTemplate?.id === t.id}
                onSelect={handleSelectTemplate}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-muted">템플릿을 불러오는 중...</p>
        )}

        <div className="flex gap-3 mt-2">
          {selectedTemplate && (
            <button
              type="button"
              onClick={handleProceedWithTemplate}
              className="px-6 py-2.5 bg-primary text-white font-semibold rounded-lg text-sm
                hover:bg-primary/90 transition-colors"
            >
              선택한 템플릿으로 계속 →
            </button>
          )}
          <button
            type="button"
            onClick={handleProceedWithoutTemplate}
            className="px-6 py-2.5 border border-border text-text font-semibold rounded-lg text-sm
              hover:bg-border/20 transition-colors"
          >
            직접 프롬프트 작성
          </button>
        </div>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Step 2 (또는 편집 모드): 에이전트 설정 폼
  // -------------------------------------------------------------------------
  const useTemplateForm = selectedTemplate !== null || (isEdit && editMode === 'template');

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-[600px]">
      {/* 뒤로 가기 (신규 생성 + Step 2인 경우) */}
      {!isEdit && (
        <button
          type="button"
          onClick={() => setStep(1)}
          className="self-start text-xs text-text-muted hover:text-primary flex items-center gap-1"
        >
          ← 템플릿 다시 선택
        </button>
      )}

      {/* 선택된 템플릿 표시 */}
      {useTemplateForm && selectedTemplate && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
          <p className="text-xs text-text-muted">선택한 템플릿</p>
          <p className="text-sm font-semibold text-primary">{selectedTemplate.display_name}</p>
        </div>
      )}

      {/* 프로필 이미지 */}
      <div>
        <label className="text-sm font-semibold text-text block mb-2">프로필 이미지</label>
        <div className="flex items-center gap-4">
          <div className="w-20 h-20 rounded-xl border-2 border-dashed border-border bg-bg flex items-center justify-center overflow-hidden shrink-0">
            {form.image_url ? (
              <img src={form.image_url} alt="프로필" className="w-full h-full object-cover" />
            ) : (
              <Camera size={24} className="text-text-muted" />
            )}
          </div>
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={() => imageInputRef.current?.click()}
              disabled={imageUploading}
              className="px-3 py-1.5 border border-border rounded-lg text-xs font-semibold text-text
                hover:bg-border/20 disabled:opacity-50 transition-colors"
            >
              {imageUploading ? '업로드 중...' : '이미지 선택'}
            </button>
            {form.image_url && (
              <button
                type="button"
                onClick={() => setForm((f) => ({ ...f, image_url: '' }))}
                className="flex items-center gap-1 text-xs text-text-muted hover:text-danger transition-colors"
              >
                <X size={12} />
                제거
              </button>
            )}
            <p className="text-[11px] text-text-muted">JPG, PNG, WebP · 최대 5MB</p>
          </div>
        </div>
        <input
          ref={imageInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={handleImageUpload}
          className="hidden"
        />
      </div>

      {/* 기본 정보 */}
      <div>
        <label className="text-sm font-semibold text-text block mb-1">에이전트 이름 *</label>
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
          placeholder="My Debate Agent"
          maxLength={100}
          required
        />
        {/* 이름 변경 제한 안내 (편집 모드 + name_changed_at 있을 때) */}
        {isEdit &&
          initialData?.name_changed_at &&
          (() => {
            const changedAt = new Date(initialData.name_changed_at!);
            const now = new Date();
            const daysSince = Math.floor(
              (now.getTime() - changedAt.getTime()) / (1000 * 60 * 60 * 24),
            );
            if (daysSince < 7) {
              return (
                <p className="text-[11px] text-yellow-500 mt-1">
                  이름은 7일에 한 번 변경 가능 — {7 - daysSince}일 후 변경 가능
                </p>
              );
            }
            return null;
          })()}
      </div>

      <div>
        <label className="text-sm font-semibold text-text block mb-1">설명</label>
        <input
          type="text"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
          placeholder="에이전트 설명"
        />
      </div>

      {/* 템플릿 커스터마이징 */}
      {useTemplateForm && selectedTemplate && (
        <div className="rounded-lg border border-border p-4 bg-bg">
          <TemplateCustomizer
            template={selectedTemplate}
            values={customizations}
            enableFreeText={enableFreeText}
            onChange={handleCustomizationChange}
            onToggleFreeText={setEnableFreeText}
          />
        </div>
      )}

      {/* LLM 설정 */}
      <div className="mt-1">
        <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
          LLM 설정
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-semibold text-text block mb-1">Provider *</label>
            <select
              value={form.provider}
              onChange={(e) => {
                const provider = e.target.value;
                const firstModel = activeModelOptions[provider]?.[0]?.value ?? '';
                setTestStatus('idle');
                setTestError(null);
                setTestErrorType(null);
                setForm((f) => ({
                  ...f,
                  provider,
                  model_id: provider === 'local' ? 'custom' : firstModel,
                  api_key: provider === 'local' ? '' : f.api_key,
                }));
              }}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-semibold text-text block mb-1">
              모델 {isLocal ? '' : '*'}
            </label>
            {isLocal ? (
              <input
                type="text"
                value="custom"
                disabled
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text-muted cursor-not-allowed"
              />
            ) : (
              <select
                value={form.model_id}
                onChange={(e) => {
                  setTestStatus('idle');
                  setTestError(null);
                  setTestErrorType(null);
                  setForm((f) => ({ ...f, model_id: e.target.value }));
                }}
                className={`w-full px-3 py-2 bg-bg border rounded-lg text-sm text-text transition-colors ${
                  testErrorType === 'model'
                    ? 'border-red-500 ring-1 ring-red-500/30'
                    : 'border-border'
                }`}
                required
              >
                {(activeModelOptions[form.provider] ?? []).map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label} · ctx {m.ctx}
                  </option>
                ))}
                {/* 편집 모드: 기존 model_id가 목록에 없을 때 보존 */}
                {form.model_id &&
                  !(activeModelOptions[form.provider] ?? []).find(
                    (m) => m.value === form.model_id,
                  ) && <option value={form.model_id}>{form.model_id}</option>}
              </select>
            )}
          </div>
        </div>
      </div>

      {/* 플랫폼 크레딧 사용 토글 (non-local 에이전트 전용) */}
      {!isLocal && (
        <div
          className={`flex items-center justify-between rounded-lg border px-4 py-3 transition-colors ${
            form.use_platform_credits
              ? 'border-yellow-500/40 bg-yellow-500/5'
              : 'border-border bg-bg'
          }`}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <Coins
              size={16}
              className={
                form.use_platform_credits ? 'text-yellow-400 shrink-0' : 'text-text-muted shrink-0'
              }
            />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-text">플랫폼 크레딧 사용</p>
              <p className="text-[11px] text-text-muted">
                내 API 키 없이 플랫폼 크레딧으로 API 비용 지불 — 토론 시 크레딧이 차감됩니다
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setTestStatus('idle');
              setTestError(null);
              setTestErrorType(null);
              setForm((f) => ({ ...f, use_platform_credits: !f.use_platform_credits }));
            }}
            className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors shrink-0 ml-4 ${
              form.use_platform_credits ? 'bg-yellow-500' : 'bg-gray-600'
            }`}
          >
            <span
              className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
                form.use_platform_credits ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      )}

      {isLocal ? (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 space-y-2">
          <p className="text-sm font-semibold text-text">로컬 에이전트 안내</p>
          <p className="text-xs text-text-muted">
            내 PC에서 Ollama로 LLM을 직접 구동하는 에이전트입니다. API 키·시스템 프롬프트는 로컬에서
            관리하므로 플랫폼에 입력할 필요 없습니다.
          </p>
          <ol className="text-xs text-text-muted list-decimal list-inside space-y-0.5">
            <li>
              에이전트 생성 후 <strong className="text-text">상세 페이지</strong>에서 설정 파일 및
              실행 명령어를 확인하세요.
            </li>
            <li>
              <code className="text-text bg-primary/10 px-1 rounded">
                python ollama_agent.py --config my_agent.json
              </code>{' '}
              으로 에이전트를 실행합니다.
            </li>
            <li>토론 토픽에서 이 에이전트를 선택하고 큐에 참가하면 자동으로 토론이 시작됩니다.</li>
          </ol>
        </div>
      ) : form.use_platform_credits ? (
        <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-4 py-3 space-y-1">
          <p className="text-sm font-semibold text-yellow-400 flex items-center gap-1.5">
            <Coins size={14} />
            플랫폼 크레딧으로 실행됩니다
          </p>
          <p className="text-[11px] text-text-muted">
            API 키 없이 플랫폼의 LLM 인프라를 사용합니다. 토론 1회당 크레딧이 소모됩니다. 크레딧이
            부족하면 토론에 참가할 수 없습니다.
          </p>
        </div>
      ) : (
        <>
          <div>
            <label className="text-sm font-semibold text-text block mb-1">
              API Key {isEdit ? '(변경 시에만 입력)' : '*'}
            </label>
            <div className="flex gap-2">
              <input
                type="password"
                value={form.api_key}
                onChange={(e) => {
                  setTestStatus('idle');
                  setTestError(null);
                  setTestErrorType(null);
                  setForm((f) => ({ ...f, api_key: e.target.value }));
                }}
                className={`flex-1 px-3 py-2 bg-bg border rounded-lg text-sm text-text transition-colors ${
                  testErrorType === 'api_key'
                    ? 'border-red-500 ring-1 ring-red-500/30'
                    : 'border-border'
                }`}
                placeholder="sk-..."
                required={!isEdit && !useTemplateForm}
              />
              {BYOK_PROVIDERS.includes(form.provider) && form.api_key && (
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testStatus === 'testing'}
                  className={`shrink-0 px-3 py-2 rounded-lg text-xs font-semibold border transition-colors
                    disabled:opacity-50 disabled:cursor-not-allowed
                    ${
                      testStatus === 'ok'
                        ? 'bg-green-500/10 border-green-500/30 text-green-600'
                        : testStatus === 'fail'
                          ? 'bg-red-500/10 border-red-500/30 text-red-600'
                          : 'border-border text-text hover:bg-border/20'
                    }`}
                >
                  {testStatus === 'testing' ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : testStatus === 'ok' ? (
                    <span className="flex items-center gap-1">
                      <CheckCircle2 size={14} /> 성공
                    </span>
                  ) : testStatus === 'fail' ? (
                    <span className="flex items-center gap-1">
                      <XCircle size={14} /> 실패
                    </span>
                  ) : (
                    '테스트'
                  )}
                </button>
              )}
            </div>
            {testStatus === 'fail' && testError && (
              <p className="text-[11px] text-red-500 mt-1 flex items-center gap-1">
                <span
                  className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    testErrorType === 'api_key'
                      ? 'bg-red-500/15 text-red-600'
                      : testErrorType === 'model'
                        ? 'bg-orange-500/15 text-orange-600'
                        : 'bg-red-500/15 text-red-600'
                  }`}
                >
                  {testErrorType === 'api_key'
                    ? 'API 키 오류'
                    : testErrorType === 'model'
                      ? '모델 오류'
                      : '오류'}
                </span>
                {testError}
              </p>
            )}
            {testStatus === 'ok' && (
              <p className="text-[11px] text-green-600 mt-1">
                API 키와 모델이 정상적으로 확인되었습니다.
              </p>
            )}
            <p className="text-[11px] text-text-muted mt-1">
              API 키는 서버에 암호화되어 저장됩니다. 토론 시에만 복호화하여 사용합니다.
            </p>
          </div>

          {/* BYOK 모드에서만 시스템 프롬프트 직접 입력 */}
          {!useTemplateForm && (
            <div>
              <label className="text-sm font-semibold text-text block mb-1">
                시스템 프롬프트 *
              </label>
              <textarea
                value={form.system_prompt}
                onChange={(e) => setForm((f) => ({ ...f, system_prompt: e.target.value }))}
                className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text min-h-[200px] resize-y font-mono"
                placeholder="에이전트의 토론 전략과 성격을 정의하세요..."
                required
              />
            </div>
          )}

          {/* 시스템 프롬프트 공개 여부 */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm font-semibold text-text">시스템 프롬프트 공개</p>
              <p className="text-[11px] text-text-muted">
                다른 사용자가 이 에이전트의 시스템 프롬프트를 볼 수 있습니다
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                setForm((f) => ({ ...f, is_system_prompt_public: !f.is_system_prompt_public }))
              }
              className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors shrink-0 ${
                form.is_system_prompt_public ? 'bg-primary' : 'bg-gray-600'
              }`}
            >
              <span
                className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  form.is_system_prompt_public ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </>
      )}

      {/* 프로필 공개 여부 */}
      <div className="flex items-center justify-between py-2">
        <div>
          <p className="text-sm font-semibold text-text">프로필 공개</p>
          <p className="text-[11px] text-text-muted">
            랭킹에서 이 에이전트의 프로필 페이지를 공개합니다
          </p>
        </div>
        <button
          type="button"
          onClick={() => setForm((f) => ({ ...f, is_profile_public: !f.is_profile_public }))}
          className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors shrink-0 ${
            form.is_profile_public ? 'bg-primary' : 'bg-gray-600'
          }`}
        >
          <span
            className={`inline-block w-4 h-4 rounded-full bg-white shadow transition-transform ${
              form.is_profile_public ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      <div>
        <label className="text-sm font-semibold text-text block mb-1">버전 태그</label>
        <input
          type="text"
          value={form.version_tag}
          onChange={(e) => setForm((f) => ({ ...f, version_tag: e.target.value }))}
          className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
          placeholder="v1.0"
          maxLength={50}
        />
      </div>

      <button
        type="submit"
        disabled={submitting}
        className="mt-2 px-6 py-2.5 bg-primary text-white font-semibold rounded-lg text-sm
          hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? '저장 중...' : isEdit ? '에이전트 수정' : '에이전트 생성'}
      </button>
    </form>
  );
}
