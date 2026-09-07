# 智能课堂考勤

前端采用 React、TypeScript 和 Vite，业务数据来自 `api/` 下的 FastAPI 服务。教师端覆盖登录、首次修改密码、工作台、课程班级、学生名单导入、课堂点名、考勤修正和 CSV/XLSX 导出；超级管理员登录后进入独立的简洁账号页面。

## 本地开发

Windows 用户安装并启动 Docker Desktop、[uv](https://docs.astral.sh/uv/) 和 Node.js 后，可以双击根目录的 `start.bat`。脚本会自动启动持久化的开发 MySQL、安装或同步依赖、执行数据库迁移，并在独立窗口启动 API 和前端，服务就绪后会打开浏览器。

首次启动会自动创建 `api/.env`，并在启动窗口显示随机生成的本地管理员密码；凭据也会保存在该文件中。后续启动会保留已有配置和数据库数据，不会覆盖 `api/.env`。

以下命令用于手动启动或排查问题。

安装前端依赖：

```powershell
npm install
```

复制前端环境配置并按需修改 API 地址：

```powershell
Copy-Item .env.example .env.local
```

按 [API README](api/README.md) 启动 MySQL、执行迁移并配置超级管理员。用于普通 HTTP 本地开发的 `api/.env` 需要包含：

```dotenv
FRONTEND_ORIGIN=http://127.0.0.1:5173
REFRESH_COOKIE_SECURE=false
ADMIN_USERNAME=admin
ADMIN_DISPLAY_NAME=超级管理员
ADMIN_PASSWORD=请替换为至少12位的安全密码
```

API 启动时会根据这些配置自动创建或同步超级管理员，不需要运行账号创建命令。修改 `ADMIN_PASSWORD` 并重启 API 可以重置密码；真实 `.env` 包含明文凭据，必须限制文件权限且不得提交。

启动 API：

```powershell
Set-Location api
uv run uvicorn attendance_api.main:app --host 127.0.0.1 --port 8000
```

另开终端启动前端：

```powershell
npm run dev
```

访问 `http://127.0.0.1:5173`。Vite 会把 `/api` 转发到 `VITE_API_PROXY_TARGET`，默认是 `http://127.0.0.1:8000`。

## 教师账号管理

使用 `ADMIN_USERNAME` 和 `ADMIN_PASSWORD` 登录后，系统进入 `/admin` 教师账号工作台。管理员可以搜索和筛选教师账号，并执行创建、停用、启用和重置密码。

创建或重置成功后，临时密码只显示一次。请立即使用“复制登录凭据”保存并通过可信渠道交给教师；关闭对话框后无法找回，只能再次重置。教师使用临时密码登录后必须先设置自己的新密码。

开发数据库使用本机端口 `33306`，测试数据库使用独立端口 `33307`，两者可以同时运行。启动并迁移测试数据库：

```powershell
Set-Location api
docker compose -f compose.test.yaml up -d --wait
uv run --env-file .env.test.example alembic upgrade head
uv run --env-file .env.test.example pytest
```

## 验证与构建

```powershell
npm run typecheck
npm run test:unit
npm run build
npm run test:browser
```

浏览器测试会自行启动临时 Vite 服务并使用确定性的 API 契约夹具，不要求本地 API 或 MySQL 正在运行。后端验证命令见 [API README](api/README.md)。

生产构建输出在 `dist/`。生产环境应从同一个 HTTPS 站点提供 `dist/` 和 `/api`，或通过等价的反向代理保持同源，并设置：

```dotenv
REFRESH_COOKIE_SECURE=true
FRONTEND_ORIGIN=https://attendance.example.edu
```

访问令牌仅保存在浏览器内存中；刷新令牌由后端通过 HttpOnly Cookie 管理。
