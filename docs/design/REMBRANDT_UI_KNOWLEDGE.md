# Rembrandt UI Knowledge Base

Purpose: canonical design guidance for Rembrandt to produce aesthetically strong, usable, governance-compatible UI.

## 1) Visual Hierarchy
- Prioritize one primary action per region; demote secondary actions with tone, size, and spacing.
- Use typographic scale and contrast before adding decoration.
- Keep information density high enough for operations dashboards, but reduce cognitive noise with grouping and rhythm.

## 2) Color System
- Use tokenized color roles:
  - `bg`, `surface`, `surface-strong`, `line`, `ink`, `muted`, `accent`, `danger`, `warning`, `success`
- Prefer perceptual color spaces (OKLCH/LCH) when generating ramps.
- Ensure contrast:
  - normal text >= 4.5:1
  - large text >= 3:1
- Avoid relying on hue alone for status; pair with icon/label.

## 3) Typography
- Use at most two families in a surface: display + body.
- Set explicit scale (example): `12, 14, 16, 20, 24, 32`.
- Favor readable line lengths and compact but legible line-height in dense tables.
- Use weight and size changes to clarify semantics, not random emphasis.

## 4) Layout & Spacing
- Compose with consistent spacing tokens (4/8/12/16/24 rhythm).
- Keep panels with clear section boundaries and stable scan paths.
- For dashboards, prefer:
  - summary strip -> alerts/intel -> detailed tables
- Preserve responsive behavior:
  - avoid horizontal overflow except deliberate tables
  - maintain touch targets on smaller viewports

## 5) Motion
- Motion should explain state changes or navigation, never distract.
- Use short entrance transitions for section clarity.
- Respect `prefers-reduced-motion` and provide low-motion fallback.
- Avoid continuous animations that interfere with reading operational data.

## 6) Data-Dense UI Patterns
- Tables: sticky semantics, clear headers, modest row contrast.
- Status chips: consistent shape and color semantics.
- Alerts: severity hierarchy, action clarity, short copy.
- Trend blocks: legible labels and exact values available on demand.

## 7) Accessibility Baseline
- Visible keyboard focus (`:focus-visible`).
- Semantic controls with labels and ARIA where needed.
- Color choices checked in both day and night themes.
- Keep control text readable under all theme/background combinations.

## 8) Governance Compatibility
- Never introduce UI affordances that bypass policy gates.
- Destructive/governed actions must show state (`allowed/blocked`) and reason.
- Audit affordances (run id, ack state, history/export) are first-class, not hidden.

## 9) OpenClaw Aesthetic Direction
- Intentional, expressive, slightly bold visual language.
- Avoid generic boilerplate layouts and default-looking controls.
- Prefer coherent palettes with one clear accent family per theme.
- Preserve operational trust: stylistic upgrades must not reduce interpretability.
