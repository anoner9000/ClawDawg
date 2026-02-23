#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip > 0:
            return
        txt = data.strip()
        if txt:
            self._parts.append(txt)

    def text(self) -> str:
        merged = "\n".join(self._parts)
        merged = html.unescape(merged)
        merged = re.sub(r"[ \t]+", " ", merged)
        merged = re.sub(r"\n{3,}", "\n\n", merged)
        return merged.strip()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_slug(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    out = out.strip("-")
    return out or "source"


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def enforce_allowed_domain(url: str, allowed_domains: list[str]) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if not host:
        return False
    for d in allowed_domains:
        d = d.lower().strip()
        if not d:
            continue
        if host == d or host.endswith("." + d):
            return True
    return False


def fetch_url(url: str, timeout_s: int) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenClaw-Rembrandt-Corpus/1.0 (+local-cache)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        code = int(getattr(resp, "status", 200))
        ctype = str(resp.headers.get("Content-Type", ""))
        data = resp.read()
    return code, data, ctype


def build(args: argparse.Namespace) -> int:
    manifest_path = Path(args.sources).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    raw_dir = out_root / "raw"
    text_dir = out_root / "text"
    meta_dir = out_root / "meta"
    index_path = out_root / "index.jsonl"
    summary_path = out_root / "LATEST_SNAPSHOT.md"

    manifest = load_manifest(manifest_path)
    allowed_domains = list(manifest.get("allowed_domains", []))
    sources = list(manifest.get("sources", []))
    if args.limit is not None:
        sources = sources[: max(0, args.limit)]

    for d in (raw_dir, text_dir, meta_dir):
        d.mkdir(parents=True, exist_ok=True)

    index_rows: list[dict] = []
    ok_count = 0
    err_count = 0
    ts = utc_now()

    for src in sources:
        src_id = safe_slug(str(src.get("id", "")))
        url = str(src.get("url", "")).strip()
        topic = str(src.get("topic", "")).strip()
        if not src_id or not url:
            continue

        row: dict[str, object] = {
            "id": src_id,
            "url": url,
            "topic": topic,
            "fetched_at": ts,
            "ok": False,
        }

        if not enforce_allowed_domain(url, allowed_domains):
            row["error"] = "domain_not_allowed"
            err_count += 1
            index_rows.append(row)
            (meta_dir / f"{src_id}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            continue

        try:
            code, raw_bytes, ctype = fetch_url(url, timeout_s=args.timeout)
            raw_html = raw_bytes.decode("utf-8", errors="replace")
            extractor = TextExtractor()
            extractor.feed(raw_html)
            text = extractor.text()
            digest = hashlib.sha256(raw_bytes).hexdigest()

            (raw_dir / f"{src_id}.html").write_text(raw_html, encoding="utf-8")
            (text_dir / f"{src_id}.txt").write_text(text, encoding="utf-8")

            row.update(
                {
                    "ok": True,
                    "status_code": code,
                    "content_type": ctype,
                    "bytes": len(raw_bytes),
                    "sha256": digest,
                    "raw_path": str((raw_dir / f"{src_id}.html").relative_to(out_root.parent)),
                    "text_path": str((text_dir / f"{src_id}.txt").relative_to(out_root.parent)),
                    "meta_path": str((meta_dir / f"{src_id}.json").relative_to(out_root.parent)),
                }
            )
            ok_count += 1
        except urllib.error.HTTPError as e:
            row["error"] = f"http_{e.code}"
            err_count += 1
        except Exception as e:  # pragma: no cover - defensive for network/runtime differences
            row["error"] = f"fetch_error:{type(e).__name__}"
            row["detail"] = str(e)[:200]
            err_count += 1

        index_rows.append(row)
        (meta_dir / f"{src_id}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")

    with index_path.open("w", encoding="utf-8") as f:
        for row in index_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = [
        "# Rembrandt Corpus Snapshot",
        "",
        f"- built_at: {ts}",
        f"- sources_total: {len(index_rows)}",
        f"- sources_ok: {ok_count}",
        f"- sources_error: {err_count}",
        f"- index: {index_path}",
        "",
        "## Errors",
    ]
    any_err = False
    for row in index_rows:
        if row.get("ok"):
            continue
        any_err = True
        summary.append(f"- {row.get('id')}: {row.get('error', 'unknown_error')}")
    if not any_err:
        summary.append("- none")

    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(f"[rembrandt-corpus] built={ts} total={len(index_rows)} ok={ok_count} err={err_count}")
    print(f"[rembrandt-corpus] index={index_path}")
    print(f"[rembrandt-corpus] summary={summary_path}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build governed local design corpus for Rembrandt.")
    p.add_argument(
        "--sources",
        default="docs/design/corpus/sources.json",
        help="Path to source manifest JSON.",
    )
    p.add_argument(
        "--out",
        default="docs/design/corpus",
        help="Output corpus directory.",
    )
    p.add_argument("--timeout", type=int, default=20, help="Fetch timeout seconds per source.")
    p.add_argument("--limit", type=int, default=None, help="Optional max number of sources.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return build(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
