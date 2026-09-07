---
title: 智能课堂考勤系统技术规格
version: 1.0
date_created: 2026-09-02
last_updated: 2026-09-03
owner: 项目开发团队
tags: [architecture, attendance, react, fastapi, mysql]
---

# Introduction

本文档定义智能课堂考勤系统首期可上线版本的技术架构、模块边界、数据模型、接口契约、安全规则、部署方式和验收标准。目标读者为产品、前端、后端、测试和运维人员。

本文档以 [考勤系统 PRD](../docs/attendance-system-prd.md) 为业务依据，并记录 2026-09-02 已确认的首期范围调整。当本文档与 PRD 的版本规划存在冲突时，首期实施以本文档的“范围调整”为准，业务语义仍以 PRD 为准。

## 1. Purpose & Scope

### 1.1 目标

交付一套部署在单校云服务器上的 Web 考勤系统，使管理员能够预建教师账号，使教师能够创建课程和班级、导入学生名单、完成课堂语音点名、修正异常状态并导出单次考勤记录。

### 1.2 首期包含

- 管理员创建、禁用、重置教师账号。
- 教师用户名和密码登录、首次登录修改密码、退出登录。
- 教师创建和归档自己的课程、班级。
- `.xlsx`、`.xls`、`.csv` 名单导入、预览、校验和确认。
- 浏览器原生中文语音播报。
- 键盘和翻页笔快捷键点名。
- 待确认、已到、缺勤、请假、迟到状态管理。
- 点名过程中的非阻塞保存、短暂失败重试和同步状态提示。
- 已完成考勤的异常修正与审计。
- 单次考勤 `.xlsx` 和 `.csv` 导出。
- Docker Compose 单机部署、HTTPS、健康检查、日志和 MySQL 备份。

### 1.3 首期不包含

- 离线点名、`localStorage` 草稿和关闭页面后的进度恢复。
- 教师自行注册、找回密码邮件和注册审批。
- 校园统一身份认证或教务系统集成。
- 多学校租户隔离。
- 教师协作授课、课程移交和复杂授权。
- 学期汇总、考勤分换算、课堂纪律、作业及综合平时分。
- 学生端签到、请假审批、移动端原生应用。
- Redis、消息队列、对象存储和微服务。

### 1.4 已确认的 PRD 范围调整

| 主题 | PRD 当前描述 | 首期决定 |
| --- | --- | --- |
| 登录 | 登录方式为开放问题 | 管理员预建账号，用户名密码登录 |
| 课程归属 | 课程来源为开放问题 | 教师自行创建课程和班级 |
| 离线恢复 | PRD MVP 包含 | 首期不实施 |
| 导出 | PRD 包含单次、学期和成绩报表 | 首期只导出单次考勤 |
| 平时分 | PRD 定义考勤换算 | 延后，与课堂纪律一起按通用明细模型设计 |
| 部署 | 未明确 | 单校、一台云服务器、Docker Compose |

### 1.5 关键假设

- 系统只服务一所学校。
- 教师账号规模不超过 2,000，单班名单不超过 500 人。
- 课堂点名的典型请求速率低于每秒 3 次。
- 浏览器以当前受支持的 Chrome 和 Edge 为主，Safari 作为兼容目标。
- 用户访问云服务器时网络可用；短暂中断允许重试，但不承诺离线工作。

## 2. Definitions

| 术语 | 定义 |
| --- | --- |
| SPA | Single-Page Application，单页 Web 应用 |
| API | Application Programming Interface，应用程序接口 |
| JWT | JSON Web Token，用于短期访问令牌 |
| TTS | Text-to-Speech，文字转语音 |
| 名单 | 某个班级当前有效的学生集合 |
| 点名场次 | 某班级在某一日期的一次课堂考勤 |
| 考勤记录 | 点名场次中某一学生的最终状态及修改信息 |
| 名单快照 | 点名场次创建时保存的学生姓名、学号和班级名称副本 |
| 乐观更新 | 前端先更新界面，再异步向服务端保存 |
| 乐观锁 | 通过版本号发现并发修改冲突 |
| 同步完成 | 当前页面产生的所有考勤修改均已被服务端确认 |

## 3. Requirements, Constraints & Guidelines

### 3.1 架构要求

- **ARC-001**：系统必须采用 React SPA、FastAPI 模块化单体和 MySQL 的前后端分离架构。
- **ARC-002**：后端必须按 `auth`、`users`、`courses`、`rosters`、`attendance`、`imports`、`exports`、`audit` 模块组织，模块通过应用服务接口协作。
- **ARC-003**：首期必须部署为单个 API 服务，不得拆分微服务。
- **ARC-004**：外部接口必须统一使用 `/api/v1` 前缀，并由 FastAPI 生成 OpenAPI 文档。
- **ARC-005**：前端 API 类型必须从 OpenAPI 生成，禁止手工维护重复的响应类型。

