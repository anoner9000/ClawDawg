# Rembrandt Corpus

This directory stores the governed local cache of approved online design references.

## Layout
- `sources.json` — allowlisted source manifest
- `raw/` — fetched raw HTML
- `text/` — normalized extracted text
- `meta/` — per-source fetch metadata
- `index.jsonl` — corpus index
- `LATEST_SNAPSHOT.md` — latest build summary
- `principles/` — distilled high-signal principles by source
- `principles_index.jsonl` — principles index
- `PRINCIPLES_SNAPSHOT.md` — principles snapshot summary
- `PRINCIPLES_CITATIONS.md` — human-friendly citation register (source -> principle file)
- `WEAK_SOURCES.md` — weak/low-signal sources flagged for replacement
- `weak_sources.json` — machine-readable weak-source report

## Build
```bash
python3 ops/scripts/design/build_rembrandt_corpus.py
python3 ops/scripts/design/extract_rembrandt_principles.py
```

## Notes
- The builder enforces allowed domains.
- Failed fetches are logged in metadata and summary.
- Rembrandt should use `principles/*.md` first, and cite those paths in outputs.
- Sources with principles below the quality gate are marked `accepted=false` and should be replaced.
