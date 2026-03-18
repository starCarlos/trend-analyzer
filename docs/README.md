# Trend Analyzer Docs

这套文档用于替代根目录下的混合草稿 [`trend-analyzer-PRD.md`](../trend-analyzer-PRD.md) 作为后续实现的主参考。
原稿保留不删，作为调研和想法池；`docs/` 下的内容才是当前执行口径。

## 文档分工

- `product-prd.md`
  说明为什么做、给谁做、MVP 到底做什么，以及上线验收标准。
- `technical-spec.md`
  说明 MVP 的架构、数据模型、接口约定、冷启动状态机和运行约束。
- `mvp-plan.md`
  说明实施顺序、里程碑、依赖关系、测试门槛和延期风险。
- `current-functional-flow.md`
  说明当前代码已经实现的完整功能流程，适合联调、维护和接手时先读。
- `mvp-completion-checklist.md`
  说明开发需求文档和当前实现的差距，适合判断是否达到 MVP 验收线。
- `docker-deployment.md`
  说明如何用 Docker Compose 启动当前 MVP，以及容器内的运行约定。
- `provider-runtime.md`
  说明如何切到 `auto/real` provider、做本地预检和在线探测。
- `local-acceptance.md`
  说明如何一键执行本地验收，包括单测、健康检查、自动拉起后端和浏览器 smoke。
- `real-provider-acceptance.md`
  说明如何在可联网环境做真实 provider 联调验收，并和 PRD 上线验收项对齐。
- `real-provider-acceptance-record-template.md`
  真实 provider 联调验收记录模板。
- `acceptance-records/`
  存放实际联调验收记录，建议由脚本自动生成后再填写。

## 当前统一决策

- MVP 只做最短闭环：`搜索 -> 冷启动 -> 趋势图/快照/内容列表 -> 加入追踪`
- MVP 必做数据源只有两个：
  - `GitHub`：仅对 `owner/repo` 或 GitHub URL 提供可回溯历史
  - `NewsNow`：提供国内/社区平台实时快照，不承诺历史补全
- `综合指数 / 自定义权重 / 热词发现 / 推送 / 导出 / 事件标注` 全部移出 MVP
- 搜索结果页必须支持异步回填和部分成功，不能要求所有数据源同时完成

## 使用规则

- 讨论产品范围时，以 `product-prd.md` 为准
- 讨论表结构、接口、状态机时，以 `technical-spec.md` 为准
- 讨论排期和交付顺序时，以 `mvp-plan.md` 为准
- 讨论当前代码已经实现了什么、实际怎么跑时，以 `current-functional-flow.md` 为准
- 当前默认运行路径是 `backend` 直接提供 API 和网页，不依赖 Node.js
