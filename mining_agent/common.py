import ipaddress
import os
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

ROOT_MODE = os.getenv('DATA_MODE', 'demo')


def today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def window(days):
    if not 1 <= days <= 90:
        raise ValueError('days must be between 1 and 90')
    return today() - timedelta(days=days - 1)


def download(url, limit=12_000_000):
    """Public HTTPS only; validate every redirect, bound response size and time."""
    with httpx.Client(timeout=25, follow_redirects=False, trust_env=False) as client:
        for _ in range(4):
            parsed = urlparse(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
                raise ValueError('Only public HTTPS URLs on port 443 are allowed')
            ips = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
            if not ips or any(not ipaddress.ip_address(item[4][0]).is_global for item in ips):
                raise ValueError('Private/local network addresses are forbidden')
            with client.stream('GET', url, headers={'User-Agent': 'MineralDailyResearch/0.1'}) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin
                    url = urljoin(url, response.headers['location'])
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > limit:
                        raise ValueError('Download exceeds size limit')
                return bytes(data)
    raise ValueError('Too many redirects')
