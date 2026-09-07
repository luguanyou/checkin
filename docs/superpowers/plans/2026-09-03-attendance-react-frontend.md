# Attendance React Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the static attendance prototype with a production-oriented React application connected to the existing FastAPI contract.

**Architecture:** Use a Vite React TypeScript SPA with route-level feature modules, an in-memory authentication provider, a small typed fetch client, and TanStack Query for server state. Preserve the approved CSS visual language while moving every business workflow to real API calls; use MSW-style fetch stubs in browser tests and the Vite `/api` proxy for local integration.

**Tech Stack:** React, TypeScript, Vite, React Router, TanStack Query, Lucide React, Vitest, Testing Library, Playwright Core, CSS.

---

## File Map

- Replace `index.html`: Vite root document with the React mount point.
- Remove `app.js` from the runtime: retain no mock application path.
- Create `src/api/client.ts`, `src/api/types.ts`, `src/api/resources.ts`: transport, API contracts, and endpoint wrappers.
- Create `src/app/auth.tsx`, `src/app/router.tsx`, `src/app/query-client.ts`, `src/main.tsx`: application providers and routing.
- Create `src/components/*`: shared feedback, form, dialog, pagination, layout, and navigation controls.
- Create `src/features/auth/*`, `dashboard/*`, `courses/*`, `roster/*`, `attendance/*`, `records/*`: route components and feature-specific state.
- Create `src/styles/*`: design tokens, global styles, shell, components, and feature layouts.
- Replace `tests/*.js` with `src/**/*.test.ts(x)` and `tests/browser-smoke.js`: unit, component, and browser behavior.
- Modify `api/src/attendance_api/config.py` and `api/src/attendance_api/modules/auth/router.py`: configurable refresh-cookie security for local HTTP only.
- Modify `api/tests/auth/test_auth_api.py`: verify secure production and configurable development cookie behavior.
- Create `README.md` and `.env.example`: local setup and frontend configuration.

The repository is not a Git worktree. Do not initialize Git or add commit steps; each task ends with a test checkpoint.

### Task 1: React and Test Foundation

**Files:**
- Modify: `package.json`
- Modify: `index.html`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `src/vite-env.d.ts`
- Create: `src/main.tsx`
- Create: `src/app/App.tsx`
- Create: `src/test/setup.ts`
- Create: `src/app/App.test.tsx`

- [ ] **Step 1: Install runtime and test dependencies**

Run:

```powershell
npm install react react-dom react-router-dom @tanstack/react-query lucide-react
npm install --save-dev typescript vite @vitejs/plugin-react vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @types/react @types/react-dom
```

Expected: `package-lock.json` records the React/Vite toolchain without audit errors that block installation.

- [ ] **Step 2: Write the failing mount test**

Create `src/app/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { App } from './App';

describe('App', () => {
  it('renders the attendance application identity', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: '课点' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the test and verify RED**

Run: `npm run test:unit -- src/app/App.test.tsx`

Expected: FAIL because `src/app/App.tsx` and the Vitest configuration do not exist.

- [ ] **Step 4: Add Vite, TypeScript, Vitest, and the minimal React mount**

Set scripts to `dev`, `build`, `typecheck`, `test:unit`, `test:browser`, and `test`. Configure Vitest with `jsdom` and `src/test/setup.ts`; configure Vite to proxy `/api` to `VITE_API_PROXY_TARGET` or `http://127.0.0.1:8000`. Render a minimal `App` heading from `src/main.tsx` into `<div id="root"></div>`.

- [ ] **Step 5: Verify GREEN and build**

Run:

```powershell
npm run test:unit -- src/app/App.test.tsx
npm run typecheck
npm run build
```

Expected: one test passes, TypeScript exits zero, and Vite emits `dist/`.

### Task 2: Typed API Client and Authentication

**Files:**
- Create: `src/api/types.ts`
- Create: `src/api/client.ts`
- Create: `src/api/client.test.ts`
- Create: `src/api/resources.ts`
- Create: `src/app/auth.tsx`
- Create: `src/features/auth/LoginPage.tsx`
- Create: `src/features/auth/ChangePasswordPage.tsx`
- Create: `src/features/auth/AuthPages.test.tsx`

- [ ] **Step 1: Write failing client tests**

Cover these observable behaviors with injected `fetch`:

```ts
it('adds the bearer token and parses JSON');
it('converts the uniform API error into ApiError');
it('shares one refresh across concurrent 401 responses');
it('retries an unauthorized request only once');
it('returns blobs and a decoded content-disposition filename');
```

