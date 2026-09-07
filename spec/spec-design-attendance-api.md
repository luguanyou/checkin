---
title: 智能课堂考勤系统 API 规范
version: 1.0
date_created: 2026-09-03
last_updated: 2026-09-03
owner: 项目开发团队
tags: [design, api, rest, fastapi, attendance]
---

# Introduction

本文档定义智能课堂考勤系统首期可上线版本的 HTTP API。它是 FastAPI 路由与 Pydantic 模型、OpenAPI 生成结果、前端类型客户端和 API 集成测试的共同契约。

本文档遵循[智能课堂考勤系统技术规格](./spec-architecture-attendance-system.md)和[数据库表结构规范](./spec-schema-attendance-database.md)。首期后端是单个 FastAPI 模块化单体，所有业务接口使用 `/api/v1` 前缀。

## 1. Purpose & Scope

### 1.1 目标

- 为管理员提供教师账号管理接口。
- 为教师提供认证、课程班级、名单导入、考勤和单次导出接口。
- 通过资源归属校验、刷新令牌轮换、幂等变更和乐观锁保证安全与一致性。
- 生成稳定 OpenAPI，使 React 前端从规范生成请求和响应类型。

### 1.2 首期接口模块

| 模块 | 前缀 | 职责 |
| --- | --- | --- |
| 健康检查 | `/api/v1/health` | 存活和就绪检查 |
| 认证 | `/api/v1/auth` | 登录、刷新、退出、当前用户、修改密码 |
| 管理员用户 | `/api/v1/admin/users` | 创建、查询、启停和重置教师账号 |
| 课程与名单 | `/api/v1/courses`、`/api/v1/classes`、`/api/v1/enrollments` | 课程班级、名单和导入 |
| 考勤 | `/api/v1/attendance-sessions`、`/api/v1/attendance-records` | 场次、状态、完成和导出 |

### 1.3 首期不提供

- 教师注册、找回密码和统一身份认证接口。
- 全校学生搜索或学生身份编辑接口。
- 审计日志查询接口。审计由服务端内部写入。
- 删除课程、班级、场次、记录或审计日志的接口。
- 离线批量同步、学期汇总和平时分接口。
- 请假审批和学生端签到接口。

## 2. Definitions

| 术语 | 定义 |
| --- | --- |
| Access Token | 有效期 15 分钟的 JWT，通过 Bearer 认证头发送 |
| Refresh Token | 有效期 7 天的随机令牌，仅通过安全 Cookie 发送，服务端只保存哈希 |
| 资源归属 | 当前教师是否为目标课程的 `owner_teacher_id` |
| 业务日期 | 按 `Asia/Shanghai` 确定的课堂日期，格式为 `YYYY-MM-DD` |
| 乐观锁 | 请求携带 `expected_version`，只更新相同版本的考勤记录 |
| 安全重试 | 相同 `client_mutation_id` 的请求重复提交时返回首次成功结果，不重复修改 |

## 3. Requirements, Constraints & Guidelines

### 3.1 协议和命名

- **API-001**：生产环境只允许 HTTPS；JSON 请求和响应使用 UTF-8。
- **API-002**：JSON 字段、路径变量和查询参数使用 `snake_case`。
- **API-003**：UUID 作为字符串传输；日期使用 `YYYY-MM-DD`；时间使用带时区的 ISO 8601。
- **API-004**：所有接口位于 `/api/v1`；不得发布无版本业务接口。
- **API-005**：创建成功返回 `201 Created`，同步更新成功返回 `200 OK`，无响应体成功返回 `204 No Content`。
- **API-006**：响应不使用额外 `data` 包装层。单资源直接返回资源对象，列表使用统一分页结构。
- **API-007**：FastAPI 必须为每个端点声明稳定的 `operation_id`，前端按 OpenAPI 生成类型和客户端。

### 3.2 认证和授权

- **AUT-001**：除登录、刷新和健康检查外，接口默认要求 `Authorization: Bearer <access_token>`。
- **AUT-002**：刷新令牌 Cookie 名称为 `refresh_token`，属性为 `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth; Max-Age=604800`。
- **AUT-003**：刷新接口必须校验 `Origin` 等于配置的 HTTPS 前端源站，并在成功时轮换刷新令牌。
- **AUT-004**：首次密码未修改的用户只能访问刷新、退出、当前用户和修改密码接口；其他业务接口返回 `PASSWORD_CHANGE_REQUIRED`。
- **AUT-005**：教师访问不属于自己的课程关联资源时统一返回 `RESOURCE_NOT_FOUND`，避免泄露资源是否存在。
- **AUT-006**：管理员接口要求 `ADMIN`；教师业务接口要求 `TEACHER`。首期管理员不通过教师接口访问教学数据。
- **AUT-007**：禁用账号、退出和密码重置必须撤销适用的刷新会话。
- **AUT-008**：登录失败提示保持一致，不区分用户名不存在、密码错误或账号不可登录。

