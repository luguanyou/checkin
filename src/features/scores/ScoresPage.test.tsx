import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import type { ScoreBook } from '../../api/scores-types';
import { ToastProvider } from '../../components/ToastProvider';
import { ScoresPage } from './ScoresPage';

const api = { courses: { list: vi.fn() }, scores: { get: vi.fn(), saveRecords: vi.fn(), saveSettings: vi.fn(), history: vi.fn(), export: vi.fn(), createItem: vi.fn(), updateItem: vi.fn() } };
vi.mock('../../app/auth', () => ({ useApi: () => api }));
const book: ScoreBook = {
  class_group: { id: 'c1', name: '一班', status: 'ACTIVE' }, course: { id: 'course1', name: '软件工程', status: 'ACTIVE' }, version: 2, readonly: false, rules_ready: false,
  settings: { base_score: '70', factors: { HOMEWORK: null, LAB: null, CLASSROOM: null, OTHER: null } },
  items: [{ id: 'i1', category: 'HOMEWORK', name: '作业 1', occurred_on: '2026-09-22', description: '' }, { id: 'i2', category: 'HOMEWORK', name: '作业 2', occurred_on: '2026-09-23', description: '' }],
  students: [{ enrollment_id: 'e1', student_id: 's1', student_number: '01', student_name: '张敏', enrollment_status: 'ACTIVE' }, { enrollment_id: 'e2', student_id: 's2', student_number: '02', student_name: '李明', enrollment_status: 'REMOVED' }],
  records: [{ id: 'r1', item_id: 'i1', enrollment_id: 'e1', points: null, note: '', updated_at: '' }, { id: 'r2', item_id: 'i1', enrollment_id: 'e2', points: '0', note: '', updated_at: '' }], summaries: [],
};
function mount(client = new QueryClient({ defaultOptions: { queries: { retry: false } } }), path = '/scores?course_id=course1&class_group_id=c1') { return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><ToastProvider><ScoresPage /></ToastProvider></MemoryRouter></QueryClientProvider>); }
beforeEach(() => {
  vi.clearAllMocks(); api.courses.list.mockResolvedValue({ items: [{ ...book.course, classes: [book.class_group] }], page: 1, page_size: 100, total: 1 });
  api.scores.get.mockResolvedValue(structuredClone(book)); api.scores.saveRecords.mockResolvedValue(structuredClone(book)); api.scores.saveSettings.mockResolvedValue(structuredClone(book)); api.scores.history.mockResolvedValue({ items: [] });
});
describe('usual scores', () => {
  it('shows pending scores as zero, keeps removed members read-only and sends only edited rows', async () => {
    const user = userEvent.setup(); mount();
    const input = await screen.findByLabelText('张敏本次积分');
    expect(input).toHaveValue(0); expect(screen.getByLabelText('李明本次积分')).toHaveValue(0); expect(screen.getByLabelText('李明本次积分')).toBeDisabled();
    await user.click(within(input.closest('tr')!).getByRole('button', { name: '5' }));
    await user.click(screen.getByRole('button', { name: '保存本次录入' }));
    expect(api.scores.saveRecords).toHaveBeenCalledWith('c1', 'i1', { expected_version: 2, records: [{ enrollment_id: 'e1', points: '5', note: '' }] });
  });
  it('retains a draft on a version conflict and requires explicit reload rather than retrying stale writes', async () => {
    const user = userEvent.setup(); api.scores.saveRecords.mockRejectedValue(new ApiError(409, 'SCORE_VERSION_CONFLICT', '版本冲突')); mount();
    fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '-0.5' } });
    await user.click(screen.getByRole('button', { name: '保存本次录入' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('版本'); expect(screen.getByLabelText('张敏本次积分')).toHaveValue(-0.5);
    expect(screen.getByRole('button', { name: '保存本次录入' })).toBeDisabled(); expect(screen.getByRole('button', { name: '刷新并核对' })).toBeEnabled();
  });
  it('allows configurable baseline and nullable factors with zero disabling a category', async () => {
    const user = userEvent.setup(); mount(); await screen.findByLabelText('张敏本次积分');
    await user.click(screen.getByRole('button', { name: '基础分与换算' }));
    const base = screen.getByLabelText('基础分'); expect(base).toHaveValue(70);
    fireEvent.change(base, { target: { value: '80' } }); fireEvent.change(screen.getByLabelText('作业每积分分值'), { target: { value: '0' } });
    await user.click(screen.getByRole('button', { name: '保存换算规则' }));
    await waitFor(() => expect(api.scores.saveSettings).toHaveBeenCalledWith('c1', { expected_version: 2, base_score: '80', factors: { HOMEWORK: '0', LAB: null, CLASSROOM: null, OTHER: null } }));
  });
  it('asks before losing edits when switching projects', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false); mount();
    fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('当前项目'), { target: { value: 'i2' } });
    expect(confirm).toHaveBeenCalled(); expect(screen.getByLabelText('当前项目')).toHaveValue('i1'); expect(screen.getByLabelText('张敏本次积分')).toHaveValue(2); confirm.mockRestore();
  });
  it('synchronizes decimal scale returned by the server after saving so tab changes do not show a false draft', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup(); api.scores.saveRecords.mockResolvedValue({ ...structuredClone(book), settings: { ...book.settings, base_score: '70.0000' } }); mount();
    fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '0' } });
    await user.click(screen.getByRole('button', { name: '保存本次录入' }));
    await user.click(screen.getByRole('button', { name: '基础分与换算' }));
    expect(await screen.findByLabelText('基础分')).toHaveValue(70); expect(confirm).not.toHaveBeenCalled(); confirm.mockRestore();
  });
  it('retains note and fractional input on a network failure for retry', async () => {
    const user = userEvent.setup(); api.scores.saveRecords.mockRejectedValueOnce(new Error('网络中断')); mount();
    fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '0.125' } });
    await user.type(screen.getByLabelText('张敏备注'), '补交'); await user.click(screen.getByRole('button', { name: '保存本次录入' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('网络中断'); expect(screen.getByLabelText('张敏本次积分')).toHaveValue(0.125); expect(screen.getByLabelText('张敏备注')).toHaveValue('补交');
    expect(screen.getByRole('button', { name: '保存本次录入' })).toBeEnabled();
  });
  it('creates a dated project in its chosen category without requiring scoring rules', async () => {
    const user = userEvent.setup(); const newItem = { id: 'i3', category: 'LAB', name: '实验环境搭建', occurred_on: '2026-09-22', description: '操作系统' };
    api.scores.createItem.mockResolvedValue({ ...structuredClone(book), items: [...book.items, newItem] }); mount(); await screen.findByLabelText('张敏本次积分');
    await user.click(screen.getByRole('button', { name: '新建项目' }));
    await user.selectOptions(screen.getByLabelText('所属类别'), 'LAB'); await user.type(screen.getByLabelText('项目名称'), newItem.name);
    fireEvent.change(screen.getByLabelText('项目日期'), { target: { value: newItem.occurred_on } }); await user.type(screen.getByLabelText('项目说明'), newItem.description);
    await user.click(screen.getByRole('button', { name: '创建项目' }));
    await waitFor(() => expect(api.scores.createItem).toHaveBeenCalledWith('c1', { expected_version: 2, category: 'LAB', name: newItem.name, occurred_on: newItem.occurred_on, description: newItem.description }));
    expect(screen.getByLabelText('当前项目')).toHaveValue('i3');
  });
  it('locks an archived book but still allows summary and detail exports', async () => {
    const user = userEvent.setup(); api.scores.get.mockResolvedValue({ ...structuredClone(book), readonly: true }); mount();
    expect(await screen.findByLabelText('张敏本次积分')).toBeDisabled(); expect(screen.getByRole('button', { name: '新建项目' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: '平时成绩汇总' }));
    expect(screen.getByRole('button', { name: '导出正式汇总' })).toBeDisabled(); expect(screen.getByRole('button', { name: '导出原始明细' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: '导出原始明细' })); await user.click(screen.getByLabelText('CSV 文本 (.csv)'));
    api.scores.export.mockRejectedValue(new Error('下载失败，请重试')); await user.click(screen.getByRole('button', { name: '生成文件' }));
    expect(api.scores.export).toHaveBeenCalledWith('c1', 'csv', 'details'); expect(await screen.findByRole('alert')).toHaveTextContent('下载失败');
  });
  it('displays the server raw and clamped summary without locally recomputing it', async () => {
    const user = userEvent.setup(); api.scores.get.mockResolvedValue({ ...structuredClone(book), rules_ready: true, summaries: [{ enrollment_id: 'e1', categories: [{ category: 'HOMEWORK', points: '120', contribution: '120', pending: 0 }], raw_score: '190', final_score: '100', status: 'READY' }] }); mount(); await screen.findByLabelText('张敏本次积分');
    await user.click(screen.getByRole('button', { name: '平时成绩汇总' }));
    expect(screen.getByText('190.00')).toBeInTheDocument(); expect(screen.getByText('100.00')).toBeInTheDocument(); expect(screen.getByText('封顶 100 分')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '导出正式汇总' })).toBeEnabled();
  });
  it('filters score entry and summary rows by student number or name', async () => {
    const user = userEvent.setup(); mount();
    await screen.findByLabelText('张敏本次积分');
    const search = screen.getByPlaceholderText('输入学号或姓名');
    await user.type(search, '02');
    expect(screen.queryByLabelText('张敏本次积分')).not.toBeInTheDocument();
    expect(screen.getByLabelText('李明本次积分')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '平时成绩汇总' }));
    expect(screen.getByText('李明')).toBeInTheDocument();
    expect(screen.queryByText('张敏')).not.toBeInTheDocument();
    await user.clear(search);
    await user.type(search, '张敏');
    expect(screen.getByText('张敏')).toBeInTheDocument();
    expect(screen.queryByText('李明')).not.toBeInTheDocument();
  });
  it('pins draft project across conflict refresh even if another earlier project is inserted', async () => {
    const user = userEvent.setup(); api.scores.saveRecords.mockRejectedValueOnce(new ApiError(409, 'SCORE_VERSION_CONFLICT', '版本冲突'));
    mount(); fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '2' } });
    await user.click(screen.getByRole('button', { name: '保存本次录入' }));
    api.scores.get.mockResolvedValue({ ...structuredClone(book), version: 3, items: [{ ...book.items[0], id: 'inserted', name: '提前作业', occurred_on: '2026-09-01' }, ...book.items] });
    await user.click(await screen.findByRole('button', { name: '刷新并核对' })); await user.click(await screen.findByRole('button', { name: '确认核对，继续保存' }));
    expect(screen.getByLabelText('当前项目')).toHaveValue('i1');
    await user.click(screen.getByRole('button', { name: '保存本次录入' }));
    expect(api.scores.saveRecords).toHaveBeenLastCalledWith('c1', 'i1', { expected_version: 3, records: [{ enrollment_id: 'e1', points: '2', note: '' }] });
  });
  it('does not silently rebase an unsaved draft when a newer query result arrives', async () => {
    const user = userEvent.setup(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); mount(client);
    fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '2' } });
    act(() => { client.setQueryData(['scores', 'c1'], { ...structuredClone(book), version: 8, records: [{ ...book.records[0], points: '1' }, book.records[1]] }); });
    await user.click(screen.getByRole('button', { name: '保存本次录入' }));
    expect(api.scores.saveRecords).toHaveBeenCalledWith('c1', 'i1', { expected_version: 2, records: [{ enrollment_id: 'e1', points: '2', note: '' }] });
  });
  it('follows incoming rules while pristine and retains the original revision once rules are edited', async () => {
    const user = userEvent.setup(); const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); mount(client); await screen.findByLabelText('张敏本次积分');
    await user.click(screen.getByRole('button', { name: '基础分与换算' }));
    act(() => { client.setQueryData(['scores', 'c1'], { ...structuredClone(book), version: 5, settings: { ...book.settings, base_score: '60.0000' } }); });
    await waitFor(() => expect(screen.getByLabelText('基础分')).toHaveValue(60));
    fireEvent.change(screen.getByLabelText('基础分'), { target: { value: '80' } });
    act(() => { client.setQueryData(['scores', 'c1'], { ...structuredClone(book), version: 8, settings: { ...book.settings, base_score: '90.0000' } }); });
    expect(screen.getByLabelText('基础分')).toHaveValue(80); await user.click(screen.getByRole('button', { name: '保存换算规则' }));
    expect(api.scores.saveSettings).toHaveBeenCalledWith('c1', { expected_version: 5, base_score: '80', factors: book.settings.factors });
  });
  it('keeps default selection and drafts when course ordering changes', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); mount(client, '/scores');
    fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '0.5' } });
    act(() => { client.setQueryData(['courses', 'scores-context'], [{ id: 'other-course', name: '新课程', classes: [{ id: 'other-class', name: '新班级', status: 'ACTIVE' }] }, { ...book.course, classes: [book.class_group] }]); });
    await screen.findByRole('option', { name: '新课程' }); expect(screen.getByLabelText('班级')).toHaveValue('c1'); expect(screen.getByLabelText('张敏本次积分')).toHaveValue(0.5); expect(api.scores.get).not.toHaveBeenCalledWith('other-class');
  });
  it('keeps a mounted draft when background scores and courses refresh fail', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); mount(client);
    fireEvent.change(await screen.findByLabelText('张敏本次积分'), { target: { value: '0.5' } });
    api.scores.get.mockRejectedValue(new Error('刷新失败')); api.courses.list.mockRejectedValue(new Error('网络失败'));
    await act(async () => { await client.refetchQueries({ queryKey: ['scores', 'c1'] }); await client.refetchQueries({ queryKey: ['courses', 'scores-context'] }); });
    await waitFor(() => expect(screen.getAllByRole('alert')).toHaveLength(2)); expect(screen.getByLabelText('张敏本次积分')).toHaveValue(0.5);
  });
});
