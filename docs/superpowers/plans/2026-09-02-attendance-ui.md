# Attendance UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive, high-fidelity teacher attendance prototype that runs directly from `index.html` and covers dashboard, courses, roster import, immersive roll call, records, correction, and export.

**Architecture:** Keep the existing no-build static structure. `index.html` owns semantic view templates and the complete responsive design system; `app.js` owns a single in-memory state object, pure derived-data helpers, DOM rendering, event delegation, Web Speech integration, and simulated synchronization. Node tests validate pure behavior and document structure, while Playwright exercises the complete browser flow at desktop and mobile sizes.

**Tech Stack:** HTML5, CSS3, vanilla JavaScript, Node.js built-in test runner, Playwright Core, browser Web Speech API, optional Lucide browser icons with text fallbacks.

---

## File Map

- Modify `index.html`: application shell, all view containers, dialogs, toast region, design tokens, responsive layout, and accessibility styles.
- Modify `app.js`: sample data, state creation, selectors, renderers, navigation, roster import simulation, roll-call state machine, keyboard handling, speech, record correction, and export simulation.
- Modify `tests/page.test.js`: static semantic structure and required-control coverage.
- Modify `tests/app.test.js`: pure-state, filtering, attendance, keyboard, and statistics coverage.
- Modify `tests/browser-smoke.js`: end-to-end navigation, modal, roll call, correction, export, overflow, and screenshot verification.

The directory is not a Git worktree. Do not initialize Git as part of this plan; replace commit steps with test checkpoints.

### Task 1: Define the Prototype State and Pure Attendance Helpers

**Files:**
- Modify: `app.js`
- Modify: `tests/app.test.js`

- [ ] **Step 1: Replace the old speech-demo tests with failing state-model tests**

Add these tests to `tests/app.test.js`:

```js
test('creates isolated prototype state with pending roster records', () => {
  const state = app.createInitialState();
  assert.equal(state.activeView, 'dashboard');
  assert.equal(state.rollCall.records.length, 12);
  assert.ok(state.rollCall.records.every((record) => record.status === 'pending'));
});

test('updates a student and advances without crossing the final boundary', () => {
  const state = app.createInitialState();
  const first = app.applyAttendanceStatus(state, 'absent');
  assert.equal(first.rollCall.records[0].status, 'absent');
  assert.equal(first.rollCall.currentIndex, 1);

  const lastState = {
    ...state,
    rollCall: { ...state.rollCall, currentIndex: state.rollCall.records.length - 1 },
  };
  const final = app.applyAttendanceStatus(lastState, 'present');
  assert.equal(final.rollCall.currentIndex, final.rollCall.records.length - 1);
});

test('derives progress, exception count and attendance rate from records', () => {
  const records = [
    { status: 'present' },
    { status: 'absent' },
    { status: 'late' },
    { status: 'pending' },
  ];
  assert.deepEqual(app.summarizeAttendance(records), {
    processed: 3,
    total: 4,
    present: 1,
    absent: 1,
    leave: 0,
    late: 1,
    pending: 1,
    exceptions: 2,
    attendanceRate: 67,
  });
});

test('maps supported point-call keys and ignores text inputs', () => {
  assert.equal(app.attendanceActionForKey(' ', false), 'present');
  assert.equal(app.attendanceActionForKey('1', false), 'absent');
  assert.equal(app.attendanceActionForKey('2', false), 'leave');
  assert.equal(app.attendanceActionForKey('3', false), 'late');
  assert.equal(app.attendanceActionForKey('Backspace', false), 'previous');
  assert.equal(app.attendanceActionForKey('1', true), null);
});
```

- [ ] **Step 2: Run the tests and verify the new API is missing**

Run:

```powershell
node --test tests/app.test.js
```

Expected: FAIL because `createInitialState`, `applyAttendanceStatus`, `summarizeAttendance`, and `attendanceActionForKey` are not defined.

- [ ] **Step 3: Implement the immutable state helpers and sample data**