### 3.3 分页、筛选和排序

- **LST-001**：分页参数 `page` 默认 1，最小 1；`page_size` 默认 20，范围 1 至 100。
- **LST-002**：列表响应包含 `items`、`page`、`page_size` 和 `total`。
- **LST-003**：未特别说明时，列表按 `created_at DESC, id DESC` 稳定排序。
- **LST-004**：搜索字符串去除首尾空格，最大 100 个字符；空字符串等同未提供。

### 3.4 并发、幂等和事务

- **CON-API-001**：考勤状态更新必须携带 UUID `client_mutation_id` 和正整数 `expected_version`。
- **CON-API-002**：相同 `client_mutation_id` 的重试返回首次成功响应，不重复更新记录或写入审计日志。
- **CON-API-003**：不同变更 ID 但版本过期的更新返回 HTTP 409 `ATTENDANCE_RECORD_CONFLICT`，并在 `details.current_record` 中返回当前可见记录。
- **CON-API-004**：写接口只能在数据库事务提交后返回成功。
- **CON-API-005**：前端点名时先乐观更新本地内存，再异步调用状态接口；请求不得阻塞移动到下一名学生。

### 3.5 请求追踪和限流

- **OBS-001**：服务端接受合法的 `X-Request-ID`，未提供时生成新值；响应始终返回 `X-Request-ID`。
- **OBS-002**：错误响应中的 `request_id` 与响应头一致。
- **OBS-003**：日志不得记录密码、访问令牌、刷新令牌、完整名单文件或完整学生名单。
- **OBS-004**：登录和上传接口由 Nginx 与应用共同限流；HTTP 429 响应包含 `Retry-After`。

## 4. Interfaces & Data Contracts

### 4.1 通用请求头

| 请求头 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `Authorization` | 受保护接口必填 | `Bearer eyJ...` | 访问令牌 |
| `Content-Type` | 有请求体时必填 | `application/json` | 文件上传为 `multipart/form-data` |
| `Accept` | 否 | `application/json` | 导出接口可省略 |
| `X-Request-ID` | 否 | `req_01HXYZ` | 1 至 64 个 ASCII 字符 |
| `Origin` | 刷新接口必填 | `https://attendance.example.edu` | 必须匹配配置源站 |

### 4.2 通用列表响应

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

`total` 是应用当前过滤条件后的总数，不是当前页数量。

### 4.3 通用错误响应

```json
{
  "code": "ATTENDANCE_RECORD_CONFLICT",
  "message": "该记录已被其他操作更新，请刷新后重试",
  "details": {
    "current_record": {
      "id": "b0b0133d-24b2-49e1-b193-1314fe230d5b",
      "status": "present",
      "version": 4
    }
  },
  "request_id": "req_01HXYZ"
}
```

`details` 始终为 JSON 对象，无附加数据时返回 `{}`。生产响应不得包含堆栈、SQL、文件路径或内部异常类名。

### 4.4 核心资源模型

#### `User`

```json
{
  "id": "2be4b8c1-6e47-4e1d-a835-fcef3f18b3b3",
  "username": "teacher01",
  "display_name": "王老师",
  "role": "TEACHER",
  "status": "ACTIVE",
  "must_change_password": false,
  "last_login_at": "2026-09-03T00:40:12.123456Z",
  "created_at": "2026-09-01T03:00:00Z",
  "updated_at": "2026-09-03T00:40:12.123456Z"
}
```

任何用户响应均不得包含 `password_hash`、失败登录计数或会话令牌。

#### `Course`

```json
{
  "id": "a8c55d19-833a-44ed-a635-f16450b17d18",
  "name": "产品设计方法",
  "code": "PD204",
  "term": "2026 秋季学期",
  "status": "ACTIVE",
  "classes": [
    {
      "id": "fa36375b-a0d5-40bc-94b5-2b6ab6721cb3",
      "name": "2024 级 2 班",
      "status": "ACTIVE",
      "active_student_count": 48
    }
  ],
  "created_at": "2026-09-01T03:00:00Z",
  "updated_at": "2026-09-01T03:00:00Z"
}
```

#### `RosterMember`

```json
{
  "enrollment_id": "5c023f9d-77bb-46ef-82f9-7dd3577d2d03",
  "enrollment_status": "ACTIVE",
  "student": {
    "id": "00cd7733-b22b-46ac-b885-bc37bb7ea807",
    "student_number": "2024010201",
    "name": "林晓雨",
    "gender": "女",
    "major": "工业设计"
  },
  "created_at": "2026-09-01T03:00:00Z",
  "updated_at": "2026-09-01T03:00:00Z"
}
```

#### `AttendanceRecord`

