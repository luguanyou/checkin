---
title: 智能课堂考勤系统数据库表结构规范
version: 1.0
date_created: 2026-09-03
last_updated: 2026-09-03
owner: 项目开发团队
tags: [schema, database, mysql, attendance]
---

# Introduction

本文档定义智能课堂考勤系统首期可上线版本的 MySQL 逻辑表结构。它是 SQLAlchemy 模型、Alembic 迁移、数据库约束和数据层测试的实现依据。

本文档遵循[智能课堂考勤系统技术规格](./spec-architecture-attendance-system.md)。若两份文档出现冲突，以技术规格确认的首期范围和安全规则为准，并同步修正文档，禁止在代码中静默选择其中一种解释。

## 1. Purpose & Scope

### 1.1 目标

- 持久化账号、课程、班级、学生名单、名单导入预览、点名场次、考勤记录和审计日志。
- 通过外键、唯一约束、检查约束和事务保证核心业务不变量。
- 支持 2,000 个教师账号、每班最多 500 人和单机 MySQL 8 部署。
- 为 FastAPI 服务提供唯一的已提交数据事实来源。

### 1.2 首期包含

本文档定义以下 10 张表：

1. `users`
2. `login_sessions`
3. `courses`
4. `class_groups`
5. `students`
6. `enrollments`
7. `import_previews`
8. `attendance_sessions`
9. `attendance_records`
10. `audit_logs`

### 1.3 首期不包含

- 多学校租户字段。
- 离线草稿和浏览器同步副本。
- 请假审批、学生端签到和教务系统主数据同步。
- 学期汇总、平时分、课堂纪律和作业分表。
- 物理保存导入原文件或导出结果文件。

## 2. Definitions

| 术语 | 定义 |
| --- | --- |
| 名单关系 | 学生与班级之间由 `enrollments` 表表示的关联 |
| 名单快照 | 创建点名场次时复制到考勤记录中的学号、姓名和班级名称 |
| 软归档 | 通过状态字段停止使用记录，不执行物理删除 |
| 乐观锁 | 更新考勤记录时要求客户端版本等于数据库版本，成功后版本加一 |
| 客户端变更 ID | 客户端为一次考勤状态变更生成的 UUID，用于安全重试和审计去重 |
| 追加式日志 | 只能插入和查询，不允许更新或删除的审计数据 |

## 3. Requirements, Constraints & Guidelines

### 3.1 数据库级约定

- **SCH-001**：数据库必须兼容 MySQL 8.0，所有表使用 `InnoDB` 和 `utf8mb4`。
- **SCH-002**：业务主键使用应用生成的 UUID，数据库类型为 `CHAR(36)`，不得依赖自增 ID。
- **SCH-003**：除显式说明外，所有字段均为 `NOT NULL`。
- **SCH-004**：所有时间以 UTC 写入 `DATETIME(6)`；日期使用 `DATE`。
- **SCH-005**：所有表包含 `created_at` 和 `updated_at`。两者默认为当前 UTC 时间；可变记录更新时刷新 `updated_at`。
- **SCH-006**：状态字段使用大写业务枚举，考勤状态使用架构规格规定的小写枚举。数据库通过 `CHECK` 约束阻止未知值。
- **SCH-007**：外键默认使用 `ON UPDATE RESTRICT ON DELETE RESTRICT`。业务数据不得依赖级联删除。
- **SCH-008**：`users`、`courses`、`class_groups` 和 `enrollments` 使用状态字段保留历史关系，不对已被业务数据引用的记录执行物理删除。
- **SCH-009**：用户名写入前去除首尾空格并转换为小写；学号和课程代码写入前去除首尾空格。
- **SCH-010**：密码、访问令牌和刷新令牌明文不得写入任何表。刷新令牌只保存 SHA-256 十六进制哈希。
- **SCH-011**：应用必须显式指定事务边界，不使用跨请求事务。
- **SCH-012**：迁移必须由 Alembic 显式执行，应用进程启动时不得自动修改表结构。