### 3.2 身份认证与授权要求

- **SEC-001**：管理员创建教师账号时必须设置一次性临时密码，教师首次登录后必须修改密码才能进入业务页面。
- **SEC-002**：密码必须使用 Argon2id 哈希，禁止保存或记录明文密码。
- **SEC-003**：访问令牌必须是有效期 15 分钟的 JWT，只保存在浏览器内存中，禁止写入 `localStorage` 或 `sessionStorage`。
- **SEC-004**：刷新令牌有效期为 7 天，必须使用至少 256 位安全随机值，通过 `HttpOnly`、`Secure`、`SameSite=Strict` Cookie 传输，数据库只保存令牌哈希。
- **SEC-005**：刷新令牌每次使用后必须轮换；退出、管理员禁用账号或重置密码时必须撤销该用户的全部刷新会话。
- **SEC-006**：后端每次受保护请求必须验证访问令牌、账号状态和资源归属，不得依赖前端权限控制。
- **SEC-007**：教师只能读写自己创建的课程、班级、名单和考勤数据。管理员首期只通过管理员 API 管理账号，不通过教师 API 访问教学数据。
- **SEC-008**：登录失败必须返回统一提示，不得泄露用户名是否存在。
- **SEC-009**：Nginx 必须对登录接口进行 IP 限流，应用必须记录账号级连续失败次数和最后失败时间。
- **SEC-010**：刷新接口必须校验 `Origin`，仅接受本系统 HTTPS 源站请求。
- **SEC-011**：密码长度必须为 12 至 128 个字符。创建账号和重置密码时由管理员输入临时密码；API 不在响应或日志中回显该密码。

### 3.3 课程和名单要求

- **CRS-001**：教师可以创建、编辑和归档课程；已产生考勤数据的课程不得物理删除。
- **CRS-002**：一个课程可以包含多个班级，同一课程内班级名称必须唯一。
- **ROS-001**：名单导入必须支持 `.xlsx`、`.xls`、`.csv`，单文件不超过 10 MiB，数据行不超过 500 行。
- **ROS-002**：必填字段为学号、姓名、班级；可选字段为性别、专业。
- **ROS-003**：学号在全校范围唯一；同一学号对应不同姓名时必须标记为身份冲突并阻止确认导入。
- **ROS-004**：同一班级中的重复学号必须提供“跳过”和“覆盖班级关系”策略。覆盖不得静默修改全局学生身份字段。
- **ROS-005**：导入必须先预览后确认；确认写入必须使用一个数据库事务。
- **ROS-006**：原始文件解析完成后必须立即删除；标准化预览数据最多保留一小时，确认或过期后必须清理。
- **ROS-007**：教师只能查看通过自己班级名单关联到的学生，不得通过学生接口枚举全校学生。

### 3.4 考勤要求

- **ATT-001**：考勤状态固定为 `pending`、`present`、`absent`、`leave`、`late`。
- **ATT-002**：创建点名场次时必须根据当时的有效名单批量创建考勤记录，并保存学生姓名、学号、班级名称快照。
- **ATT-003**：同一班级和同一日期只能创建一个点名场次，由数据库唯一约束保证。
- **ATT-004**：前端状态变更必须乐观更新，不得等待 HTTP 请求完成后才移动到下一名学生。
- **ATT-005**：状态保存接口必须通过客户端变更 ID 保证安全重试，并使用记录版本号进行乐观锁控制。
- **ATT-006**：请求短暂失败时，前端必须在当前页面内存中保留待发送变更并按退避策略重试，同时显示明确的同步状态。
- **ATT-007**：存在 `pending` 记录或未同步变更时，系统必须阻止结束点名。
- **ATT-008**：结束点名必须二次确认；服务端必须重新检查所有记录状态后原子更新场次状态。
- **ATT-009**：已完成场次允许修正。修正必须填写原因，并记录原状态、目标状态、操作人、时间和来源 IP。
- **ATT-010**：后续名单变化不得修改已创建场次的学生集合或快照字段。
- **ATT-011**：页面刷新或关闭后，前端不承诺恢复尚未提交的数据，并必须在存在未同步变更时触发离开页面警告。

### 3.5 语音和快捷键要求

