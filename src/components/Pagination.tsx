import { ChevronLeft, ChevronRight } from 'lucide-react';
export function Pagination({ page, pageSize, total, onChange }: { page: number; pageSize: number; total: number; onChange(page: number): void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return <nav className="pagination" aria-label="分页"><span>第 {page} / {pages} 页，共 {total} 条</span><span><button className="icon-btn" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="上一页"><ChevronLeft /></button><button className="icon-btn" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="下一页"><ChevronRight /></button></span></nav>;
}
