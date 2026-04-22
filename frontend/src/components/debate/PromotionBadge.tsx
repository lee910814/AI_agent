'use client';

type Props = {
  type: 'promotion' | 'demotion';
  size?: 'sm' | 'md';
};

export function PromotionBadge({ type, size = 'md' }: Props) {
  const isPromotion = type === 'promotion';

  const baseClass =
    size === 'sm'
      ? 'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold'
      : 'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold';

  if (isPromotion) {
    return (
      <span
        className={`${baseClass} promotion-shimmer text-yellow-900`}
        style={{
          background: 'linear-gradient(90deg, #f59e0b, #fbbf24, #fde68a, #f59e0b)',
          backgroundSize: '200% auto',
          animation: 'shimmer 2s linear infinite',
        }}
      >
        ⚔️ 승급전
      </span>
    );
  }

  return <span className={`${baseClass} animate-pulse bg-red-600 text-white`}>🛡️ 강등전</span>;
}
