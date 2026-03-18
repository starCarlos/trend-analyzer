# TrendScope 真实 Provider 联调验收

## 1. 目标

这份文档只回答一件事：

- 当你处于可联网环境时，如何对当前 Python-only 路径做一次完整的真实 provider 联调验收

它对应的是当前仍未完全在线完成的工程验证项：

- 真实 provider 在线联调验证

这份文档不替代本地验收文档。
本地验收请先看 [`local-acceptance.md`](./local-acceptance.md)。

## 2. 验收前提

开始前至少确认：

- 当前机器可访问 GitHub 和 NewsNow
- `backend/.venv` 已可用
- 你已经准备好 `backend/.env`
- 若网络需要代理，已配置 `HTTP_PROXY`
- 若要减少 GitHub 限流风险，已配置 `GITHUB_TOKEN`

推荐先完成一次本地验收：

```bash
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui
```

## 3. 推荐模式

建议按下面顺序做：

1. 先用 `auto` 模式验收
2. `auto` 模式通过后，再用 `real` 模式复核

原因：

- `auto` 更适合首次联网联调
- `real` 更适合做正式失败暴露和最终验收记录

## 4. 推荐验收顺序

### 4.1 切到 Auto

```bash
cd backend
cp .env.auto.example .env
```

### 4.2 跑 provider 预检

```bash
cd backend
backend/.venv/bin/python -m app.cli provider-status
```

预期：

- `resolved_provider` 为 `auto`
- GitHub 和 NewsNow 至少不应为 `misconfigured`

### 4.3 跑在线探测

```bash
cd backend
backend/.venv/bin/python -m app.cli provider-verify --probe-mode real
```

预期：

- GitHub `status=success`
- NewsNow `status=success`

如果某个源失败：

- 先修配置或网络
- 不建议直接把失败结果当通过

### 4.4 跑 smoke 总览

```bash
cd backend
backend/.venv/bin/python -m app.cli provider-smoke openai/openai-python --probe-mode real
```

预期：

- `summary` 明确给出联调总览
- `provider_verify` 两个源都成功
- `search.status=success`

如果需要强制继续真实搜索：

```bash
cd backend
backend/.venv/bin/python -m app.cli provider-smoke openai/openai-python --probe-mode real --force-search
```

### 4.5 启动服务

```bash
cd backend
RELOAD=1 backend/.venv/bin/python run_server.py
```

### 4.6 验收 GitHub 项目搜索

浏览器打开：

- `http://127.0.0.1:8000/?q=openai/openai-python&period=30d`

人工确认：

- 页面可正常打开
- 能看到今日快照
- 能看到 GitHub 相关内容
- 若首次冷启动，后续能看到历史趋势线
- `Track` / `Untrack` 可切换

### 4.7 验收普通关键词搜索

浏览器打开：

- `http://127.0.0.1:8000/?q=mcp&period=30d`

人工确认：

- 能看到 NewsNow 快照
- 能看到内容列表
- 若没有历史，会提示“从当前开始积累”语义
- 若已有本地历史，能看到累计曲线

### 4.8 验收追踪页 provider 面板

浏览器打开：

- `http://127.0.0.1:8000/tracked`

人工确认：

- `Provider preflight` 面板能展示当前模式
- `Verify real` 能返回在线探测结果
- `Run smoke` 能返回 summary、search 状态和 next steps

### 4.9 验收追踪与采集

在 `/tracked` 页人工确认：

- 已追踪词可见
- `Collect tracked` 可运行
- `Recent collect runs` 有记录

如果要验证持续补数：

- 打开 `SCHEDULER_ENABLED=true`
- 等待至少一个采集周期
- 确认新的采集记录和更新时间出现

### 4.10 用 Real 模式复核

在 `auto` 通过后，再执行一次：

```bash
cd backend
cp .env.real.example .env
backend/.venv/bin/python -m app.cli provider-status
backend/.venv/bin/python -m app.cli provider-verify --probe-mode real
backend/.venv/bin/python -m app.cli provider-smoke openai/openai-python --probe-mode real
```

