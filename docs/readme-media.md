# README media

The README shows the logo, the slogan and three scenes of the real page, then how to start and
five facts. Steps, privacy and limits live in the [guide](guide.md). No captions on the scenes.

## Scenes

Each scene is in `docs/images/readme/`, in light and dark, cropped to the part of the page it
is about, taken at 1.5 pixels per CSS pixel and shown at its CSS size (450 to 860 px wide).
They differ in look as in subject: one still, then two animations.

- `library` (a PNG): the Library map, which agent loads which plugin and skill. No pointer.
- `pick` (a looping WebP): Context7 (Cursor), memory (Claude Code) and playwright (Codex) are
  picked with a band and dragged onto the lit gateway together.
- `tools` (a looping WebP): memory is in the gateway with its nine tools. The three that delete
  are turned off on the map (each link's ×) and applied for every agent.

Each animation ends on its key moment, holds it, and fades back to its start.

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

`--only pick-dark` makes one picture; `--serve` only starts the page to look around. It needs
`ffmpeg` and `img2webp` (from libwebp) on the PATH.
Each picture starts the real page on a fresh copy of the sample from
`scripts/readme_demo.py`, in a temporary folder. Stand-ins keep it local: a fake Keychain,
fake client commands, canned tool lists, and no access checks. Nothing goes online, and nothing
of the real home folder is read or written. `scripts/record_scenes.py` plays each scene and
takes it.

Look at every picture before you commit it, and do not retouch the UI.

## Examples and sources

Checked against their official sources on **2026-11-02**:

- [Context7](https://context7.com): the remote server `https://mcp.context7.com/mcp`, which
  needs no key.
- [memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory): a local `npx`
  server; its nine tools and their read-only and destructive hints come from its
  `src/memory/index.ts`.
- [Playwright MCP](https://github.com/microsoft/playwright-mcp): `npx @playwright/mcp@latest`.
- [Superpowers](https://github.com/obra/superpowers) and the
  [frontend-design](https://github.com/anthropics/skills) skill, as the demo sample has them.

The sample only shows these; it starts none of them and calls nothing. These
examples do not imply endorsement.

## Release checklist

The README uses these short commands, available from Kitden 0.3.0:

```bash
uvx --python 3.13 kitden demo
uv tool install --python 3.13 kitden
```

Before promoting a release, verify both commands in temporary uv tool and cache folders.
The README sample is not proof of the published package.
uv [downloads Python if needed](https://docs.astral.sh/uv/guides/install-python/#automatic-python-downloads).

Checked 2026-10-28: GitHub supports relative image sources inside
[`picture`](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/).
Relative sources follow the current branch. Fallback image URLs point to main. PyPI's
[cleaner](https://github.com/pypa/readme_renderer/blob/main/readme_renderer/clean.py)
keeps `img` and removes `source`, so its package page uses the light fallback.
Merge the images before publishing.
