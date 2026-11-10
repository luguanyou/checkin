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
    data.registrations ??= [];
    if (endpoint === '/api/v1/auth/student-registration/classes') return json({ items: [{ id: 'class-1', name: '一班', course_name: '设计', term: '2026' }] });
    if (endpoint === '/api/v1/auth/student-register') {
      const input = request.postDataJSON();
      data.registrations.push({ id: 'registration-1', name: input.name, student_number: input.student_number, status: 'PENDING', created_at: '2026-11-03T00:00:00', can_review: true });
      return json({ status: 'PENDING', message: '申请已提交' }, 201);
    }
    if (endpoint === '/api/v1/classes/class-1/registrations') return json({ items: data.registrations.filter((item) => url.searchParams.get('status') === 'all' || item.status === (url.searchParams.get('status') || 'PENDING')) });
    if (endpoint === '/api/v1/classes/class-1/registrations/review' && method === 'POST') {
      const input = request.postDataJSON();
      for (const item of data.registrations.filter((row) => input.registration_ids.includes(row.id))) { item.status = input.decision; item.can_review = false; item.reviewer_name = data.user.display_name; item.reason = input.reason; }
      return json({ reviewed: input.registration_ids.length });
    }
    data.monitorGrants ??= [];
    const monitorItem = { id: 'mi1', name: '班长登记项目', category: 'HOMEWORK', occurred_on: '2026-11-02', description: '', default_points: null };
    const monitorManagement = () => ({ readonly: false, items: [monitorItem], members: [{ student: { id: 's1', student_number: '001', name: '班长' }, enrollment_status: 'ACTIVE', user_id: 'monitor-user', username: '001', account_status: 'ACTIVE', item_ids: data.monitorGrants, can_review_registrations: Boolean(data.canReview) }] });
    if (endpoint === '/api/v1/classes/class-1/monitors') return json(monitorManagement());
    if (endpoint === '/api/v1/classes/class-1/monitors/monitor-user' && method === 'PUT') { data.monitorGrants = request.postDataJSON().item_ids; data.canReview = Boolean(request.postDataJSON().can_review_registrations); return json(monitorManagement()); }
    if (endpoint === '/api/v1/student/monitor-projects') return json({ items: data.monitorGrants.length ? [{ ...monitorItem, class_id: 'class-1', class_name: '一班', course_name: '设计' }] : [] });
    if (endpoint.startsWith('/api/v1/student/classes/class-1/monitor-projects/')) {
      if (method === 'PUT') data.monitorRecord = { ...request.postDataJSON().records[0], id: 'mr1', item_id: 'mi1', updated_at: '' };
      return json({ version: data.monitorRecord ? 1 : 0, item: monitorItem, students: [
        { enrollment_id: 'me1', student_id: 's1', student_number: '001', student_name: '班长本人', enrollment_status: 'ACTIVE', can_edit: false },
        { enrollment_id: 'me2', student_id: 's2', student_number: '002', student_name: '被登记同学', enrollment_status: 'ACTIVE', can_edit: true },
      ], records: data.monitorRecord ? [data.monitorRecord] : [] });
    }
    data.visibility ??= { attendance_visible: false, score_visibility: 'HIDDEN' };
    if (endpoint === '/api/v1/classes/class-1/student-visibility') {
      if (method === 'PUT') data.visibility = request.postDataJSON();
      return json(data.visibility);
    }
    if (endpoint === '/api/v1/student/classes') return json({ items: [{ id: 'class-1', name: '一班', course_name: '设计', term: '2026', can_record_scores: data.monitorGrants.length > 0, can_review_registrations: Boolean(data.canReview), ...data.visibility }] });
    if (endpoint === '/api/v1/student/classes/class-1/teaching-content') return json({ items: [] });
    if (endpoint === '/api/v1/student/classes/class-1') return json({ ...data.visibility,
      attendance: data.visibility.attendance_visible ? [{ id: 'a1', date: '2026-11-02', status: 'present', session_status: 'COMPLETED' }] : null,
      score: data.visibility.score_visibility === 'HIDDEN' ? null : { final_score: '75.2', status: 'READY' }, details: null,
    });
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
    if (/^\/api\/v1\/classes\/class-1\/roster\/[^/]+$/.test(endpoint) && method === 'PUT') {
      const member = data.roster.find((row) => row.enrollment_id === endpoint.split('/').pop());
      if (!member) return error('RESOURCE_NOT_FOUND', '名单成员不存在', 404);
      const input = request.postDataJSON();
      member.student = { ...member.student, ...input, gender: input.gender || null, major: input.major || null };
      return json(member);
    }
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

    const signupPage = await browser.newPage({ viewport: { width: 375, height: 812 } });
    watchPage(signupPage);
    const signupData = createFixtures('STUDENT'); signupData.registrations = [];
    // Leave the teacher's empty list open before another session submits an application.
    const registrationTeacherPage = await browser.newPage(); watchPage(registrationTeacherPage);
    const registrationTeacher = createFixtures(); registrationTeacher.login(); registrationTeacher.registrations = signupData.registrations;
    await installApi(registrationTeacherPage, registrationTeacher); await registrationTeacherPage.goto(`${baseUrl}/classes/class-1/registrations`);
    await registrationTeacherPage.getByText('暂无匹配的注册申请').waitFor();
    await installApi(signupPage, signupData); await signupPage.goto(`${baseUrl}/register`);
    await signupPage.getByRole('heading', { name: '学生注册' }).waitFor();
    await signupPage.getByLabel('学号', { exact: true }).fill('009'); await signupPage.getByLabel('姓名', { exact: true }).fill('注册同学');
    await signupPage.getByRole('button', { name: '匹配班级名单' }).click();
    await signupPage.getByLabel('设置密码', { exact: true }).fill('Student-password-123'); await signupPage.getByLabel('确认密码', { exact: true }).fill('Student-password-123');
    assert.equal(await signupPage.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'signup mobile overflow');
    await signupPage.getByRole('button', { name: '提交注册申请' }).click(); await signupPage.getByText(/申请已提交，等待任课老师/).waitFor();
    await registrationTeacherPage.getByRole('checkbox', { name: '选择注册同学的申请' }).check({ timeout: 20_000 });
    await registrationTeacherPage.getByRole('button', { name: '通过所选（1）' }).click(); await registrationTeacherPage.getByText('已处理 1 条注册申请').waitFor();
    assert.equal(signupData.registrations[0].status, 'APPROVED');
    await signupPage.getByRole('link', { name: '返回登录', exact: true }).click();
    await signupPage.getByLabel('用户名', { exact: true }).fill('009'); await signupPage.getByLabel('密码', { exact: true }).fill('Student-password-123');
    await signupPage.getByRole('button', { name: '登录', exact: true }).click(); await signupPage.getByRole('heading', { name: '我的课程' }).waitFor();
    await signupPage.close(); await registrationTeacherPage.close();
    const studentPage = await browser.newPage({ viewport: { width: 375, height: 812 } });
    watchPage(studentPage);
    const studentData = createFixtures('STUDENT'); studentData.login(); studentData.monitorGrants = ['mi1']; studentData.canReview = true; studentData.registrations = [{ id: 'monitor-review', name: '班长审核同学', student_number: '010', status: 'PENDING', created_at: '2026-11-03T00:00:00', can_review: true }];
    await installApi(studentPage, studentData); await studentPage.goto(`${baseUrl}/scores`);
    await studentPage.getByRole('heading', { name: '我的课程' }).waitFor();
    assert.equal(new URL(studentPage.url()).pathname, '/student');
    await studentPage.getByText('老师暂未开放考勤查看').waitFor();
    await studentPage.getByText('老师暂未开放平时分查看').waitFor();
    studentData.visibility = { attendance_visible: true, score_visibility: 'TOTAL' };
    await studentPage.getByRole('button', { name: '刷新数据' }).click();
    await studentPage.getByText('75.2', { exact: true }).waitFor();
    await studentPage.getByRole('cell', { name: '出勤', exact: true }).waitFor();
    assert.equal(await studentPage.getByText('项目明细', { exact: true }).count(), 0);
    studentData.visibility = { attendance_visible: false, score_visibility: 'HIDDEN' };
    await studentPage.getByRole('button', { name: '刷新数据' }).click();
    await studentPage.getByText('老师暂未开放平时分查看').waitFor();
    assert.equal(await studentPage.getByText('75.2', { exact: true }).count(), 0);
    assert.equal(await studentPage.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'student mobile overflow');
    await studentPage.getByRole('link', { name: '班长登记授权项目' }).click();
    await studentPage.getByRole('heading', { name: '授权项目平时分' }).waitFor();
    assert.equal(await studentPage.getByLabel('班长本人本次积分').isDisabled(), true);
    assert.equal(await studentPage.getByRole('button', { name: '新建项目', exact: true }).count(), 0);
    await studentPage.getByLabel('被登记同学本次积分').fill('2.5');
    await studentPage.getByLabel('被登记同学备注').fill('班长代录');
    await studentPage.getByRole('button', { name: '保存本次录入' }).click();
    await studentPage.getByText('授权项目积分已保存').waitFor();
    assert.equal(studentData.monitorRecord.points, '2.5');
    assert.equal(studentData.monitorRecord.note, '班长代录');
    assert.equal(await studentPage.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'monitor mobile overflow');
    await studentPage.getByRole('link', { name: '返回个人中心' }).click();
    await studentPage.getByRole('link', { name: '审核本班学生注册' }).click();
    await studentPage.getByRole('heading', { name: '学生注册审核' }).waitFor();
    await studentPage.getByRole('button', { name: '通过', exact: true }).click(); await studentPage.getByText('已处理 1 条注册申请').waitFor();
    assert.equal(studentData.registrations[0].status, 'APPROVED');
    assert.equal(await studentPage.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'review mobile overflow');
    await studentPage.close();

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
    await page.getByRole('button', { name: '编辑张敏', exact: true }).click();
    await page.getByRole('heading', { name: '编辑学生资料' }).waitFor();
    assert.equal(await page.getByLabel('学号', { exact: true }).inputValue(), '20260001');
    await page.getByLabel('专业', { exact: true }).fill('交互设计');
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await page.getByText('学生资料已保存', { exact: true }).waitFor();
    await page.getByRole('cell', { name: '交互设计', exact: true }).waitFor();
    assert.equal(fixtures.roster[0].student.major, '交互设计');
    await page.getByRole('button', { name: '班长授权管理' }).click();
    await page.getByRole('checkbox', { name: '允许审核本班学生注册' }).check();
    await page.getByRole('checkbox', { name: /班长登记项目/ }).check();
    await page.getByRole('button', { name: '保存授权' }).click();
    await page.getByText('班长授权已更新').waitFor();
    assert.deepEqual(fixtures.monitorGrants, ['mi1']);
    await page.getByRole('button', { name: '撤销全部授权' }).click();
    await page.getByRole('button', { name: '撤销全部授权' }).waitFor({ state: 'visible' });
    await page.waitForFunction(() => !document.querySelector('fieldset input[type=checkbox]')?.checked);
    assert.deepEqual(fixtures.monitorGrants, []);
    await page.getByRole('button', { name: '关闭', exact: true }).click();
    await page.getByRole('button', { name: '学生查看设置' }).click();
    await page.getByLabel('考勤数据').selectOption('true');
    await page.getByLabel('平时分数据').selectOption('TOTAL');
    await page.getByRole('button', { name: '保存设置' }).click();
    await page.getByText('学生查看权限已保存').waitFor();
    assert.deepEqual(fixtures.visibility, { attendance_visible: true, score_visibility: 'TOTAL' });
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
    console.log('React browser checks passed: student registration and teacher/monitor approval, monitor grants/revocation and scoring, student privacy and visibility, admin routing/logout, teacher attendance and scores workflows, accessibility, and responsive overflow.');
  } finally {
    if (browser) await browser.close(); vite.kill();
  }
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
