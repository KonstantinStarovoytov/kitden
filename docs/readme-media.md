# README media

The README shows the logo, the slogan and three pictures of the real page, then two commands.
Steps, privacy and limits live in the [guide](guide.md). No captions on the pictures, and no
animations: recorded motion stuttered, so each scene is one sharp key moment, cropped to the
part of the page it is about.

## Pictures

Each picture is a PNG in `docs/images/readme/`, in light and dark, taken at twice the page's
size and shown at about its CSS size (880 or 450 px wide).

- `find`: context7, found in the catalog, held over the lit gateway.
- `pick`: memory (Claude Code), playwright (Codex) and sequential-thinking (Cursor), picked
  with a band and held over the lit gateway together.
- `token`: Stripe in the gateway says Token works; the token is masked and Apply waits.

## Take them again

```bash
uv run --with playwright==1.64.1 python scripts/record_readme.py
```

`--only pick-dark` takes one picture; `--serve` only starts the page to look around.
Each picture starts the real page on a fresh copy of the sample from
`scripts/readme_demo.py`, in a temporary folder. Stand-ins keep it local: a fake Keychain,
fake client commands, canned tool lists, and a local test server that takes one key in place
of Stripe's. Only the catalog search goes online. Nothing of the real home folder is read or
written. The key in the scene is a made-up test value. `scripts/record_scenes.py` plays each
scene and holds the area each picture shows.

Look at every picture before you commit it, and do not retouch the UI.

## Examples and sources

Checked against their official sources on **2026-11-02**:

- [Context7](https://github.com/upstash/context7): a remote server that needs no key; found in
  the official MCP Registry under `upstash`.
- [memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) and
  [sequential-thinking](https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking):
  local `npx` servers.
- [Playwright MCP](https://github.com/microsoft/playwright-mcp): `npx @playwright/mcp@latest`.
- [Stripe MCP](https://docs.stripe.com/mcp): `https://mcp.stripe.com`, which takes an API key.

The sample only shows these servers; it starts none of them and never calls Stripe. These
examples do not imply endorsement.

## Release checklist

The README uses these short commands, available from Kitden 0.3.0:

```bash
uvx --python 3.13 kitden demo
uv tool install --python 3.13 kitden
```

Before promoting a release, verify both commands in temporary uv tool and cache folders.
The picture sample is not proof of the published package.
uv [downloads Python if needed](https://docs.astral.sh/uv/guides/install-python/#automatic-python-downloads).

Checked 2026-10-28: GitHub supports relative image sources inside
[`picture`](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/).
Relative sources follow the current branch. Fallback image URLs point to main. PyPI's
[cleaner](https://github.com/pypa/readme_renderer/blob/main/readme_renderer/clean.py)
keeps `img` and removes `source`, so its package page uses the light fallback.
Merge the images before publishing.
