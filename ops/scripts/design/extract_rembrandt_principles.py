#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


PRINCIPLE_HINTS = {
    "must",
    "should",
    "avoid",
    "prefer",
    "ensure",
    "never",
    "always",
    "contrast",
    "accessible",
    "accessibility",
    "focus",
    "typography",
    "color",
    "spacing",
    "layout",
    "hierarchy",
    "responsive",
    "motion",
    "animation",
    "readable",
    "consistency",
}

ACTION_HINTS = {
    "must",
    "should",
    "avoid",
    "prefer",
    "ensure",
    "never",
    "always",
    "use",
    "provide",
    "maintain",
    "keep",
}

DOMAIN_HINTS = {
    "contrast",
    "accessibility",
    "accessible",
    "focus",
    "typography",
    "color",
    "spacing",
    "layout",
    "hierarchy",
    "responsive",
    "motion",
    "animation",
    "readable",
    "keyboard",
    "wcag",
}

FLUFF_HINTS = {
    "sign in",
    "log in",
    "cookie",
    "newsletter",
    "advert",
    "sponsor",
    "skip to main content",
    "table of contents",
    "copyright",
    "all rights reserved",
    "save and categorize content",
    "course",
    "round-up",
    "overview of",
    "to see the code",
    "converter below",
    "we want to help you",
    "article explains",
}

