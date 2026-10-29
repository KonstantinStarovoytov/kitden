# README media

The README shows Library, a shared server and Undo, then offers a safe sample and installation.
Requirements sit beside the first command; details follow the main story.
The house stays the brand gesture. Product motion shows real states from the app.

## Capture

Run `uv run python scripts/readme_demo.py`. It creates a temporary sample home with
three clients, Superpowers, frontend-design and a direct Context7 connection in Claude Code.
These are offline fixtures with real project names, not downloaded plugins or a live
integration test. The script never reads or writes real client settings, starts an MCP server
or uses the real Keychain. Ctrl+C deletes the sample.

Captures were taken on 2026-10-29 at 1280 × 720. Let every transition finish, including
appearance changes, before taking a screenshot. Save both `-light.png` and `-dark.png`:

1. `library-start`: Library map before adding Superpowers to Codex.
2. `library-preview`: drag Superpowers onto Codex; leave the connection in preview.
3. `library-applied`: Apply, wait for verification and the toast to disappear.
4. `start`: Gateway map before moving Context7.
5. `preview`: Context7 Details → Move into gateway; close Details, leaving the preview open.
6. `review`: open **Show changes**.
7. `applied`: close the review and Apply. Wait for verification; the gateway holds one server
   with two tools and connects to three clients.
8. `history`: the applied Context7 row in Changes.
9. `undone`: Undo the same change; wait for the row to say Undone.

Run `uv run --with pillow python scripts/make_readme_media.py --captures FOLDER`.
The script stores relevant crops in `docs/images/readme/`, with no retouched UI.
Rebuild from those crops with `uv run python scripts/make_readme_media.py`.

## Examples and sources

Checked against official sources on **2026-10-29**:

- [Superpowers](https://github.com/obra/superpowers): plugin `superpowers`, version 7.0.1,
  marketplace `superpowers-dev`, 15 skill names from its `skills/` directory and plugin manifests.
- [frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design):
  the skill name from its SKILL.md.
- [Context7](https://github.com/upstash/context7): remote endpoint `https://mcp.context7.com/mcp`.
  Its two tools are `resolve-library-id` and `query-docs`, checked in
  [tool-names.ts](https://github.com/upstash/context7/blob/master/packages/mcp/src/lib/tool-names.ts).

Names and tool counts are accurate for that date. The fixture bodies and all setup data are
synthetic; no external tool is called. These examples do not imply endorsement.

## Presentation

- `compare.svg` and its dark variant show three Library map states in a 16-second loop.
- `walkthrough.svg` and its dark variant show four Gateway states in a 20-second loop.
- Both are edited sequences of actual still captures, not continuous recordings. The Gateway
  review is a close-up. Each tour holds its result for about eight seconds.
- `undo.svg` and its dark variant put the same history row before and after Undo together.
- SVGs embed their PNGs and run no script. Tours show the applied state when animation is
  unavailable or `prefers-reduced-motion` is set.
- Do not show success before verification, imply that an open client session refreshed,
  or add moving traffic to the map.

## Release checklist

The README uses these short commands, available from Kitden 0.3.0:

```bash
uvx --python 3.13 kitden demo
uv tool install --python 3.13 kitden
```

Before promoting a release, verify both commands in temporary uv tool and cache folders.
The screenshot fixture is not proof of the published package.
uv [downloads Python if needed](https://docs.astral.sh/uv/guides/install-python/#automatic-python-downloads).
Installation needs a connection; the demo itself uses offline stand-ins and deletes its sample
on exit. uv keeps its download cache.

Checked 2026-10-28: GitHub supports relative image sources inside
[`picture`](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/).
Relative sources follow the current branch. Fallback image URLs point to main. PyPI's
[cleaner](https://github.com/pypa/readme_renderer/blob/main/readme_renderer/clean.py)
keeps `img` and removes `source`, so its package page uses the light fallback.
Merge the images and CONTRIBUTING.md before publishing. Badges link to checks on main,
the latest release and the license.
