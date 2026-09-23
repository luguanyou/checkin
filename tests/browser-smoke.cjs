const assert = require('node:assert/strict');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright-core');
const { createScoreFixture, handleScoreRequest } = require('./scores-browser-fixture.cjs');

const root = path.join(__dirname, '..');
const baseUrl = 'http://127.0.0.1:4173';

async function waitForServer() {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try { if ((await fetch(baseUrl)).ok) return; } catch {}
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error('Vite server did not start');
}

function createFixtures(role = 'TEACHER') {
  const user = { id: 'user-1', username: role === 'ADMIN' ? 'admin' : 'teacher01', display_name: role === 'ADMIN' ? '系统管理员' : '王老师', role, status: 'ACTIVE', must_change_password: false, last_login_at: null, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' };
  const teachers = role === 'ADMIN' ? [{ id: 'teacher-1', username: 'wang01', display_name: '王老师', role: 'TEACHER', status: 'ACTIVE', must_change_password: true, last_login_at: null, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' }] : [];
  const courses = [{ id: 'course-1', name: '产品设计方法', code: 'PD204', term: '2026 秋季学期', status: 'ACTIVE', classes: [{ id: 'class-1', name: '2024 级 2 班', status: 'ACTIVE', active_student_count: 2 }], created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z' }];
  const roster = [
    { enrollment_id: 'e1', enrollment_status: 'ACTIVE', student: { id: 's1', student_number: '20260001', name: '张敏', gender: '女', major: '工业设计' }, created_at: '', updated_at: '' },
    { enrollment_id: 'e2', enrollment_status: 'ACTIVE', student: { id: 's2', student_number: '20260002', name: '李明', gender: '男', major: '工业设计' }, created_at: '', updated_at: '' },
  ];
  const records = roster.map((member, index) => ({ id: `r${index + 1}`, student_id: member.student.id, student_number: member.student.student_number, student_name: member.student.name, class_name: '2024 级 2 班', status: 'pending', marked_at: null, last_modified_at: null, last_modified_by: { id: 'user-1', display_name: '王老师' }, version: 1 }));
  const session = { id: 'session-1', course: { id: 'course-1', name: '产品设计方法', code: 'PD204' }, class_group: { id: 'class-1', name: '2024 级 2 班' }, session_date: '2026-09-03', status: 'DRAFT', started_at: '2026-09-03T01:00:00Z', completed_at: null, created_at: '2026-09-03T01:00:00Z', updated_at: '2026-09-03T01:00:00Z', summary: {}, records };
  let authenticated = false;
  const requests = [];
  function summary() {
    const counts = { total: records.length, pending: 0, present: 0, absent: 0, leave: 0, late: 0, exceptions: 0 };
    records.forEach((record) => { counts[record.status] += 1; });
    counts.exceptions = counts.absent + counts.late;
    session.summary = counts;
    return counts;
  }
  summary();
  return { user, teachers, courses, roster, records, session, requests, summary, scores: createScoreFixture(courses[0], roster), get authenticated() { return authenticated; }, login() { authenticated = true; }, logout() { authenticated = false; } };
}

async function installApi(page, data) {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request(); const url = new URL(request.url()); const endpoint = url.pathname; const method = request.method();
    data.requests.push(`${method} ${endpoint}`);
    const json = (body, status = 200, headers = {}) => route.fulfill({ status, contentType: 'application/json', headers, body: JSON.stringify(body) });
    const error = (code, message, status = 400) => json({ code, message, details: {}, request_id: 'browser-request' }, status);
    if (await handleScoreRequest({ route, endpoint, method, url, book: data.scores, json, error })) return;
    if (endpoint === '/api/v1/auth/refresh') return data.authenticated ? json({ access_token: 'token', token_type: 'bearer', expires_in: 900, user: data.user }) : error('AUTHENTICATION_REQUIRED', '请先登录', 401);
    if (endpoint === '/api/v1/auth/login' && method === 'POST') { data.login(); return json({ access_token: 'token', token_type: 'bearer', expires_in: 900, user: data.user }); }
    if (endpoint === '/api/v1/auth/logout') { data.logout(); return route.fulfill({ status: 204 }); }
    if (endpoint === '/api/v1/admin/users' && method === 'GET') {
      const status = url.searchParams.get('status'); const q = (url.searchParams.get('q') || '').toLowerCase();
      const items = data.teachers.filter((item) => (!status || item.status === status) && (!q || item.username.includes(q) || item.display_name.includes(q)));
      return json({ items, page: Number(url.searchParams.get('page') || 1), page_size: Number(url.searchParams.get('page_size') || 20), total: items.length });
    }
    if (endpoint === '/api/v1/admin/users' && method === 'POST') {
      const body = request.postDataJSON(); const created = { id: 'teacher-created', username: body.username, display_name: body.display_name, role: 'TEACHER', status: 'ACTIVE', must_change_password: true, last_login_at: null, created_at: '2026-09-04T00:00:00Z', updated_at: '2026-09-04T00:00:00Z' };
      data.teachers.unshift(created); return json(created, 201);
    }
    const userStatusMatch = endpoint.match(/^\/api\/v1\/admin\/users\/([^/]+)\/status$/);
    if (userStatusMatch && method === 'PATCH') { const account = data.teachers.find((item) => item.id === userStatusMatch[1]); account.status = request.postDataJSON().status; return json(account); }
    if (/^\/api\/v1\/admin\/users\/[^/]+\/reset-password$/.test(endpoint) && method === 'POST') return route.fulfill({ status: 204 });
    if (endpoint === '/api/v1/courses' && method === 'GET') return json({ items: data.courses, page: 1, page_size: 100, total: data.courses.length });
    if (endpoint === '/api/v1/courses' && method === 'POST') { const body = request.postDataJSON(); const course = { id: 'course-2', ...body, status: 'ACTIVE', classes: [], created_at: '', updated_at: '' }; data.courses.push(course); return json(course, 201); }
    if (/\/api\/v1\/courses\/[^/]+\/classes$/.test(endpoint) && method === 'POST') { const body = request.postDataJSON(); const item = { id: 'class-2', name: body.name, status: 'ACTIVE', active_student_count: 0 }; data.courses[1].classes.push(item); return json(item, 201); }
    if (endpoint === '/api/v1/classes/class-1/roster' && method === 'GET') return json({ items: data.roster, page: 1, page_size: 20, total: data.roster.length });
    if (endpoint === '/api/v1/classes/class-1/roster/import-preview' && method === 'POST') return json({ preview_id: 'preview-1', expires_at: '2026-09-03T02:00:00Z', summary: { total: 2, valid: 2, errors: 0, duplicates: 0, importable: 2 }, rows: [{ row_number: 2, student_number: '20260001', name: '张敏', gender: '女', class_name: '2024 级 2 班', major: '工业设计', status: 'valid', code: null, fields: [], message: null }] }, 201);
    if (endpoint === '/api/v1/classes/class-1/roster/import-confirm' && method === 'POST') return json({ preview_id: 'preview-1', created_students: 0, created_enrollments: 0, restored_enrollments: 0, skipped: 2, failed: 0 });
    if (endpoint === '/api/v1/classes/class-1/attendance-sessions' && method === 'POST') return json(data.session, 201);
    if (endpoint === '/api/v1/attendance-sessions' && method === 'GET') return json({ items: data.session.status === 'DRAFT' || data.session.completed_at ? [{ ...data.session, records: undefined, summary: data.summary() }] : [], page: 1, page_size: 20, total: 1 });
    if (endpoint === '/api/v1/attendance-sessions/session-1' && method === 'GET') return json({ ...data.session, summary: data.summary(), records: data.records });
    const recordMatch = endpoint.match(/^\/api\/v1\/attendance-records\/(r\d+)$/);
    if (recordMatch && method === 'PATCH') { const body = request.postDataJSON(); const record = data.records.find((item) => item.id === recordMatch[1]); if (body.expected_version !== record.version) return error('ATTENDANCE_RECORD_CONFLICT', '记录已被修改', 409); Object.assign(record, { status: body.status, version: record.version + 1, marked_at: record.marked_at || '2026-09-03T01:02:00Z', last_modified_at: '2026-09-03T01:02:00Z' }); data.summary(); return json(record); }
    if (endpoint === '/api/v1/attendance-sessions/session-1/complete' && method === 'POST') { data.session.status = 'COMPLETED'; data.session.completed_at = '2026-09-03T01:05:00Z'; return json({ ...data.session, records: undefined, summary: data.summary() }); }
    if (endpoint === '/api/v1/attendance-sessions/session-1/export') return route.fulfill({ status: 200, headers: { 'Content-Type': url.searchParams.get('format') === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': "attachment; filename*=UTF-8''attendance.xlsx" }, body: 'attendance export' });
    return error('NOT_FOUND', `Unhandled ${method} ${endpoint}`, 404);
  });
}

async function run() {
  const vite = spawn(process.execPath, [path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', '4173', '--strictPort'], { cwd: root, windowsHide: true, stdio: 'ignore' });
  let browser;
  try {
    await waitForServer();
    browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
    const errors = [];
    const watchPage = (candidate) => {
      candidate.on('console', (message) => { if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) errors.push(message.text()); });
      candidate.on('response', (response) => { if (response.status() >= 400 && !response.url().endsWith('/api/v1/auth/refresh')) errors.push(`${response.status()} ${response.url()}`); });
      candidate.on('pageerror', (error) => errors.push(error.message));
    };

    const adminPage = await browser.newPage({ viewport: { width: 1280, height: 720 } });
    watchPage(adminPage);
    const adminFixtures = createFixtures('ADMIN'); await installApi(adminPage, adminFixtures); await adminPage.goto(baseUrl);
    await adminPage.getByRole('heading', { name: '登录课点' }).waitFor();
    await adminPage.getByLabel('用户名').fill('admin'); await adminPage.getByLabel('密码').fill('short-pass'); await adminPage.getByRole('button', { name: '登录' }).click();
    await adminPage.getByRole('heading', { name: '教师账号' }).waitFor();
    assert.equal(new URL(adminPage.url()).pathname, '/admin');
    assert.equal(adminFixtures.requests.filter((request) => request === 'POST /api/v1/auth/login').length, 1);
    await adminPage.getByRole('button', { name: '创建教师' }).click();
    await adminPage.getByLabel('教师姓名').fill('李老师'); await adminPage.getByLabel('用户名').fill('Li02'); await adminPage.getByRole('button', { name: '确认创建' }).click();
    await adminPage.getByRole('heading', { name: '一次性登录凭据' }).waitFor();
    await adminPage.getByRole('button', { name: '复制登录凭据' }).click(); await adminPage.getByText('登录凭据已复制').waitFor();
    await adminPage.getByRole('button', { name: '完成' }).click(); await adminPage.getByText('李老师').first().waitFor();
    await adminPage.getByRole('button', { name: '停用李老师' }).click(); await adminPage.getByRole('button', { name: '确认停用' }).click(); await adminPage.getByRole('button', { name: '启用李老师' }).waitFor();
    await adminPage.getByRole('button', { name: '启用李老师' }).click(); await adminPage.getByRole('button', { name: '确认启用' }).click(); await adminPage.getByRole('button', { name: '停用李老师' }).waitFor();
    await adminPage.getByRole('button', { name: '重置李老师密码' }).click(); await adminPage.getByRole('button', { name: '确认重置' }).click(); await adminPage.getByRole('heading', { name: '一次性登录凭据' }).waitFor(); await adminPage.getByRole('button', { name: '完成' }).click();
    for (const viewport of [{ name: 'desktop', width: 1280, height: 720 }, { name: 'mobile', width: 375, height: 812 }]) {
      await adminPage.setViewportSize({ width: viewport.width, height: viewport.height });
      assert.equal(await adminPage.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `admin ${viewport.name} overflow`);
      await adminPage.screenshot({ path: path.join(root, '.superpowers', `attendance-admin-${viewport.name}.png`), fullPage: true });
    }
    assert.equal(adminFixtures.requests.some((request) => /courses|attendance/.test(request)), false);
    assert.equal(adminFixtures.requests.some((request) => request === 'POST /api/v1/admin/users'), true);
    assert.equal(adminFixtures.requests.some((request) => request === 'PATCH /api/v1/admin/users/teacher-created/status'), true);
    assert.equal(adminFixtures.requests.some((request) => request === 'POST /api/v1/admin/users/teacher-created/reset-password'), true);
    await adminPage.getByRole('button', { name: '退出登录' }).click();
    await adminPage.getByRole('heading', { name: '登录课点' }).waitFor();
    await adminPage.close();

    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    watchPage(page);
    await page.addInitScript(() => {
      Object.defineProperty(window, 'speechSynthesis', { value: { cancel() {}, speak() {} } });
      Object.defineProperty(window, 'SpeechSynthesisUtterance', { value: class { constructor(text) { this.text = text; } } });
    });
    const fixtures = createFixtures(); await installApi(page, fixtures); await page.goto(baseUrl);
    await page.getByRole('heading', { name: '登录课点' }).waitFor();
    await page.getByLabel('用户名').fill('teacher01'); await page.getByLabel('密码').fill('correct-password'); await page.getByRole('button', { name: '登录' }).click();
    await page.getByRole('heading', { name: '工作台' }).waitFor();
    assert.equal(await page.locator('.metric').count(), 3);

    await page.getByRole('link', { name: '课程班级' }).first().click(); await page.getByRole('button', { name: '新建课程' }).first().click();
    await page.getByLabel('课程名称').fill('服务设计专题'); await page.getByLabel('课程代码').fill('SD301'); await page.getByRole('button', { name: '创建课程' }).click();
    await page.getByText('服务设计专题').waitFor();

    await page.getByRole('link', { name: '管理名单' }).first().click(); await page.getByRole('heading', { name: '2024 级 2 班' }).waitFor();
    await page.getByRole('button', { name: '导入名单' }).click(); await page.locator('input[type=file]').setInputFiles({ name: 'roster.csv', mimeType: 'text/csv', buffer: Buffer.from('student_number,name\n1,test') });
    await page.getByText('检查校验结果并选择重复数据处理方式。').waitFor(); await page.getByRole('button', { name: '确认导入' }).click(); await page.getByRole('heading', { name: '导入完成' }).waitFor(); await page.getByRole('button', { name: '完成' }).click();

    await page.getByRole('link', { name: '工作台' }).first().click(); await page.getByRole('button', { name: '开始点名' }).click(); await page.getByRole('heading', { name: '张敏' }).waitFor();
    await page.keyboard.press('Space'); await page.getByRole('heading', { name: '李明' }).waitFor(); await page.keyboard.press('1'); await page.getByText('全部已同步').waitFor();
    await page.getByRole('button', { name: '结束点名' }).click(); await page.getByRole('button', { name: '确认结束' }).click(); await page.getByRole('heading', { name: '产品设计方法' }).waitFor();
    await page.getByRole('button', { name: '修正' }).last().click(); await page.getByLabel('修正原因').fill('学生课间到场补签'); await page.getByRole('combobox', { name: '考勤状态' }).selectOption('late'); await page.getByRole('button', { name: '确认修正' }).click(); await page.getByText('考勤状态已修正').waitFor();
    await page.getByRole('button', { name: '导出记录' }).click(); const downloadPromise = page.waitForEvent('download'); await page.getByRole('button', { name: '生成文件' }).click(); const download = await downloadPromise; assert.equal(download.suggestedFilename(), 'attendance.xlsx');

    await page.getByRole('link', { name: '平时成绩', exact: true }).first().click();
    await page.getByRole('heading', { name: '平时成绩', exact: true }).waitFor();
    await page.getByRole('button', { name: '新建项目', exact: true }).click();
    await page.getByLabel('项目名称').fill('作业 1 · 需求分析');
    await page.getByLabel('所属类别').selectOption('HOMEWORK');
    await page.getByLabel('项目日期').fill('2026-09-22');
    await page.getByRole('button', { name: '创建项目', exact: true }).click();
    await page.getByLabel('张敏本次积分').waitFor();
    await page.getByLabel('张敏本次积分').fill('0.5');
    await page.getByLabel('张敏备注').fill('部分完成，已反馈');
    await page.getByLabel('李明本次积分').fill('0');
    const recordsResponse = page.waitForResponse((response) => response.url().endsWith('/scores/items/score-item-1/records') && response.status() === 200);
    await page.getByRole('button', { name: '保存本次录入', exact: true }).click();
    await recordsResponse;
    assert.equal(fixtures.scores.records.find((record) => record.enrollment_id === 'e1').points, '0.5');
    assert.equal(fixtures.scores.records.find((record) => record.enrollment_id === 'e2').points, '0');
    await page.getByRole('button', { name: '基础分与换算', exact: true }).click();
    await page.getByLabel('基础分', { exact: true }).fill('80');
    for (const label of ['作业', '课堂表现', '上机实验表现', '其他']) {
      await page.getByLabel(`${label}每积分分值`, { exact: true }).fill(label === '作业' ? '0.5' : '1');
    }
    const settingsResponse = page.waitForResponse((response) => response.url().endsWith('/scores/settings') && response.status() === 200);
    await page.getByRole('button', { name: '保存换算规则', exact: true }).click();
    await settingsResponse;
    assert.equal(fixtures.scores.settings.base_score, '80');
    await page.getByRole('button', { name: '平时成绩汇总', exact: true }).click();
    await page.getByRole('button', { name: '导出正式汇总', exact: true }).click();
    await page.getByLabel('CSV 文本 (.csv)', { exact: true }).check();
    const scoresDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: '生成文件', exact: true }).click();
    assert.equal((await scoresDownload).suggestedFilename(), 'scores.csv');
    for (const width of [1440, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      for (const tab of ['项目积分录入', '基础分与换算', '平时成绩汇总']) {
        await page.getByRole('button', { name: tab, exact: true }).click();
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `scores ${tab} at ${width}px overflow`);
      }
      if (width !== 320) await page.screenshot({ path: path.join(root, '.superpowers', `scores-${width}.png`), fullPage: true });
    }

    for (const viewport of [{ name: 'desktop', width: 1440, height: 1000 }, { name: 'mobile', width: 390, height: 844 }, { name: 'small', width: 320, height: 740 }]) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height }); await page.goto(`${baseUrl}/`); await page.getByRole('heading', { name: '工作台' }).waitFor();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${viewport.name} overflow`);
      if (viewport.name !== 'small') await page.screenshot({ path: path.join(process.env.TEMP || root, `attendance-react-${viewport.name}.png`), fullPage: true });
    }
    const unnamed = await page.locator('button:visible').evaluateAll((items) => items.filter((item) => !(item.getAttribute('aria-label') || item.textContent.trim())).length);
    assert.equal(unnamed, 0, 'all visible buttons need an accessible name'); assert.deepEqual(errors, []);
    console.log('React browser checks passed: admin routing/logout, teacher attendance and scores workflows, accessibility, and responsive overflow.');
  } finally {
    if (browser) await browser.close(); vite.kill();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
