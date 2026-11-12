# 矿业日报Agent

按面试题第二题搭建：3 个 MCP Server、5 个工具、1 个 MCP 客户端，输出 Markdown 简报与 JSON 调用证据。

请先阅读 [RUN.md](RUN.md)。默认运行演示数据；真实数据模式需要公开 PDF 和有使用权限的行情 CSV。

```powershell
.\.venv\Scripts\python.exe -m mining_agent.agent "给我生成一份关于 Pilbara 锂矿的今日简报"
```

流程：用户主题 → 新闻搜索及正文 → PDF 资源量候选 → 当日行情及趋势 → 引用与风险 → output/daily-brief.md。

这版是确定性工作流 Agent，不依赖 LLM；对复杂 PDF 保守拒答，不将示例数据作为真实矿业信息。
