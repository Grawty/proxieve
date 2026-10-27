import concurrent.futures
import random
import re
import requests

SOURCES = {
    "http": [
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
        "https://vakhov.github.io/fresh-proxy-list/http.txt",
        "https://vakhov.github.io/fresh-proxy-list/https.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    ],
    "socks4": [
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.txt",
        "https://vakhov.github.io/fresh-proxy-list/socks4.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=5000&country=all",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks4/global/socks4_checked.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    ],
    "socks5": [
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
        "https://vakhov.github.io/fresh-proxy-list/socks5.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=all",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    ],
}

IP_PORT_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?):\d{2,5}\b"
)


def _fetch_source(url, protocol, timeout=6):
    try:
        r = requests.get(url, headers={"User-Agent": "proxieve/2.0"}, timeout=timeout)
        if r.status_code == 200 and r.text:
            matches = [(match, protocol) for match in IP_PORT_RE.findall(r.text)]
            random.shuffle(matches)
            return matches
    except Exception:
        pass
    return []


def parse_proxy_file(filepath, default_protocol="http"):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()
    seen = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        proto = default_protocol
        for p in ("socks5", "socks4", "https", "http"):
            if line.lower().startswith(f"{p}://"):
                proto = "http" if p == "https" else p
                break
        m = IP_PORT_RE.search(line)
        if m and m.group(0) not in seen:
            seen[m.group(0)] = {"proxy": m.group(0), "protocol": proto}
    return list(seen.values())


def fetch_proxies(protocols=None, extra_urls=None, workers=16):
    protocols = [p.lower() for p in (protocols or ["http", "socks4", "socks5"])]
    tasks = []
    max_len = max((len(SOURCES.get(p, [])) for p in protocols), default=0)
    for i in range(max_len):
        for proto in protocols:
            urls = SOURCES.get(proto, [])
            if i < len(urls):
                tasks.append((urls[i], proto))
    for url in (extra_urls or []):
        tasks.append((url, protocols[0] if protocols else "http"))

    buckets = []
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [executor.submit(_fetch_source, url, proto) for url, proto in tasks]
        for fut in futures:
            try:
                res = fut.result(timeout=8)
                if res:
                    buckets.append(res)
            except Exception:
                pass
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    unique = {}
    max_bucket = max((len(b) for b in buckets), default=0)
    for idx in range(max_bucket):
        for b in buckets:
            if idx < len(b):
                ip_port, proto = b[idx]
                if ip_port not in unique:
                    unique[ip_port] = {"proxy": ip_port, "protocol": proto}
    return list(unique.values())
