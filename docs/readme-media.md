# README media

The README shows the logo, the slogan and three short recordings of the real page, then two
commands. Steps, privacy and limits live in the [guide](guide.md). No captions on the scenes:
the motion should explain itself.

## Scenes

Each scene is an animated WebP in `docs/images/readme/`, in light and dark, about 11 seconds,
under 3 MB. Each ends on the applied state and holds it before the loop starts again.

- `find`: **+ Add servers**, search for context7, drag it onto the gateway, Apply.
- `pick`: a band picks memory (Claude Code), playwright (Codex) and sequential-thinking
  (Cursor); drag them onto the gateway together, Apply all.
- `token`: drag Stripe onto the gateway; it waits for a token; paste it, it works, Apply.

## Record

Needs ffmpeg with libwebp (`brew install ffmpeg`).

```bash
uv run --with playwright==1.64.1 python scripts/record_readme.py
```

`--only pick-dark` records one scene; `--serve` only starts the page to look around.
Each recording starts the real page on a fresh copy of the sample from
`scripts/readme_demo.py`, in a temporary folder. Stand-ins keep it local: a fake Keychain,
fake client commands, canned tool lists, and a local test server that takes one key in place
of Stripe's. Only the catalog search goes online. Nothing of the real home folder is read or
written. The key in the scene is a made-up test value.

Look at every recording before you commit it: the scene shows its whole story and ends on
the toast. Do not show success before verification or retouch the UI.

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
The recording sample is not proof of the published package.
uv [downloads Python if needed](https://docs.astral.sh/uv/guides/install-python/#automatic-python-downloads).

Checked 2026-10-28: GitHub supports relative image sources inside
[`picture`](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/).
Relative sources follow the current branch. Fallback image URLs point to main. PyPI's
[cleaner](https://github.com/pypa/readme_renderer/blob/main/readme_renderer/clean.py)
keeps `img` and removes `source`, so its package page uses the light fallback.
Merge the images before publishing.
