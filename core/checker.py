import concurrent.futures
import random
import socket
import threading
import time
import requests

PROXY_HEADERS = ("via", "x-forwarded-for", "forwarded", "proxy-connection", "x-real-ip", "client-ip")
_GEO_CACHE = {}
_GEO_LOCK = threading.Lock()


def get_public_ip(timeout=3):
    for url in ("https://api.ipify.org?format=json", "http://httpbin.org/ip"):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                return data.get("ip") or data.get("origin", "").split(",")[0].strip()
        except Exception:
            continue
    return None


def _lookup_geo(ip_only):
    with _GEO_LOCK:
        if ip_only in _GEO_CACHE:
            return _GEO_CACHE[ip_only]
    country, isp = "??", "Unknown"
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip_only}?fields=status,countryCode,isp",
            timeout=2.0,
        )
        if r.status_code == 200:
            geo = r.json()
            if geo.get("status") == "success":
                country = geo.get("countryCode") or "??"
                isp = (geo.get("isp") or "Unknown")[:28]
    except Exception:
        pass
    with _GEO_LOCK:
        _GEO_CACHE[ip_only] = (country, isp)
    return country, isp


def _build_proxy_map(ip_port, protocol):
    scheme = "http" if protocol in ("http", "https") else protocol.lower()
    uri = f"{scheme}://{ip_port}"
    return {"http": uri, "https": uri}


def check_single_proxy(item, real_ip=None, target_url=None, timeout=4.0, stop_event=None):
    if stop_event and stop_event.is_set():
        return None

    ip_port = item["proxy"]
    protocol = item.get("protocol", "http").lower()
    host, _, port_str = ip_port.partition(":")

    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, int(port_str)), timeout=min(timeout, 2.0)):
            pass
    except Exception:
        return None

    if stop_event and stop_event.is_set():
        return None

    proxies = _build_proxy_map(ip_port, protocol)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/134.0.0.0"}
    probe_url = target_url or "http://httpbin.org/get"
    anonymity = "elite"

    try:
        t1 = time.perf_counter()
        r = requests.get(
            probe_url,
            proxies=proxies,
            headers=headers,
            timeout=(min(timeout, 2.5), timeout),
        )
        if r.status_code >= 400:
            return None
        latency = int((time.perf_counter() - t1) * 1000)

        if "httpbin.org" in probe_url:
            body = r.json()
            origin = body.get("origin", "")
            req_headers = {k.lower(): v for k, v in body.get("headers", {}).items()}
            if real_ip and real_ip in origin:
                anonymity = "transparent"
            elif any(h in req_headers for h in PROXY_HEADERS):
                anonymity = "anonymous"
    except Exception:
        return None

    if stop_event and stop_event.is_set():
        return None

    country, isp = _lookup_geo(host)

    return {
        "proxy": ip_port,
        "protocol": protocol,
        "latency_ms": max(1, latency),
        "anonymity": anonymity,
        "country": country,
        "isp": isp,
        "target": probe_url,
    }


def check_proxies(candidates, target_url=None, max_probe=500, limit=30, concurrency=64, timeout=4.0, on_found=None):
    if not candidates:
        return []

    window = list(candidates[: max(max_probe * 2, 1000)])
    random.shuffle(window)
    sample = window[:max_probe]
    real_ip = get_public_ip()

    working = []
    lock = threading.Lock()
    stop_event = threading.Event()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=concurrency)

    try:
        futures = [
            executor.submit(check_single_proxy, item, real_ip, target_url, timeout, stop_event)
            for item in sample
        ]
        for fut in concurrent.futures.as_completed(futures):
            if stop_event.is_set():
                break
            try:
                res = fut.result()
            except Exception:
                continue
            if not res:
                continue
            with lock:
                if len(working) >= limit:
                    stop_event.set()
                    break
                working.append(res)
                if on_found:
                    on_found(res, len(working))
                if len(working) >= limit:
                    stop_event.set()
                    break
    except KeyboardInterrupt:
        stop_event.set()
        print("\n[!] Stopped early by user (Ctrl+C).")
    finally:
        stop_event.set()
        executor.shutdown(wait=False, cancel_futures=True)

    working.sort(key=lambda x: x["latency_ms"])
    return working


class ProxyPool:

    def __init__(self, proxies=None, protocols=None, target_url=None, min_size=10):
        self._lock = threading.Lock()
        self._protocols = protocols or ["http", "socks5"]
        self._target_url = target_url
        self._min_size = min_size
        self._pool = list(proxies or [])
        self._idx = 0

    def refresh(self, limit=30):
        from core.scraper import fetch_proxies
        raw = fetch_proxies(self._protocols)
        checked = check_proxies(raw, target_url=self._target_url, limit=limit)
        with self._lock:
            self._pool = checked
            self._idx = 0
        return len(self._pool)

    def next_proxy(self):
        with self._lock:
            if not self._pool:
                return None
            item = self._pool[self._idx % len(self._pool)]
            self._idx += 1
            return item

    def remove(self, proxy_addr):
        with self._lock:
            self._pool = [p for p in self._pool if p["proxy"] != proxy_addr]

    def request(self, method, url, retries=3, timeout=8, **kwargs):
        if len(self._pool) < self._min_size and not self._pool:
            self.refresh(limit=max(20, self._min_size))

        last_err = None
        for _ in range(retries):
            item = self.next_proxy()
            if not item:
                break
            proxies = _build_proxy_map(item["proxy"], item.get("protocol", "http"))
            try:
                resp = requests.request(method, url, proxies=proxies, timeout=timeout, **kwargs)
                if resp.status_code < 500:
                    return resp
            except Exception as e:
                last_err = e
                self.remove(item["proxy"])
        if last_err:
            raise last_err
        return requests.request(method, url, timeout=timeout, **kwargs)
