# Acceptance Records

这个目录用于存放真实 provider 联调验收记录。

推荐生成方式：

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py --mode auto
```

如果要把页面验收结果也一并写回记录：

```bash
backend/.venv/bin/python scripts/run_real_provider_acceptance.py \
  --mode auto \
  --run-ui \
  --ui-python /path/to/python-with-playwright
```

如果你仍想手动分步执行：

```bash
backend/.venv/bin/python scripts/init_real_provider_acceptance_record.py
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py
```

如果要把页面验收结果也写回记录：

```bash
backend/.venv/bin/python scripts/update_real_provider_acceptance_record.py \
  --run-ui \
  --ui-python /path/to/python-with-playwright
```

生成后再按实际联调结果补充内容。

如果页面验收因为 Playwright 或浏览器运行环境失败，当前脚本也会把失败原因写回记录，而不是直接丢失这一步的结果。

当前自动写回还包括：

- 临时空库启动验证结果
- provider 配置缺失 / 在线探测跳过文案的可读性验证结果
