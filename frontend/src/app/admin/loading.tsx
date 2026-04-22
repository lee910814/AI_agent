export default function AdminLoading() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-bg">
      <div className="flex flex-col items-center gap-3">
        <span className="inline-block w-8 h-8 border-2 border-text-muted border-t-primary rounded-full animate-spin" />
        <span className="text-sm text-text-muted">로딩 중...</span>
      </div>
    </div>
  );
}
