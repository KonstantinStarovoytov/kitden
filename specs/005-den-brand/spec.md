# Feature: Quiet Den identity

Date: 2026-10-18. Status: approved direction, implemented; verification limits in validation.md.

## Confirmed direction
The owner chose the Quiet Den house and Graphite light/dark backgrounds, and asked to align the whole application. The house retains the same shape and terracotta color in both themes. Use #C85835 from the selected board as the exact brand value.

## User scenarios and acceptance
### US1 — Recognize Kitden (P1)
Opening any page shows the Quiet Den house and Kitden wordmark. The browser tab uses the same house. Changing theme never recolors the logo.
### US2 — Use one consistent interface (P1)
Overview, Load map, Gateway, Changes, setup instructions and detail/review panels share neutral Graphite surfaces and terracotta actions, selection and focus. Success, warning, unknown and error remain distinguishable with words and shapes.
### US3 — Read either theme (P1)
Explicit light/dark selection and system dark preference remain usable. Normal text meets 4.5:1 contrast; focus and essential control indicators meet 3:1. Small viewports retain existing navigation and scrolling.

## Requirements
- FR-001: Use one local house asset for the sidebar and favicon, with a constant #C85835 fill.
- FR-002: Use Graphite light #F5F6F8 and dark #171A20 canvases with distinct panel elevations.
- FR-003: Replace old blue interaction accents with a coherent terracotta family. Text shades may adapt for contrast; the logo may not.
- FR-004: Preserve behavior, accessible names, keyboard navigation, reduced motion, privacy, CSP, backup and explicit Apply/Undo flows.
- FR-005: Document the approved identity and asset source for future work.

## Edge cases
System theme without a saved setting; selected and hovered rows; warning cards beside brand actions; disabled controls; narrow navigation; long item names.

## Success criteria
All five pages and a detail panel render in both themes. The mark is identical across themes, designed for small sizes and delivered locally from the application package. Existing checks pass. No configuration is changed during visual verification.

## Exclusions and assumptions
No new product behavior, vendor-logo sourcing, fonts, runtime dependencies or speculative layout redesign. Existing client monograms remain honest placeholders. Historical mockups remain archived references; DESIGN.md becomes current visual authority.

## Owner follow-up: transition and project picker

- Opening a detail drawer during navigation or theme switching must never place a table snapshot above the drawer.
- The project picker reads Project: Global by default; options show folder names, not parent paths. Missing folders remain labeled. Full paths may remain in tooltips for disambiguation.
- The project picker has one visible focus ring.

## Owner follow-up: client icons

Replace CC/CD/CX/CU placeholders with recognizable Claude, Codex and Cursor icons wherever the shared client mark is used. Preserve full client names and distinguish Claude Code from the Desktop Code tab by text. Store assets locally, preserve their colors, keep unknown-client fallback, and record origin and third-party ownership. The generic Claude family mark identifies both Claude surfaces; it is not presented as a separate Claude Code-only logo.
