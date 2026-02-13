# Event Types

## Purpose
- Define canonical event names and required field shapes for onboarding and scorecard workflows.

## Event Type Catalog
| Event Type | Description | Producer | Consumer | Notes |
|---|---|---|---|---|
| `TASK_ACCEPTED` | [Placeholder] | [Placeholder] | [Placeholder] | [Placeholder] |
| `TASK_COMPLETED` | [Placeholder] | [Placeholder] | [Placeholder] | [Placeholder] |
| `APPROVAL_REQUESTED` | [Placeholder] | [Placeholder] | [Placeholder] | [Placeholder] |
| `APPROVAL_GRANTED` | [Placeholder] | [Placeholder] | [Placeholder] | [Placeholder] |
| `RISK_BLOCKED` | [Placeholder] | [Placeholder] | [Placeholder] | [Placeholder] |
| `UNBLOCKED` | [Placeholder] | [Placeholder] | [Placeholder] | [Placeholder] |
| `SCORECARD_PUBLISHED` | [Placeholder] | [Placeholder] | [Placeholder] | [Placeholder] |

## Required Event Fields
### Common fields (all event types)
- `ts`: [Placeholder]
- `event_type`: [Placeholder]
- `producer`: [Placeholder]
- `payload`: [Placeholder]

### Event-specific required fields
#### `TASK_ACCEPTED`
- `ts`
- `event_type`
- `producer`
- `payload.task_id`
- `payload.owner`

#### `TASK_COMPLETED`
- `ts`
- `event_type`
- `producer`
- `payload.task_id`
- `payload.artifact_refs`

#### `APPROVAL_REQUESTED`
- `ts`
- `event_type`
- `producer`
- `approval_id`
- `payload.request_scope`

#### `APPROVAL_GRANTED`
- `ts`
- `event_type`
- `producer`
- `approval_id`
- `expires_at`

#### `RISK_BLOCKED`
- `ts`
- `event_type`
- `producer`
- `risk`
- `payload.block_reason`

#### `UNBLOCKED`
- `ts`
- `event_type`
- `producer`
- `approval_id`
- `expires_at` (if applicable)
- `payload.unblock_reason`

#### `SCORECARD_PUBLISHED`
- `ts`
- `event_type`
- `producer`
- `payload.scorecard_ref`
- `payload.period`

## Validation Rules
- `event_type` must match one catalog value exactly.
- Required fields for the matching event type must be present.
- `payload` must be an object/map shape.
- [Placeholder for additional validation constraints]
