'use client';

import type { PromotionSeries } from '@/stores/debateStore';

type Props = {
  series: PromotionSeries;
};

export function PromotionSeriesProgress({ series }: Props) {
  const isPromotion = series.series_type === 'promotion';
  // 승급전: 3슬롯(2선승제), 강등전: 1슬롯
  const totalSlots = isPromotion ? 3 : 1;

  const slots = Array.from({ length: totalSlots }, (_, i) => {
    if (i < series.current_wins) return 'win';
    if (i < series.current_wins + series.current_losses) return 'loss';
    return 'pending';
  });

  const label = isPromotion
    ? `${series.from_tier} → ${series.to_tier} 승급전`
    : `${series.from_tier} 강등전`;

  const statusLabel =
    series.status === 'won'
      ? isPromotion
        ? '승급 성공!'
        : '강등전 생존!'
      : series.status === 'lost'
        ? isPromotion
          ? '승급 실패'
          : '강등 확정'
        : series.status === 'expired'
          ? '시리즈 만료'
          : null;

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="flex items-center gap-2">
        {slots.map((slot, idx) => (
          <span
            key={idx}
            className={`h-4 w-4 rounded-full border-2 ${
              slot === 'win'
                ? 'border-green-500 bg-green-500'
                : slot === 'loss'
                  ? 'border-red-500 bg-red-500'
                  : 'border-gray-400 bg-transparent'
            }`}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{label}</p>
      {statusLabel && (
        <p
          className={`text-xs font-bold ${
            series.status === 'won'
              ? 'text-green-600'
              : series.status === 'expired'
                ? 'text-gray-500'
                : 'text-red-600'
          }`}
        >
          {statusLabel}
        </p>
      )}
    </div>
  );
}