In `app.js`, export these exact functions from the existing UMD wrapper:

```js
const ATTENDANCE_STATUSES = ['pending', 'present', 'absent', 'leave', 'late'];

function createInitialState() {
  const students = createSampleStudents();
  return {
    activeView: 'dashboard',
    mobileNavOpen: false,
    filters: { query: '', course: 'all', classGroup: 'all', status: 'all' },
    dialogs: { createCourse: false, importRoster: false, endRollCall: false, correction: false, export: false },
    toast: null,
    speech: { enabled: true, muted: false, rate: 1, volume: 1 },
    sync: { status: 'synced', pendingCount: 0 },
    courses: createSampleCourses(),
    students,
    attendanceSessions: createSampleSessions(),
    rollCall: {
      courseId: 'course-product-design',
      classGroupId: 'class-product-2',
      currentIndex: 0,
      started: false,
      completed: false,
      records: students.slice(0, 12).map((student) => ({ ...student, status: 'pending', markedAt: null })),
    },
  };
}

function applyAttendanceStatus(state, status) {
  if (!ATTENDANCE_STATUSES.includes(status) || status === 'pending') return state;
  const index = state.rollCall.currentIndex;
  const records = state.rollCall.records.map((record, recordIndex) => (
    recordIndex === index ? { ...record, status, markedAt: new Date().toISOString() } : record
  ));
  return {
    ...state,
    sync: { status: 'syncing', pendingCount: state.sync.pendingCount + 1 },
    rollCall: {
      ...state.rollCall,
      started: true,
      records,
      currentIndex: Math.min(index + 1, records.length - 1),
    },
  };
}

function summarizeAttendance(records) {
  const counts = { present: 0, absent: 0, leave: 0, late: 0, pending: 0 };
  records.forEach((record) => { counts[record.status] += 1; });
  const processed = records.length - counts.pending;
  const attended = counts.present + counts.late;
  return {
    processed,
    total: records.length,
    ...counts,
    exceptions: counts.absent + counts.late,
    attendanceRate: processed ? Math.round((attended / processed) * 100) : 0,
  };
}

function attendanceActionForKey(key, isTextInput) {
  if (isTextInput) return null;
  return ({ ' ': 'present', '1': 'absent', '2': 'leave', '3': 'late', Backspace: 'previous', r: 'repeat', R: 'repeat', m: 'mute', M: 'mute' })[key] || null;
}
```

Use these deterministic sample factories so browser assertions remain stable:

```js
function createSampleStudents() {
  const names = ['林晓雨', '陈嘉禾', '周子墨', '李思涵', '王宇辰', '许安然', '赵清和', '钱书宁', '孙嘉言', '郑思远', '冯可欣', '褚明轩'];
  return names.map((name, index) => ({
    id: 'student-' + String(index + 1).padStart(2, '0'),
    studentNumber: '20240102' + String(index + 1).padStart(2, '0'),
    name,
    gender: index % 2 ? '男' : '女',
    major: index < 8 ? '工业设计' : '数字媒体艺术',
    classGroupId: 'class-product-2',
  }));
}

function createSampleCourses() {
  return [
    { id: 'course-product-design', name: '产品设计方法', code: 'PD204', term: '2026 秋季学期', status: 'active', classes: [{ id: 'class-product-2', name: '2024 级 2 班', studentCount: 48, rosterStatus: 'ready' }] },
    { id: 'course-interaction', name: '交互设计基础', code: 'IXD102', term: '2026 秋季学期', status: 'active', classes: [{ id: 'class-interaction-1', name: '2024 级 1 班', studentCount: 46, rosterStatus: 'ready' }] },
    { id: 'course-service', name: '服务设计专题', code: 'SD301', term: '2026 秋季学期', status: 'active', classes: [{ id: 'class-service-1', name: '2023 级 1 班', studentCount: 32, rosterStatus: 'warning' }] },
  ];
}

function createSampleSessions() {
  return [
    { id: 'session-01', courseId: 'course-product-design', classGroupId: 'class-product-2', date: '2026-09-02', status: 'completed', exceptions: 3 },
    { id: 'session-02', courseId: 'course-product-design', classGroupId: 'class-product-2', date: '2026-08-28', status: 'completed', exceptions: 2 },
    { id: 'session-03', courseId: 'course-product-design', classGroupId: 'class-product-2', date: '2026-08-21', status: 'completed', exceptions: 4 },
    { id: 'session-04', courseId: 'course-interaction', classGroupId: 'class-interaction-1', date: '2026-09-01', status: 'completed', exceptions: 1 },
    { id: 'session-05', courseId: 'course-service', classGroupId: 'class-service-1', date: '2026-08-31', status: 'syncing', exceptions: 2 },
  ];
}
```

