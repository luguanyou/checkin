# 平时成绩 Implementation Plan

**Goal:** 将已确认的基础分加表现积分设计实现为可持久保存、可导出的教师业务模块。

**Architecture:** FastAPI 独立 scores 模块负责权限、事务、计算与导出；React 复用现有查询、表单和反馈组件。按班级统一版本防止设置与批量录入互相覆盖；Decimal 在服务端计算。

**Tech Stack:** React / TypeScript / TanStack Query / FastAPI / SQLAlchemy / Alembic / MySQL / pytest / Vitest。

设计及完整前后端接口类型见 `docs/superpowers/specs/2026-09-22-usual-scores-design.md`，作为共同契约。

## 1. 后端（独立实现）

- [x] 新建 `api/tests/scores/test_scores_api.py`，先断言未实现接口返回不了 ScoreBook，再覆盖基础分、系数、小数、负积分、版本冲突、权限、历史和生命周期。
- [x] 新建 `api/src/attendance_api/models/scores.py`、`schemas/scores.py`、`modules/scores/{__init__,service,router,export}.py`。服务计算规则依照设计，独立函数使用 Decimal，正式汇总按 ROUND_HALF_UP 到两位。
- [x] 新增 `api/migrations/versions/0004_add_scores.py`，扩展 `models/__init__.py`、`main.py` 及班级清理逻辑。保持历史迁移不变。
- [x] 更新迁移表集合及 OpenAPI operation ID 测试，运行 pytest、Ruff 与 mypy，结果见下文。

## 2. 前端（独立实现）

- [x] 新建 `src/features/scores/ScoresPage.test.tsx`，先验证不存在的录入流程失败，再覆盖快捷值、基础分、保存错误、空值与零、只读状态。
- [x] 新建 `src/api/scores-types.ts`、`scores.test.ts`，扩展 `resources.ts`，严格按设计契约实现 scores resource。
- [x] 新建 `src/features/scores/` 下独立页面、项目录入、设置、汇总和历史组件；不得用客户端重算结果覆盖服务端正式汇总。
- [x] 扩展 `router.tsx`、`AppShell.tsx`、`CoursesPage.tsx`、`RosterPage.tsx` 与 `global.css`，提供第五项导航和快捷入口，修订删除提示。
- [x] 运行 `npm run test:unit` 与 `npm run build`，检查 390px 下页面无整体横向溢出。

## 3. 集成、文档与核验

- [x] 主代理检查两边契约一致性，验证真实 API 与界面端到端连通、不同班级的独立数据及刷新持久性。
- [x] 更新 `tests/browser-smoke.cjs` fixture 与成绩录入/设置/汇总流程，保留原有教师和管理员冒烟检查。
- [x] 更新用户指南、README、API README，描述基础分配置、系数、空值、积分、移除学生、导出和升级迁移。
- [x] 复核范围与权限、测试失败并修正；记录实际检查结果，交付本地变更，不自动推送或发布。

## 4. 验证记录（2026-09-22）

- 前端全量 Vitest：16 个文件、67 项测试通过；TypeScript 检查与生产构建通过。
- 后端全量 pytest：116 项通过，包含独立 MySQL 数据库上的迁移往返、权限、版本冲突及并发首次写入。
- mypy：60 个源文件通过；Alembic 检查无待生成迁移；本次变更的 Python 文件 Ruff 通过。全量 Ruff 存在原有 `modules/tts/router.py:76` 的 UP041 提示，未修改该无关文件。
- 独立 MySQL、真实 API 与浏览器联调通过：项目创建、小数与零积分、基础分配置、81.00 分汇总、刷新持久化、班级隔离、真实 XLSX 下载及移除/恢复名单。
- 浏览器验证桌面 1440px、手机 390px 和窄屏 320px 布局；最终 `npm run test:browser` 通过，涵盖原有教师、管理员流程、新增成绩操作、可访问性与横向溢出检查。`git diff --check` 通过。
- 补充修复并测试开发环境 StrictMode 下重复刷新登录令牌导致刷新页面退出登录的问题，以及弹窗输入时重复抢焦点的问题。
- 成绩草稿回归覆盖：固定项目和班级、防止后台刷新绕过版本冲突、网络错误时保留输入；原始积分显示和导出保留四位小数精度。
- 测试使用独立临时数据库，未升级或写入用户原有数据库，未提交、推送或部署。
