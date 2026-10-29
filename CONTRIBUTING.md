# Contributing to Kitden

Bug reports, documentation fixes and small improvements are welcome. For a larger feature,
[open an issue](https://github.com/KonstantinStarovoytov/kitden/issues) before starting so we
can agree on the scope. The [roadmap](ROADMAP.md) shows current plans.

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

Every change to client settings must go through preview → Apply with a backup → verify →
Undo. Tests must use sandbox homes, never your real settings. If behavior or plans change,
update [ROADMAP.md](ROADMAP.md) and the relevant documentation in the same pull request.

## Check your work

Run these from the checkout before committing:

```bash
uv run pytest -q
uv run ruff check .
node --test tests/frontend/*.test.mjs
```

For a UI change, also check both themes and reduced motion on the sample setup.

## Open a pull request

Explain the problem, what changes for the user and how you checked it. Link the related
issue if there is one. Include before/after screenshots for visible changes and state any
checks you could not run. Remove secrets and private paths from screenshots and logs.

Use a short, plain commit subject. If a client file format or external API is involved,
check its official documentation and record the date beside the claim.