### 3.2 通用列

除非具体表另有说明，每张表都包含：

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `id` | `CHAR(36)` | 无 | UUID 主键 |
| `created_at` | `DATETIME(6)` | `CURRENT_TIMESTAMP(6)` | 创建时间，UTC |
| `updated_at` | `DATETIME(6)` | `CURRENT_TIMESTAMP(6)` | 最后更新时间，UTC |

`updated_at` 由应用在更新语句中显式赋值，避免数据库隐式时区或批量更新行为造成歧义。`audit_logs` 不允许更新，因此其 `updated_at` 永远等于 `created_at`。

## 4. Interfaces & Data Contracts

### 4.1 关系总览

```text
users ──< login_sessions
  │
  ├──< courses ──< class_groups ──< enrollments >── students
  │                         │
  │                         ├──< import_previews
  │                         └──< attendance_sessions ──< attendance_records >── students
  │
  └──< audit_logs
```

考勤历史主要依赖 `attendance_records` 内的快照字段。即使学生被移出当前名单、班级改名或课程归档，历史点名内容仍保持不变。

### 4.2 `users`

保存管理员和教师账号。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `username` | `VARCHAR(64)` | 否 | 无 | 标准化小写，UNIQUE |
| `password_hash` | `VARCHAR(255)` | 否 | 无 | Argon2id 编码结果 |
| `display_name` | `VARCHAR(100)` | 否 | 无 | 显示名称 |
| `role` | `VARCHAR(20)` | 否 | 无 | `ADMIN`、`TEACHER` |
| `status` | `VARCHAR(20)` | 否 | `ACTIVE` | `ACTIVE`、`DISABLED` |
| `must_change_password` | `BOOLEAN` | 否 | `TRUE` | 首次登录或密码重置后为真 |
| `failed_login_count` | `INT UNSIGNED` | 否 | `0` | 连续失败次数 |
| `last_failed_login_at` | `DATETIME(6)` | 是 | `NULL` | 最近一次登录失败时间 |
| `last_login_at` | `DATETIME(6)` | 是 | `NULL` | 最近一次成功登录时间 |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `PRIMARY KEY (id)`
- `UNIQUE KEY uq_users_username (username)`
- `CHECK (role IN ('ADMIN', 'TEACHER'))`
- `CHECK (status IN ('ACTIVE', 'DISABLED'))`
- `CHECK (failed_login_count >= 0)`
- `INDEX ix_users_role_status (role, status)`

状态规则：

- 成功登录后将 `failed_login_count` 置零并更新 `last_login_at`。
- 登录失败后在同一事务中递增 `failed_login_count` 并更新 `last_failed_login_at`。
- 禁用或重置密码时必须同时撤销该用户所有未撤销的登录会话。

### 4.3 `login_sessions`

保存刷新会话。访问令牌为 15 分钟 JWT，不落库。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK，同时作为 JWT `sid` |
| `user_id` | `CHAR(36)` | 否 | 无 | FK -> `users.id` |
| `refresh_token_hash` | `CHAR(64)` | 否 | 无 | SHA-256 十六进制，UNIQUE |
| `expires_at` | `DATETIME(6)` | 否 | 无 | 绝对过期时间 |
| `revoked_at` | `DATETIME(6)` | 是 | `NULL` | 撤销时间 |
| `last_used_at` | `DATETIME(6)` | 否 | 无 | 创建或最近轮换时间 |
| `ip_address` | `VARCHAR(45)` | 否 | 无 | IPv4 或 IPv6 文本 |
| `user_agent` | `VARCHAR(255)` | 否 | 无 | 截断后的 User-Agent |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `UNIQUE KEY uq_login_sessions_refresh_hash (refresh_token_hash)`
- `INDEX ix_login_sessions_user_active (user_id, revoked_at, expires_at)`
- `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT`

刷新令牌轮换必须在一个事务中更新当前会话的令牌哈希和 `last_used_at`。旧哈希在事务提交后立即失效。

### 4.4 `courses`