- [ ] **Step 4: Run the unit tests**

Run:

```powershell
node --test tests/app.test.js
```

Expected: all state-model tests PASS.

### Task 2: Build the Responsive Application Shell and Navigation

**Files:**
- Modify: `index.html`
- Modify: `app.js`
- Modify: `tests/page.test.js`

- [ ] **Step 1: Add failing static structure tests**

Replace the speech-demo structure assertions in `tests/page.test.js` with:

```js
test('provides the teacher application shell and all primary views', () => {
  assert.match(html, /id="appSidebar"/);
  assert.match(html, /data-view-target="dashboard"/);
  assert.match(html, /data-view-target="courses"/);
  assert.match(html, /data-view-target="roster"/);
  assert.match(html, /data-view-target="records"/);
  assert.match(html, /id="view-dashboard"/);
  assert.match(html, /id="view-courses"/);
  assert.match(html, /id="view-roster"/);
  assert.match(html, /id="view-records"/);
  assert.match(html, /id="view-rollcall"/);
});

test('provides accessible shared feedback and dialog regions', () => {
  assert.match(html, /id="toastRegion"[^>]+aria-live="polite"/);
  assert.match(html, /id="modalRoot"/);
  assert.match(html, /class="skip-link"/);
  assert.match(html, /prefers-reduced-motion/);
});
```

- [ ] **Step 2: Run page tests and verify failure**

Run:

```powershell
node --test tests/page.test.js
```

Expected: FAIL because the attendance application shell is absent.

- [ ] **Step 3: Replace `index.html` with the approved shell and design tokens**

Build this semantic skeleton and fill each view with its Task-specific section containers:

```html
<body>
  <a class="skip-link" href="#mainContent">跳到主要内容</a>
  <div class="app-shell" id="appShell">
    <aside class="sidebar" id="appSidebar" aria-label="主导航">
      <a class="brand" href="#dashboard" data-view-target="dashboard" aria-label="课点工作台">
        <span class="brand-mark" aria-hidden="true">课</span><span>课点</span>
      </a>
      <nav class="primary-nav">
        <button data-view-target="dashboard" aria-current="page">工作台</button>
        <button data-view-target="courses">课程班级</button>
        <button data-view-target="roster">学生名单</button>
        <button data-view-target="records">考勤记录</button>
      </nav>
    </aside>
    <div class="app-content">
      <header class="topbar" id="appTopbar"></header>
      <main id="mainContent" tabindex="-1">
        <section id="view-dashboard" data-view="dashboard"></section>
        <section id="view-courses" data-view="courses" hidden></section>
        <section id="view-roster" data-view="roster" hidden></section>
        <section id="view-records" data-view="records" hidden></section>
        <section id="view-rollcall" data-view="rollcall" hidden></section>
      </main>
      <nav class="mobile-nav" aria-label="移动端主导航"></nav>
    </div>
  </div>
  <div id="modalRoot"></div>
  <div id="toastRegion" class="toast-region" aria-live="polite"></div>
  <script src="app.js"></script>
</body>
```

