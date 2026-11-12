import io
import re

from mcp.server.fastmcp import FastMCP
from pypdf import PdfReader

from mining_agent.common import ROOT_MODE, download

mcp = FastMCP('mineral-pdf-mcp')
DEMO_URL = 'https://example.org/demo/technical-report.pdf'


def parse_pages(pages, url):
    """Conservative table-row extractor; ambiguous/multi-line tables abstain."""
    joined = '\n'.join(pages)
    standard = 'NI 43-101' if re.search(r'NI\s*43[-–]101', joined, re.I) else ('JORC' if 'JORC' in joined.upper() else 'unknown')
    rows, evidence = [], []
    # Require category, tonnes unit, grade unit and contained-metal unit on one row.
    pattern = re.compile(r'\b(Indicated|Inferred)\s+([\d,.]+)\s*(Mt|kt|t)\s+([\d,.]+)\s*(%\s*(?:Li2O|Cu)|g/t\s*Au)\s+([\d,.]+)\s*(Moz|koz|oz|kt|t)\b', re.I)
    for page, text in enumerate(pages, 1):
        for line in text.splitlines():
            if re.search(r'\b(indicated|inferred)\b', line, re.I):
                evidence.append({'page': page, 'text': line[:700], 'url': f'{url}#page={page}'})
            match = pattern.search(line)
            if match:
                category, tonnage, mass_unit, grade, grade_unit, metal, metal_unit = match.groups()
                rows.append({'category': category.title(), 'ore': float(tonnage.replace(',', '')), 'ore_unit': mass_unit, 'grade': float(grade.replace(',', '')), 'grade_unit': grade_unit, 'contained_metal': float(metal.replace(',', '')), 'metal_unit': metal_unit, 'page': page, 'evidence': line, 'url': f'{url}#page={page}'})
    categories = {r['category'] for r in rows}
    complete = categories == {'Indicated', 'Inferred'} and len(rows) == 2 and standard != 'unknown'
    return {'status': 'needs_review' if complete else 'abstain', 'standard': standard, 'resources': rows, 'evidence': evidence[:30], 'url': url, 'reason': '规则匹配候选，尚未核验项目、有效日期、表头及金属量口径；须人工审核。' if complete else '未获得唯一且完整的两类资源行；可能为扫描件、跨行表格或口径不明，拒绝补数。', 'terminology': 'Indicated/Inferred 是矿产资源量分类，不能称为已证实或概略储量。'}


@mcp.tool()
def extract_resources(pdf_url: str) -> dict:
    """Extract resource candidates with page evidence; abstain on uncertain PDFs."""
    if ROOT_MODE == 'demo':
        if pdf_url != DEMO_URL:
            raise ValueError('Demo mode only supports its fixture URL')
        result = parse_pages(['SYNTHETIC NI 43-101 TEST FIXTURE\nIndicated 100 Mt 1.2 % Li2O 1200000 t\nInferred 20 Mt 1.0 % Li2O 200000 t'], pdf_url)
        return dict(result, mode='demo', synthetic=True)
    data = download(pdf_url)
    if not data.startswith(b'%PDF-'):
        raise ValueError('Response is not a PDF')
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted or len(reader.pages) > 500:
        raise ValueError('Encrypted or oversized PDF is unsupported')
    return dict(parse_pages([p.extract_text() or '' for p in reader.pages], pdf_url), mode='live')


if __name__ == '__main__':
    mcp.run(transport='stdio')
