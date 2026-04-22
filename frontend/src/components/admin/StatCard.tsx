/** 관리자 대시보드 통계 카드. 제목, 수치, 변동률, 아이콘 표시. */
import { memo, type ReactNode } from 'react';

type Props = {
  title: string;
  value: string | number;
  description?: string;
  icon?: ReactNode;
};

export const StatCard = memo(function StatCard({ title, value, description, icon }: Props) {
  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-1">
        {icon && (
          <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
            {icon}
          </div>
        )}
        <div className="text-[13px] text-text-muted">{title}</div>
      </div>
      <div className="text-[28px] font-bold text-text">
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      {description && <div className="text-xs text-text-muted mt-1">{description}</div>}
    </div>
  );
});
