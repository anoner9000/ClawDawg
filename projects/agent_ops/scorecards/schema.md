# Monthly Scorecard Schema

## Purpose
- Define required fields and allowed status values for monthly scorecard artifacts.

## Metadata (required)
- `period`: [Placeholder format]
- `generated_at`: [Placeholder format]
- `prepared_by`: [Placeholder]
- `reviewed_by`: [Placeholder]
- `approved_by`: [Placeholder]
- `scorecard_version`: [Placeholder]

## KPI Entry Schema (required per KPI row)
- `kpi_id`: [Placeholder]
- `kpi_name`: [Placeholder]
- `definition`: [Placeholder]
- `owner`: [Placeholder]
- `source_ref`: [Placeholder]
- `target`: [Placeholder]
- `actual`: [Placeholder]
- `status`: [Must use Status Model value]
- `notes`: [Placeholder]

## Incident Schema (required per incident row)
- `incident_id`: [Placeholder]
- `summary`: [Placeholder]
- `severity`: [Placeholder]
- `status`: [Must use Status Model value where applicable]
- `owner`: [Placeholder]
- `linked_event_refs`: [Placeholder]
- `notes`: [Placeholder]

## Compliance Check Schema (required per check row)
- `check_id`: [Placeholder]
- `check_name`: [Placeholder]
- `result`: [Pass/Fail/Blocked placeholder]
- `evidence_ref`: [Placeholder]
- `owner`: [Placeholder]
- `notes`: [Placeholder]

## Action Schema (required per action row)
- `action_id`: [Placeholder]
- `action`: [Placeholder]
- `owner`: [Placeholder]
- `due_date`: [Placeholder]
- `status`: [Must use Status Model value]
- `dependency`: [Placeholder]
- `notes`: [Placeholder]

## Status Model (allowed values)
- `on_track`
- `at_risk`
- `off_track`
- `blocked`
