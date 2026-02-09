# ACCESS.md — example_project

# Allow rules for project example_project
allow:
  Peabody:
    - write: CONTEXT.md
    - write: research/*
  Scribe:
    - write: CONTEXT.md
    - write: briefs/*
  Custodian:
    - write: ~/.openclaw/runtime/config.known-good/*
    - write: ACCESS.md
  Deiphobe:
    - write: '*'
# Notes:
# - Paths are relative to the project folder unless absolute.
# - Wildcard '*' suffix matches any suffix.
# - This ACCESS.md is an example for testing check_access.sh in dry-run mode.
