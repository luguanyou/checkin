import { useState, type ReactNode } from 'react';
import type { ContentKind, TeachingContent } from '../../api/teaching-content-types';
import { useApi } from '../../app/auth';
import { useToast } from '../../components/ToastProvider';
import './teaching-content.css';

export function ContentList<T extends TeachingContent>({
  classId, items, kind, student = false, actions,
}: {
  classId: string;
  items: T[];
  kind: ContentKind;
  student?: boolean;
  actions?: (item: T) => ReactNode;
}) {
  const api = useApi();
  const toast = useToast();
  const [downloading, setDownloading] = useState<string | null>(null);
  const matching = items.filter((item) => item.kind === kind);
  const materials = new Map(items.filter((item) => item.kind === 'MATERIAL').map((item) => [item.id, item]));
  const groups = new Map<string, T[]>();
  for (const item of matching) {
    const key = kind === 'MATERIAL' ? (item.chapter || '未分章节') : '';
    const group = groups.get(key) ?? [];
    group.push(item);
    groups.set(key, group);
  }
  const now = Date.now();
  const upcoming = (item: T) => Date.parse(item.due_at ?? '') >= now;
  groups.get('')?.sort((a, b) => {
    const difference = Number(upcoming(b)) - Number(upcoming(a));
    const deadline = Date.parse(a.due_at ?? '') - Date.parse(b.due_at ?? '');
    return difference || (upcoming(a) ? deadline : -deadline);
  });

  async function download(item: TeachingContent) {
    setDownloading(item.id);
    try {
      const file = await api.teachingContent.download(classId, item.id, student);
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (reason) {
      toast.show((reason as Error).message, 'error');
    } finally {
      setDownloading(null);
    }
  }

  if (!matching.length) return <p className="teaching-empty">暂无{kind === 'MATERIAL' ? '课程资料' : '作业'}。</p>;

  return <div className="teaching-list">
    {[...groups].sort(([a], [b]) => a.localeCompare(b, 'zh-CN', { numeric: true })).map(([chapter, rows]) => (
      <div key={chapter}>
        {chapter && <h3 className="teaching-chapter">{chapter}</h3>}
        {rows.map((item) => {
          const resource = item.resource_id ? materials.get(item.resource_id) : undefined;
          const Title = chapter ? 'h4' : 'h3';
          return <article key={item.id} id={`teaching-${item.id}`} className="teaching-item">
            <div className="actions">
              <Title>{item.title}</Title>
              {item.category && <span className="status">{item.category === 'SELF_STUDY' ? '自主学习' : '课堂资料'}</span>}
              {item.due_at && <span className={`status ${upcoming(item) ? 'active' : 'archived'}`}>{upcoming(item) ? '待截止' : '已截止'}</span>}
            </div>
            {item.due_at && <p>截止时间 <time dateTime={item.due_at}>{new Date(item.due_at).toLocaleString('zh-CN', { hour12: false })}</time></p>}
            {item.description && <p className="teaching-description">{item.description}</p>}
            {item.submission_method && <p className="teaching-description">提交方式：{item.submission_method}</p>}
            {resource && <p>参考资料：<a className="teaching-reference" href={`#teaching-${resource.id}`}>{resource.title}</a></p>}
            <div className="actions">
              {item.url && <a className="btn btn-secondary btn-sm" href={item.url} target="_blank" rel="noopener noreferrer">打开链接</a>}
              {item.attachment_name && <button className="btn btn-secondary btn-sm" disabled={downloading !== null} onClick={() => void download(item)}>
                {downloading === item.id ? '下载中…' : `下载 ${item.attachment_name}`}
              </button>}
            </div>
            {actions?.(item)}
          </article>;
        })}
      </div>
    ))}
  </div>;
}
