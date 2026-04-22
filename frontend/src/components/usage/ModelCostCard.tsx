/** LLM 모델별 비용 카드. 입력/출력 토큰 단가 및 총 비용 표시. */
import { memo } from 'react';

type Props = {
  modelName: string;
  inputCost: number;
  outputCost: number;
  totalTokens: number;
  totalCost: number;
};

export const ModelCostCard = memo(function ModelCostCard({
  modelName,
  inputCost,
  outputCost,
  totalTokens,
  totalCost,
}: Props) {
  return (
    <div className="card">
      <h3 className="m-0 mb-3 text-base">{modelName}</h3>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-text-muted">입력 단가</span>
          <span className="text-base font-semibold text-text">${inputCost}/1M</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-text-muted">출력 단가</span>
          <span className="text-base font-semibold text-text">${outputCost}/1M</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-text-muted">총 토큰</span>
          <span className="text-base font-semibold text-text">{totalTokens.toLocaleString()}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-text-muted">총 비용</span>
          <span className="text-base font-semibold text-danger-cost">${totalCost.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
});
