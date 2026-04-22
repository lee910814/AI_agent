import React from 'react';
import { MessageSquare } from 'lucide-react';

export default function TopicsPage() {
  return (
    <div className="max-w-[800px] mx-auto py-10 px-4">
      <div className="flex flex-col items-center justify-center text-center py-20 bg-bg-surface border border-border rounded-3xl">
        <div className="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center mb-6">
          <MessageSquare size={32} className="text-blue-500" />
        </div>
        <h1 className="text-3xl font-bold text-text mb-4">전체 토픽 목록</h1>
        <p className="text-text-muted max-w-md mx-auto leading-relaxed">
          다른 사용자들이 제안한 수많은 흥미로운 토론 주제들이 표시되는 공간입니다.
          <br />
          (현재 준비 중인 하드코딩된 페이지입니다)
        </p>
      </div>
    </div>
  );
}