- **TTS-001**：语音必须使用浏览器 `Web Speech API`，服务端不生成音频。
- **TTS-002**：不支持 TTS 或播报失败时，点名流程必须仍可通过文字和键盘完成。
- **TTS-003**：快捷键仅在点名页面且焦点不位于文本输入控件时生效。
- **TTS-004**：快捷键映射必须与 PRD FR-11 一致；最后一名完成后不得数组越界。
- **TTS-005**：按键后必须先保存本地内存状态并更新视图，再触发后台同步和下一名播报。

### 3.6 导出要求

- **EXP-001**：教师只能导出自己课程的单次考勤记录。
- **EXP-002**：导出格式必须支持 `.xlsx` 和 UTF-8 with BOM 的 `.csv`。
- **EXP-003**：导出字段至少包含课程、班级、日期、姓名、学号、考勤状态、点名时间、最后修改时间和最后修改人。
- **EXP-004**：导出文件必须实时生成并流式返回，不在服务器长期保存。
- **EXP-005**：文件名格式为 `{课程}_{班级}_{日期}_单次考勤.{扩展名}`，非法文件名字符必须替换为下划线。

### 3.7 数据与通用约束

- **DAT-001**：业务主键统一使用 UUID 字符串；数据库列使用 `CHAR(36)`。
- **DAT-002**：所有时间在数据库中以 UTC `DATETIME(6)` 保存，API 使用带时区的 ISO 8601，前端按 Asia/Shanghai 展示。
- **DAT-003**：数据表必须使用 InnoDB、`utf8mb4` 字符集和明确的外键、唯一约束及索引。
- **DAT-004**：课程、班级、用户和名单关系采用状态或归档字段，不对已被考勤引用的数据执行物理删除。
- **DAT-005**：所有写接口必须在成功提交事务后才返回成功。
- **DAT-006**：分页列表默认每页 20 条，最大每页 100 条。
- **CON-001**：首期不提供离线一致性保证，后端是已提交数据的唯一事实来源。
- **CON-002**：首期不实现多租户字段；未来 SaaS 化必须单独迁移，不得把教师 ID 当作租户 ID。
- **GUD-001**：模块内部允许直接使用 SQLAlchemy，跨模块不得绕过应用服务直接修改对方聚合数据。
- **GUD-002**：错误信息必须面向用户可理解，详细堆栈只进入服务端日志。

## 4. Interfaces & Data Contracts

### 4.1 系统拓扑

```text
Browser
  └── React SPA
        ├── Web Speech API
        └── HTTPS / REST / JSON
                 │
              Nginx
        ┌────────┴────────┐
   Static assets     /api reverse proxy
                            │
                       FastAPI API
                            │
                          MySQL
```

生产环境仅对公网开放 TCP 80 和 443。MySQL 仅在 Docker 内部网络开放。

### 4.2 后端模块边界

| 模块 | 职责 | 允许依赖 |
| --- | --- | --- |
| `auth` | 登录、刷新、退出、密码修改、会话撤销 | `users`, `audit` |
| `users` | 管理员创建、禁用、重置教师账号 | `audit` |
| `courses` | 课程、班级、归属校验 | `users`, `audit` |
| `rosters` | 学生身份、班级关系、名单查询 | `courses`, `audit` |
| `imports` | 文件解析、预览、冲突检测、确认 | `courses`, `rosters` |
| `attendance` | 场次、记录、状态机、修正 | `courses`, `rosters`, `audit` |
| `exports` | 单次考勤文件生成 | `attendance`, `courses` |
| `audit` | 追加式操作日志 | 无业务模块依赖 |

### 4.3 前端模块边界

```text
web/src/
├── app/                 # 路由、全局 Provider、错误边界
├── api/                 # OpenAPI 生成客户端和请求封装
├── features/auth/       # 登录、会话、首次改密
├── features/courses/    # 课程和班级
├── features/rosters/    # 名单、导入预览
├── features/attendance/ # 点名状态机、同步队列、TTS、快捷键
├── features/admin/      # 教师账号管理
├── components/          # 跨功能通用组件
└── styles/              # 设计令牌和全局样式
```

前端使用 React Router、TanStack Query、React Hook Form、Zod 和 CSS Modules。图标使用 `lucide-react`。考勤同步队列属于 `features/attendance`，不得放入全局状态。

### 4.4 数据模型

所有表包含 `created_at` 和 `updated_at`，下表只列业务关键字段。