```json
{
  "id": "b0b0133d-24b2-49e1-b193-1314fe230d5b",
  "student_id": "00cd7733-b22b-46ac-b885-bc37bb7ea807",
  "student_number": "2024010201",
  "student_name": "林晓雨",
  "class_name": "2024 级 2 班",
  "status": "present",
  "marked_at": "2026-09-03T06:10:00Z",
  "last_modified_at": "2026-09-03T06:10:00Z",
  "last_modified_by": {
    "id": "2be4b8c1-6e47-4e1d-a835-fcef3f18b3b3",
    "display_name": "王老师"
  },
  "version": 2
}
```

`student_number`、`student_name` 和 `class_name` 来自场次快照，不从当前学生或班级记录动态覆盖。

#### `AttendanceSession`

```json
{
  "id": "2d7331e7-ff86-4d87-b854-df565bf97e4d",
  "course": {
    "id": "a8c55d19-833a-44ed-a635-f16450b17d18",
    "name": "产品设计方法",
    "code": "PD204"
  },
  "class_group": {
    "id": "fa36375b-a0d5-40bc-94b5-2b6ab6721cb3",
    "name": "2024 级 2 班"
  },
  "session_date": "2026-09-03",
  "status": "DRAFT",
  "started_at": "2026-09-03T06:00:00Z",
  "completed_at": null,
  "summary": {
    "total": 48,
    "pending": 47,
    "present": 1,
    "absent": 0,
    "leave": 0,
    "late": 0,
    "exceptions": 0
  },
  "records": [],
  "created_at": "2026-09-03T06:00:00Z",
  "updated_at": "2026-09-03T06:10:00Z"
}
```

列表响应中的 `records` 字段省略；单场次详情返回全部记录，最多 500 条。

### 4.5 端点总览

| 方法 | 路径 | 权限 | operation_id |
| --- | --- | --- | --- |
| GET | `/api/v1/health/live` | 公开 | `getHealthLive` |
| GET | `/api/v1/health/ready` | 公开 | `getHealthReady` |
| POST | `/api/v1/auth/login` | 公开 | `login` |
| POST | `/api/v1/auth/refresh` | 刷新 Cookie | `refreshAccessToken` |
| POST | `/api/v1/auth/logout` | 刷新 Cookie 或 Bearer | `logout` |
| GET | `/api/v1/auth/me` | 已登录 | `getCurrentUser` |
| POST | `/api/v1/auth/change-password` | 已登录 | `changePassword` |
| GET | `/api/v1/admin/users` | ADMIN | `listUsers` |
| POST | `/api/v1/admin/users` | ADMIN | `createTeacher` |
| PATCH | `/api/v1/admin/users/{user_id}/status` | ADMIN | `updateUserStatus` |
| POST | `/api/v1/admin/users/{user_id}/reset-password` | ADMIN | `resetUserPassword` |
| GET | `/api/v1/courses` | TEACHER | `listCourses` |
| POST | `/api/v1/courses` | TEACHER | `createCourse` |
| PATCH | `/api/v1/courses/{course_id}` | TEACHER/owner | `updateCourse` |
| POST | `/api/v1/courses/{course_id}/classes` | TEACHER/owner | `createClassGroup` |
| PATCH | `/api/v1/classes/{class_group_id}` | TEACHER/owner | `updateClassGroup` |
| GET | `/api/v1/classes/{class_group_id}/roster` | TEACHER/owner | `getClassRoster` |
| POST | `/api/v1/classes/{class_group_id}/roster/import-preview` | TEACHER/owner | `previewRosterImport` |
| POST | `/api/v1/classes/{class_group_id}/roster/import-confirm` | TEACHER/owner | `confirmRosterImport` |
| PATCH | `/api/v1/enrollments/{enrollment_id}/status` | TEACHER/owner | `updateEnrollmentStatus` |
| GET | `/api/v1/attendance-sessions` | TEACHER | `listAttendanceSessions` |
| POST | `/api/v1/classes/{class_group_id}/attendance-sessions` | TEACHER/owner | `createAttendanceSession` |
| GET | `/api/v1/attendance-sessions/{session_id}` | TEACHER/owner | `getAttendanceSession` |
| PATCH | `/api/v1/attendance-records/{record_id}` | TEACHER/owner | `updateAttendanceRecord` |
| POST | `/api/v1/attendance-sessions/{session_id}/complete` | TEACHER/owner | `completeAttendanceSession` |
| GET | `/api/v1/attendance-sessions/{session_id}/export` | TEACHER/owner | `exportAttendanceSession` |

### 4.6 健康检查

#### `GET /api/v1/health/live`

不访问数据库，用于判断 API 进程是否可响应。

成功响应 `200`：

```json
{"status":"ok"}
```

#### `GET /api/v1/health/ready`

检查数据库连接和当前 Alembic 迁移版本。

- `200`：`{"status":"ready"}`
- `503`：`{"status":"not_ready"}`。就绪检查不使用业务错误响应，避免暴露内部细节。

### 4.7 认证接口

#### `POST /api/v1/auth/login`

请求：