重点确认：

- 不再依赖 mock 回退
- 失败时能明确暴露真实错误

## 5. 与 PRD 验收项的对应关系

当前真实 provider 联调时，建议至少覆盖下列 PRD 验收项：

| PRD 验收项 | 建议验证动作 |
|---|---|
| 可以从空库启动 | 用空 SQLite 启动一次后端 |
| GitHub 项目首次搜索能完成冷启动并看到历史图 | 搜索 `openai/openai-python` 并等待趋势图准备完成 |
| 普通关键词首次搜索能看到 NewsNow 快照和内容列表 | 搜索 `mcp` 或其他普通词 |
| 加入追踪后，定时任务能持续写入新点位 | 开启 scheduler 或至少手动 collect 一次 |
| 搜索、回填、采集失败都有可读错误状态 | 故意使用错误配置或观察 provider 返回失败时的提示 |

`Docker` 相关验收仍应单独执行，不在这份文档里完成。

## 6. 建议留存的证据

建议至少保留：

- `provider-status` 输出
- `provider-verify` 输出
- `provider-smoke` 输出
- 搜索页截图
- `/tracked` 页截图
- collect runs 截图或文本记录
- 本次验收时间、环境、网络条件、provider 模式

## 7. 验收记录模板

推荐优先使用一键编排脚本：

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto
```

如果当前机器已经装好 Playwright，并且你也想把页面验收结果一起写回记录：

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py \
  --mode auto \
  --run-ui \
  --ui-python /path/to/python-with-playwright
```

这个入口会自动完成：

- 初始化或复用当天的验收记录文件
- 先执行 `scripts/local_acceptance.py`
- 自动写回本地验收结果、CLI 输出
- 如开启 `--run-ui`，会在需要时自动拉起 FastAPI，再把 7.x / 8 / 9 / 10 段写回记录
- 如果 `--run-ui` 因 Playwright / 浏览器沙箱失败，记录文件仍会写入失败原因，方便留痕

说明：

- 如果同时传了 `--local-with-ui` 和 `--run-ui`，编排脚本会只执行一次 UI 验收，避免重复跑两次浏览器 smoke

如果你希望手动分步执行，也可以继续使用下面这组命令。

建议先生成一份当天记录文件：

```bash
backend/.venv/bin/python scripts/init_real_provider_acceptance_record.py --mode auto
```

然后把当前 CLI 输出自动写回记录：

```bash
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py --mode auto
```

如果当前机器已经装好 Playwright，并且你也想把页面人工验收结果半自动写回记录：

```bash
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py \
  --mode auto \
  --run-ui \
  --ui-python /path/to/python-with-playwright
```

如果当前 `backend/.env` 已存在，脚本会自动预填：

- 验收日期
- 机器环境
- Python 解释器
- `PROVIDER_MODE`
- 关键 provider 配置摘要

更新脚本当前会自动写入：

- 本地验收前置结果可由 `run_real_provider_acceptance.py` 自动写入
- `provider-status` 摘要和原始 JSON
- `provider-verify` 摘要和原始 JSON
- `provider-smoke` 摘要和原始 JSON
- 页面验收地址、截图路径和主要通过项
- 临时空库启动验证结果
- provider 配置缺失 / 在线探测跳过文案的可读性验证结果
- PRD 验收项映射
- 最终结论和后续动作

请把最终结果记录到：

- [`real-provider-acceptance-record-template.md`](./real-provider-acceptance-record-template.md)
- [`acceptance-records/`](./acceptance-records/README.md)

## 8. 常见失败点

- GitHub 失败
  - 优先检查 `GITHUB_TOKEN`、代理、限流和出口网络
- NewsNow 失败
  - 优先检查 `NEWSNOW_BASE_URL`、`NEWSNOW_SOURCE_IDS` 和代理
- smoke 跳过真实搜索
  - 通常是在线探测未全部成功，或没有开启 `force_search`
- 页面正常但数据不完整
  - 先检查 availability、collect runs 和 provider smoke 的 `next_steps`