#### `users`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `username` | `VARCHAR(64)` | UNIQUE，标准化为小写 |
| `password_hash` | `VARCHAR(255)` | NOT NULL |
| `display_name` | `VARCHAR(100)` | NOT NULL |
| `role` | `VARCHAR(20)` | `ADMIN` 或 `TEACHER` |
| `status` | `VARCHAR(20)` | `ACTIVE` 或 `DISABLED` |
| `must_change_password` | `BOOLEAN` | 默认 true |
| `failed_login_count` | `INT` | 默认 0 |
| `last_failed_login_at` | `DATETIME(6)` | NULLABLE |
| `last_login_at` | `DATETIME(6)` | NULLABLE |

#### `login_sessions`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK，同时作为 JWT `sid` |
| `user_id` | `CHAR(36)` | FK users |
| `refresh_token_hash` | `CHAR(64)` | UNIQUE，SHA-256 十六进制 |
| `expires_at` | `DATETIME(6)` | NOT NULL |
| `revoked_at` | `DATETIME(6)` | NULLABLE |
| `last_used_at` | `DATETIME(6)` | NOT NULL |
| `ip_address` | `VARCHAR(45)` | NOT NULL |
| `user_agent` | `VARCHAR(255)` | NOT NULL |

#### `courses`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `owner_teacher_id` | `CHAR(36)` | FK users，INDEX |
| `name` | `VARCHAR(120)` | NOT NULL |
| `code` | `VARCHAR(50)` | NOT NULL |
| `term` | `VARCHAR(50)` | NOT NULL |
| `status` | `VARCHAR(20)` | `ACTIVE` 或 `ARCHIVED` |

唯一约束：`(owner_teacher_id, code, term)`。

#### `class_groups`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `course_id` | `CHAR(36)` | FK courses，INDEX |
| `name` | `VARCHAR(120)` | NOT NULL |
| `status` | `VARCHAR(20)` | `ACTIVE` 或 `ARCHIVED` |

唯一约束：`(course_id, name)`。

#### `students`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `student_number` | `VARCHAR(50)` | UNIQUE |
| `name` | `VARCHAR(100)` | NOT NULL |
| `gender` | `VARCHAR(20)` | NULLABLE |
| `major` | `VARCHAR(120)` | NULLABLE |

教师导入已存在学号时只能建立班级关系。姓名不一致时阻止导入，由管理员在后续治理流程中解决；首期不提供教师修改全局身份的接口。

#### `enrollments`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `class_group_id` | `CHAR(36)` | FK class_groups，INDEX |
| `student_id` | `CHAR(36)` | FK students，INDEX |
| `status` | `VARCHAR(20)` | `ACTIVE` 或 `REMOVED` |

唯一约束：`(class_group_id, student_id)`。

#### `attendance_sessions`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `class_group_id` | `CHAR(36)` | FK class_groups，INDEX |
| `session_date` | `DATE` | NOT NULL |
| `status` | `VARCHAR(20)` | `DRAFT` 或 `COMPLETED` |
| `started_at` | `DATETIME(6)` | NOT NULL |
| `completed_at` | `DATETIME(6)` | NULLABLE |
| `created_by` | `CHAR(36)` | FK users |

唯一约束：`(class_group_id, session_date)`。

#### `attendance_records`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `session_id` | `CHAR(36)` | FK attendance_sessions，INDEX |
| `student_id` | `CHAR(36)` | FK students |
| `student_number_snapshot` | `VARCHAR(50)` | NOT NULL |
| `student_name_snapshot` | `VARCHAR(100)` | NOT NULL |
| `class_name_snapshot` | `VARCHAR(120)` | NOT NULL |
| `status` | `VARCHAR(20)` | 五种考勤状态之一 |
| `marked_at` | `DATETIME(6)` | NULLABLE |
| `last_modified_by` | `CHAR(36)` | FK users |
| `last_modified_at` | `DATETIME(6)` | NULLABLE |
| `version` | `INT` | 默认 1，用于乐观锁 |

唯一约束：`(session_id, student_id)`。

#### `import_previews`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `class_group_id` | `CHAR(36)` | FK class_groups |
| `created_by` | `CHAR(36)` | FK users |
| `source_filename` | `VARCHAR(255)` | 清理路径后的原始文件名 |
| `normalized_rows` | `JSON` | 标准化后的行数据 |
| `validation_result` | `JSON` | 汇总及逐行错误 |
| `expires_at` | `DATETIME(6)` | 最多创建后一小时 |
| `confirmed_at` | `DATETIME(6)` | NULLABLE，确认后不可再次确认 |