```json
{
  "username": "teacher01",
  "password": "user-supplied-password"
}
```

约束：`username` 长度 1 至 64；`password` 长度 12 至 128。用户名在服务端标准化为小写。

成功响应 `200`，同时设置刷新 Cookie：

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "2be4b8c1-6e47-4e1d-a835-fcef3f18b3b3",
    "username": "teacher01",
    "display_name": "王老师",
    "role": "TEACHER",
    "status": "ACTIVE",
    "must_change_password": false,
    "last_login_at": "2026-09-03T00:40:12Z",
    "created_at": "2026-09-01T03:00:00Z",
    "updated_at": "2026-09-03T00:40:12Z"
  }
}
```

错误：`INVALID_CREDENTIALS`、`RATE_LIMITED`、`INVALID_REQUEST`。用户名不存在、密码错误和禁用账号的登录响应均使用相同 `INVALID_CREDENTIALS` 文案。

#### `POST /api/v1/auth/refresh`

无 JSON 请求体。读取并轮换刷新 Cookie，校验会话、账号状态和 `Origin`。

成功响应 `200` 与登录响应相同，并设置新的刷新 Cookie。错误：`AUTHENTICATION_REQUIRED`、`INVALID_ORIGIN`、`ACCOUNT_DISABLED`。

#### `POST /api/v1/auth/logout`

撤销当前刷新会话并清除 Cookie。成功始终返回 `204`；刷新 Cookie 已失效时也返回 `204`，使退出操作幂等。

#### `GET /api/v1/auth/me`

成功返回 `User`，状态码 `200`。该接口允许 `must_change_password=true` 的用户访问。

#### `POST /api/v1/auth/change-password`

请求：

```json
{
  "current_password": "current-password-value",
  "new_password": "new-password-value"
}
```

新密码长度 12 至 128，不得与当前密码相同。成功后清除首次改密标记，撤销其他会话，轮换当前刷新令牌并返回新的登录响应，状态码 `200`。

错误：`CURRENT_PASSWORD_INVALID`、`PASSWORD_POLICY_VIOLATION`、`AUTHENTICATION_REQUIRED`。

### 4.8 管理员用户接口

#### `GET /api/v1/admin/users`

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | 1 | 页码 |
| `page_size` | integer | 20 | 每页 1 至 100 条 |
| `role` | string | 无 | `ADMIN` 或 `TEACHER` |
| `status` | string | 无 | `ACTIVE` 或 `DISABLED` |
| `q` | string | 无 | 匹配用户名或显示名称 |

成功返回 `User` 分页列表。

#### `POST /api/v1/admin/users`

请求：

```json
{
  "username": "teacher01",
  "display_name": "王老师",
  "temporary_password": "temporary-password"
}
```

只创建 `TEACHER`，状态为 `ACTIVE`，`must_change_password=true`。成功返回 `User`，状态码 `201`；响应和日志不得回显临时密码。

错误：`DUPLICATE_RESOURCE`、`PASSWORD_POLICY_VIOLATION`、`INVALID_REQUEST`。

#### `PATCH /api/v1/admin/users/{user_id}/status`

请求：`{"status":"DISABLED"}`，只允许 `ACTIVE` 或 `DISABLED`。禁用成功时同一事务撤销该用户全部刷新会话。成功返回更新后的 `User`。

管理员不得通过此接口禁用自己，违反时返回 `SELF_ADMIN_ACTION_FORBIDDEN`。

#### `POST /api/v1/admin/users/{user_id}/reset-password`

请求：

```json
{"temporary_password":"new-temporary-password"}
```

成功设置新密码哈希、`must_change_password=true` 并撤销全部刷新会话，返回 `204`。不得在响应或日志中回显密码。

### 4.9 课程、班级和名单接口

#### `GET /api/v1/courses`

查询参数：`page`、`page_size`、`status=ACTIVE|ARCHIVED`、`term`、`q`。只返回当前教师的课程；每个 `Course` 嵌入班级摘要。成功返回分页列表。

#### `POST /api/v1/courses`

请求：

```json
{
  "name": "产品设计方法",
  "code": "PD204",
  "term": "2026 秋季学期"
}
```

三个字段去除首尾空格后不能为空，最大长度依次为 120、50、50。成功返回 `Course`，状态码 `201`。同一教师的 `(code, term)` 重复时返回 `DUPLICATE_RESOURCE`。

#### `PATCH /api/v1/courses/{course_id}`

请求可包含 `name`、`code`、`term`、`status` 中至少一个字段；`status` 只允许 `ACTIVE` 或 `ARCHIVED`。成功返回更新后的 `Course`。

归档后禁止创建班级和点名场次，但允许查询与导出历史数据。首期不允许重新启用已归档课程。

#### `POST /api/v1/courses/{course_id}/classes`

请求：`{"name":"2024 级 2 班"}`。名称最长 120，同一课程内唯一。成功返回班级摘要，状态码 `201`。

#### `PATCH /api/v1/classes/{class_group_id}`

请求可包含 `name`、`status` 中至少一个字段。`status` 只允许 `ACTIVE` 或 `ARCHIVED`；首期不允许重新启用已归档班级。成功返回班级摘要。

#### `GET /api/v1/classes/{class_group_id}/roster`

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | 1 | 页码 |
| `page_size` | integer | 20 | 每页 1 至 100 条 |
| `status` | string | `ACTIVE` | `ACTIVE`、`REMOVED` 或 `all` |
| `q` | string | 无 | 在授权班级内匹配姓名、学号或专业 |

成功返回 `RosterMember` 分页列表。该接口不得搜索或枚举当前班级之外的学生。

#### `POST /api/v1/classes/{class_group_id}/roster/import-preview`

请求为 `multipart/form-data`，字段 `file` 必填。支持 `.xlsx`、`.xls`、`.csv`，文件最大 10 MiB，数据最多 500 行。服务端必须校验扩展名和实际内容，不得只信任 `Content-Type`。

文件表头必须包含学号、姓名和班级，可选性别和专业。每个非空行的班级值必须与目标班级名称一致，否则该行标记为 `CLASS_MISMATCH` 且禁止确认。

成功响应 `201`：

```json
{
  "preview_id": "99598091-ed49-4413-b794-37eea45843a3",
  "expires_at": "2026-09-03T08:00:00Z",
  "summary": {
    "total": 3,
    "valid": 1,
    "errors": 1,
    "duplicates": 1,
    "importable": 1
  },
  "rows": [
    {
      "row_number": 2,
      "student_number": "20260001",
      "name": "张敏",
      "gender": "女",
      "class_name": "2024 级 2 班",
      "major": "工业设计",
      "status": "valid",
      "code": null,
      "fields": [],
      "message": null
    }
  ]
}
```

预览即使含行级错误仍返回 `201`，由 `summary.errors` 和逐行状态表达；文件整体不可解析时返回错误。状态只允许 `valid`、`error`、`duplicate`、`identity_conflict`。

行级校验代码：

| 代码 | 状态 | 说明 |
| --- | --- | --- |
| `MISSING_REQUIRED_FIELD` | `error` | 学号、姓名或班级为空 |
| `INVALID_FIELD` | `error` | 字段类型、格式或长度非法 |
| `CLASS_MISMATCH` | `error` | 行内班级与目标班级名称不一致 |
| `DUPLICATE_IN_FILE` | `duplicate` | 文件内学号重复 |
| `DUPLICATE_ENROLLMENT` | `duplicate` | 目标班级已有相同学号关系 |
| `STUDENT_IDENTITY_CONFLICT` | `identity_conflict` | 系统已有相同学号但姓名不同 |

错误：`UNSUPPORTED_FILE_TYPE`、`FILE_TOO_LARGE`、`ROSTER_ROW_LIMIT_EXCEEDED`、`ROSTER_PARSE_FAILED`、`RATE_LIMITED`。

#### `POST /api/v1/classes/{class_group_id}/roster/import-confirm`

请求：

```json
{
  "preview_id": "99598091-ed49-4413-b794-37eea45843a3",
  "duplicate_policy": "skip"
}
```

`duplicate_policy` 只允许 `skip` 或 `replace`。预览必须属于当前用户和路径中的班级、尚未过期且未确认。存在缺少必填字段或同号异名时禁止确认，并且不得写入部分数据。

成功响应 `200`：

```json
{
  "preview_id": "99598091-ed49-4413-b794-37eea45843a3",
  "created_students": 1,
  "created_enrollments": 1,
  "restored_enrollments": 0,
  "skipped": 1,
  "failed": 0
}
```

错误：`IMPORT_PREVIEW_EXPIRED`、`IMPORT_PREVIEW_ALREADY_CONFIRMED`、`ROSTER_VALIDATION_FAILED`、`STUDENT_IDENTITY_CONFLICT`。

#### `PATCH /api/v1/enrollments/{enrollment_id}/status`

请求：`{"status":"REMOVED"}`，只允许 `ACTIVE` 或 `REMOVED`。成功返回更新后的 `RosterMember`。修改当前名单不得改变已创建场次的考勤记录集合和快照。

### 4.10 考勤接口

#### `GET /api/v1/attendance-sessions`

该列表接口支持前端考勤记录页，是总架构端点摘要的必要补充。

查询参数：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | 1 | 页码 |
| `page_size` | integer | 20 | 每页 1 至 100 条 |
| `course_id` | UUID | 无 | 按当前教师课程筛选 |
| `class_group_id` | UUID | 无 | 按班级筛选 |
| `status` | string | 无 | `DRAFT` 或 `COMPLETED` |
| `date_from` | date | 无 | 起始业务日期，包含 |
| `date_to` | date | 无 | 结束业务日期，包含 |

`date_from` 不得晚于 `date_to`。成功返回不含 `records` 的 `AttendanceSession` 分页列表。

#### `POST /api/v1/classes/{class_group_id}/attendance-sessions`

请求：

```json
{"session_date":"2026-09-03"}
```

班级必须为 `ACTIVE`，所属课程必须为 `ACTIVE`，并且至少存在一个 `ACTIVE` 名单成员。服务端在同一事务创建场次和所有 `pending` 快照记录。

成功返回包含全部记录的 `AttendanceSession`，状态码 `201`。同一班级和业务日期重复时返回 `DUPLICATE_RESOURCE`；空名单返回 `ROSTER_EMPTY`。

#### `GET /api/v1/attendance-sessions/{session_id}`

成功返回包含全部记录的 `AttendanceSession`。记录按创建时名单顺序稳定返回；首期若导入数据没有显式序号，则按 `student_number_snapshot ASC, id ASC` 排序。

#### `PATCH /api/v1/attendance-records/{record_id}`

请求：

```json
{
  "status": "late",
  "expected_version": 3,
  "client_mutation_id": "e9329885-359a-49b9-8846-6fad26c6501b",
  "reason": "学生点名后到场"
}
```

规则：

- `status` 只允许 `present`、`absent`、`leave`、`late`，不得改回 `pending`。
- `expected_version` 最小为 1。
- `client_mutation_id` 必须为 UUID。
- `DRAFT` 场次的首次或后续标记可省略 `reason`。
- `COMPLETED` 场次的任何修正都必须提供去除首尾空格后 1 至 500 字符的 `reason`。
- 成功更新记录与审计日志必须在同一事务提交。

成功返回更新后的 `AttendanceRecord`。版本冲突返回：

```json
{
  "code": "ATTENDANCE_RECORD_CONFLICT",
  "message": "该记录已被其他操作更新，请刷新后重试",
  "details": {
    "current_record": {
      "id": "b0b0133d-24b2-49e1-b193-1314fe230d5b",
      "status": "present",
      "version": 4
    }
  },
  "request_id": "req_01HXYZ"
}
```

#### `POST /api/v1/attendance-sessions/{session_id}/complete`

无请求体。服务端锁定场次，重新检查不存在 `pending` 记录，然后将状态从 `DRAFT` 原子更新为 `COMPLETED`。

成功返回更新后的场次摘要，状态码 `200`。已完成场次重复调用时返回当前场次摘要并保持 `completed_at` 不变，使操作幂等。存在 `pending` 时返回 `ATTENDANCE_INCOMPLETE`，`details.pending_count` 给出数量。

客户端在本地同步队列非空时不得调用此接口；服务端只能校验已提交数据库状态，不能确认客户端是否仍有未发送变更。

#### `GET /api/v1/attendance-sessions/{session_id}/export`

查询参数 `format` 必填，只允许 `xlsx` 或 `csv`。只允许导出 `COMPLETED` 场次。

成功响应：

| 格式 | Content-Type |
| --- | --- |
| `xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `csv` | `text/csv; charset=utf-8` |