Define CSS variables for `--page: #f4f6f5`, `--surface: #ffffff`, `--ink: #17231f`, `--muted: #66746e`, `--border: #dce3e0`, `--brand: #173e36`, `--brand-active: #2a6256`, `--accent: #e69b32`, status colors, a 6px radius, and restrained shadows. Add desktop sidebar tracks, a mobile breakpoint at 768px, 44px minimum controls, focus-visible styles, and reduced-motion overrides.

- [ ] **Step 4: Add view switching to `app.js`**

Implement:

```js
function setActiveView(nextView) {
  state.activeView = nextView;
  document.querySelectorAll('[data-view]').forEach((view) => {
    view.hidden = view.dataset.view !== nextView;
  });
  document.querySelectorAll('[data-view-target]').forEach((control) => {
    const active = control.dataset.viewTarget === nextView;
    control.toggleAttribute('aria-current', active);
  });
  document.getElementById('appShell').classList.toggle('rollcall-mode', nextView === 'rollcall');
  document.getElementById('mainContent').focus({ preventScroll: true });
}
```

Use one delegated click listener for `[data-view-target]`, update `location.hash`, and initialize from a recognized hash or `dashboard`.

- [ ] **Step 5: Run structure and unit tests**

Run:

```powershell
node --test tests/page.test.js tests/app.test.js
```

Expected: all tests PASS.

### Task 3: Implement Dashboard and Course/Class Management Views

**Files:**
- Modify: `index.html`
- Modify: `app.js`
- Modify: `tests/browser-smoke.js`

- [ ] **Step 1: Add failing Playwright assertions for management navigation**

Add these checks after loading the page:

```js
await expectVisible(page, '#view-dashboard');
assert.equal(await page.locator('[data-dashboard-course]').count(), 3);
await page.locator('[data-view-target="courses"]').first().click();
await expectVisible(page, '#view-courses');
assert.equal(await page.locator('[data-course-row]').count(), 3);
await page.locator('[data-action="open-create-course"]').click();
await expectVisible(page, '[role="dialog"][data-dialog="create-course"]');
```

Define `expectVisible(page, selector)` as:

```js
async function expectVisible(page, selector) {
  assert.equal(await page.locator(selector).isVisible(), true, selector + ' should be visible');
}
```

- [ ] **Step 2: Run the browser smoke test and verify failure**

Run:

```powershell
node tests/browser-smoke.js
```

Expected: FAIL on the missing dashboard course rows or create-course dialog.

- [ ] **Step 3: Render the dashboard**

Implement `renderDashboard(state)` to produce:

- a compact page heading with date and teacher greeting;
- three metrics: today courses, pending roll calls, weekly attendance rate;
- three stable-height course rows with time, course, class, roster state, and contextual action;
- a recent-activity list and one roster warning band.

Each course row must use `data-dashboard-course` and each contextual button must use `data-action="start-rollcall"`, `data-action="continue-rollcall"`, or `data-action="view-session"`.

- [ ] **Step 4: Render courses and add the create-course dialog**

Implement `renderCourses(state)` with query and status filters plus `data-course-row` rows. Implement `openDialog('create-course')` so the modal root contains:

```html
<div class="modal-backdrop" data-action="close-dialog">
  <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="createCourseTitle" data-dialog="create-course">
    <header><h2 id="createCourseTitle">新建课程</h2></header>
    <form id="createCourseForm">
      <label>课程名称<input name="name" required maxlength="120"></label>
      <label>课程代码<input name="code" required maxlength="50"></label>
      <label>学期<select name="term"><option>2026 秋季学期</option></select></label>
      <label>首个班级<input name="className" required maxlength="120"></label>
      <footer><button type="button" data-action="close-dialog">取消</button><button type="submit">创建课程</button></footer>
    </form>
  </section>
</div>
```

Prevent backdrop clicks from closing when the click originates inside `.dialog`. On valid submit, append a deterministic course object, close the dialog, re-render courses, and show `课程已创建` in the toast region.

- [ ] **Step 5: Run all tests**

Run:

