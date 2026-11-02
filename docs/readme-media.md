# README media

The README shows the logo, the slogan and three short animations of the real page, then two
commands. Steps, privacy and limits live in the [guide](guide.md). No captions on the
animations.

## Animations

Each animation is a looping WebP in `docs/images/readme/`, in light and dark, cropped to the
part of the page it is about, filmed at 1.5 pixels per CSS pixel and shown at its CSS size (880
or 450 px wide).

- `find`: context7, found in the catalog, is dragged onto the gateway, which lights up.
- `pick`: memory (Claude Code), playwright (Codex) and sequential-thinking (Cursor) are picked
  with a band and dragged onto the lit gateway together.
- `token`: a token is typed for Stripe in the gateway, and it works.

Each one ends on its key moment, holds it, and fades back to its start.

An earlier screen recording stuttered: frames came at uneven times. Now the page runs on a
paused clock. Each step moves the page one frame (1/30 s) on, puts every animation at that
time, and saves the frame. So the motion is even, however long a frame takes to save.
Waiting for the network is cut out.

The WebPs are near-lossless (`-near_lossless 60`). Lossy WebP left dark bars and blocks
where frames differ a little, and lower settings left grain on warm dark cards.

## Make them again

```bash
uv run --with playwright==1.64.1 python scripts/record_readme.py
```

`--only pick-dark` makes one animation; `--serve` only starts the page to look around. It needs
`ffmpeg` and `img2webp` (from libwebp) on the PATH.
Each animation starts the real page on a fresh copy of the sample from
`scripts/readme_demo.py`, in a temporary folder. Stand-ins keep it local: a fake Keychain,
fake client commands, canned tool lists, and a local test server that takes one key in place
of Stripe's. Only the catalog search goes online. Nothing of the real home folder is read or
written. The key in the scene is a made-up test value. `scripts/record_scenes.py` plays each
scene and films it.

Watch every animation before you commit it, and do not retouch the UI.

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
The animation sample is not proof of the published package.
uv [downloads Python if needed](https://docs.astral.sh/uv/guides/install-python/#automatic-python-downloads).

Checked 2026-10-28: GitHub supports relative image sources inside
[`picture`](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/).
Relative sources follow the current branch. Fallback image URLs point to main. PyPI's
[cleaner](https://github.com/pypa/readme_renderer/blob/main/readme_renderer/clean.py)
keeps `img` and removes `source`, so its package page uses the light fallback.
Merge the images before publishing.