响应包含：

```text
Content-Disposition: attachment; filename*=UTF-8''<percent-encoded-filename>
X-Content-Type-Options: nosniff
```

文件名为 `{课程}_{班级}_{日期}_单次考勤.{扩展名}`，非法字符替换为下划线。CSV 使用 UTF-8 BOM；以 `=`, `+`, `-`, `@` 开头的文本加前导单引号。XLSX 中学号和文本字段写为字符串。

导出列按以下顺序固定：课程、课程代码、班级、日期、姓名、学号、考勤状态、点名时间、最后修改时间、最后修改人。

错误：`ATTENDANCE_SESSION_NOT_COMPLETED`、`INVALID_REQUEST`、`RESOURCE_NOT_FOUND`。

### 4.11 错误码目录

| HTTP | 错误码 | 使用场景 |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | JSON、查询参数、路径参数或字段非法 |
| 400 | `INVALID_ORIGIN` | 刷新请求源站不匹配 |
| 400 | `UNSUPPORTED_FILE_TYPE` | 不支持或扩展名与内容不符 |
| 400 | `ROSTER_PARSE_FAILED` | 文件无法解析 |
| 401 | `AUTHENTICATION_REQUIRED` | 访问或刷新凭据缺失、失效、撤销或过期 |
| 401 | `INVALID_CREDENTIALS` | 登录凭据无效，使用统一文案 |
| 401 | `CURRENT_PASSWORD_INVALID` | 修改密码时当前密码错误 |
| 403 | `PASSWORD_CHANGE_REQUIRED` | 首次密码尚未修改 |
| 403 | `ACCOUNT_DISABLED` | 已登录会话对应账号被禁用 |
| 403 | `RESOURCE_FORBIDDEN` | 角色无权执行操作 |
| 403 | `SELF_ADMIN_ACTION_FORBIDDEN` | 管理员尝试禁用自己 |
| 404 | `RESOURCE_NOT_FOUND` | 资源不存在、不可见或不属于当前教师 |
| 409 | `DUPLICATE_RESOURCE` | 用户名、课程、班级或场次唯一冲突 |
| 409 | `STUDENT_IDENTITY_CONFLICT` | 相同学号对应不同姓名 |
| 409 | `IMPORT_PREVIEW_EXPIRED` | 导入预览已过期或已被清理 |
| 409 | `IMPORT_PREVIEW_ALREADY_CONFIRMED` | 预览已确认 |
| 409 | `ATTENDANCE_RECORD_CONFLICT` | 考勤记录版本冲突 |
| 409 | `ATTENDANCE_SESSION_NOT_COMPLETED` | 尝试导出草稿场次 |
| 409 | `ROSTER_EMPTY` | 空名单无法创建场次 |
| 422 | `PASSWORD_POLICY_VIOLATION` | 新密码不符合长度或复用规则 |
| 422 | `ROSTER_VALIDATION_FAILED` | 预览存在禁止确认的行错误 |
| 422 | `ROSTER_ROW_LIMIT_EXCEEDED` | 名单数据超过 500 行 |
| 422 | `ATTENDANCE_INCOMPLETE` | 尚有 `pending` 记录 |
| 413 | `FILE_TOO_LARGE` | 文件超过 10 MiB |
| 429 | `RATE_LIMITED` | 登录或上传请求超过限制 |
| 500 | `INTERNAL_ERROR` | 未预期服务端错误 |

