# Contributing to Kitden

Bug reports, documentation fixes and other small fixes are welcome directly. Anything new a
user can see or set (a route, a command, a setting, a page element, a dependency; see
[PRINCIPLES.md](PRINCIPLES.md)) needs an
[issue](https://github.com/KonstantinStarovoytov/kitden/issues) first, so the maintainer can
agree to it. The [roadmap](ROADMAP.md) shows current plans.

## Set up

Use macOS, [uv](https://docs.astral.sh/uv/) and Node.js for the frontend tests.
Fork the repository and clone your fork. From the checkout:

```bash
uv sync --locked
uv run kitden demo
```

uv installs Python 3.13 or later if needed. The demo opens a temporary sample setup in your
browser. It does not read or change your real client settings. Press Ctrl+C to stop it.

See [Development](docs/development.md) for the code layout, commands and release process.

## Make a change

Keep each pull request focused on one problem. Use short, plain English for code, UI text
and documentation. Follow the [design guide](docs/design.md) for interface changes and
[AGENTS.md](AGENTS.md) when working with a coding agent.

Changes are judged against [PRINCIPLES.md](PRINCIPLES.md). Read the [AI policy](AI_POLICY.md)
if you used AI or want to know what the review bots do.

Every change to client settings must go through preview → Apply with a backup → verify →
Undo. Tests must use sandbox homes, never your real settings.

In the same pull request:

- If what Kitden does changes, add one line to [ROADMAP.md](ROADMAP.md) under
  "Not yet released": a short bold title, one plain sentence, and the pull request number.
  For example:

  ```markdown
  - **The toast names the client that refused a change:** when a client's own command
    fails, "Nothing was changed" now says which client refused it (#25).
  ```

- If what the user sees changes, update [the guide](docs/guide.md).

## Check your work

Run these from the checkout before committing:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run pyright
node --test tests/frontend/*.test.mjs
```

For a UI change, also check both themes and reduced motion on the sample setup.

## Open a pull request

The pull request form has a short checklist; tick each item or say why it does not apply.
Explain the problem, what changes for the user and how you checked it. Link the related
issue if there is one. Include before/after screenshots for visible changes and state any
checks you could not run. Remove secrets and private paths from screenshots and logs.

The pull request title becomes the commit subject when it is merged. Say what changes for
the user, in plain English. Do not add a `fix:` or `feat(...)` prefix or the issue number;
put `Fixes #23` in the description instead.

| Good | Not |
| --- | --- |
| Name the client when it refuses a change | fix(dock): name client when a change is refused in toast (#23) |
| Remove a plugin when Claude Code was started in the home folder | fix: plugin uninstall scope bug |

Commit subjects inside the pull request follow the same style.

If a client file format or external API is involved, check its official documentation and
record the date beside the claim.
