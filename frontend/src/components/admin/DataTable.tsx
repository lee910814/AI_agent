/** 관리자 대시보드용 제네릭 데이터 테이블. 정렬, 스크롤, 빈 상태, 로딩 스켈레톤 지원. */
'use client';

import { useRef, useEffect } from 'react';
import { SkeletonTable } from '@/components/ui/Skeleton';
import { Inbox } from 'lucide-react';

type Column<T> = {
  key: keyof T;
  label: string;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
};

type Props<T> = {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  loading?: boolean;
  selectable?: boolean;
  selectedIds?: Set<string>;
  onSelectChange?: (id: string, checked: boolean) => void;
  onSelectAll?: (checked: boolean) => void;
  idKey?: keyof T;
};

function IndeterminateCheckbox({
  checked,
  indeterminate,
  onChange,
}: {
  checked: boolean;
  indeterminate: boolean;
  onChange: (checked: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <input
      ref={ref}
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      className="w-4 h-4 cursor-pointer accent-primary"
    />
  );
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  loading,
  selectable,
  selectedIds,
  onSelectChange,
  onSelectAll,
  idKey = 'id' as keyof T,
}: Props<T>) {
  if (loading) {
    return <SkeletonTable rows={5} cols={columns.length + (selectable ? 1 : 0)} />;
  }

  const allSelected = data.length > 0 && data.every((row) => selectedIds?.has(String(row[idKey])));
  const someSelected = data.some((row) => selectedIds?.has(String(row[idKey])));
  const totalCols = columns.length + (selectable ? 1 : 0);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm min-w-[600px]">
        <thead>
          <tr>
            {selectable && (
              <th className="w-10 px-3 py-2.5 border-b-2 border-border">
                <IndeterminateCheckbox
                  checked={allSelected}
                  indeterminate={someSelected && !allSelected}
                  onChange={(checked) => onSelectAll?.(checked)}
                />
              </th>
            )}
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className="text-left px-3 py-2.5 border-b-2 border-border text-[13px] text-text-muted font-semibold"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 && (
            <tr>
              <td colSpan={totalCols} className="p-10">
                <div className="flex flex-col items-center justify-center text-text-muted">
                  <Inbox className="w-10 h-10 mb-2" />
                  <span className="text-sm">데이터가 없습니다</span>
                </div>
              </td>
            </tr>
          )}
          {data.map((row, i) => {
            const rawId = row[idKey];
            const rowId = rawId != null ? String(rawId) : String(i);
            const isSelected = selectedIds?.has(rowId) ?? false;
            return (
              <tr
                key={rowId}
                onClick={() => onRowClick?.(row)}
                className={`transition-colors duration-100 hover:bg-bg-hover ${
                  onRowClick ? 'cursor-pointer' : 'cursor-default'
                } ${isSelected ? 'bg-primary/5' : ''}`}
              >
                {selectable && (
                  <td className="w-10 px-3 py-2.5 border-b border-bg">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => {
                        e.stopPropagation();
                        onSelectChange?.(rowId, e.target.checked);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="w-4 h-4 cursor-pointer accent-primary"
                    />
                  </td>
                )}
                {columns.map((col) => (
                  <td key={String(col.key)} className="px-3 py-2.5 border-b border-bg text-text">
                    {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