保存教师自行创建的课程。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `owner_teacher_id` | `CHAR(36)` | 否 | 无 | FK -> `users.id`，必须为教师 |
| `name` | `VARCHAR(120)` | 否 | 无 | 课程名称 |
| `code` | `VARCHAR(50)` | 否 | 无 | 教师范围内的课程代码 |
| `term` | `VARCHAR(50)` | 否 | 无 | 例如 `2026 秋季学期` |
| `status` | `VARCHAR(20)` | 否 | `ACTIVE` | `ACTIVE`、`ARCHIVED` |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `UNIQUE KEY uq_courses_owner_code_term (owner_teacher_id, code, term)`
- `INDEX ix_courses_owner_status (owner_teacher_id, status)`
- `CHECK (status IN ('ACTIVE', 'ARCHIVED'))`
- `FOREIGN KEY (owner_teacher_id) REFERENCES users(id) ON DELETE RESTRICT`

课程归档后禁止创建新班级和新点名场次，但允许查询和导出历史数据。

### 4.5 `class_groups`

保存课程下的教学班级。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `course_id` | `CHAR(36)` | 否 | 无 | FK -> `courses.id` |
| `name` | `VARCHAR(120)` | 否 | 无 | 同一课程内唯一 |
| `status` | `VARCHAR(20)` | 否 | `ACTIVE` | `ACTIVE`、`ARCHIVED` |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `UNIQUE KEY uq_class_groups_course_name (course_id, name)`
- `INDEX ix_class_groups_course_status (course_id, status)`
- `CHECK (status IN ('ACTIVE', 'ARCHIVED'))`
- `FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT`

班级归档后禁止修改当前名单或创建新点名场次。

### 4.6 `students`

保存全校范围唯一的学生身份。首期不向教师提供修改学生身份的接口。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `student_number` | `VARCHAR(50)` | 否 | 无 | 全校唯一学号 |
| `name` | `VARCHAR(100)` | 否 | 无 | 学生姓名 |
| `gender` | `VARCHAR(20)` | 是 | `NULL` | 原始导入文本 |
| `major` | `VARCHAR(120)` | 是 | `NULL` | 专业 |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `UNIQUE KEY uq_students_student_number (student_number)`
- `INDEX ix_students_name (name)`，仅用于已授权名单内的辅助查询，不开放全校枚举接口。

导入中遇到已有学号时：

- 姓名完全一致：复用学生记录，只处理班级关系。
- 姓名不一致：返回身份冲突，整次确认事务回滚。
- `gender` 或 `major` 不一致：首期保留已有值，不由教师导入静默覆盖。

### 4.7 `enrollments`

保存学生与班级的当前名单关系。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `class_group_id` | `CHAR(36)` | 否 | 无 | FK -> `class_groups.id` |
| `student_id` | `CHAR(36)` | 否 | 无 | FK -> `students.id` |
| `status` | `VARCHAR(20)` | 否 | `ACTIVE` | `ACTIVE`、`REMOVED` |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `UNIQUE KEY uq_enrollments_class_student (class_group_id, student_id)`
- `INDEX ix_enrollments_class_status (class_group_id, status)`
- `INDEX ix_enrollments_student (student_id)`
- `CHECK (status IN ('ACTIVE', 'REMOVED'))`
- 两个外键均为 `ON DELETE RESTRICT`。

重复导入策略：

- `skip`：已有 `ACTIVE` 或 `REMOVED` 关系均不修改，并计入跳过数量。
- `replace`：已有 `REMOVED` 关系恢复为 `ACTIVE`；已有 `ACTIVE` 关系保持不变。该策略不修改 `students` 身份字段。

### 4.8 `import_previews`

