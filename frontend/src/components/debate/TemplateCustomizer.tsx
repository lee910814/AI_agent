'use client';

import type { AgentTemplate } from '@/stores/debateAgentStore';

type Props = {
  template: AgentTemplate;
  values: Record<string, unknown>;
  enableFreeText: boolean;
  onChange: (key: string, value: unknown) => void;
  onToggleFreeText: (enabled: boolean) => void;
};

export function TemplateCustomizer({
  template,
  values,
  enableFreeText,
  onChange,
  onToggleFreeText,
}: Props) {
  const { sliders, selects, free_text: freeText } = template.customization_schema;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">커스터마이징</p>

      {/* 슬라이더 */}
      {sliders.map((slider) => {
        const val = (values[slider.key] as number) ?? slider.default;
        return (
          <div key={slider.key}>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-semibold text-text">{slider.label}</label>
              <span className="text-sm font-mono text-primary">
                {val}/{slider.max}
              </span>
            </div>
            {slider.description && (
              <p className="text-[11px] text-text-muted mb-1">{slider.description}</p>
            )}
            <input
              type="range"
              min={slider.min}
              max={slider.max}
              value={val}
              onChange={(e) => onChange(slider.key, parseInt(e.target.value, 10))}
              className="w-full accent-primary"
            />
            <div className="flex justify-between text-[10px] text-text-muted mt-0.5">
              <span>{slider.min}</span>
              <span>{slider.max}</span>
            </div>
          </div>
        );
      })}

      {/* 셀렉트 */}
      {selects.map((sel) => {
        const val = (values[sel.key] as string) ?? sel.default;
        return (
          <div key={sel.key}>
            <label className="text-sm font-semibold text-text block mb-1">{sel.label}</label>
            <select
              value={val}
              onChange={(e) => onChange(sel.key, e.target.value)}
              className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm text-text"
            >
              {sel.options.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        );
      })}

      {/* 자유 텍스트 */}
      {freeText && (
        <div>
          <label className="flex items-center gap-2 cursor-pointer mb-2">
            <input
              type="checkbox"
              checked={enableFreeText}
              onChange={(e) => onToggleFreeText(e.target.checked)}
              className="w-4 h-4 accent-primary"
            />
            <span className="text-sm font-semibold text-text">{freeText.label} 활성화</span>
          </label>
          <textarea
            value={enableFreeText ? ((values[freeText.key] as string) ?? '') : ''}
            onChange={(e) => onChange(freeText.key, e.target.value)}
            disabled={!enableFreeText}
            placeholder={enableFreeText ? freeText.placeholder : '(비활성 상태)'}
            maxLength={freeText.max_length}
            rows={3}
            className={[
              'w-full px-3 py-2 border rounded-lg text-sm resize-none transition-colors',
              enableFreeText
                ? 'bg-bg border-border text-text'
                : 'bg-bg/50 border-border/50 text-text-muted cursor-not-allowed',
            ].join(' ')}
          />
          {enableFreeText && (
            <p className="text-[11px] text-text-muted mt-0.5 text-right">
              {((values[freeText.key] as string) ?? '').length}/{freeText.max_length}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
