"""Download the raw traces in configs/data.yaml into data/raw/ and write MANIFEST.json. Tier B.

Existing trace files are never modified: if one is present it is only read (hashed and counted).
Exit code is non-zero on a checksum mismatch or a failed download.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "configs" / "data.yaml"
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def to_seconds(value: str, kind: str) -> float:
    if kind == "seconds":
        return float(value)
    # Azure stamps carry 7 fractional digits; datetime accepts at most 6.
    value = re.sub(r"(\.\d{6})\d+", r"\1", value.strip())
    return datetime.fromisoformat(value).timestamp()


def file_stats(path: Path, src: dict) -> dict:
    """One pass over the CSV: row count (header excluded), columns, first/last timestamp."""
    kind = src["timestamp_kind"]
    sid_col = src.get("session_id_column")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        columns = next(reader)
        ts_i = columns.index(src["timestamp_column"])
        sid_i = columns.index(sid_col) if sid_col else None
        rows = sid_non_empty = 0
        first = last = None
        prev = None
        sorted_ok = True
        for row in tqdm(reader, desc=f"scan {path.name}", unit="row", leave=False):
            if not row:
                continue
            rows += 1
            ts = row[ts_i]
            first = ts if first is None else first
            last = ts
            t = to_seconds(ts, kind)
            if prev is not None and t < prev:
                sorted_ok = False
            prev = t
            if sid_i is not None and row[sid_i].strip():
                sid_non_empty += 1
    stats = {
        "rows": rows,
        "columns": columns,
        "first_timestamp": first,
        "last_timestamp": last,
        "timestamps_non_decreasing": sorted_ok,
        "span_seconds": to_seconds(last, kind) - to_seconds(first, kind) if rows else None,
    }
    if sid_i is not None:
        stats["session_id_non_empty"] = sid_non_empty
        stats["session_id_fraction"] = sid_non_empty / rows if rows else None
    return stats


def remote_size(client: httpx.Client, url: str) -> int | None:
    try:
        r = client.head(url, follow_redirects=True)
        r.raise_for_status()
        return int(r.headers["content-length"])
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def download(client: httpx.Client, url: str, dest: Path) -> None:
    """Stream to <dest>.part (resuming with a Range request), then rename."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={have}-"} if have else {}
    with client.stream("GET", url, headers=headers, follow_redirects=True) as r:
        r.raise_for_status()
        if have and r.status_code != 206:  # server ignored Range: start over
            have = 0
        total = r.headers.get("content-length")
        total = int(total) + have if total else None
        with (
            part.open("ab" if have else "wb") as f,
            tqdm(total=total, initial=have, unit="B", unit_scale=True, desc=dest.name) as bar,
        ):
            for chunk in r.iter_bytes(CHUNK):
                f.write(chunk)
                bar.update(len(chunk))
    part.rename(dest)


def human(n: int | None) -> str:
    return "unknown" if n is None else f"{n / 1e6:.1f} MB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="source name from configs/data.yaml")
    ap.add_argument("--dry-run", action="store_true", help="print planned downloads and sizes")
    args = ap.parse_args()

    cfg = yaml.safe_load(CONFIG.read_text())
    raw_dir = ROOT / cfg["raw_dir"]
    manifest_path = raw_dir / "MANIFEST.json"
    sources = [s for s in cfg["sources"] if args.only in (None, s["name"])]
    if not sources:
        print(f"no source named {args.only!r}", file=sys.stderr)
        return 2

    if args.dry_run:
        with httpx.Client(timeout=30) as client:
            for s in sources:
                state = "present" if (raw_dir / s["filename"]).exists() else "to download"
                size = human(remote_size(client, s["url"]))
                print(f"{s['name']:18} {s['filename']:32} {size:>10}  [{state}]  {s['url']}")
        return 0

    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    status = 0
    with httpx.Client(timeout=60) as client:
        for s in sources:
            dest = raw_dir / s["filename"]
            expected = s.get("sha256") or manifest.get(s["name"], {}).get("sha256")
            fresh = not dest.exists()
            if fresh:
                try:
                    download(client, s["url"], dest)
                except httpx.HTTPError as e:
                    print(f"{s['name']}: download failed: {e}", file=sys.stderr)
                    status = 1
                    continue
            digest = sha256_of(dest)
            if expected and digest != expected:
                print(
                    f"{s['name']}: CHECKSUM MISMATCH\n  expected {expected}\n  got      {digest}",
                    file=sys.stderr,
                )
                status = 1
                continue
            manifest[s["name"]] = {
                "filename": s["filename"],
                "url": s["url"],
                "release": s["release"],
                "licence": s["licence"],
                "source_page": s["source_page"],
                "sha256": digest,
                "size_bytes": dest.stat().st_size,
                **file_stats(dest, s),
            }
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    entries = [manifest[s["name"]] | {"name": s["name"]} for s in sources if s["name"] in manifest]
    print(f"\n{'name':18} {'bytes':>12} {'rows':>10}  {'sha256':14} first -> last timestamp")
    for e in entries:
        print(
            f"{e['name']:18} {e['size_bytes']:>12} {e['rows']:>10}  {e['sha256'][:12]:14} "
            f"{e['first_timestamp']} -> {e['last_timestamp']}"
        )
        print(f"{'':18} columns: {', '.join(e['columns'])}")
        if not e["timestamps_non_decreasing"]:
            print(f"{'':18} note: timestamps are not non-decreasing in file order")
        if e["name"].startswith("azure"):
            span = e["span_seconds"]
            print(f"{'':18} time span: {span:.3f} s ({span / 3600:.3f} h)")
        if "session_id_non_empty" in e:
            print(
                f"{'':18} non-empty Session ID: {e['session_id_non_empty']} of {e['rows']} "
                f"({e['session_id_fraction']:.4%})"
            )
    return status


if __name__ == "__main__":
    sys.exit(main())