#### `audit_logs`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | `CHAR(36)` | PK |
| `actor_user_id` | `CHAR(36)` | FK users，INDEX |
| `action` | `VARCHAR(80)` | 例如 `ATTENDANCE_STATUS_CHANGED` |
| `entity_type` | `VARCHAR(80)` | NOT NULL |
| `entity_id` | `CHAR(36)` | INDEX |
| `before_value` | `JSON` | NULLABLE |
| `after_value` | `JSON` | NULLABLE |
| `reason` | `VARCHAR(500)` | NULLABLE |
| `ip_address` | `VARCHAR(45)` | NOT NULL |
| `request_id` | `VARCHAR(64)` | INDEX |
| `client_mutation_id` | `CHAR(36)` | NULLABLE，UNIQUE |

审计日志为追加式数据，应用不得更新或删除已有记录。考勤状态修改必须写入 `client_mutation_id`；相同变更 ID 的重试直接返回首次变更结果，不得再次修改记录或重复写审计日志。

### 4.5 API 通用契约

- 请求和响应媒体类型为 `application/json`，文件上传除外。
- 访问令牌通过 `Authorization: Bearer <token>` 传输。
- ID 使用 UUID 字符串。
- 日期使用 `YYYY-MM-DD`；时间使用带 `Z` 或偏移量的 ISO 8601。
- 列表响应格式：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

- 错误响应格式：

```json
{
  "code": "ATTENDANCE_RECORD_CONFLICT",
  "message": "该记录已被其他操作更新，请刷新后重试",
  "details": {},
  "request_id": "req_01HXYZ"
}
```

### 4.6 API 端点

#### 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | 用户名密码登录，返回访问令牌并设置刷新 Cookie |
| POST | `/api/v1/auth/refresh` | 轮换刷新令牌并返回新访问令牌 |
| POST | `/api/v1/auth/logout` | 撤销当前刷新会话并清除 Cookie |
| GET | `/api/v1/auth/me` | 返回当前用户及首次改密状态 |
| POST | `/api/v1/auth/change-password` | 修改密码并撤销其他会话 |

登录请求：

```json
{
  "username": "teacher01",
  "password": "user-supplied-password"
}
```

登录响应：

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
    "must_change_password": false
  }
}
```

#### 管理员用户

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/admin/users` | 分页查询账号 |
| POST | `/api/v1/admin/users` | 创建教师账号和临时密码 |
| PATCH | `/api/v1/admin/users/{id}/status` | 启用或禁用账号 |
| POST | `/api/v1/admin/users/{id}/reset-password` | 设置新临时密码并撤销会话 |

#### 课程、班级和名单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/courses` | 当前教师课程列表 |
| POST | `/api/v1/courses` | 创建课程 |
| PATCH | `/api/v1/courses/{id}` | 编辑或归档课程 |
| POST | `/api/v1/courses/{id}/classes` | 创建班级 |
| PATCH | `/api/v1/classes/{id}` | 编辑或归档班级 |
| GET | `/api/v1/classes/{id}/roster` | 当前有效名单 |
| POST | `/api/v1/classes/{id}/roster/import-preview` | 上传并解析名单 |
| POST | `/api/v1/classes/{id}/roster/import-confirm` | 确认预览数据 |
| PATCH | `/api/v1/enrollments/{id}/status` | 移除或恢复名单成员 |

确认导入请求：

```json
{
  "preview_id": "99598091-ed49-4413-b794-37eea45843a3",
  "duplicate_policy": "skip"
}
```

`duplicate_policy` 只允许 `skip` 或 `replace`。`replace` 表示恢复或更新当前班级关系，不修改已存在学生的姓名。

#### 考勤和导出

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/attendance-sessions` | 分页筛选当前教师的考勤场次 |
| POST | `/api/v1/classes/{id}/attendance-sessions` | 创建点名场次及快照记录 |
| GET | `/api/v1/attendance-sessions/{id}` | 获取场次和全部记录 |
| PATCH | `/api/v1/attendance-records/{id}` | 设置考勤状态 |
| POST | `/api/v1/attendance-sessions/{id}/complete` | 结束点名 |
| GET | `/api/v1/attendance-sessions/{id}/export?format=xlsx` | 导出单次记录 |

状态更新请求：

```json
{
  "status": "late",
  "expected_version": 3,
  "client_mutation_id": "e9329885-359a-49b9-8846-6fad26c6501b",
  "reason": "学生点名后到场"
}
```

`client_mutation_id` 由浏览器为每次用户状态变更生成 UUID。草稿场次首次标记时 `reason` 可省略；修改已完成场次时 `reason` 必填。成功响应返回新 `version`。版本不一致返回 HTTP 409 和 `ATTENDANCE_RECORD_CONFLICT`。相同 `client_mutation_id` 的重试返回首次成功响应，即使客户端未收到首次响应也不会产生重复修改。

### 4.7 前端点名状态流

```text
加载场次
  -> 初始化当前索引和同步队列
  -> 用户按状态快捷键
  -> 内存状态立即更新
  -> 当前项进入 pending-sync
  -> 视图移动到下一名并触发 TTS
  -> 后台 PATCH
       ├─ 成功：记录 server version，标记 synced
       ├─ 网络错误：退避重试，页面显示保存失败
       ├─ 401：刷新令牌后重试一次
       └─ 409：暂停该记录同步并要求刷新解决冲突