保存名单文件解析后的短期标准化结果，不保存原文件。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK，作为 `preview_id` |
| `class_group_id` | `CHAR(36)` | 否 | 无 | FK -> `class_groups.id` |
| `created_by` | `CHAR(36)` | 否 | 无 | FK -> `users.id` |
| `source_filename` | `VARCHAR(255)` | 否 | 无 | 清理路径后的原始文件名 |
| `normalized_rows` | `JSON` | 否 | 无 | 标准化行数组 |
| `validation_result` | `JSON` | 否 | 无 | 汇总和逐行校验结果 |
| `expires_at` | `DATETIME(6)` | 否 | 无 | 不晚于创建后 1 小时 |
| `confirmed_at` | `DATETIME(6)` | 是 | `NULL` | 确认成功时间；非空后不可再次确认 |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `INDEX ix_import_previews_owner_expiry (created_by, expires_at)`
- `INDEX ix_import_previews_class_expiry (class_group_id, expires_at)`
- 两个外键均为 `ON DELETE RESTRICT`。
- 应用约束 `expires_at <= created_at + 1 hour`。

`normalized_rows` 每项结构：

```json
{
  "row_number": 2,
  "student_number": "20260001",
  "name": "张敏",
  "gender": "女",
  "class_name": "2026 级 1 班",
  "major": "工业设计"
}
```

`validation_result` 结构：

```json
{
  "summary": {
    "total": 3,
    "valid": 1,
    "errors": 1,
    "duplicates": 1,
    "importable": 1
  },
  "rows": [
    {
      "row_number": 3,
      "status": "error",
      "code": "MISSING_REQUIRED_FIELD",
      "fields": ["name"],
      "message": "姓名不能为空"
    }
  ]
}
```

后台清理任务至少每小时物理删除已过期或已确认的预览记录。原始上传文件必须在解析结束或异常退出的 `finally` 清理阶段删除。

### 4.9 `attendance_sessions`

保存某班级某天的一次点名场次。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `class_group_id` | `CHAR(36)` | 否 | 无 | FK -> `class_groups.id` |
| `session_date` | `DATE` | 否 | 无 | 按 Asia/Shanghai 业务日期确定 |
| `status` | `VARCHAR(20)` | 否 | `DRAFT` | `DRAFT`、`COMPLETED` |
| `started_at` | `DATETIME(6)` | 否 | 无 | 场次创建时间，UTC |
| `completed_at` | `DATETIME(6)` | 是 | `NULL` | 完成时间，UTC |
| `created_by` | `CHAR(36)` | 否 | 无 | FK -> `users.id` |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `UNIQUE KEY uq_attendance_sessions_class_date (class_group_id, session_date)`
- `INDEX ix_attendance_sessions_creator_date (created_by, session_date)`
- `INDEX ix_attendance_sessions_class_status_date (class_group_id, status, session_date)`
- `CHECK (status IN ('DRAFT', 'COMPLETED'))`
- `CHECK ((status = 'DRAFT' AND completed_at IS NULL) OR (status = 'COMPLETED' AND completed_at IS NOT NULL))`
- 外键均为 `ON DELETE RESTRICT`。

`DRAFT -> COMPLETED` 是唯一允许的状态迁移，完成后不可恢复为草稿。

### 4.10 `attendance_records`

保存场次中每名学生的考勤事实和名单快照。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `session_id` | `CHAR(36)` | 否 | 无 | FK -> `attendance_sessions.id` |
| `student_id` | `CHAR(36)` | 否 | 无 | FK -> `students.id` |
| `student_number_snapshot` | `VARCHAR(50)` | 否 | 无 | 场次创建时复制 |
| `student_name_snapshot` | `VARCHAR(100)` | 否 | 无 | 场次创建时复制 |
| `class_name_snapshot` | `VARCHAR(120)` | 否 | 无 | 场次创建时复制 |
| `status` | `VARCHAR(20)` | 否 | `pending` | `pending`、`present`、`absent`、`leave`、`late` |
| `marked_at` | `DATETIME(6)` | 是 | `NULL` | 首次从 `pending` 变为最终状态的时间 |
| `last_modified_by` | `CHAR(36)` | 否 | 无 | FK -> `users.id`；初始为场次创建者 |
| `last_modified_at` | `DATETIME(6)` | 是 | `NULL` | 最近一次状态修改时间 |
| `version` | `INT UNSIGNED` | 否 | `1` | 每次成功更新加一 |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |

