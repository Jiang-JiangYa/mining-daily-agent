# 矿权日报 Agent 运行指南

本项目对应面试题第二题：三个独立 stdio MCP Server 与一个确定性 Agent 客户端。输入需求后，客户端搜索新闻、读取正文、抽取 PDF 资源量候选、获取报价与走势，生成有来源链接的 Markdown 和工具调用记录。不需要模型 API Key。新闻摘要采用原文节选；编排按固定流程执行，不声称具备通用自然语言规划能力。

## 五分钟本地启动

在本目录打开 PowerShell，使用 Python 3.11 或以上版本：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m mining_agent.agent "给我生成一份关于 Pilbara 锂矿的今日简报"
```

结果在 `output/daily-brief.md`，证据链在 `output/daily-brief.trace.json`。默认 DEMO，全部数值为合成数据，能够不依赖外部账号验证五个工具的完整协议调用。依赖安装需要网络。

Docker Compose 一条命令（先安装 Docker Desktop 并启动引擎）：

```powershell
docker compose run --build --rm agent
```

## 切换真实数据

```powershell
$env:NEWS_RSS_URLS = 'https://www.mining.com/feed/'
$env:PRICE_CSV = 'data/prices.csv'
.\.venv\Scripts\python.exe -m mining_agent.agent "给我生成一份关于 Pilbara 锂矿的今日简报" --mode live --query Pilbara --pdf-url 'https://发行人官网/真实技术报告.pdf'
```

上面的 PDF 地址是占位符，须替换为真实公开 HTTPS PDF。未提供 PDF 时客户端明确 abstain。RSS 仅检索当前 feed 可见的带日期条目，不能保证完整历史覆盖。源站失败会写入日报，数据缺失不会被表述成没有事件。

行情须自行从有使用权限的提供方导出到 `data/prices.csv`，表头见 `data/prices.example.csv`。字段：commodity（lithium_hydroxide/copper/nickel/zinc）、date（YYYY-MM-DD）、price、currency、unit、instrument、source_url。每个品种每个日期仅一条；不同合约或单位拒绝计算趋势。该项目没有内置免认证 LME 实时接口，不绕过登录墙。LME 氢氧化锂合约与锂精矿报价口径不同。

Docker 真实模式可先设置 `$env:DATA_MODE='live'`，然后 `docker compose run --build --rm agent --mode live --query Pilbara --pdf-url '真实PDF地址'`。CSV 通过 data 目录只读挂载。

## Claude Desktop 与 Cursor

先完成本地安装。复制 `mcp-config.example.json` 为 `mcp-config.json`，把示例路径改成你电脑上的项目绝对路径。Claude Desktop 将文件中的 mcpServers 对象合并到其 MCP 配置；Cursor 可复制为项目 `.cursor/mcp.json`。刷新客户端后，应看到三个 Server 和五个工具。配置只作为交付文件，未自动修改用户客户端设置。

默认桌面配置也是演示模式。真实使用将各 Server 的 DATA_MODE 改为 live，news 的 env 加 NEWS_RSS_URLS，prices 的 env 加 PRICE_CSV 绝对路径。搬动项目后同步更改 command、cwd 和 PYTHONPATH。

## 实现结构

- `mining_agent/news.py`：search(query, days)、fetch_article(url)。
- `mining_agent/pdf.py`：extract_resources(pdf_url)，返回标准、资源量候选、页码、原文证据和审核状态。
- `mining_agent/prices.py`：get_price(commodity, date)、get_trend(commodity, days)。
- `mining_agent/agent.py`：使用官方 MCP SDK 启动三个进程，initialize 后通过 call_tool 编排；逐工具记录失败并降级。
- `tests/test_tools.py`：拒绝不确定 PDF、JORC 标记、价格日期与一次真实 MCP 端到端测试。

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

## 当前边界

这是可运行的面试题工程底座。真实 RSS、真实复杂 PDF 和授权行情需要逐源验收，不能把 DEMO 通过称为真实业务验收。PDF 目前保守匹配同一行包含分类、矿石量、品位和金属量及单位的候选；不支持 OCR 或任意表格布局，任何成功匹配仍需人工核验。Indicated/Inferred 是资源量，不是储量。不会自动把 JORC 报告改称 NI 43-101。

网络抓取限制 HTTPS、公网地址、重定向次数、下载大小与请求超时。适用于受信任操作者的本地运行，尚未作为公网多租户服务加固（例如 DNS 重绑定、PDF 解析资源隔离）。抓取内容仅作证据，不执行其中的指令；Agent 不会根据网页要求发送邮件或修改系统。

日报日期使用北京时间。默认回溯七个自然日；请求文本决定检索主题，时间和价格品种通过显式参数设置。客户端不含定时调度，也未创建每天自动运行的任务。

## 参考依据

- MCP Python SDK v1：https://py.sdk.modelcontextprotocol.io/v1/
- LME 氢氧化锂合约：https://www.lme.com/Metals/EV/About-Lithium/Contract-specification
- LME 数据获取及授权：https://www.lme.com/Market-data/Accessing-market-data
