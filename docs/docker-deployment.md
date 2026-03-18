# TrendScope Docker 部署

## 1. 目标

用一条 `docker compose` 命令启动当前 MVP：

- `backend`：FastAPI + SQLite + 内置网页

默认部署模式面向本地演示和自测，后端 provider 默认使用 `mock`。

## 2. 前置要求

- 已安装 Docker
- 已安装 Docker Compose v2

## 3. 启动

在项目根目录执行：

```bash
docker compose up --build
```

启动后访问：

- 网页：`http://localhost:5081`
- 后端健康检查：`http://localhost:5081/api/health`

## 4. 当前编排说明

`docker-compose.yml` 当前只包含一个服务：

- `backend`
  - 基于 `backend/Dockerfile`
  - 使用 `uv sync --frozen --no-dev` 安装依赖
  - 数据库存储在容器内 `/app/data/trendscope.db`

SQLite 数据通过 named volume 持久化：

- `backend-data`

## 5. 常用命令

停止服务：

```bash
docker compose down
```

停止并删除本地 SQLite volume：

```bash
docker compose down -v
```

仅重建后端：

```bash
docker compose up --build backend
```

## 6. 切到真实 provider

如果要切到真实数据源，可在 `docker-compose.yml` 里覆盖 `backend.environment`：

- `PROVIDER_MODE=real` 或 `auto`
- `GITHUB_TOKEN`
- `NEWSNOW_BASE_URL`
- `NEWSNOW_SOURCE_IDS`
- `HTTP_PROXY`（如需要）

## 7. 当前限制

- 本文档已覆盖 compose 文件和镜像构建路径
- 如果要作为生产部署基线，仍建议补：
  - 反向代理
  - 健康检查
  - 真实 provider 联网验证
  - 更明确的 secrets 注入方式
