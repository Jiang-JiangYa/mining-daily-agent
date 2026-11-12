"""Deterministic evidence-driven Agent, communicating exclusively through MCP."""
import argparse
import asyncio
import json
import os
import re
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mining_agent.common import today

ROOT = Path(__file__).resolve().parents[1]


def safe(text):
    return re.sub(r'[\r\n]+', ' ', str(text)).replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;')


async def invoke(session, name, arguments):
    result = await asyncio.wait_for(session.call_tool(name, arguments), timeout=90)
    if result.isError:
        raise RuntimeError('; '.join(c.text for c in result.content if c.type == 'text'))
    if result.structuredContent:
        return result.structuredContent
    return json.loads(next(c.text for c in result.content if c.type == 'text'))


async def generate(args):
    trace, failures = [], []
    async with AsyncExitStack() as stack:
        sessions = {}
        for name, module in [('news', 'news'), ('pdf', 'pdf'), ('prices', 'prices')]:
            params = StdioServerParameters(command=sys.executable, args=['-m', f'mining_agent.{module}'], cwd=str(ROOT), env=dict(os.environ, DATA_MODE=args.mode))
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await asyncio.wait_for(session.initialize(), 30)
            sessions[name] = session

        async def call(server, tool, **kwargs):
            try:
                result = await invoke(sessions[server], tool, kwargs)
                trace.append({'server': server, 'tool': tool, 'arguments': kwargs, 'result': result})
                return result
            except Exception as exc:
                failures.append(f'{server}.{tool}: {exc}')
                trace.append({'server': server, 'tool': tool, 'arguments': kwargs, 'error': str(exc)})
                return {}

        # Explicit tool arguments keep article/PDF content out of the control flow.
        query = args.query or ('Pilbara' if 'pilbara' in args.prompt.lower() else args.prompt)
        found = await call('news', 'search', query=query, days=args.days)
        articles = []
        for article in found.get('articles', [])[:5]:
            body = await call('news', 'fetch_article', url=article['url'])
            articles.append(dict(article, body=body.get('text', '正文不可用')))
        pdf_url = args.pdf_url or ('https://example.org/demo/technical-report.pdf' if args.mode == 'demo' else None)
        resources = await call('pdf', 'extract_resources', pdf_url=pdf_url) if pdf_url else {'status': 'abstain', 'reason': '未指定项目技术报告；请用 --pdf-url 提供正式披露 PDF。'}
        price = await call('prices', 'get_price', commodity=args.commodity, date=today().isoformat())
        trend = await call('prices', 'get_trend', commodity=args.commodity, days=args.days)

    lines = [f'# 矿业日报 · {today().isoformat()}', '', f'需求：{safe(args.prompt)}', '', f'数据模式：**{args.mode.upper()}**。覆盖最近 {args.days} 个自然日；仅覆盖已配置来源。', '']
    if args.mode == 'demo':
        lines += ['> 演示数据：新闻、报告资源量和报价均为合成验收样例，不能用于判断 Pilbara 真实情况。', '']
    lines += ['## 新闻摘要', '']
    for article in articles:
        # Extractive synopsis only, never an unsupported LLM conclusion.
        lines += [f"- **{safe(article['title'])}**（{article['published']}）", f"  原文节选：{safe(article['body'][:500])}", f"  来源：{article['url']}"]
    if not articles:
        lines += ['本次检索未获得符合日期和关键词要求的新闻；这不代表没有新闻。']
    lines += ['', '## 矿产资源量', '', f"状态：{resources.get('status', 'unavailable')}；报告标准：{resources.get('standard', '未知')}。", safe(resources.get('reason', '工具未返回结果')), '', 'Indicated / Inferred 属于资源量分类；下列候选尚未核验，不作为储量或项目估值依据。', '']
    for row in resources.get('resources', []):
        lines += [f"- {row['category']} 候选：矿石量 {row['ore']} {row['ore_unit']}；品位 {row['grade']} {row['grade_unit']}；金属量 {row['contained_metal']} {row['metal_unit']}。", f"  第 {row['page']} 页证据：{row['url']}"]
    lines += ['', '## 价格与走势', '', f'品种：{args.commodity}。氢氧化锂、碳酸锂和锂辉石精矿的价格不能互换。', '']
    observation = price.get('observation')
    if observation:
        lines += [f"当日报价：{observation['price']} {observation['currency']}/{observation['unit']}；合约：{safe(observation['instrument'])}。", f"来源：{observation['source_url']}"]
    else:
        lines += ['当日报价不可用：' + safe(price.get('reason', '行情工具失败'))]
    if trend.get('status') == 'ok':
        rows = trend['observations']
        lines += [f"{trend['start_date']} 至 {trend['end_date']}：{rows[0]['price']} → {rows[-1]['price']}，变动 {trend['change_pct']:+.2f}%（{len(rows)} 个观测值）。", f"走势来源：{rows[-1]['source_url']}"]
    else:
        lines += ['走势不可用：' + safe(trend.get('reason', '行情工具失败'))]
    lines += ['', '## 风险提示', '', '- 资源量候选需核对项目名称、报告生效日、JORC/NI 43-101 标准和表格脚注；扫描件需 OCR 或人工审核。', '- 新闻为原文节选，可能遗漏上下文；RSS 覆盖有限，不构成全面尽调。', '- 行情有交易日、延迟、合约及授权限制；商品报价不能直接推导矿山利润。']
    for error in found.get('errors', []):
        failures.append(f"RSS {error['source']}: {error['error']}")
    if failures:
        lines += ['', '## 数据缺口与执行错误', ''] + [f'- {safe(e)}' for e in failures]
    return '\n'.join(lines) + '\n', trace


def main():
    parser = argparse.ArgumentParser(description='通过三个 MCP Server 生成矿业日报')
    parser.add_argument('prompt', nargs='?', default='给我生成一份关于 Pilbara 锂矿的今日简报')
    parser.add_argument('--mode', choices=['demo', 'live'], default=os.getenv('DATA_MODE', 'demo'))
    parser.add_argument('--query', help='RSS 搜索关键词，默认从 Pilbara 请求中提取 Pilbara')
    parser.add_argument('--days', type=int, choices=range(1, 91), default=7)
    parser.add_argument('--commodity', choices=['lithium_hydroxide', 'copper', 'nickel', 'zinc'], default='lithium_hydroxide')
    parser.add_argument('--pdf-url')
    parser.add_argument('--output', default='output/daily-brief.md')
    args = parser.parse_args()
    report, trace = asyncio.run(generate(args))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding='utf-8')
    output.with_suffix('.trace.json').write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'日报已生成：{output.resolve()}')


if __name__ == '__main__':
    main()
