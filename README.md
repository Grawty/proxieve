# proxieve

Concurrent proxy scraper, anonymity classifier (`elite` / `anonymous` / `transparent`), target validator, and self-healing `ProxyPool` for Python.

## Features

- **Multi-Protocol Scraper**: Scrapes and deduplicates `HTTP`, `SOCKS4`, and `SOCKS5` proxies concurrently.
- **Anonymity & GeoIP Classification**: Detects header leaks (`Via`, `X-Forwarded-For`, `Forwarded`), origin IP exposure, latency (`ms`), country code, and ASN/ISP.
- **Target-Specific Probing**: Validates proxies directly against any target URL (`-t https://api.spotify.com`, `-t https://github.com`, etc.).
- **Developer SDK (`ProxyPool`)**: Drop-in rotating `requests` wrapper that automatically evicts dead proxies and replenishes the pool when depleted.

## CLI Usage

```bash
pip install -r requirements.txt

# Scrape and find 30 working proxies across HTTP/SOCKS4/SOCKS5
python main.py -n 30 -c 64

# Validate only SOCKS5 elite proxies against a custom target
python main.py -p socks5 -t https://www.google.com --elite-only -n 20

# Validate an existing proxy list
python main.py -i my_proxies.txt -m 1000 -n 200
```

## Library Usage (`ProxyPool`)

```python
from core import ProxyPool

pool = ProxyPool(protocols=["http", "socks5"], min_size=10)
pool.refresh(limit=20)

# Automatically rotates proxies and drops dead nodes on failure
resp = pool.request("GET", "https://httpbin.org/ip")
print(resp.json())
```

## Output Files (`output/`)

- `proxies.txt`: Raw `ip:port` list
- `proxies_uri.txt`: Protocol-prefixed `protocol://ip:port` list
- `proxies.json`: Full metadata (`latency_ms`, `anonymity`, `country`, `isp`)
- `proxies.csv`: CSV table

## Disclaimer

For educational, QA testing, and authorized network research only. Provided "AS IS" under the [MIT License](LICENSE); the author assumes no liability for misuse or third-party ToS violations.