```powershell
node --test tests/page.test.js tests/app.test.js
node tests/browser-smoke.js
```

Expected: unit tests PASS and browser navigation/create-dialog checks PASS.

### Task 4: Implement Roster Search and Three-Step Import Validation

**Files:**
- Modify: `index.html`
- Modify: `app.js`
- Modify: `tests/app.test.js`
- Modify: `tests/browser-smoke.js`

- [ ] **Step 1: Add failing roster helper tests**

```js
test('filters roster by name, number and major', () => {
  const students = app.createInitialState().students;
  assert.equal(app.filterStudents(students, '林晓雨').length, 1);
  assert.equal(app.filterStudents(students, '20240102').length, 12);
  assert.ok(app.filterStudents(students, '工业设计').length > 1);
});

test('validates imported rows and blocks missing required fields', () => {
  const result = app.validateImportRows([
    { row: 2, studentNumber: '2026001', name: '赵清', className: '2024级2班' },
    { row: 3, studentNumber: '', name: '钱宁', className: '2024级2班' },
    { row: 4, studentNumber: '2026001', name: '赵清', className: '2024级2班' },
  ]);
  assert.deepEqual(result.summary, { valid: 1, errors: 1, duplicates: 1, importable: 1 });
  assert.equal(result.canConfirm, false);
});
```

- [ ] **Step 2: Run tests and verify failure**

Run `node --test tests/app.test.js`.

Expected: FAIL because `filterStudents` and `validateImportRows` are missing.

- [ ] **Step 3: Implement roster helpers and renderer**

Implement case-insensitive `filterStudents` across `name`, `studentNumber`, and `major`. Implement `validateImportRows` so empty required values are errors and repeated student numbers after the first occurrence are duplicates. Return `{ rows, summary, canConfirm }` with exact summary keys from the test.

Render `#view-roster` with course/class selectors, query input, roster metadata, template download button, import button, and a semantic table. Use `data-roster-row` on each visible row and update results on input without changing the layout height of the toolbar.

- [ ] **Step 4: Implement the three-step import dialog**

The dialog states are:

1. `select`: drag/drop surface plus file input accepting `.xlsx,.xls,.csv`.
2. `preview`: fixed sample rows containing one missing name and one duplicate number; summary counts and an error-highlighted table.
3. `result`: success, skipped, and failed totals with a close action.

Use `data-import-step`, `data-action="simulate-file"`, `data-action="confirm-import"`, and `data-action="download-errors"`. Disable confirmation while `canConfirm` is false. Provide `使用修正后的示例数据` to replace the invalid sample with valid rows so the full success path can be demonstrated.

- [ ] **Step 5: Add and run browser checks**

Add:

```js
await page.locator('[data-view-target="roster"]').first().click();
await page.locator('[data-action="open-import"]').click();
await page.locator('[data-action="simulate-file"]').click();
assert.equal(await page.locator('[data-import-error]').count(), 1);
assert.equal(await page.locator('[data-action="confirm-import"]').isDisabled(), true);
await page.locator('[data-action="use-corrected-sample"]').click();
await page.locator('[data-action="confirm-import"]').click();
await expectVisible(page, '[data-import-step="result"]');
```

Run all unit and browser tests. Expected: PASS.

### Task 5: Implement Immersive Roll Call, Speech, Keyboard, and Sync Feedback

**Files:**
- Modify: `index.html`
- Modify: `app.js`
- Modify: `tests/page.test.js`
- Modify: `tests/app.test.js`
- Modify: `tests/browser-smoke.js`

- [ ] **Step 1: Add failing structure and behavior coverage**

Add static assertions for `id="studentName"`, `id="rollCallProgress"`, `id="exceptionList"`, `data-attendance-status="present"`, `absent`, `leave`, `late`, and `id="syncStatus"`.

Add this unit test:

