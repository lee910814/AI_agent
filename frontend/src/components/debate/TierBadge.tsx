'use client';

import { getTierInfo } from '@/lib/tierUtils';

type Props = {
  tier: string;
  size?: 'sm' | 'md';
};

export function TierBadge({ tier, size = 'sm' }: Props) {
  const info = getTierInfo(tier);
  const sizeClass = size === 'md' ? 'text-xs px-2 py-0.5' : 'text-[10px] px-1.5 py-0';

  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full font-semibold border
        ${sizeClass} ${info.color} ${info.bgColor} ${info.borderColor}`}
    >
      <span>{info.icon}</span>
      <span>{info.name}</span>
    </span>
  );
}