约束和索引：

- `UNIQUE KEY uq_attendance_records_session_student (session_id, student_id)`
- `INDEX ix_attendance_records_session_status (session_id, status)`
- `INDEX ix_attendance_records_student (student_id)`
- `CHECK (status IN ('pending', 'present', 'absent', 'leave', 'late'))`
- `CHECK (version >= 1)`
- `CHECK ((status = 'pending' AND marked_at IS NULL) OR (status <> 'pending' AND marked_at IS NOT NULL))`
- 所有外键均为 `ON DELETE RESTRICT`。

更新语句必须同时匹配记录 ID 和期望版本：

```sql
UPDATE attendance_records
SET status = :status,
    marked_at = COALESCE(marked_at, :now),
    last_modified_by = :actor_id,
    last_modified_at = :now,
    version = version + 1,
    updated_at = :now
WHERE id = :record_id
  AND version = :expected_version;
```

受影响行数为零时，应用重新检查资源归属和当前版本，并返回 404 或 `ATTENDANCE_RECORD_CONFLICT`。状态更新与对应审计日志必须在同一事务中提交。

### 4.11 `audit_logs`

保存安全事件和业务修改的追加式审计记录。

| 字段 | 类型 | 可空 | 默认值 | 约束或说明 |
| --- | --- | --- | --- | --- |
| `id` | `CHAR(36)` | 否 | 无 | PK |
| `actor_user_id` | `CHAR(36)` | 否 | 无 | FK -> `users.id` |
| `action` | `VARCHAR(80)` | 否 | 无 | 受控动作代码 |
| `entity_type` | `VARCHAR(80)` | 否 | 无 | 例如 `attendance_record` |
| `entity_id` | `CHAR(36)` | 否 | 无 | 被操作实体 ID，不设跨表外键 |
| `before_value` | `JSON` | 是 | `NULL` | 修改前的必要字段 |
| `after_value` | `JSON` | 是 | `NULL` | 修改后的必要字段 |
| `reason` | `VARCHAR(500)` | 是 | `NULL` | 已完成考勤修正时必填 |
| `ip_address` | `VARCHAR(45)` | 否 | 无 | 请求来源 IP |
| `request_id` | `VARCHAR(64)` | 否 | 无 | 请求追踪 ID |
| `client_mutation_id` | `CHAR(36)` | 是 | `NULL` | 考勤修改时必填并全局唯一 |
| `created_at` | `DATETIME(6)` | 否 | 当前时间 | UTC |
| `updated_at` | `DATETIME(6)` | 否 | 当前时间 | 必须等于 `created_at` |

约束和索引：

- `UNIQUE KEY uq_audit_logs_client_mutation (client_mutation_id)`；MySQL 允许多个 `NULL`。
- `INDEX ix_audit_logs_actor_created (actor_user_id, created_at)`
- `INDEX ix_audit_logs_entity_created (entity_type, entity_id, created_at)`
- `INDEX ix_audit_logs_request (request_id)`
- `FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE RESTRICT`

首期至少使用以下动作代码：

| 动作代码 | 实体类型 | 说明 |
| --- | --- | --- |
| `USER_CREATED` | `user` | 管理员创建教师账号 |
| `USER_STATUS_CHANGED` | `user` | 启用或禁用账号 |
| `USER_PASSWORD_RESET` | `user` | 管理员重置临时密码，不记录密码值 |
| `PASSWORD_CHANGED` | `user` | 用户修改密码，不记录密码值 |
| `COURSE_CREATED` | `course` | 创建课程 |
| `COURSE_UPDATED` | `course` | 编辑或归档课程 |
| `CLASS_GROUP_CREATED` | `class_group` | 创建班级 |
| `CLASS_GROUP_UPDATED` | `class_group` | 编辑或归档班级 |
| `ROSTER_IMPORTED` | `class_group` | 确认名单导入 |
| `ENROLLMENT_STATUS_CHANGED` | `enrollment` | 移除或恢复名单成员 |
| `ATTENDANCE_SESSION_CREATED` | `attendance_session` | 创建场次和快照 |
| `ATTENDANCE_STATUS_CHANGED` | `attendance_record` | 更新考勤状态 |
| `ATTENDANCE_SESSION_COMPLETED` | `attendance_session` | 结束点名 |