```js
test('moves to the previous student without crossing index zero', () => {
  const state = app.createInitialState();
  assert.equal(app.moveRollCallIndex(state, -1).rollCall.currentIndex, 0);
  const atTwo = { ...state, rollCall: { ...state.rollCall, currentIndex: 2 } };
  assert.equal(app.moveRollCallIndex(atTwo, -1).rollCall.currentIndex, 1);
});
```

- [ ] **Step 2: Run page and unit tests and verify failure**

Run `node --test tests/page.test.js tests/app.test.js`.

Expected: FAIL on missing point-call structure and `moveRollCallIndex`.

- [ ] **Step 3: Build the approved desktop/mobile roll-call layout**

Render `#view-rollcall` with:

- a standalone top bar containing return, course/class/date, `#syncStatus`, and end action;
- progress text and stable progress track;
- centered `#studentName`, student number, major, current state, and speaking label;
- four 54px status buttons with shortcut labels;
- previous, repeat, and mute utility controls;
- desktop `#exceptionList` sidebar and mobile exception drawer summary.

Apply `.rollcall-mode` to hide the normal sidebar/topbar/mobile navigation. Keep status buttons in four columns on desktop and two columns below 560px.

- [ ] **Step 4: Wire attendance, keyboard, speech, and simulated synchronization**

Use one `updateAttendance(status)` function for mouse and keyboard. It must apply state immediately, render the roll-call view, call `speakCurrentStudent`, then schedule:

```js
clearTimeout(syncTimer);
syncTimer = window.setTimeout(() => {
  state.sync = { status: 'synced', pendingCount: 0 };
  renderSyncStatus();
}, 450);
```

Detect text inputs with:

```js
function isTextInputTarget(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target.isContentEditable;
}
```

For Web Speech, cancel the previous utterance, use `zh-CN`, current rate and volume, and skip speaking when muted or unsupported. Show a non-blocking toast on unsupported browsers.

- [ ] **Step 5: Add end-point-call blocking and confirmation**

When pending records or sync changes exist, open a dialog listing exact counts and keep confirmation disabled. When all records are resolved and synced, enable confirmation; confirming sets the session completed, shows `本次点名已完成`, and navigates to records.

- [ ] **Step 6: Add browser flow checks and run tests**

```js
await page.locator('[data-action="start-rollcall"]').first().click();
await expectVisible(page, '#view-rollcall');
await page.keyboard.press('1');
assert.equal(await page.locator('#exceptionList [data-exception-row]').count(), 1);
assert.equal(await page.locator('#studentName').textContent(), '陈嘉禾');
await page.keyboard.press('Backspace');
assert.equal(await page.locator('#studentName').textContent(), '林晓雨');
```

Expected: all tests PASS; speech calls contain `林晓雨` and no console errors occur.

### Task 6: Implement Attendance Records, Correction Audit, and Export Simulation

**Files:**
- Modify: `index.html`
- Modify: `app.js`
- Modify: `tests/app.test.js`
- Modify: `tests/browser-smoke.js`

- [ ] **Step 1: Add failing record filter and correction tests**

```js
test('filters attendance sessions by course, class and status', () => {
  const sessions = app.createInitialState().attendanceSessions;
  assert.equal(app.filterSessions(sessions, { course: 'all', classGroup: 'all', status: 'all' }).length, 5);
  assert.equal(app.filterSessions(sessions, { course: 'course-product-design', classGroup: 'all', status: 'completed' }).length, 3);
});

test('requires a reason when correcting a completed record', () => {
  assert.deepEqual(app.validateCorrection({ status: 'late', reason: '' }), { valid: false, message: '请填写修正原因' });
  assert.deepEqual(app.validateCorrection({ status: 'late', reason: '学生课间到场补签' }), { valid: true, message: '' });
});
```

- [ ] **Step 2: Run tests and verify failure**

Run `node --test tests/app.test.js`.

Expected: FAIL because `filterSessions` and `validateCorrection` are undefined.

- [ ] **Step 3: Implement the records list and detail drawer**

