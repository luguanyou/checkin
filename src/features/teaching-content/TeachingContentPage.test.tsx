import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../components/ToastProvider';
import { TeachingContentPage } from './TeachingContentPage';

const teachingContent = { list: vi.fn(), save: vi.fn() };
vi.mock('../../app/auth', () => ({ useApi: () => ({ teachingContent }) }));

beforeEach(() => {
  vi.clearAllMocks();
  teachingContent.list.mockResolvedValue({
    course_name: '软件工程',
    classes: [
      { id: 'c1', name: '一班', status: 'ACTIVE' },
      { id: 'c2', name: '二班', status: 'ACTIVE' },
    ],
    items: [],
  });
  teachingContent.save.mockResolvedValue({});
});

it.each([false, true])('publishes with the selected class scope (multi-class=%s)', async (multi) => {
  const user = userEvent.setup();
  render(<QueryClientProvider client={new QueryClient()}>
    <ToastProvider>
      <MemoryRouter initialEntries={['/classes/c1/teaching-content']}>
        <Routes><Route path="/classes/:classId/teaching-content" element={<TeachingContentPage />} /></Routes>
      </MemoryRouter>
    </ToastProvider>
  </QueryClientProvider>);
  await user.click(await screen.findByRole('button', { name: '发布资料' }));
  const dialog = within(screen.getByRole('dialog'));
  expect(dialog.getByRole('checkbox', { name: '一班' })).toBeChecked();
  expect(dialog.getByRole('checkbox', { name: '二班' })).not.toBeChecked();
  if (multi) await user.click(dialog.getByRole('checkbox', { name: '二班' }));
  await user.type(dialog.getByLabelText('标题'), '第 3 章扩展练习');
  await user.selectOptions(dialog.getByLabelText('资料类型'), 'SELF_STUDY');
  await user.type(dialog.getByLabelText('学习说明'), '先读示例，再做练习');
  await user.click(dialog.getByRole('button', { name: '发布资料' }));
  await waitFor(() => expect(teachingContent.save).toHaveBeenCalledWith('c1', undefined, expect.objectContaining({
    kind: 'MATERIAL',
    category: 'SELF_STUDY',
    title: '第 3 章扩展练习',
    class_ids: multi ? ['c1', 'c2'] : ['c1'],
  }), null));
});
