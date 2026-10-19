# Quickstart: check feature 007, Step A

## Automated

```sh
uv run pytest -q
uv run ruff check .
node --test tests/frontend/motion.test.mjs
```

## In the browser (fixture home, fake Obot and the live one)

Start the page on a sandbox home built from `tests/fixtures` with the fake Obot from
`tests/unit/fake_obot.py` (two servers) and the owner's live Obot registered beside it; the
live key is read from the environment, never typed or printed. Never use the real home.

1. Gateway page: the fake Obot card says "In the gateway · 2" with the names; Details opens
   the panel with the kind and, for a remote server, its address.
2. The live Obot card: with a key that works but no vMCP yet, the card says "Obot has no
   connection named <id>"; the rest of the page works.
3. Connect clients → Preview → Apply: the review lists the three client files and the login
   notes (OAuth); after Apply the card says "Used · 3 clients"; the fixture files hold the
   connection address and never the key.
4. Undo from the Changes page: the fixture files are byte for byte the originals.
5. "Add another gateway": an Obot address shows "Obot API key variable name (not the key)" and
   hides the MetaMCP sign-in fields.
6. Repeat 1–3 in the other theme and at 375 px.

## Result (2026-10-19)

- [x] Steps 1–6 done in the built-in browser (dark and light, 375 px) on a fixture home with
  the fake Obot; Apply and Undo touched only the fixture files, which equal the originals after
  Undo; no `ok1-` value in any file or response.
- [x] Live Obot v0.26.3 (Docker on the Mac, GitHub sign-in, empty): the key from the named
  variable is accepted (`/api/me` 200), and `GET /api/vmcps/<id>` for an id that does not exist
  gives the one-line card note. Reading a real vMCP's components was checked only on the fake:
  the owner's Obot holds no vMCP yet.
