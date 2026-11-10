import { useState, type FormEvent } from 'react';
import type {
  ContentKind, MaterialCategory, PublicationClass, TeacherTeachingContent, TeachingContentInput,
} from '../../api/teaching-content-types';
import { useApi } from '../../app/auth';
import { Dialog } from '../../components/Dialog';

function localDeadline(iso: string | null | undefined) {
  if (!iso) return '';
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export function ContentForm({
  classId, classes, kind, initial, materials, onClose, onSaved,
}: {
  classId: string;
  classes: PublicationClass[];
  kind: ContentKind;
  initial?: TeacherTeachingContent;
  materials: TeacherTeachingContent[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const api = useApi();
  const assignment = kind === 'ASSIGNMENT';
  const noun = assignment ? '作业' : '资料';
  const [title, setTitle] = useState(initial?.title ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [chapter, setChapter] = useState(initial?.chapter ?? '');
  const [category, setCategory] = useState<MaterialCategory>(initial?.category ?? 'CLASSROOM');
  const [url, setUrl] = useState(initial?.url ?? '');
  const [deadline, setDeadline] = useState(localDeadline(initial?.due_at));
  const [method, setMethod] = useState(initial?.submission_method ?? '');
  const [resource, setResource] = useState(
    materials.find((item) => item.id === initial?.resource_id)?.id ?? '',
  );
  const [targets, setTargets] = useState(initial?.class_ids ?? [classId]);
  const [file, setFile] = useState<File | null>(null);
  const [remove, setRemove] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!targets.length) return setError('请选择至少一个发布班级。');
    if (file && file.size > 10 * 1024 * 1024) return setError('附件最大为 10 MB。');
    if (assignment && (!deadline || !Number.isFinite(Date.parse(deadline)))) {
      return setError('请选择有效的截止时间。');
    }
    const input: TeachingContentInput = {
      kind, title: title.trim(), description: description.trim(),
      chapter: assignment ? null : chapter.trim() || null,
      category: assignment ? null : category,
      url: url.trim() || null,
      due_at: assignment ? new Date(deadline).toISOString() : null,
      submission_method: assignment ? method.trim() : null,
      resource_id: assignment ? resource || null : null,
      class_ids: targets,
      remove_attachment: remove && !file,
    };
    setSaving(true);
    setError('');
    try {
      await api.teachingContent.save(classId, initial?.id, input, file);
      onSaved();
    } catch (reason) {
      setError((reason as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return <Dialog title={`${initial ? '编辑' : '发布'}${noun}`}
    onClose={() => { if (!saving) onClose(); }}
    footer={<>
      <button className="btn btn-secondary" disabled={saving} onClick={onClose}>取消</button>
      <button className="btn btn-primary" form="teaching-content-form" disabled={saving}>
        {saving ? '保存中…' : initial ? '保存修改' : `发布${noun}`}
      </button>
    </>}>
    <form id="teaching-content-form" onSubmit={save}>
      <label className="field"><span>标题</span><input required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      {assignment ? <>
        <label className="field"><span>截止时间（本地时间）</span><input required type="datetime-local" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></label>
        <label className="field"><span>提交方式</span><input required maxLength={500} value={method} onChange={(e) => setMethod(e.target.value)} placeholder="例如：下次课交纸质作业" /></label>
        <label className="field"><span>参考资料（可选）</span><select value={resource} onChange={(e) => setResource(e.target.value)}>
          <option value="">选择本班已发布的资料</option>
          {materials.map((item) => <option key={item.id} value={item.id}>{item.chapter ? `${item.chapter} · ` : ''}{item.title}</option>)}
        </select></label>
      </> : <>
        <label className="field"><span>章节（可选）</span><input maxLength={120} value={chapter} onChange={(e) => setChapter(e.target.value)} placeholder="例如：第 3 章" /></label>
        <label className="field"><span>资料类型</span><select value={category} onChange={(e) => setCategory(e.target.value as MaterialCategory)}>
          <option value="CLASSROOM">课堂资料</option><option value="SELF_STUDY">自主学习</option>
        </select></label>
      </>}
      <label className="field"><span>{assignment ? '作业要求' : '学习说明'}</span>
        <textarea required={assignment} rows={4} maxLength={10000} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label className="field"><span>链接（可选）</span><input type="url" maxLength={2048} value={url} onChange={(e) => setUrl(e.target.value)} /></label>
      <label className="field"><span>附件（可选，最大 10 MB）</span><input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
      {initial?.attachment_name && <p><label>
        <input type="checkbox" checked={remove && !file} disabled={Boolean(file)} onChange={(e) => setRemove(e.target.checked)} />
        移除现有附件 {initial.attachment_name}
      </label></p>}
      {!assignment && <fieldset className="policy">
        <legend>发布班级</legend>
        {classes.filter((group) => group.status === 'ACTIVE' || initial?.class_ids.includes(group.id)).map((group) => (
          <label key={group.id}><input type="checkbox" checked={targets.includes(group.id)} onChange={(e) => {
            setTargets((current) => e.target.checked ? [...current, group.id] : current.filter((id) => id !== group.id));
          }} /> {group.name}{group.status === 'ARCHIVED' ? '（已归档）' : ''}</label>
        ))}
      </fieldset>}
      {initial && !assignment && initial.class_ids.length > 1 && <p className="form-note">保存后，所选班级会看到同一份更新。</p>}
      {error && <p className="form-alert" role="alert">{error}</p>}
    </form>
  </Dialog>;
}
