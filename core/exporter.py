import csv
import json
import os

DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")


def export_results(items, out_dir=DEFAULT_OUT_DIR, prefix="proxies"):
    os.makedirs(out_dir, exist_ok=True)
    raw_path = os.path.join(out_dir, f"{prefix}.txt")
    uri_path = os.path.join(out_dir, f"{prefix}_uri.txt")
    json_path = os.path.join(out_dir, f"{prefix}.json")
    csv_path = os.path.join(out_dir, f"{prefix}.csv")

    with open(raw_path, "w", encoding="utf-8") as f:
        for p in items:
            f.write(f"{p['proxy']}\n")

    with open(uri_path, "w", encoding="utf-8") as f:
        for p in items:
            f.write(f"{p['protocol']}://{p['proxy']}\n")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    fields = ["proxy", "protocol", "latency_ms", "anonymity", "country", "isp", "target"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in items:
            writer.writerow({k: p.get(k, "") for k in fields})

    return {
        "txt": raw_path,
        "uri": uri_path,
        "json": json_path,
        "csv": csv_path,
    }
