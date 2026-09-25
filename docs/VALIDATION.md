# 验证记录 · 2026-09-25

## 已实际验证

- Python 3.9.6 / macOS arm64。
- Streamlit 1.50.0、OpenAI SDK 2.48.0、Pydantic 2.13.5。
- `python -m pytest -q`：**21 passed**，包含 Streamlit AppTest 完整审核/人工 remove/申诉/人工 allow/改判统计流程。
- 已启动 Streamlit 并通过真实浏览器打开 `http://127.0.0.1:8501`。
- 在浏览器点击 TG-001 的“分析内容”，页面显示 VIOLATION、REMOVE recommendation、REQUIRED human review，并说明尚未执行处罚。
- 证据虚构、未知 policy ID、错误来源、只有站外信号、低置信度、高严重度、冲突、缺 key、拒绝、provider 失败、重复申诉与陈旧记录提交均有测试。
- `requirements-tested.txt` 保存本次实测环境依赖版本；跨操作系统优先使用 requirements.txt 安装。

## Demo 基线结果

36 条 synthetic smoke cases：13 违规 / 13 正常 / 10 灰区。

| 指标 | 结果 |
|---|---:|
| Precision | 100%（12 / 12） |
| Recall | 92.3%（12 / 13） |
| False Positive Rate | 0%（0 / 13） |
| Human Escalation Rate | 69.4%（25 / 36） |
| Gray Escalation Rate | 60%（6 / 10） |
| Binary Abstention Rate | 26.9%（7 / 26） |

这些是小型、自编合成样本上的确定性规则结果，不是模型实测或生产效果。灰区有 4 条未正确升级，集中在省略语、混合语言和缺失上下文。含“Education only”免责声明的违规样本被基线弃判并转人工，因此计入 FN。反诈引用等正常文本也会被保守升级，FPR=0 并不代表没有用户摩擦或人工成本。

## 未验证

没有配置或使用真实 OpenAI key，因此未进行真实模型端到端调用。已用模拟客户端验证 Responses parse 参数、Pydantic 输出类型及拒绝处理；真实服务的模型可用性、延迟、费用与分类质量仍需配置 key 后验证。

申诉改判统计通过隔离测试数据库验证；基线报告中无真实申诉数据，overturn_rate 保持 null。不能将测试中的模拟改判当作线上运营结果。
