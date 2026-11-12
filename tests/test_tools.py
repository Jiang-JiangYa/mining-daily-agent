import asyncio
import os
from argparse import Namespace

os.environ['DATA_MODE'] = 'demo'

from mining_agent.agent import generate
from mining_agent.pdf import parse_pages
from mining_agent.prices import get_price, get_trend
from mining_agent.news import search


def test_uncertain_pdf_abstains():
    result = parse_pages(['NI 43-101\nIndicated 100\nInferred unavailable'], 'https://example.org/report.pdf')
    assert result['status'] == 'abstain'
    assert not result['resources']


def test_candidate_is_never_approved():
    result = parse_pages(['JORC\nIndicated 10 Mt 1 % Li2O 100000 t\nInferred 5 Mt 1 % Li2O 50000 t'], 'https://example.org/report.pdf')
    assert result['standard'] == 'JORC'
    assert result['status'] == 'needs_review'
    assert result['resources'][0]['page'] == 1


def test_exact_date_no_backfill():
    assert get_price('lithium_hydroxide', '2000-01-01')['status'] == 'unavailable'
    assert get_trend('lithium_hydroxide', 7)['change_pct'] > 0


def test_no_irrelevant_demo_news():
    assert not search('unrelated query', 7)['articles']


def test_live_price_contract_mismatch(tmp_path, monkeypatch):
    import mining_agent.prices as prices
    from mining_agent.common import today
    from datetime import timedelta
    path = tmp_path / 'prices.csv'
    path.write_text('commodity,date,price,currency,unit,instrument,source_url\n'
                    f'copper,{today()-timedelta(days=1)},100,USD,t,cash,https://example.org/a\n'
                    f'copper,{today()},110,USD,t,3-month,https://example.org/b\n', encoding='utf-8')
    monkeypatch.setattr(prices, 'ROOT_MODE', 'live')
    monkeypatch.setenv('PRICE_CSV', str(path))
    assert prices.get_trend('copper', 7)['status'] == 'unavailable'


def test_live_price_missing_is_not_demo(tmp_path, monkeypatch):
    import mining_agent.prices as prices
    monkeypatch.setattr(prices, 'ROOT_MODE', 'live')
    monkeypatch.setenv('PRICE_CSV', str(tmp_path / 'missing.csv'))
    result = prices.get_price('copper', '2026-10-19')
    assert result['mode'] == 'live'
    assert result['observation'] is None


def test_real_mcp_roundtrip():
    args = Namespace(mode='demo', query=None, prompt='Pilbara 今日简报', days=7, pdf_url=None, commodity='lithium_hydroxide')
    report, trace = asyncio.run(generate(args))
    assert {t['tool'] for t in trace} == {'search', 'fetch_article', 'extract_resources', 'get_price', 'get_trend'}
    assert all('error' not in t for t in trace)
    assert '演示数据' in report and 'needs_review' in report
