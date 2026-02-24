# ops/governance

This is the only allowed place for shared governance logic (pure functions).
Everything else must call into here or `ops/scripts/policy/`.

Target end state:
- receipt creation helpers (pure, data-only)
- receipt validation helpers (pure, data-only)
- authority checks (pure)
- policy contract loading/validation (pure)
