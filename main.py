import argparse
import sys

from core.checker import check_proxies
from core.exporter import export_results
from core.scraper import fetch_proxies, parse_proxy_file


def _print_hit(res, idx):
    print(
        f"[{idx:02d}] {res['protocol'].upper():<6} {res['proxy']:<21} "
        f"{res['latency_ms']:>4}ms  {res['country']:<3}  {res['anonymity']:<11} {res['isp']}"
    )


def build_parser():
    p = argparse.ArgumentParser(
        prog="proxieve",
        description="Concurrent proxy scraper, anonymity classifier, target validator & rotating pool.",
        epilog="Disclaimer: For educational and authorized QA testing only. Provided AS-IS.",
    )
    p.add_argument("-p", "--protocols", nargs="+", default=["http", "socks4", "socks5"], choices=["http", "socks4", "socks5"])
    p.add_argument("-i", "--input", help="Test proxies from a local file instead of scraping")
    p.add_argument("-t", "--target", default="http://httpbin.org/get", help="Target URL to validate against")
    p.add_argument("-n", "--limit", type=int, default=30, help="Stop after finding N working proxies")
    p.add_argument("-m", "--max-probe", type=int, default=600, help="Maximum candidates to probe")
    p.add_argument("-c", "--concurrency", type=int, default=80, help="Worker thread count")
    p.add_argument("--timeout", type=float, default=4.0, help="Socket timeout in seconds")
    p.add_argument("--elite-only", action="store_true", help="Keep only elite (high-anonymity) proxies")
    p.add_argument("-o", "--out-dir", default=None, help="Output directory for exported files")
    return p


def run_cli(args):
    if args.input:
        candidates = parse_proxy_file(args.input)
        print(f"[*] Loaded {len(candidates)} proxies from {args.input}")
    else:
        candidates = fetch_proxies(args.protocols)
        print(f"[*] Scraped {len(candidates)} unique candidates ({', '.join(args.protocols)})")

    print(f"[*] Probing up to {min(len(candidates), args.max_probe)} candidates (concurrency={args.concurrency}, target={args.target})...")
    working = check_proxies(
        candidates,
        target_url=args.target,
        max_probe=args.max_probe,
        limit=args.limit,
        concurrency=args.concurrency,
        timeout=args.timeout,
        on_found=_print_hit,
    )

    if args.elite_only:
        working = [w for w in working if w["anonymity"] == "elite"]

    paths = export_results(working, out_dir=args.out_dir) if args.out_dir else export_results(working)
    print(f"\n[+] Found {len(working)} working proxies.")
    for k, v in paths.items():
        print(f"    {k:<4} -> {v}")
    return 0


def interactive_menu():
    print("proxieve — CLI & SDK")
    print("  [1] Scrape & validate (HTTP / SOCKS4 / SOCKS5)")
    print("  [2] Validate custom target URL")
    print("  [3] Validate local proxy list (.txt)")
    choice = input("\nSelect [1-3] (default 1): ").strip() or "1"

    parser = build_parser()
    if choice == "2":
        target = input("Target URL: ").strip()
        if target and not target.startswith("http"):
            target = "https://" + target
        args = parser.parse_args(["-t", target or "http://httpbin.org/get"])
    elif choice == "3":
        path = input("File path: ").strip().strip('"')
        args = parser.parse_args(["-i", path, "-m", "2000", "-n", "500"])
    else:
        args = parser.parse_args([])

    run_cli(args)


if __name__ == "__main__":
    try:
        parser = build_parser()
        if len(sys.argv) > 1:
            sys.exit(run_cli(parser.parse_args()))
        interactive_menu()
    except KeyboardInterrupt:
        print("\n[!] Exited.")
        sys.exit(130)