Pydantic 字段校验失败必须转换为统一 `INVALID_REQUEST` 错误结构；不得直接向前端暴露框架默认错误格式。

### 4.12 前端同步协议

```text
读取场次及记录版本
  -> 用户标记状态
  -> 前端立即更新内存和界面
  -> 为最终目标状态生成 client_mutation_id
  -> PATCH attendance-records/{id}
       ├─ 200：保存返回的 version，标记 synced
       ├─ 网络/5xx：按 1、2、4、8 秒重试同一 mutation ID
       ├─ 401：刷新令牌后重试一次原请求
       ├─ 409 version：停止该记录自动同步并展示冲突
       └─ 其他 4xx：停止重试并展示可操作错误
```

同一记录尚未发送的旧目标状态可被新状态覆盖，并生成新的 `client_mutation_id`。已经在途的请求不得取消后直接并发发送相同期望版本；必须等待响应并使用返回的新版本发送最终状态。

## 5. Acceptance Criteria

- **AC-API-001**：Given 临时密码登录成功，When 用户访问课程接口，Then 返回 `PASSWORD_CHANGE_REQUIRED`，但仍可访问当前用户和修改密码接口。
- **AC-API-002**：Given 刷新成功，When 再次使用旧刷新 Cookie，Then 返回 `AUTHENTICATION_REQUIRED` 且不签发令牌。
- **AC-API-003**：Given 教师 A 的课程资源，When 教师 B 请求关联课程、名单或考勤，Then 返回 `RESOURCE_NOT_FOUND` 且响应不泄露资源内容。
- **AC-API-004**：Given 合法课程数据，When 创建课程，Then 返回 `201`、可由列表查到且审计已提交。
- **AC-API-005**：Given 名单预览含同号异名，When 确认导入，Then 返回 `STUDENT_IDENTITY_CONFLICT` 且没有部分写入。
- **AC-API-006**：Given 班级有 500 名有效学生，When 创建场次，Then 返回 `201` 和 500 条固定快照记录。
- **AC-API-007**：Given 考勤记录版本为 3，When 使用版本 2 更新，Then 返回 409 和当前记录摘要。
- **AC-API-008**：Given 首次更新响应丢失，When 使用相同 `client_mutation_id` 重试，Then 返回首次成功结果且版本和审计不再增加。
- **AC-API-009**：Given 场次存在 `pending`，When 请求完成，Then 返回 `ATTENDANCE_INCOMPLETE` 和准确数量。
- **AC-API-010**：Given 已完成场次，When 不提供原因修改记录，Then 返回 `INVALID_REQUEST` 且状态不变。
- **AC-API-011**：Given 已完成场次，When 导出 CSV，Then 响应流具有 BOM、固定列序、合规文件名和公式注入防护。
- **AC-API-012**：Given 500 人场次，When 获取详情或导出，Then 单请求在目标服务器上低于 5 秒。
- **AC-API-013**：Given 任意错误响应，When 客户端读取响应，Then 格式符合统一错误模型且请求头与正文 request ID 一致。

