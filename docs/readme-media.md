# README media

The README tells one short story: see what loads, share a server, and undo a change.
The house stays the brand gesture. Product motion shows real states from the app.

## Capture

Run `uv run python scripts/readme_demo.py`. It creates a fresh temporary sample home,
with three connected clients, two held servers and one direct server named `docs`.
It starts the real page with the demo's offline stand-ins. Ctrl+C deletes the sample.
It never reads or writes a real client setup, starts an MCP server or uses the real Keychain.

The captures were taken on 2026-10-28 at 1280 × 720, after each transition settled.
In both light and dark themes, save these PNGs in a temporary capture folder:

1. `start-light.png` / `start-dark.png`: the Gateway before the move.
2. `preview-light.png` / `preview-dark.png`: drag `docs` into Kitden; leave it in preview.
3. `review-light.png` / `review-dark.png`: open **Show changes**.
4. `applied-light.png` / `applied-dark.png`: close the review, Apply, wait for verification
   and for the toast to go away. The map now has three servers.
5. `history-light.png` / `history-dark.png`: Changes with that change's Details open.
6. `undone-light.png` / `undone-dark.png`: use Undo, wait for the row to say Undone.
7. `library-light.png` / `library-dark.png`: Library, List, search `review`.

Then run `uv run --with pillow python scripts/make_readme_media.py --captures FOLDER`.
The script keeps only the relevant crops in `docs/images/readme/`, with no retouched UI.
Rebuild the SVGs from those crops with `uv run python scripts/make_readme_media.py`.

## Presentation

- `walkthrough.svg` and `walkthrough-dark.svg` use the four real Gateway states. They are
  an edited sequence of still captures, not a continuous screen recording. The review is
  a close-up. A 20-second loop gives the result about eight seconds at rest.
- `compare.svg` and `compare-dark.svg` show the Library's two matching rows.
- `undo.svg` and `undo-dark.svg` put the same history row before and after Undo together.
- Every SVG embeds its PNGs and runs no script. The tour shows the applied state if animation
  is unavailable or `prefers-reduced-motion` is set. Supporting images are still.
- Do not show success before verification, imply that an open client session has refreshed,
  or add moving traffic to the map. All setup values are synthetic.

## GitHub and PyPI

Checked 2026-10-28: GitHub supports relative image sources inside
[`picture`](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/).
The README uses relative `source` paths so previews follow the current branch.
Its fallback `img` URLs point to main. PyPI's
[cleaner](https://github.com/pypa/readme_renderer/blob/main/readme_renderer/clean.py)
keeps `img` and removes `source`, so the package page uses the light fallback after merge.
Publish the release only after its images are on main.

The trial command uses uv's
[`--from` Git source](https://docs.astral.sh/uv/guides/tools/#requesting-different-sources)
(checked 2026-10-28). The illustrated interface is not in the published 0.2.0 release.
After releasing it, change the main commands to `uvx kitden demo` and `uvx kitden`, and
remove the source-preview note. Do not change the commands before the release is available.
