# TrendScope 真实 Provider 验收记录模板

> 使用说明：
> 复制本文件，按一次真实联调验收填写一份记录。
> 也可以先运行 `scripts/init_real_provider_acceptance_record.py` 自动生成一份带日期和环境信息的记录文件。

## 1. 基本信息

- 验收日期：
- 验收人：
- 机器环境：
- 操作系统：
- Python 解释器：
- 网络环境：
- 是否使用代理：
- 验收模式：`auto` / `real`

## 2. 配置摘要

- `PROVIDER_MODE`：
- `GITHUB_API_BASE_URL`：
- `NEWSNOW_BASE_URL`：
- `NEWSNOW_SOURCE_IDS`：
- `REQUEST_TIMEOUT_SECONDS`：
- `SCHEDULER_ENABLED`：

## 3. 本地验收前置结果

- 是否先运行 `scripts/local_acceptance.py`：
- 命令：
- 结果：`通过` / `失败` / `未执行`
- 备注：

## 4. Provider 预检结果

命令：

```bash
backend/.venv/bin/python -m app.cli provider-status
```

结果摘要：

- `requested_mode`：
- `resolved_provider`：
- GitHub 状态：
- NewsNow 状态：
- 是否通过：`通过` / `失败`

原始输出摘录：

```text
在这里粘贴
```

## 5. 在线探测结果

命令：

```bash
backend/.venv/bin/python -m app.cli provider-verify --probe-mode real
```

结果摘要：

- GitHub 状态：
- NewsNow 状态：
- 是否通过：`通过` / `失败`

原始输出摘录：

```text
在这里粘贴
```

## 6. Smoke 总览结果

命令：

```bash
backend/.venv/bin/python -m app.cli provider-smoke openai/openai-python --probe-mode real
```

如有强制搜索：

```bash
backend/.venv/bin/python -m app.cli provider-smoke openai/openai-python --probe-mode real --force-search
```

结果摘要：

- summary：
- `search.status`：
- `search.message`：
- `next_steps`：
- 是否通过：`通过` / `失败`

原始输出摘录：

```text
在这里粘贴
```

## 7. 页面人工验收

### 7.1 GitHub 项目搜索

- 验证地址：
- 是否可打开：`是` / `否`
- 是否看到今日快照：`是` / `否`
- 是否看到 GitHub 内容流：`是` / `否`
- 是否看到趋势图：`是` / `否`
- `Track/Untrack` 是否正常：`是` / `否`
- 截图路径：
- 备注：

### 7.2 普通关键词搜索

- 验证地址：
- 是否看到 NewsNow 快照：`是` / `否`
- 是否看到内容列表：`是` / `否`
- 是否看到累计提示或累计曲线：`是` / `否`
- 截图路径：
- 备注：

### 7.3 `/tracked` 页

- 是否可打开：`是` / `否`
- `Verify real` 是否正常：`是` / `否`
- `Run smoke` 是否正常：`是` / `否`
- 是否看到 collect runs：`是` / `否`
- 截图路径：
- 备注：

## 8. 追踪与采集结果

- 是否验证 `Collect tracked`：`是` / `否`
- 是否验证 scheduler：`是` / `否`
- collect runs 是否新增：`是` / `否`
- 是否观察到新点位或更新时间变化：`是` / `否`
- 备注：

## 9. PRD 验收项映射

| 项目 | 结果 | 备注 |
|---|---|---|
| 可以从空库启动 | 通过 / 失败 / 待人工确认 | |
| GitHub 项目首次搜索能完成冷启动并看到历史图 | 通过 / 失败 / 待人工确认 | |
| 普通关键词首次搜索能看到 NewsNow 快照和内容列表 | 通过 / 失败 / 待人工确认 | |
| 加入追踪后，定时任务能持续写入新点位 | 通过 / 失败 / 部分通过 / 待人工确认 | |
| 搜索、回填、采集失败都有可读错误状态 | 通过 / 失败 / 部分通过 / 待人工确认 | |

## 10. 最终结论

- 本次真实 provider 联调结果：`通过` / `失败` / `部分通过`
- 是否允许继续上线前步骤：`是` / `否`
- 阻塞项：
- 后续动作：
