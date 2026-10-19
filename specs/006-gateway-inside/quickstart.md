# Quickstart: check feature 006

## Automated

```sh
uv run pytest -q
uv run ruff check .
node --test tests/frontend/motion.test.mjs
```

## In the browser (fixture home, fake MetaMCP)

Start a fake MetaMCP and the page on a sandbox home built from `tests/fixtures` (the test
helper `tests/unit/fake_metamcp.py` serves the gateway; never use the real home):

1. Gateway page: the card shows "In the gateway" with the names the fake holds; Details opens
   the panel with the address.
2. "Move into the gateway…" on one row: the review lists the gateway step first, then one step
   per client; the diff hides header values.
3. Apply: the button turns Applied, the row leaves the "Can move" group and appears under "In
   the gateway"; Changes shows the move with Undo.
4. Undo: the row comes back, the fake no longer holds the server, the fixture files are back.
5. "Move all N…": one review, one Apply, one Undo.
6. Stop the fake: the card says the gateway could not be reached; the rest of the page works.
7. Repeat 1–3 in the other theme and at 375 px.

## Result

- [x] Steps 1–5 and 7 done on 2026-10-19 in the built-in browser (dark and light, 375 px):
  one move, Move all 4, Undo from the Changes page both times; fixture files back after Undo.
- [ ] Step 6 (gateway stopped) was checked by the unit test
  `test_the_page_reads_what_the_gateway_holds` only; the page shows the error line from the same
  answer. Not tried in the browser.