数据库账号权限不得授予应用用户对 `audit_logs` 的 `UPDATE` 或 `DELETE` 权限；若部署方式无法按表授权，应用仓储层仍必须只暴露插入和查询操作。

### 4.12 事务边界

| 操作 | 同一事务内必须完成的写入 |
| --- | --- |
| 创建教师 | 插入 `users`、插入审计日志 |
| 禁用或重置教师 | 更新 `users`、批量撤销 `login_sessions`、插入审计日志 |
| 刷新令牌轮换 | 校验并更新 `login_sessions.refresh_token_hash` 和 `last_used_at` |
| 确认名单导入 | 锁定预览、创建或复用学生、创建或恢复名单关系、标记预览已确认、插入审计日志 |
| 创建点名场次 | 插入场次、按有效名单批量插入记录快照、插入审计日志 |
| 修改考勤状态 | 通过版本更新记录、插入唯一客户端变更 ID 的审计日志 |
| 完成点名 | 锁定场次、确认无 `pending`、更新场次、插入审计日志 |

任一步失败时必须回滚整个事务。API 只能在事务提交成功后返回成功。

### 4.13 数据生命周期

| 数据 | 保留和删除规则 |
| --- | --- |
| 用户、课程、班级、名单关系 | 使用状态字段保留，不物理删除已引用记录 |
| 登录会话 | 撤销后保留用于安全审计；保留期由运维策略设置，建议不少于 90 天 |
| 导入原文件 | 解析完成或失败后立即删除 |
| 导入预览 | 最多 1 小时；确认成功或过期后由清理任务删除 |
| 点名场次、考勤记录 | 首期不提供删除操作 |
| 审计日志 | 追加式保存，首期不提供更新和删除操作 |
| 导出文件 | 实时流式生成，响应结束后不在服务器保存 |

## 5. Acceptance Criteria

- **AC-DB-001**：Given 空 MySQL 数据库，When 执行 `alembic upgrade head`，Then 10 张表及本文档规定的约束和索引全部创建成功。
- **AC-DB-002**：Given 已存在标准化用户名，When 再次创建相同用户名，Then 唯一约束拒绝写入。
- **AC-DB-003**：Given 教师被禁用或重置密码，When 事务提交，Then 该用户所有未撤销刷新会话均已有 `revoked_at`。
- **AC-DB-004**：Given 全校已存在某学号且姓名不同，When 确认名单导入，Then 整个事务回滚且没有新增学生或名单关系。
- **AC-DB-005**：Given 一个班级当天已有场次，When 再次创建，Then 唯一约束阻止重复场次。
- **AC-DB-006**：Given 班级有 500 个有效名单成员，When 创建场次，Then 同一事务创建 500 条 `pending` 记录并写入固定快照。
- **AC-DB-007**：Given 记录当前版本为 3，When 客户端以期望版本 2 更新，Then 更新影响 0 行且原记录不变。
- **AC-DB-008**：Given 相同 `client_mutation_id` 的请求被重试，When 第二次写审计日志，Then 唯一约束阻止重复业务变更。
- **AC-DB-009**：Given 场次仍有 `pending` 记录，When 请求完成场次，Then 事务拒绝状态迁移。
- **AC-DB-010**：Given 学生被移出名单且班级随后改名，When 查询历史场次，Then 考勤记录仍返回场次创建时的学生和班级快照。
- **AC-DB-011**：Given 预览已过期或已确认，When 清理任务运行，Then 预览记录被删除且业务名单不受影响。
- **AC-DB-012**：Given 应用数据库账号，When 尝试更新或删除审计日志，Then 权限或仓储层拒绝操作。

