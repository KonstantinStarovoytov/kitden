# Tasks: Overview and panel polish

**Input**: [spec.md](spec.md) and Part A of the
[design review](../../docs/research/design-and-install-review-2026-10-18.md).

**Tests**: Required: a failing test first for every model or wording change, then the code.
Page-only changes (CSS, layout) are checked in the browser on a sandbox home.

- [ ] T001 [US1] Overview cards: one card per item, a short title, one sentence, one primary
  button, no paths. Tests in `tests/unit/test_overview.py`; code in `views/overview.py`,
  `web/static/js/overview.js`, `style.css`.
- [ ] T002 [US2] Side panel: flags carry `fix` and `fix_action` (`views/load_map.py`, tests in
  `tests/unit/test_load_map.py`); the panel shows the fix, the matching primary button and
  "More" (`panel.js`); the wins row uses a neutral tint (`style.css`).
- [ ] T003 [US3] Review: the preview answer carries `after` per client (`web/app.py`, tests in
  `tests/unit/test_api_changes.py`); the panel shows it first in sockets, folds the diff and the
  command under "Show file change", and keeps one Cancel (`panel.js`, `style.css`).
- [ ] T004 [US4] Remove list: rail counters (`index.html`, `app.js`), Overview pills, gateway
  bar and Recent changes (`overview.js`, `overview.py`), Load map badges, `×2` and legend
  (`load_map.py`, `map.js`), diff headers (`panel.js`), Entry name field and paths
  (`gateway.js`), Details buttons (`changes.js`). Tests in `test_load_map.py` and
  `tests/unit/test_page_words.py`.
- [ ] T005 [US5] Problems 4–7: Gateway button, wires, grouped rows and "Used" (`gateway.js`,
  `gateway_view.py`, tests in `test_gateway_view.py`); Changes rows (`changes.js`); "Loads ·
  account" (`style.css`); words (`index.html`, `parts.js`, `load_map.py`).
- [ ] T006 Docs: wording changes in `docs/superpowers/specs/2026-10-17-portal-ui-design.md`;
  a note in `specs/001-agent-setup-inventory/validation.md`; browser check on a sandbox home.

## Order

T001 → T002 → T003 → T004 → T005 → T006, one commit each.
