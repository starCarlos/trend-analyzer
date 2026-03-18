# TrendScope 本地验收

## 1. 目标

这份文档只回答一件事：

- 如何用一个命令完成当前 Python-only 路径的本地验收

当前仓库已经提供：

- 后端单元测试
- FastAPI 健康检查
- FastAPI 直接提供的网页
- 浏览器 smoke 脚本

现在新增的 [`scripts/local_acceptance.py`](../scripts/local_acceptance.py) 会把这些动作串起来。

## 2. 默认流程

脚本默认会按顺序执行：

1. 运行 `backend/tests` 单测
2. 检查 `GET /api/health`
3. 如果后端没启动，则自动拉起 `backend/run_server.py`
4. 运行 [`scripts/ui_smoke_test.py`](../scripts/ui_smoke_test.py)
5. 如果后端是脚本拉起的，则在结束时自动停止

## 3. 前置条件

至少需要满足：

- `backend/.venv` 已存在
- 后端依赖已安装

如果要跑浏览器 smoke，还需要：

- Playwright 已安装在你用于执行 UI 脚本的 Python 环境里
- Chromium 已安装

## 4. 常用命令

### 4.1 只跑后端验收

适合当前机器还没有 Playwright 时先验证后端：

```bash
backend/.venv/bin/python scripts/local_acceptance.py --skip-ui
```

### 4.2 跑完整本地验收

如果当前 Python 环境已经装好 Playwright：

```bash
backend/.venv/bin/python scripts/local_acceptance.py
```

如果当前环境没有 Playwright，但你要跑内置的 inprocess UI smoke：

```bash
TRENDSCOPE_UI_DRIVER=inprocess \
backend/.venv/bin/python scripts/local_acceptance.py
```

如果 Playwright 装在另一个 Python 环境：

```bash
backend/.venv/bin/python scripts/local_acceptance.py \
  --ui-python /path/to/python-with-playwright
```

## 5. 可选参数

- `--skip-tests`
  - 跳过后端单测
- `--skip-ui`
  - 跳过浏览器 smoke
- `--require-running`
  - 要求后端必须已在运行，不允许脚本自动启动
- `--base-url`
  - 指定验收目标地址，默认 `http://127.0.0.1:5081`
- `--backend-python`
  - 指定用于跑单测和启动后端的 Python
- `--ui-python`
  - 指定用于执行 `ui_smoke_test.py` 的 Python
- `--json`
  - 把本地验收结果以 JSON 输出到 stdout，适合给其他脚本集成调用

## 6. 当前浏览器 smoke 覆盖范围

[`scripts/ui_smoke_test.py`](../scripts/ui_smoke_test.py) 当前会覆盖：

- 搜索页加载
- `Track` / `Untrack` 就绪状态
- `/tracked` 页加载
- `Provider preflight` 面板存在
- `Run smoke` 按钮流程
- smoke 结果卡片出现

## 7. 结果输出

浏览器 smoke 成功时，当前会输出截图到：

- `/tmp/trendscope-search-smoke.png`
- `/tmp/trendscope-tracked-smoke.png`

如果你使用 `--json`，脚本会额外输出结构化结果，包含：

- 是否执行了 tests / UI
- 后端原本是否已在运行
- 是否由脚本自动拉起后端
- `/api/health` 返回的环境和 provider 模式
- 本次失败原因

## 8. 当前边界

这套本地验收主要验证：

- Python-only 本地运行链路
- FastAPI 页面是否可访问
- 关键前端交互是否还能跑通

它不能替代：

- 真实 provider 联网联调
- Docker 运行环境验证
