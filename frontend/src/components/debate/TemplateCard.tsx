'use client';

import type { AgentTemplate } from '@/stores/debateAgentStore';

// 아이콘 slug → 이모지 매핑
const ICON_MAP: Record<string, string> = {
  brain: '🧠',
  fire: '🔥',
  scale: '⚖️',
  star: '⭐',
  shield: '🛡️',
  lightning: '⚡',
  test: '🧪',
};

type Props = {
  template: AgentTemplate;
  selected: boolean;
  onSelect: (template: AgentTemplate) => void;
};

export function TemplateCard({ template, selected, onSelect }: Props) {
  const icon = template.icon ? (ICON_MAP[template.icon] ?? '🤖') : '🤖';

  return (
    <button
      type="button"
      onClick={() => onSelect(template)}
      className={[
        'flex flex-col gap-2 p-4 rounded-xl border-2 text-left transition-all cursor-pointer',
        selected
          ? 'border-primary bg-primary/10 shadow-md'
          : 'border-border bg-card hover:border-primary/50 hover:bg-card/80',
      ].join(' ')}
    >
      <div className="flex items-center gap-2">
        <span className="text-2xl" role="img" aria-label={template.display_name}>
          {icon}
        </span>
        <span className="font-semibold text-text text-sm">{template.display_name}</span>
        {selected && (
          <span className="ml-auto text-xs font-bold text-primary px-2 py-0.5 rounded-full bg-primary/20">
            선택됨
          </span>
        )}
      </div>

      {template.description && (
        <p className="text-xs text-text-muted leading-relaxed line-clamp-2">
          {template.description}
        </p>
      )}

      {/* 기본값 미리보기 */}
      <div className="flex flex-wrap gap-1 mt-1">
        {template.customization_schema.sliders.map((slider) => {
          const val = template.default_values[slider.key] as number | undefined;
          return (
            <span
              key={slider.key}
              className="text-[10px] px-1.5 py-0.5 rounded bg-border/60 text-text-muted"
            >
              {slider.label} {val}/{slider.max}
            </span>
          );
        })}
        {template.customization_schema.selects.map((sel) => {
          const val = template.default_values[sel.key] as string | undefined;
          const label = sel.options.find((o) => o.value === val)?.label ?? val;
          return (
            <span
              key={sel.key}
              className="text-[10px] px-1.5 py-0.5 rounded bg-border/60 text-text-muted"
            >
              {label}
            </span>
          );
        })}
      </div>
    </button>
  );
}