## 6. Test Automation Strategy

### 6.1 OpenAPI 契约测试

- 启动 FastAPI 后获取 `/openapi.json`，断言本文档全部路径、方法和 `operation_id` 存在。
- 使用生成的 TypeScript 客户端执行编译检查，禁止手工维护重复响应类型。
- 保存经过评审的 OpenAPI 快照；破坏性变化必须显式更新版本或先完成兼容迁移。

### 6.2 API 集成测试

- 使用 FastAPI TestClient 和真实 MySQL 测试库。
- 覆盖成功、无认证、错误角色、错误归属、字段边界、唯一冲突和事务回滚。
- 覆盖刷新令牌轮换、禁用账号、密码重置和首次改密门禁。
- 覆盖名单支持格式、编码、损坏文件、扩展名伪装、10 MiB 和 500 行边界。
- 覆盖考勤幂等重试、版本冲突、完成门禁和已完成修正审计。

### 6.3 端到端测试

- 管理员创建教师，教师首次登录改密。
- 教师创建课程班级，预览并确认名单。
- 创建场次，使用快捷键完成全部记录，在同步结束后完成场次。
- 修正已完成记录并导出 XLSX、CSV。
- 教师之间交叉访问资源均失败。

### 6.4 性能和安全测试

- 常规 JSON API 服务端 P95 低于 500 ms。
- 500 人导入预览、确认、场次创建和导出单请求低于 5 秒。
- 验证登录和上传限流、Cookie 属性、Origin 校验、日志脱敏和公式注入防护。

