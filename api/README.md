# 智能课堂考勤 API

FastAPI + MySQL 8 后端。以下命令均在 `api/` 目录执行。

## 本地启动

安装开发依赖：

```powershell
uv sync --group dev
```

复制 `.env.example` 为 `.env`，并修改数据库连接、前端源站和 JWT 密钥。`.env` 不应提交到版本控制；生产环境不得使用示例账号、密码或 JWT 密钥。

普通 HTTP 本地开发需设置 `FRONTEND_ORIGIN=http://127.0.0.1:5173` 和 `REFRESH_COOKIE_SECURE=false`。生产环境必须使用 HTTPS，并设置 `REFRESH_COOKIE_SECURE=true`。

启动测试 MySQL：

```powershell
docker compose -f compose.test.yaml up -d --wait
```

应用数据库迁移：

```powershell
$env:DATABASE_URL='mysql+pymysql://attendance:attendance@127.0.0.1:33307/attendance_test'
uv run alembic upgrade head
```

在实际 `.env` 中配置超级管理员。密码必须为 12 至 128 个字符：

```dotenv
ADMIN_USERNAME=admin
ADMIN_DISPLAY_NAME=超级管理员
ADMIN_PASSWORD=请替换为安全的管理员密码
```

执行迁移后启动 API，系统会自动创建该管理员。以后修改 `ADMIN_PASSWORD` 并重启 API 即可重置密码，同时撤销该管理员的旧登录会话；配置未变化时不会重复哈希密码或中断会话。删除或留空 `ADMIN_PASSWORD` 会禁用自动同步。

`.env` 中保存了管理员明文密码，必须限制服务器上的文件读取权限，且绝不能提交到版本控制。若配置用户名已被教师账号占用、字段为空或密码不符合长度要求，API 会拒绝启动并保留原有账号数据。

启动 API：

```powershell
uv run uvicorn attendance_api.main:app --host 127.0.0.1 --port 8000
```

OpenAPI 文档地址：`http://127.0.0.1:8000/docs`，原始契约地址：`http://127.0.0.1:8000/openapi.json`。

## 验证

```powershell
uv run --env-file .env.test.example pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run --env-file .env.test.example alembic check
```

停止并删除测试数据库容器与数据卷：

```powershell
docker compose -f compose.test.yaml down -v
```

生产发布时应把 `uv run alembic upgrade head` 作为独立发布步骤执行；API 容器启动命令不会自动迁移数据库。管理员同步在迁移完成后的 API 启动阶段执行。
