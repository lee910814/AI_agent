/** 빈 상태 표시 컴포넌트. 아이콘 + 메시지 + 선택적 액션 버튼. */
import type { ReactNode } from 'react';

type Props = {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
};

export function EmptyState({ icon, title, description, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-text-muted mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-text mb-1">{title}</h3>
      {description && <p className="text-sm text-text-muted mb-4 max-w-[320px]">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