Assert that authentication requests use `credentials: 'include'`, JSON requests set `Content-Type: application/json`, and multipart requests do not set that header manually.

- [ ] **Step 2: Run the client tests and verify RED**

Run: `npm run test:unit -- src/api/client.test.ts`

Expected: FAIL because `ApiClient`, `ApiError`, and filename parsing are missing.

- [ ] **Step 3: Implement the API contracts and client**

Define exact snake_case interfaces for `User`, `Course`, `ClassGroup`, `RosterMember`, import preview/confirmation, `AttendanceSession`, `AttendanceRecord`, pagination, and `ErrorResponse`. Implement:

```ts
class ApiClient {
  setAccessToken(token: string | null): void;
  request<T>(path: string, init?: RequestInit, retry?: boolean): Promise<T>;
  download(path: string): Promise<{ blob: Blob; filename: string }>;
}
```

Use one private refresh promise. A 401 from any endpoint except login/refresh triggers `/auth/refresh`, updates the in-memory token through a callback, and retries once. Convert non-2xx JSON responses to `ApiError` and preserve request IDs.

- [ ] **Step 4: Verify the API client GREEN**

Run: `npm run test:unit -- src/api/client.test.ts`

Expected: all transport tests pass.

- [ ] **Step 5: Write failing authentication page tests**

Test login field validation, disabled submit while pending, backend message rendering, `must_change_password` redirection, password mismatch, and logout state clearing.

- [ ] **Step 6: Implement `AuthProvider`, login, and change-password pages**

Expose `status`, `user`, `login`, `changePassword`, and `logout`. On mount, call refresh once; show a full-page boot state until it resolves. Keep tokens only inside the provider/client. Login requires a nonblank username and a password of at least 12 characters. Change password requires current password, 12-character new password, and exact confirmation.

- [ ] **Step 7: Verify authentication GREEN**

Run: `npm run test:unit -- src/features/auth/AuthPages.test.tsx`

Expected: authentication tests pass with no React act warnings.

### Task 3: Router, Application Shell, and Shared UI

**Files:**
- Create: `src/app/router.tsx`
- Create: `src/app/query-client.ts`
- Create: `src/components/AppShell.tsx`
- Create: `src/components/AsyncState.tsx`
- Create: `src/components/Dialog.tsx`
- Create: `src/components/ToastProvider.tsx`
- Create: `src/components/Pagination.tsx`
- Create: `src/components/AppShell.test.tsx`
- Create: `src/styles/tokens.css`
- Create: `src/styles/global.css`
- Create: `src/styles/shell.css`
- Create: `src/styles/components.css`

- [ ] **Step 1: Write failing routing and shell tests**

Assert that anonymous users are redirected to `/login`, authenticated users see four primary navigation items, forced-password users are redirected to `/change-password`, active navigation uses `aria-current="page"`, dialogs restore focus on close, and loading/error/empty states expose accessible status text.

- [ ] **Step 2: Run the shell tests and verify RED**

Run: `npm run test:unit -- src/components/AppShell.test.tsx`

Expected: FAIL because protected routing and shared UI do not exist.

- [ ] **Step 3: Implement providers, routes, shared UI, and approved visual tokens**

Build the desktop sidebar, sticky top bar, mobile header, and bottom navigation. Implement focus-managed dialogs, polite Toast announcements, reusable loading/error/empty states, and pagination. Preserve deep green navigation, amber primary actions, compact 4-8px spacing, status colors with text, 44px targets, 320px minimum layout, and reduced-motion support.

- [ ] **Step 4: Verify shell GREEN**

Run: `npm run test:unit -- src/components/AppShell.test.tsx`

Expected: routing, navigation, dialog focus, and shared state tests pass.

### Task 4: Dashboard and Course/Class Management

**Files:**
- Create: `src/features/dashboard/DashboardPage.tsx`
- Create: `src/features/dashboard/dashboard-selectors.ts`
- Create: `src/features/dashboard/dashboard-selectors.test.ts`
- Create: `src/features/courses/CoursesPage.tsx`
- Create: `src/features/courses/CourseDialog.tsx`
- Create: `src/features/courses/ClassDialog.tsx`
- Create: `src/features/courses/CoursesPage.test.tsx`
- Create: `src/styles/dashboard.css`
- Create: `src/styles/courses.css`

- [ ] **Step 1: Write failing dashboard selector tests**

Verify metrics are derived from API courses and sessions, completed-session rate uses `present + late` over non-pending records, and empty arrays produce zero-valued metrics.

- [ ] **Step 2: Run selectors and verify RED**

Run: `npm run test:unit -- src/features/dashboard/dashboard-selectors.test.ts`

