import csv
import math
import os
from datetime import date, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mining_agent.common import ROOT_MODE, today, window

mcp = FastMCP('lme-price-mcp')


def records(commodity):
    allowed = {'lithium_hydroxide', 'copper', 'nickel', 'zinc'}
    if commodity not in allowed:
        raise ValueError(f'commodity must be one of {sorted(allowed)}')
    if ROOT_MODE == 'demo':
        return [{'commodity': commodity, 'date': (today() - timedelta(days=29-i)).isoformat(), 'price': 10000 + i*20, 'currency': 'USD', 'unit': 't', 'instrument': 'SYNTHETIC TEST SERIES', 'source_url': 'https://example.org/demo/prices', 'mode': 'demo'} for i in range(30)]
    path = Path(os.getenv('PRICE_CSV', 'data/prices.csv'))
    if not path.is_file():
        return []
    with path.open(encoding='utf-8-sig', newline='') as file:
        rows = []
        for row in csv.DictReader(file):
            if row['commodity'] != commodity:
                continue
            date.fromisoformat(row['date'])
            row['price'] = float(row['price'])
            if not math.isfinite(row['price']) or row['price'] <= 0 or not all(row.get(k) for k in ('currency', 'unit', 'instrument', 'source_url')):
                raise ValueError('Price must be positive and include instrument, units and source')
            rows.append(dict(row, mode='live'))
        return sorted(rows, key=lambda r: r['date'])


@mcp.tool()
def get_price(commodity: str, date: str) -> dict:
    """Exact-date licensed CSV observation; never substitute a different trading day."""
    from datetime import date as Date
    Date.fromisoformat(date)
    rows = [r for r in records(commodity) if r['date'] == date]
    return {'mode': ROOT_MODE, 'status': 'ok' if len(rows) == 1 else 'unavailable', 'observation': rows[0] if len(rows) == 1 else None, 'reason': '' if len(rows) == 1 else '该日无唯一报价；请配置有授权的行情 CSV，休市日不回填。'}


@mcp.tool()
def get_trend(commodity: str, days: int = 7) -> dict:
    """Compare observations only when instrument, currency and unit agree."""
    cutoff = window(days).isoformat()
    rows = [r for r in records(commodity) if cutoff <= r['date'] <= today().isoformat()]
    keys = {(r['instrument'], r['currency'], r['unit']) for r in rows}
    if len(rows) < 2 or len(keys) != 1 or len({r['date'] for r in rows}) != len(rows):
        return {'mode': ROOT_MODE, 'status': 'unavailable', 'observations': rows, 'change_pct': None, 'reason': '至少需要两个日期唯一且合约、币种、单位相同的报价。'}
    return {'mode': ROOT_MODE, 'status': 'ok', 'observations': rows, 'change_pct': round((rows[-1]['price']/rows[0]['price']-1)*100, 2), 'start_date': rows[0]['date'], 'end_date': rows[-1]['date']}


if __name__ == '__main__':
    mcp.run(transport='stdio')
