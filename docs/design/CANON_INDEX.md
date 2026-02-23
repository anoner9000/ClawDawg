# Design Canon Index

Purpose: approved source-of-truth inventory for Rembrandt design decisions.

## Core Canon (Local)
- `docs/design/REMBRANDT_UI_KNOWLEDGE.md`
- `docs/design/CANON_INDEX.md`

## Curated Online Corpus (Local Cache)
- Source manifest: `docs/design/corpus/sources.json`
- Corpus output root: `docs/design/corpus/`
- Generated index: `docs/design/corpus/index.jsonl`
- Latest summary: `docs/design/corpus/LATEST_SNAPSHOT.md`
- Principles index: `docs/design/corpus/principles_index.jsonl`
- Principles snapshot: `docs/design/corpus/PRINCIPLES_SNAPSHOT.md`
- Principles citations (human-friendly): `docs/design/corpus/PRINCIPLES_CITATIONS.md`
- Per-source principles: `docs/design/corpus/principles/*.md`

## Governance Rules
- Rembrandt uses local canon first.
- Web-derived content must come from approved domains in `sources.json`.
- Every recommendation must cite at least one source path under `docs/design/`.
- If no relevant canonical source exists, output must explicitly state unknowns.

## Refresh Cadence
- Recommended corpus refresh: weekly or before major UI redesign passes.
- Refresh command:
  - `python3 ops/scripts/design/build_rembrandt_corpus.py`
  - `python3 ops/scripts/design/extract_rembrandt_principles.py`
