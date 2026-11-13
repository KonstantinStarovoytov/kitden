# README media

The README shows the logo, the slogan and five parts: the map, whether skills fit, find and
add, the gateway, and why it is safe. Then come the other features and how to start. Steps,
privacy and limits live in the [guide](guide.md). Each part has a heading and a few plain
sentences; the first four have a picture of the real page, with no caption.

## Scenes

Each scene is in `docs/images/readme/`, in light and dark, cropped to the part of the page it
is about, taken at 1.5 pixels per CSS pixel and shown at its CSS size or smaller (470 to
860 px wide). They differ in look as in subject: three stills, then one animation.

- `library` (a PNG): the Library map, which agent loads which plugin and skill. The four
  skills under "Your skills" start folded as a stack, as on the page. No pointer.
- `context` (a PNG): Context for Claude Code, from the client tabs down to the two boxes. The
  last chat's skill list is over its limit, so four skills show only a name; the 1M window is
  an estimate. Taken on the sample `kitden demo` opens (its medium size), so a reader who
  runs the demo sees the same. No pointer.
- `find` (a PNG): two add panels side by side, each cut to its own size with clear space
  between. Left, a search for "mcp" in skills.sh: one skill is open with its description, and
  two agents are ticked under Add to. Right, a search for "linear" in the MCP Registry:
  Linear's own server is open with Sign in. Taken in a taller window (1280 by 1000), so the
  panels show whole.
- `tools` (a looping WebP): memory is in the gateway with its nine tools, and the two servers
  left outside are folded back into their stack. The three tools that delete are turned off on
  the map (each link's ×) and applied for every agent. Taken in a shorter window (1280 by
  780): the page can scroll from the start, so the map does not move a pixel when the tray
  opens.
- `pick` (a looping WebP), for posts, not in the README: the servers outside the gateway start
  as a stack. A press opens it, and Context7 (Cursor), memory (Claude Code) and playwright
  (Codex) are picked with a band and dragged onto the lit gateway together.

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
`scripts/readme_demo.py`, in a temporary folder; `context` uses the demo's own sample.
Stand-ins keep it local: a fake Keychain, fake client commands, canned tool lists and catalog
answers, and no access checks. Nothing goes online, and nothing
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
- [Superpowers](https://github.com/obra/superpowers), as the demo sample has it, and four
  skills from [anthropics/skills](https://github.com/anthropics/skills): frontend-design, pdf,
  skill-creator and webapp-testing. The skills checked **2026-11-13**.
- [skills.sh](https://skills.sh): its answer to "mcp", the first six rows as the page sorts
  them, and [mcp-builder](https://github.com/anthropics/skills/tree/main/skills/mcp-builder)'s
  name and description (Apache-2.0). Checked **2026-11-05**.
- [Official MCP Registry](https://registry.modelcontextprotocol.io): its answer to "linear",
  the first six servers in its own order, and that [Linear's server](https://mcp.linear.app/mcp)
  asks for a sign-in. Checked **2026-11-05**.

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