Expected: FAIL because dashboard selectors are missing.

- [ ] **Step 3: Implement dashboard selectors and page**

Query active courses and the latest attendance sessions in parallel. Render stable metric panels, upcoming/unfinished sessions, recent activity, and direct actions to create or resume a session. Render a first-course call to action when no courses exist.

- [ ] **Step 4: Write failing course workflow tests**

Test URL-backed search/status filters, course creation fields (`name`, `code`, `term`), class creation (`name`), archive confirmation, retained input after server failure, and query invalidation after success.

- [ ] **Step 5: Run course tests and verify RED**

Run: `npm run test:unit -- src/features/courses/CoursesPage.test.tsx`

Expected: FAIL because course pages and mutations are missing.

- [ ] **Step 6: Implement course and class management**

Use list, create, and patch endpoints. Keep filters in `useSearchParams`; use separate dialogs for courses and classes. Display class counts and provide roster and start-attendance links per class. Do not show controls unsupported by the API.

- [ ] **Step 7: Verify Task 4 GREEN**

Run: `npm run test:unit -- src/features/dashboard src/features/courses`

Expected: dashboard and course tests pass.

### Task 5: Roster, Membership, and Import

**Files:**
- Create: `src/features/roster/RosterPage.tsx`
- Create: `src/features/roster/ImportRosterDialog.tsx`
- Create: `src/features/roster/import-utils.ts`
- Create: `src/features/roster/import-utils.test.ts`
- Create: `src/features/roster/RosterPage.test.tsx`
- Create: `src/styles/roster.css`

- [ ] **Step 1: Write failing import utility tests**

Test accepted `.csv`, `.xlsx`, and `.xls` names; reject other extensions and files larger than 10 MiB; generate a UTF-8 BOM CSV template; map preview row status to visible labels.

- [ ] **Step 2: Run import utility tests and verify RED**

Run: `npm run test:unit -- src/features/roster/import-utils.test.ts`

Expected: FAIL because the validation and template helpers are absent.

- [ ] **Step 3: Implement import utilities**

Return concrete Chinese validation messages, generate columns `学号,姓名,性别,班级,专业`, and create/revoke the template object URL only around the click.

- [ ] **Step 4: Write failing roster workflow tests**

Test debounced query parameters, status filter, pagination, empty roster, remove/restore confirmation, real `FormData` preview upload, error-row blocking, duplicate policy selection, expired preview recovery, and list invalidation after confirmation.

- [ ] **Step 5: Run roster tests and verify RED**

Run: `npm run test:unit -- src/features/roster/RosterPage.test.tsx`

Expected: FAIL because the page and import state machine are missing.

- [ ] **Step 6: Implement roster and import workflow**

Load class context from cached courses or refetch it. Query the paginated roster from the server, patch membership status, and implement select → preview → confirm → result import steps. Preserve the selected file only until preview completes and never store file contents in browser storage.

- [ ] **Step 7: Verify Task 5 GREEN**

Run: `npm run test:unit -- src/features/roster`

Expected: all roster and import tests pass.

### Task 6: Attendance Session and Optimistic Roll Call

**Files:**
- Create: `src/features/attendance/AttendancePage.tsx`
- Create: `src/features/attendance/attendance-state.ts`
- Create: `src/features/attendance/attendance-state.test.ts`
- Create: `src/features/attendance/useRecordMutationQueue.ts`
- Create: `src/features/attendance/useRecordMutationQueue.test.tsx`
- Create: `src/hooks/useSpeech.ts`
- Create: `src/hooks/useSpeech.test.tsx`
- Create: `src/styles/attendance.css`

- [ ] **Step 1: Write failing attendance state tests**

Test first-pending initialization, final-index bounds, summary derivation, supported keys, input-focus exclusion, exception selection, and completion blocking for pending or unsynced records.

- [ ] **Step 2: Run state tests and verify RED**

Run: `npm run test:unit -- src/features/attendance/attendance-state.test.ts`

Expected: FAIL because the pure attendance functions are missing.

- [ ] **Step 3: Implement pure attendance state helpers**

Define `attendanceActionForKey`, `firstPendingIndex`, `clampIndex`, `summarizeRecords`, `exceptionRecords`, and `canCompleteSession` with API record/status types.

- [ ] **Step 4: Write failing mutation queue tests**

Verify immediate optimistic display, same-record sequential submission with the returned version, cross-record parallel submission, rollback on network failure, session refetch on `ATTENDANCE_RECORD_CONFLICT`, stable UUID reuse for one retry, and pending mutation count.

- [ ] **Step 5: Run queue tests and verify RED**