## 6. Test Automation Strategy

### 6.1 迁移测试

- 在空 MySQL 测试库执行全部升级迁移。
- 执行一次完整降级再升级；生产迁移若声明不可逆，必须提供显式保护和恢复说明。
- 校验表、列类型、默认值、外键、唯一约束、检查约束和索引名称。

### 6.2 数据层集成测试

- 使用真实 MySQL 测试容器，不使用 SQLite 替代约束行为。
- 每个测试使用事务回滚或独立数据库清理数据。
- 覆盖唯一冲突、外键限制、JSON 序列化、UTC 微秒精度、乐观锁和审计幂等。
- 覆盖 0、1、500 人名单的场次创建。

### 6.3 性能验证

- 500 人名单导入确认和点名场次创建分别在目标云服务器上低于 5 秒。
- 历史场次分页、单场次详情和名单查询使用 `EXPLAIN` 验证命中预期复合索引。
- 禁止在名单、场次和记录列表中产生逐行查询。

## 7. Rationale & Context

### 7.1 学生身份与名单关系分离

学号在全校范围唯一，而同一学生可能出现在多个课程班级。将学生身份放入 `students`，将班级成员关系放入 `enrollments`，可以避免重复身份数据，同时允许名单成员软移除和恢复。

### 7.2 在考勤记录中保存快照

历史考勤必须反映点名发生时的名单。只关联当前学生和班级会使后续改名或移除影响历史导出，因此记录同时保留关联 ID 和必要文本快照。

### 7.3 审计日志与考勤更新同事务

已完成场次的修正属于敏感操作。状态已修改但审计写入失败会失去可追溯性，因此二者必须共同提交或共同回滚。

### 7.4 使用版本号和客户端变更 ID

版本号发现来自不同客户端状态的并发覆盖；客户端变更 ID 处理网络超时后的相同请求重试。两者解决的问题不同，不能相互替代。

## 8. Dependencies & External Integrations

- **PLT-DB-001**：MySQL 8.0，支持 InnoDB、JSON、微秒时间和生效的 `CHECK` 约束。
- **PLT-DB-002**：SQLAlchemy 2 同步会话。
- **PLT-DB-003**：Alembic 迁移。
- **INF-DB-001**：持久化 MySQL 数据卷和服务器外加密备份位置。
- **INF-DB-002**：应用使用最小权限数据库账号，MySQL 端口不对公网开放。

## 9. Examples & Edge Cases

### 9.1 同一记录连续修改

客户端先将版本 3 的记录改为缺勤，再立即改为迟到。第一笔已在途修改成功后记录版本变为 4；客户端必须使用版本 4 提交最终迟到状态。最终记录版本为 5，审计日志保存两次已提交变化。

### 9.2 导入同号异名

文件包含学号 `20260001`、姓名“张明”，数据库已有相同学号、姓名“张敏”。该冲突不能使用 `replace` 绕过，确认导入事务必须整体失败。

### 9.3 并发创建场次

两个请求同时为同一班级和业务日期创建场次。数据库唯一约束只允许一个事务成功；失败请求转换为 `DUPLICATE_RESOURCE`，不得遗留孤立考勤记录。

## 10. Validation Criteria

- 文档中的表名、字段名和状态值与 API 规范完全一致。
- 每个外键都有明确删除策略，每个高频查询都有匹配索引。
- 所有业务唯一性均由数据库约束保证，不只依赖应用查询。
- 所有敏感多表写操作都有明确事务边界。
- 不存在明文密码、令牌、上传文件或导出文件持久化字段。
- 不包含首期排除的离线、学期汇总或平时分数据结构。

## 11. Related Specifications / Further Reading

- [智能课堂考勤系统技术规格](./spec-architecture-attendance-system.md)
- [智能课堂考勤系统 API 规范](./spec-design-attendance-api.md)
- [智能课堂考勤系统 PRD](../docs/attendance-system-prd.md)
