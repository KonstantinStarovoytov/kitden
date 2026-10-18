# Plan: Quiet Den identity

## Technical context
Keep the existing Starlette static site, native CSS variables and JavaScript modules. No dependency or API changes. Create a hand-authored SVG based on the selected concept, with fixed terracotta fill, reused by CSS and the favicon. Keep the existing sidebar span to preserve its accessible and tested wordmark structure.

## Constitution check
Pass: specified before implementation; local assets only; no client writes; no secrets; approved scope; English artifacts and Russian discussion.

## Design
Graphite canvas #F5F6F8 / #171A20. White / #20242C panels. Fixed brand #C85835. Accessible brand text #A44226 / #F09A7C, primary button #B34B2D with white text, neutral readable secondary text. Distinct semantic colors stay intact. Use the established spacing and component shapes, with a larger house/wordmark and consistent selection, focus, inputs and primary buttons.

## Verification
Run existing pytest and Ruff checks, inspect a fixture-backed application in both themes and narrow viewport, open a detail panel, check contrast mathematically and static asset delivery. No schema or data model changes. Document findings in validation.md and current visual rules in DESIGN.md.

## Follow-up implementation
Use a single root snapshot for transitions rather than independently lifting the main page above the drawer. Isolate scrolling content below the overlay; cancel active snapshots when opening details and guard stale completion callbacks. Keep existing reduced-motion behavior. Simplify picker labels and expose paths only as tooltips; refresh options when their data changes rather than only their count. Verify lifecycle races with Node's built-in test runner and the open fixture preview.

Client icons: use unchanged official-site PNGs for Claude and Cursor, and the named Codex icon from the installed OpenAI app resources. Reuse the shared mark() component with decorative images beside existing labels. No image service at runtime. Keep provenance in the asset directory; third-party marks are not relicensed under Kitden's Apache license.