## 7. Rationale & Context

### 7.1 资源归属返回 404

教师知道一个有效 UUID 不代表有权确认该资源存在。对非本人教学资源统一返回 404，可避免通过状态差异枚举其他教师的课程和学生数据。

### 7.2 不为响应添加通用包装层

HTTP 状态码已经表达请求结果。单资源直接返回模型、列表使用明确分页结构，可以简化 OpenAPI 类型和前端查询缓存键，错误则使用独立稳定模型。

### 7.3 更新状态采用 PATCH

考勤接口只修改记录的部分字段，并且需要携带并发控制信息。`PATCH` 比替换整个记录的 `PUT` 更准确，也避免客户端回传不可修改的快照字段。

### 7.4 补充场次列表接口

总架构已有单场次详情，但前端考勤记录页面需要按课程、班级、日期和状态查询历史。增加只返回摘要的分页列表不会扩大首期业务范围，并避免通过课程列表拼接多次请求。

## 8. Dependencies & External Integrations

- **PLT-API-001**：FastAPI 和 Pydantic，用于运行时校验和 OpenAPI 生成。
- **PLT-API-002**：SQLAlchemy 2 同步会话和 MySQL 8。
- **PLT-API-003**：Argon2id 密码哈希库和 JWT 签名库。
- **PLT-API-004**：`pandas`、`openpyxl`、`xlrd` 和标准库 `csv`，用于导入导出。
- **INF-API-001**：Nginx 提供 TLS、`/api` 反向代理、上传大小限制和登录限流。
- **EXT-API-001**：首期无统一身份认证、教务系统或其他必需外部业务系统。

## 9. Examples & Edge Cases

### 9.1 快速连续修改同一学生

前端以版本 3 提交“缺勤”，请求在途时教师改为“迟到”。前端等待第一笔返回版本 4，再用新的变更 ID 和期望版本 4 提交“迟到”。不得并发发送两个期望版本 3 的请求。

### 9.2 超时后的安全重试

服务端已提交更新但响应在网络中丢失。客户端使用同一个 `client_mutation_id` 重试。服务端从审计幂等记录返回首次结果，不再次递增版本或重复写审计。

### 9.3 完成请求与最后一次状态更新竞态

客户端只有同步队列为空时才请求完成。服务端在事务中锁定场次并检查数据库不存在 `pending`。任何条件不满足都拒绝完成，从而避免只依赖前端状态。

### 9.4 上传扩展名伪装

文件名为 `roster.xlsx` 但内容不是有效 Office Open XML。服务端返回 `UNSUPPORTED_FILE_TYPE` 或 `ROSTER_PARSE_FAILED`，清理临时文件，不创建预览记录。

## 10. Validation Criteria

- OpenAPI 包含 26 个本文档定义的端点及稳定 `operation_id`。
- 所有请求和响应模型禁止未声明字段，PATCH 模型至少包含一个可更新字段。
- 所有受保护接口声明角色和资源归属测试。
- 数据库字段名、枚举、长度和空值规则与数据库规范一致。
- 错误响应只有一种结构，所有错误码在目录中定义。
- 文件导入、导出和考勤修改的边界条件均有自动化集成测试。
- 不存在首期排除的离线、学期汇总、平时分或全校学生搜索接口。

## 11. Related Specifications / Further Reading

- [智能课堂考勤系统技术规格](./spec-architecture-attendance-system.md)
- [智能课堂考勤系统数据库表结构规范](./spec-schema-attendance-database.md)
- [智能课堂考勤系统 PRD](../docs/attendance-system-prd.md)
- 实施后的交互文档：`GET /docs`
- 实施后的 OpenAPI：`GET /openapi.json`