TOPIC_REPLACEMENTS = {
    "accessibility": [
        "https://www.w3.org/WAI/fundamentals/accessibility-intro/",
        "https://web.dev/learn/accessibility/test-automate",
    ],
    "typography": [
        "https://web.dev/articles/font-best-practices",
        "https://developer.mozilla.org/en-US/docs/Web/CSS/font",
    ],
    "color": [
        "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Colors_and_Luminance",
        "https://web.dev/articles/color-and-contrast-accessibility",
    ],
    "motion": [
        "https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion",
        "https://web.dev/articles/animations-guide",
    ],
    "layout": [
        "https://web.dev/learn/design/box-model",
        "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout",
    ],
    "design-system": [
        "https://web.dev/learn/design/",
        "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Design_for_developers",
    ],
    "css": [
        "https://developer.mozilla.org/en-US/docs/Web/CSS/Reference",
        "https://web.dev/learn/css",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sentence_chunks(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+|\n+", text)
    out: list[str] = []
    for chunk in raw:
        s = re.sub(r"\s+", " ", chunk).strip(" -\t")
        if s:
            out.append(s)
    return out


def is_fluff(s: str) -> bool:
    l = s.lower()
    return any(tok in l for tok in FLUFF_HINTS)


def score_sentence(s: str) -> int:
    l = s.lower()
    score = 0
    if len(s) < 55 or len(s) > 240:
        return -10
    has_action = any(a in l for a in ACTION_HINTS)
    has_domain = any(d in l for d in DOMAIN_HINTS)
    has_wcag_ratio = bool(re.search(r"\b\d+(\.\d+)?\s*:\s*1\b", l))
    if not (has_wcag_ratio or (has_action and has_domain)):
        return -8
    for h in PRINCIPLE_HINTS:
        if h in l:
            score += 2
    if has_wcag_ratio:
        score += 3
    if "for example" in l or "e.g." in l:
        score += 1
    if is_fluff(s):
        score -= 20
    return score


def normalize_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def extract_principles(text: str, max_items: int) -> list[str]:
    seen: set[str] = set()
    ranked: list[tuple[int, str]] = []
    for s in sentence_chunks(text):
        score = score_sentence(s)
        if score <= 0:
            continue
        key = normalize_key(s)
        if not key or key in seen:
            continue
        seen.add(key)
        ranked.append((score, s))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in ranked[:max_items]]


def load_index(index_path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
        t = line.strip()
        if not t:
            continue
        try:
            obj = json.loads(t)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def build(args: argparse.Namespace) -> int:
    root = Path(args.corpus).expanduser().resolve()
    index_path = root / "index.jsonl"
    text_dir = root / "text"
    out_dir = root / "principles"
    out_dir.mkdir(parents=True, exist_ok=True)
    principles_index_path = root / "principles_index.jsonl"
    snapshot_path = root / "PRINCIPLES_SNAPSHOT.md"
    weak_report_md = root / "WEAK_SOURCES.md"
    weak_report_json = root / "weak_sources.json"
    citations_md = root / "PRINCIPLES_CITATIONS.md"

    if not index_path.exists():
        print(f"missing index: {index_path}", file=sys.stderr)
        return 1

    rows = load_index(index_path)
    now = utc_now()
    out_rows: list[dict] = []
    weak_rows: list[dict] = []
    ok = 0
    for row in rows:
        if not row.get("ok"):
            continue
        src_id = str(row.get("id", "")).strip()
        if not src_id:
            continue
        text_path = text_dir / f"{src_id}.txt"
        if not text_path.exists():
            continue
        text = text_path.read_text(encoding="utf-8", errors="replace")
        principles = extract_principles(text, max_items=args.max_per_source)
        accepted = len(principles) >= args.min_principles
        p_path = out_dir / f"{src_id}.md"
        lines = [f"# Principles — {src_id}", "", f"- generated_at: {now}", f"- source_url: {row.get('url','')}", ""]
        for p in principles:
            lines.append(f"- {p}")
        if not principles:
            lines.append("- [no high-signal principles extracted]")
        p_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_row = {
            "id": src_id,
            "topic": row.get("topic", ""),
            "url": row.get("url", ""),
            "source_name": src_id.replace("-", " ").title(),
            "generated_at": now,
            "principles_count": len(principles),
            "principles_path": str(p_path.relative_to(root.parent)),
            "accepted": accepted,
        }
        out_rows.append(out_row)
        ok += 1
        if not accepted:
            topic = str(row.get("topic", "")).strip()
            weak_rows.append(
                {
                    "id": src_id,
                    "topic": topic,
                    "url": row.get("url", ""),
                    "principles_count": len(principles),
                    "min_required": args.min_principles,
                    "replacement_candidates": TOPIC_REPLACEMENTS.get(topic, []),
                }
            )

    with principles_index_path.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    snap = [
        "# Rembrandt Principles Snapshot",
        "",
        f"- generated_at: {now}",
        f"- sources_with_principles: {ok}",
        f"- min_principles_gate: {args.min_principles}",
        f"- accepted_sources: {sum(1 for r in out_rows if r.get('accepted'))}",
        f"- weak_sources: {len(weak_rows)}",
        f"- index: {principles_index_path}",
        "",
        "## Top Principle Files",
    ]
    for row in sorted(out_rows, key=lambda r: int(r.get("principles_count", 0)), reverse=True)[:12]:
        snap.append(f"- {row['id']} ({row['principles_count']}): {row['principles_path']}")
    if not out_rows:
        snap.append("- none")
    snapshot_path.write_text("\n".join(snap) + "\n", encoding="utf-8")

    weak_lines = [
        "# Rembrandt Weak Sources",
        "",
        f"- generated_at: {now}",
        f"- min_principles_gate: {args.min_principles}",
        f"- weak_sources: {len(weak_rows)}",
        "",
        "## Weak Source List",
    ]
    if weak_rows:
        for row in weak_rows:
            weak_lines.append(
                f"- {row['id']} [{row.get('topic','')}]: {row.get('principles_count',0)} principles (< {args.min_principles})"
            )
            weak_lines.append(f"  - current: {row.get('url','')}")
            recs = row.get("replacement_candidates", [])
            if recs:
                for rec in recs:
                    weak_lines.append(f"  - replacement: {rec}")
            else:
                weak_lines.append("  - replacement: [manual review required]")
    else:
        weak_lines.append("- none")
    weak_report_md.write_text("\n".join(weak_lines) + "\n", encoding="utf-8")
    weak_report_json.write_text(json.dumps({"generated_at": now, "min_principles_gate": args.min_principles, "weak_sources": weak_rows}, indent=2), encoding="utf-8")

    citation_lines = [
        "# Rembrandt Principles Citations",
        "",
        "Human-friendly source register for distilled web design principles.",
        "",
        f"- generated_at: {now}",
        "",
        "| Source | Topic | Domain | URL | Principles File | Status |",
        "|---|---|---|---|---|---|",
    ]
    for row in sorted(out_rows, key=lambda r: str(r.get("id", ""))):
        url = str(row.get("url", ""))
        m = re.match(r"^https?://([^/]+)/?", url)
        domain = m.group(1) if m else "unknown"
        status = "accepted" if row.get("accepted") else "weak"
        citation_lines.append(
            f"| {row.get('source_name','')} | {row.get('topic','')} | {domain} | {url} | `{row.get('principles_path','')}` | {status} |"
        )
    if not out_rows:
        citation_lines.append("| none | n/a | n/a | n/a | n/a | n/a |")
    citations_md.write_text("\n".join(citation_lines) + "\n", encoding="utf-8")

    print(f"[rembrandt-principles] generated={now} sources={ok}")
    print(f"[rembrandt-principles] index={principles_index_path}")
    print(f"[rembrandt-principles] snapshot={snapshot_path}")
    print(f"[rembrandt-principles] weak_md={weak_report_md}")
    print(f"[rembrandt-principles] weak_json={weak_report_json}")
    print(f"[rembrandt-principles] citations={citations_md}")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract high-signal design principles from Rembrandt corpus text.")
    p.add_argument("--corpus", default="docs/design/corpus", help="Corpus root directory.")
    p.add_argument("--max-per-source", type=int, default=32, help="Max principles per source file.")
    p.add_argument("--min-principles", type=int, default=2, help="Minimum principles required for a source to be accepted.")
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    return build(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