Render a filter toolbar and table with `data-session-row`. Each row includes date, course, class, processed count, exceptions, status, sync result, and actions. `查看详情` opens a right-side drawer with student records and `data-action="correct-record"` on abnormal rows.

- [ ] **Step 4: Implement correction validation and audit feedback**

Open a dialog with student, old status, target status, and required reason. Reject blank reasons with `请填写修正原因`; on success update final status and modified metadata, append an in-memory audit item, re-render, and show `考勤状态已修正`.

- [ ] **Step 5: Implement export confirmation and download feedback**

The export dialog must show course, class, date, row count, and a segmented format control for `.xlsx` and `.csv`. Confirming creates a small text Blob for the selected format, triggers a deterministic filename such as `产品设计方法_2024级2班_2026-09-02_单次考勤.csv`, revokes the object URL, closes the dialog, and shows `导出文件已生成`.

- [ ] **Step 6: Add browser assertions and run all tests**

```js
await page.locator('[data-view-target="records"]').first().click();
await page.locator('[data-session-row] [data-action="view-session"]').first().click();
await page.locator('[data-action="correct-record"]').first().click();
await page.locator('[name="correctionReason"]').fill('学生课间到场补签');
await page.locator('[data-action="confirm-correction"]').click();
assert.match(await page.locator('#toastRegion').textContent(), /考勤状态已修正/);
await page.locator('[data-action="open-export"]').first().click();
await page.locator('[data-action="confirm-export"]').click();
assert.match(await page.locator('#toastRegion').textContent(), /导出文件已生成/);
```

Expected: all tests PASS.

### Task 7: Finish Accessibility, Responsive QA, and Visual Verification

**Files:**
- Modify: `index.html`
- Modify: `app.js`
- Modify: `tests/browser-smoke.js`

- [ ] **Step 1: Expand the browser smoke matrix**

Add a loop over these viewports:

```js
const viewports = [
  { name: 'desktop', width: 1440, height: 1000 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'small-mobile', width: 320, height: 740 },
];
```

For dashboard, roster, roll call, and records, assert:

```js
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
assert.equal(overflow, false, viewport.name + ' must not scroll horizontally');
```

Also assert dialogs have a visible heading, Escape closes non-blocking dialogs, focus returns to the opener, and every visible button has an accessible name.

- [ ] **Step 2: Run the smoke test and fix each reported issue**

Run:

```powershell
node tests/browser-smoke.js
```

Expected before fixes: any overflow, focus, or accessible-name defect fails with the exact viewport/view name.

- [ ] **Step 3: Apply responsive and focus corrections**

Use `minmax(0, 1fr)` for all flexible grid tracks, `min-width: 0` for grid children, `overflow-wrap: anywhere` for user data, stable minimum heights for status buttons and rows, a single-column toolbar below 560px, and drawer/dialog widths constrained with `width: min(100% - 24px, 560px)`.

Store the modal opener before opening, focus the first meaningful control after render, trap Tab inside the dialog, close with Escape when allowed, and restore focus after close.

- [ ] **Step 4: Save required screenshots and inspect them**

Save these files under the system temp directory:

```text
attendance-dashboard-desktop.png
attendance-roster-desktop.png
attendance-rollcall-desktop.png
attendance-records-desktop.png
attendance-dashboard-mobile.png
attendance-rollcall-mobile.png
```

Inspect all six for blank regions, overlapping text, clipped controls, inconsistent spacing, status legibility, and mobile navigation collisions. Fix any defect and regenerate the affected screenshot.

- [ ] **Step 5: Run the complete verification suite**

Run:

```powershell
node --test tests/page.test.js tests/app.test.js
node tests/browser-smoke.js
```

Expected:

```text
All Node tests pass.
Browser smoke checks pass for navigation, import, roll call, correction, export, accessibility, and desktop/mobile overflow.
No browser console errors are recorded.
```

- [ ] **Step 6: Open the final artifact**

Open `index.html` directly in Chrome or Edge and verify the first screen is the working teacher dashboard. No server or dependency installation should be required.
