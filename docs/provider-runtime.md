# TrendScope Provider 联调说明

## 1. 目标

这份文档只回答一件事：

- 如何把当前默认的 `mock` 模式切到 `real` 或 `auto`
- 切换后如何用本地预检和在线探测确认配置状态

当前仓库默认仍推荐：

- 日常开发用 `mock`
- 首次联调真实源先用 `auto`
- 要做严格失败暴露时再切到 `real`

## 2. 推荐切换顺序

建议按下面顺序操作：

1. 从 `backend/.env.auto.example` 或 `backend/.env.real.example` 复制出 `backend/.env`
2. 先运行 `provider-status`
3. 再运行 `provider-verify --probe-mode real`
4. 再运行 `provider-smoke <query> --probe-mode real`
5. 通过后再启动 FastAPI 并做真实搜索

## 3. 模板文件

仓库里现在提供三份模板：

- `backend/.env.example`
  - 默认 `mock`
- `backend/.env.auto.example`
  - 真实请求失败时自动回退到 mock
- `backend/.env.real.example`
  - 只走真实 provider，不做 mock 回退

## 4. 切到 Auto

```bash
cd backend
cp .env.auto.example .env
uv sync
uv run python -m app.cli provider-status
uv run python -m app.cli provider-verify --probe-mode real
uv run python -m app.cli provider-smoke openai/openai-python --probe-mode real
RELOAD=1 uv run python run_server.py
```

适用场景：

- 你想先确认真实配置是否能跑
- 某个 provider 偶发失败时，希望页面还能回退到 mock

## 5. 切到 Real

```bash
cd backend
cp .env.real.example .env
uv sync
uv run python -m app.cli provider-status
uv run python -m app.cli provider-verify --probe-mode real
uv run python -m app.cli provider-smoke openai/openai-python --probe-mode real
RELOAD=1 uv run python run_server.py
```

适用场景：

- 你要明确暴露真实 provider 失败
- 你要做正式的真实源联调记录

## 6. 必填项

至少应确认这些配置是可用的：

- `PROVIDER_MODE`
- `GITHUB_API_BASE_URL`
- `GITHUB_HISTORY_MAX_PAGES`
- `NEWSNOW_BASE_URL`
- `NEWSNOW_SOURCE_IDS`
- `REQUEST_TIMEOUT_SECONDS`

建议补齐：

- `GITHUB_TOKEN`
  - 不填也可以请求 GitHub，但更容易被限流
- `HTTP_PROXY`
  - 当前网络需要代理时再填

## 7. 本地预检

### 7.1 CLI

```bash
cd backend
uv run python -m app.cli provider-status
```

它不会发网络请求，只检查：

- 当前 `PROVIDER_MODE`
- GitHub / NewsNow 的关键配置是否齐全
- `auto` 模式下哪个数据源会直接回退到 mock

### 7.2 页面

启动后访问：

- `http://127.0.0.1:8000/tracked`

页面里的 `Provider preflight` 面板会展示：

- 当前模式
- 每个数据源会优先用 real 还是 mock
- 配置缺口
- 风险提示
- smoke query / period / force_search 输入项

## 8. 在线探测

### 8.1 CLI

```bash
cd backend
uv run python -m app.cli provider-verify --probe-mode real
```

### 8.2 API

```bash
curl -X POST http://127.0.0.1:8000/api/provider-verify \
  -H 'Content-Type: application/json' \
  -d '{"probe_mode":"real"}'
```

### 8.3 Smoke 总览

```bash
cd backend
uv run python -m app.cli provider-smoke openai/openai-python --probe-mode real
```

默认行为：

- 会先做 `provider-status`
- 再做 `provider-verify`
- 如果在线探测没有全部成功，会默认跳过真实搜索

如需强制继续：

```bash
cd backend
uv run python -m app.cli provider-smoke openai/openai-python --probe-mode real --force-search
```

### 8.4 页面

在 `/tracked` 页点击：

- `Verify real`
- `Run smoke`

页面内 `Run smoke` 当前固定用 `probe_mode=real`，并允许你直接填写：

- `query`
- `period`
- `force_search`

页面 smoke 结果会展示：

- summary
- search.status 和 search.message
- search.availability
- next_steps

当前在线探测会做两件轻量请求：

- GitHub: `GET /rate_limit`
- NewsNow: 优先 `GET /api/s?id=<第一个 source id>`，兼容回退到 `GET /api/s/<第一个 source id>`

## 9. 结果解释

### `provider-status`

- `mock_only`
  - 当前模式只会使用 mock
- `ready`
  - 本地配置看起来可用
- `warning`
  - 可用，但有明显风险项
- `fallback_only`
  - `auto` 下该数据源会直接退回 mock
- `misconfigured`
  - `real` 下该数据源配置不完整

### `provider-verify`

- `success`
  - 已收到目标 provider 的真实响应
- `failed`
  - 发起了真实请求，但请求失败
- `skipped`
  - 因本地配置不完整或当前模式限制，没有发请求

## 10. 当前环境说明

如果你在当前 Codex 沙箱里执行在线探测，可能会看到：

- `Operation not permitted`

这表示当前执行环境禁网，不表示代码路径有问题。

## 11. 建议验收动作

当你处于可联网环境时，建议至少执行一次：

1. `uv run python -m app.cli provider-status`
2. `uv run python -m app.cli provider-verify --probe-mode real`
3. `uv run python -m app.cli provider-smoke openai/openai-python --probe-mode real`
4. `uv run python -m app.cli search openai/openai-python --period 30d`
5. 浏览器打开 `/tracked`
6. 浏览器打开 `/?q=openai/openai-python&period=30d`

如果你需要按验收流程完整记录，请继续看：

- [`real-provider-acceptance.md`](./real-provider-acceptance.md)
- [`real-provider-acceptance-record-template.md`](./real-provider-acceptance-record-template.md)