Run: `npm run test:unit -- src/features/attendance/useRecordMutationQueue.test.tsx`

Expected: FAIL because the queue hook does not exist.

- [ ] **Step 6: Implement mutation queue, speech hook, and attendance page**

Load the session by ID and reject completed sessions from edit mode. Render current student, fixed-size progress, four status controls, previous/repeat/mute controls, and an exception panel. Submit record patches with version and `crypto.randomUUID()`. Complete only after all records are final and mutations have settled; on success navigate to `/records/:sessionId`.

- [ ] **Step 7: Verify Task 6 GREEN**

Run: `npm run test:unit -- src/features/attendance src/hooks/useSpeech.test.tsx`

Expected: attendance, queue, and speech tests pass.

### Task 7: Records, Correction, and Binary Export

**Files:**
- Create: `src/features/records/RecordsPage.tsx`
- Create: `src/features/records/RecordDetailPage.tsx`
- Create: `src/features/records/CorrectionDialog.tsx`
- Create: `src/features/records/ExportDialog.tsx`
- Create: `src/features/records/RecordsPages.test.tsx`
- Create: `src/styles/records.css`

- [ ] **Step 1: Write failing record workflow tests**

Test URL-backed course/class/status/date filters, paging, empty results, detail summary, required correction reason for completed sessions, expected record version and UUID payload, conflict refresh, CSV/XLSX selection, server filename use, and object URL cleanup.

- [ ] **Step 2: Run record tests and verify RED**

Run: `npm run test:unit -- src/features/records/RecordsPages.test.tsx`

Expected: FAIL because records pages and dialogs are absent.

- [ ] **Step 3: Implement records pages, correction, and export**

Query session lists and detail using route/search parameters. Correct records through the shared endpoint and require a trimmed reason for completed sessions. Download the binary response, create a temporary anchor with the parsed filename, click it, and revoke the object URL in `finally`.

- [ ] **Step 4: Verify Task 7 GREEN**

Run: `npm run test:unit -- src/features/records`

Expected: all record and export tests pass.

### Task 8: Development Cookie, Browser QA, and Documentation

**Files:**
- Modify: `api/src/attendance_api/config.py`
- Modify: `api/src/attendance_api/modules/auth/router.py`
- Modify: `api/tests/auth/test_auth_api.py`
- Replace: `tests/browser-smoke.js`
- Create: `tests/browser-fixtures.js`
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: Write the failing backend cookie test**

Add a test that overrides settings with `refresh_cookie_secure=False`, logs in, and asserts the refresh cookie is HttpOnly, SameSite strict, scoped to `/api/v1/auth`, and lacks Secure. Keep the existing/default assertion that production-style settings emit Secure.

- [ ] **Step 2: Run the cookie test and verify RED**

Run from `api/`: `uv run pytest tests/auth/test_auth_api.py -k cookie -q`

Expected: FAIL because cookie security is hard-coded.

- [ ] **Step 3: Implement the cookie setting**

Add `refresh_cookie_secure: bool = True` to settings and use it consistently in `set_cookie` and `delete_cookie`. Document `REFRESH_COOKIE_SECURE=false` only for local HTTP development.

- [ ] **Step 4: Verify backend GREEN**

Run from `api/`:

```powershell
uv run pytest tests/auth/test_auth_api.py -q
uv run ruff check .
uv run mypy src
```

Expected: auth tests, lint, and type checking pass.

- [ ] **Step 5: Write browser fixtures and end-to-end checks**

Intercept `/api/v1/**` requests with deterministic in-memory fixtures that implement refresh/login, course/class creation, roster preview/confirm, session creation/detail, record version updates, completion, and binary export. Exercise login → course/class → roster import → session creation → keyboard point call → completion → correction → export.

- [ ] **Step 6: Run browser tests and fix only test-demonstrated defects**

Run: `npm run test:browser`

Expected: workflow passes in Chrome at 1440×1000, 390×844, and 320×740; no page-level overflow, unhandled page errors, console errors, inaccessible visible buttons, or focus loss.

- [ ] **Step 7: Document development and production commands**

Document `npm install`, `npm run dev`, API startup, `VITE_API_PROXY_TARGET`, `REFRESH_COOKIE_SECURE`, full tests, and build output. State that production must serve `dist/` and `/api` from the same HTTPS origin or an equivalently configured reverse proxy.

- [ ] **Step 8: Run the full verification suite**

Run:

```powershell
npm run typecheck
npm run test:unit
npm run build
npm run test:browser
Set-Location api
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Expected: every command exits zero, browser console error count is zero, and the build produces a nonempty `dist/` bundle.