```

同一记录的新变更覆盖尚未发送的旧变更并生成新的 `client_mutation_id`；已经在途的请求完成后，再使用服务端返回的新版本发送最新目标状态。同一请求的网络重试沿用原 `client_mutation_id`。重试间隔为 1、2、4、8 秒，之后改为用户手动重试。页面 `beforeunload` 仅在队列非空时提示。

### 4.8 错误码

| HTTP | 错误码 | 场景 |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | 请求格式或字段非法 |
| 401 | `AUTHENTICATION_REQUIRED` | 未登录或访问令牌失效 |
| 401 | `INVALID_CREDENTIALS` | 用户名或密码错误 |
| 403 | `PASSWORD_CHANGE_REQUIRED` | 首次密码尚未修改 |
| 403 | `RESOURCE_FORBIDDEN` | 无资源归属权限 |
| 404 | `RESOURCE_NOT_FOUND` | 资源不存在或不可见 |
| 409 | `DUPLICATE_RESOURCE` | 课程、班级或场次唯一约束冲突 |
| 409 | `STUDENT_IDENTITY_CONFLICT` | 相同学号对应不同姓名 |
| 409 | `ATTENDANCE_RECORD_CONFLICT` | 乐观锁版本冲突 |
| 422 | `ROSTER_VALIDATION_FAILED` | 名单存在校验错误 |
| 422 | `ATTENDANCE_INCOMPLETE` | 尚有待确认记录 |
| 429 | `RATE_LIMITED` | 登录或上传频率超限 |
| 500 | `INTERNAL_ERROR` | 未预期服务端错误 |

## 5. Acceptance Criteria

- **AC-001**：Given 管理员已登录，When 创建教师账号，Then 系统生成带首次改密标记的启用账号，且数据库中不存在明文密码。
- **AC-002**：Given 教师使用临时密码登录，When 访问课程页面，Then 系统阻止访问并引导修改密码。
- **AC-003**：Given 教师 A 已创建课程，When 教师 B 请求该课程或其班级资源，Then 返回 404 或 403，且数据不出现在响应中。
- **AC-004**：Given 合法 Excel 名单，When 预览并确认导入，Then 有效学生和班级关系在一个事务中写入，并返回成功、跳过和失败数量。
- **AC-005**：Given 名单中同一学号对应不同姓名，When 请求确认导入，Then 返回 `STUDENT_IDENTITY_CONFLICT`，且不写入任何行。
- **AC-006**：Given 班级已有 45 名有效学生，When 创建当日点名场次，Then 生成 45 条 `pending` 记录和固定快照。
- **AC-007**：Given 教师按状态快捷键，When 网络响应尚未返回，Then 界面立即推进到下一名并显示同步中。
- **AC-008**：Given 某保存请求短暂失败，When 网络恢复，Then 内存队列按退避策略自动重试并最终显示已同步。
- **AC-009**：Given 存在 `pending` 或未同步记录，When 教师结束点名，Then 前端和后端均拒绝完成场次。
- **AC-010**：Given 已完成场次，When 教师填写原因并修改状态，Then 记录版本递增且审计日志保存修改前后值。
- **AC-011**：Given 场次创建后移除一名学生，When 查看或导出历史场次，Then 该学生仍以创建时快照出现。
- **AC-012**：Given 教师选择 `.xlsx` 或 `.csv`，When 导出自己的已完成场次，Then 下载内容、文件名、编码和字段符合 EXP-002 至 EXP-005。
- **AC-013**：Given 浏览器不支持 TTS，When 教师进入点名页，Then 页面显示降级提示且所有键盘点名功能可用。
- **AC-014**：Given 刷新令牌已轮换、撤销或过期，When 再次使用旧令牌，Then 刷新失败且不签发访问令牌。
- **AC-015**：Given 恶意扩展名、超限文件或无法解析的文件，When 上传名单，Then 系统拒绝处理、删除临时文件并记录请求结果。

## 6. Test Automation Strategy

### 6.1 测试层级

| 层级 | 工具 | 重点 |
| --- | --- | --- |
| 前端单元 | Vitest、React Testing Library | 状态映射、快捷键、同步队列、表单校验 |
| 后端单元 | Pytest | 状态机、权限策略、导入规则、导出命名 |
| API 集成 | Pytest、FastAPI TestClient、MySQL 测试库 | 路由、事务、唯一约束、乐观锁、会话轮换 |
| 端到端 | Playwright | 登录、建课、导入、点名、修正、导出 |
| 部署冒烟 | Docker Compose、HTTP 检查 | 容器启动、迁移、健康检查、反向代理 |

### 6.2 必测数据

- 正常 `.xlsx`、`.xls`、UTF-8 CSV、UTF-8 BOM CSV、GB18030 CSV。
- 缺少表头、缺少必填值、空行、重复学号、同号异名、超过 500 行。
- 文件扩展名与内容不一致、损坏工作簿、压缩炸弹特征和超大文件。
- 0 人、1 人、500 人班级。
- 访问令牌过期、刷新令牌轮换、账号禁用、密码重置。
- 保存超时、HTTP 500、HTTP 409、刷新后重试和连续失败。

### 6.3 覆盖门槛

- 后端领域服务和权限策略语句覆盖率不低于 85%。
- 前端考勤状态机和同步队列语句覆盖率不低于 90%。
- 其他业务模块总体语句覆盖率不低于 75%。
- 覆盖率不是发布的唯一条件，AC-001 至 AC-015 必须全部由自动化测试或明确的验收脚本覆盖。

### 6.4 CI 门槛

```text
Frontend: eslint -> tsc --noEmit -> vitest -> vite build
Backend:  ruff check -> ruff format --check -> mypy -> pytest
Database: alembic upgrade head on empty MySQL -> schema assertions
E2E:      docker compose up -> Playwright critical path
Images:   docker build for web and api
```

## 7. Rationale & Context

### 7.1 选择 FastAPI 模块化单体

系统首期业务量有限，核心复杂度在权限、名单校验、考勤状态和报表，不在分布式吞吐。模块化单体可保持清晰边界，同时避免微服务部署、链路追踪和分布式事务成本。Python 对 Excel 解析、统计和未来成绩计算有成熟生态。

### 7.2 选择 MySQL

课程、名单、场次和记录之间存在强关系与事务要求。MySQL 可通过外键、唯一约束和事务保证一致性，也符合单校云服务器的运维条件。

### 7.3 不做离线恢复

首期优先验证账号、名单和课堂点名闭环。仍保留页面内存同步队列，解决短暂网络抖动，但页面刷新后不恢复未提交数据。未来若实施离线模式，需要单独设计本地数据库、冲突合并和幂等提交协议。

### 7.4 为平时分扩展保留边界

考勤记录只保存考勤事实，不保存综合成绩。未来新增 `score_categories` 和 `score_events`：前者定义考勤、课堂纪律、作业等项目及权重，后者记录每个学生的加扣分事实。成绩通过明细聚合计算，不修改当前考勤表，也不在学生表写死总分。

## 8. Dependencies & External Integrations

### 8.1 前端平台

- **PLT-001**：React、Vite、TypeScript。
- **PLT-002**：React Router、TanStack Query、React Hook Form、Zod。
- **PLT-003**：浏览器 Web Speech API。
- **PLT-004**：Playwright，用于端到端测试。

### 8.2 后端平台

- **PLT-005**：Python 稳定版本、FastAPI、Pydantic。
- **PLT-006**：SQLAlchemy 2 同步会话和 Alembic 迁移。
- **PLT-007**：兼容 MySQL 的 Python 驱动。
- **PLT-008**：Argon2id 密码库和 JWT 签名库。
- **PLT-009**：pandas、openpyxl、xlrd，用于名单解析；openpyxl 和 Python 标准库 `csv` 用于导出。

具体版本在创建项目锁文件时选择当时仍受支持的稳定版本，并由依赖锁文件固定；本规格不绑定未经验证的版本号。

### 8.3 基础设施

- **INF-001**：一台支持 Docker Compose 的 Linux 云服务器。
- **INF-002**：Nginx，负责 TLS、静态文件、反向代理、上传限制和登录限流。
- **INF-003**：MySQL 8 兼容数据库，数据卷必须持久化。
- **INF-004**：域名和有效 HTTPS 证书。
- **INF-005**：服务器外部或独立磁盘的加密备份位置，避免备份与数据库同时丢失。

### 8.4 外部系统

首期无必须的外部业务系统。统一身份认证和教务系统是后续可选集成，未来应通过认证适配器和导入适配器接入，不得直接耦合当前领域服务。

## 9. Examples & Edge Cases

### 9.1 同一记录快速重复修改

教师先标记“缺勤”，请求尚未完成时立即回退改为“迟到”。同步队列不得并发发送两个相同版本请求。第一条请求成功后取得新版本，再发送最终“迟到”状态；导出只显示“迟到”，审计保留两次已提交修改。

### 9.2 点名期间账号失效

管理员禁用教师账号后，下一次 API 请求返回 401/403。前端停止同步和点名推进，保留当前页面内存队列并提示联系管理员。首期不保证关闭页面后的队列恢复。

### 9.3 名单中的同号异名

```json
{
  "student_number": "20260001",
  "existing_name": "张敏",
  "imported_name": "张明",
  "error": "STUDENT_IDENTITY_CONFLICT"
}
```

该冲突不能通过“覆盖”处理，整次确认导入失败。教师修正文件后重新预览。

### 9.4 已完成场次修正

修改已完成场次时必须提供原因。服务端在一个事务中更新记录、递增版本并追加审计日志。审计写入失败时整个事务回滚。

### 9.5 导出中的公式注入

任何以 `=`, `+`, `-`, `@` 开头的文本值在 CSV 输出时必须加前导单引号，避免电子表格公式注入。XLSX 输出必须把学号和文本字段写为字符串单元格。

## 10. Validation Criteria

- 数据库空库能够执行 `alembic upgrade head` 并生成全部表、索引和约束。
- OpenAPI 中存在本规格列出的所有端点和错误响应。
- 自动化测试覆盖 AC-001 至 AC-015，CI 全部通过。
- 使用 500 人名单完成导入预览、场次创建和导出时，单个请求在目标云服务器上不超过 5 秒。
- 常规 JSON API 在数据库正常且无外部依赖时，服务器端 P95 响应时间低于 500 ms。
- Playwright 在桌面 1440×900 和移动 390×844 视口验证无横向溢出；首期业务以桌面使用为主。
- 键盘可以完成登录后的课程选择、点名、回退、结束确认和异常修正。
- 安全检查确认访问令牌不落盘、Cookie 标志正确、数据库端口不暴露、日志不包含密码和令牌。
- 备份脚本能够生成可验证备份，并至少完成一次恢复到临时 MySQL 实例的演练。

## 11. Deployment & Operations

### 11.1 容器

```text
compose.yaml
├── web     # Nginx + React 构建产物，公开 80/443
├── api     # FastAPI，仅容器网络可见
└── mysql   # MySQL，仅容器网络可见，挂载持久卷
```

迁移作为显式发布步骤运行，不在每个 API 容器启动时自动执行。迁移失败必须停止发布。

### 11.2 健康检查

- `GET /api/v1/health/live`：进程可响应，不访问数据库。
- `GET /api/v1/health/ready`：验证数据库连接和当前迁移版本。

### 11.3 日志与监控

- 应用日志输出 JSON 到标准输出。
- 每个请求生成或透传 `X-Request-ID`。
- 请求日志包含请求 ID、用户 ID、方法、路由模板、状态码和耗时。
- 禁止记录密码、访问令牌、刷新令牌、完整上传内容和完整学生名单。
- 首期至少监控容器存活、磁盘空间、数据库连接失败、HTTP 5xx 比例和登录失败突增。

### 11.4 备份

- 每日执行一次 MySQL 一致性备份，保留最近 7 天。
- 备份必须复制到服务器系统盘之外的加密位置。
- 每月至少恢复一次到临时实例，并记录恢复耗时和校验结果。

## 12. Future Extension Contract

后续平时分模块不得向 `attendance_records` 增加纪律、作业或总分字段。建议新增：

```text
score_categories
  id, course_id, name, type, weight, max_score, status

score_events
  id, category_id, student_id, occurred_at,
  score_delta, reason, actor_user_id, source_type, source_id
```

考勤换算通过 `source_type=ATTENDANCE` 和 `source_id=attendance_record_id` 产生可追溯分值事件。课堂纪律使用 `source_type=DISCIPLINE`。综合成绩是查询或结算结果，不是学生主数据字段。

## 13. Related Specifications / Further Reading

- [智能课堂考勤系统 PRD](../docs/attendance-system-prd.md)
- [智能课堂考勤系统数据库表结构规范](./spec-schema-attendance-database.md)
- [智能课堂考勤系统 API 规范](./spec-design-attendance-api.md)
- FastAPI OpenAPI 文档：由实施后的 `/docs` 和 `/openapi.json` 提供
- Web Speech API：浏览器端 TTS 能力参考
