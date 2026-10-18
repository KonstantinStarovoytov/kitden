# Validation: Quiet Den + Graphite

Date: 2026-10-18.

- Requirements checklist: 4/4 passed; spec, plan and tasks reviewed together before implementation. No extension hooks configured.
- Existing suite: 405 passed, 7 failed under sandbox restrictions, 8 contract tests deselected. The seven failures required local socket binding or filesystem events. Rerun outside sandbox: all 7 passed. No failing application tests remain from this run.
- Ruff: passed. Git whitespace check: passed.
- Static logo request through authenticated TestClient: 200, image/svg+xml. Same asset referenced by sidebar and favicon. Fixed fill #C85835; no theme-dependent filter or opacity.
- Browser: fixture-backed local app, no real client settings modified. Opened Overview, Load map, Gateway, Changes and Agents in both themes; opened a Load map detail panel in light theme. Inspected compact navigation and horizontally scrolling table at a narrow viewport and desktop layout via viewport override. Reset override afterward. Initial system dark and explicit light/dark switches work.
- Saved overview screenshots in docs/design/den-brand. Desktop capture is soft at the browser's scaled viewport, so it is not a pixel-fidelity proof. Narrow dark capture is clearer. No claim of exhaustive accessibility or every interaction-state testing.
- Contrast ratios: white/action 5.30; light muted/canvas 4.95; dark muted/raised panel 6.11; light accent/canvas 5.74; dark accent/raised panel 6.33; selected label light 5.19 / dark 6.29; fixed logo against light/dark canvas 3.96 / 4.07.
- Impeccable detector returned no regex findings but reported missing parser modules; computed contrast was checked separately above, not inferred from that result.
- Wheel build could not be run through the existing environment because hatchling is not installed. The existing wheel target includes src/kitden; the SVG sits within that package. Static delivery is verified; a release build remains a release-time check.

No data model, client configuration, API, dependency or permission changes.

## Owner follow-up verification

Project picker now shows Global and folder names; full paths remain only in tooltips. Missing folders stay labeled. Removed duplicate inner focus outline. Main page no longer has an independent View Transition snapshot; content is isolated beneath the overlay and opening details cancels the active snapshot. Verified the superpowers panel in both themes, including opening after a theme change. Browser computed state: page viewTransitionName=none, content isolation=isolate, drawer is topmost at its center. Saved panel-fixed.png.

15 existing wording/security tests pass; 2 new Node lifecycle tests pass (drawer interruption and stale completion race); Ruff and whitespace checks pass. Run lifecycle tests with `node --test tests/frontend/motion.test.mjs`.

## Client icons

Replaced shared monograms with local Claude, Codex and Cursor PNG assets; unknown and image-error fallbacks retained. Browser confirmed all four overview images loaded (naturalWidth > 0), and light/dark overview screenshots were visually inspected. Shared component also supplies table headers and detail panels. Sources, ownership and public-release rights-review limits are recorded in static/brand/clients/ATTRIBUTION.md.

Follow-up (same day): every client mark now draws as one white rounded tile (24 px; 28 px in the Clients card and panel titles), including the SVG route diagram on Gateway, which had kept the old CC/CX/CU letters. The 493 KB Codex asset was trimmed and scaled to 128 px (14 KB); `tests/unit/test_brand_assets.py` keeps every icon under 24 KB. Checked in the browser on a fixture home: Overview, Load map, Gateway and a detail panel in light and dark, and the phone layout. Full suite: 414 passed; Ruff passed.
