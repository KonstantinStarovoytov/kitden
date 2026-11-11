# Working on Kitden

- Write code, comments, UI text and documentation in simple English, short and plain.
- Kitden reads and changes what AI coding clients load. Every change goes through preview →
  Apply with a backup → verify → Undo. Never write a client's settings any other way.
- Main pages show only a name, the client and an action; paths, addresses and commands go
  behind Details.
- Changes are judged against [PRINCIPLES.md](PRINCIPLES.md).
- Follow [docs/design.md](docs/design.md) for how the page looks and moves.
- Tests use sandbox homes and never touch the real home folder. Run `uv run pytest -q`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright` and
  `node --test tests/frontend/*.test.mjs` before each commit.
- Keep work proportional to a self-hosted tool for one person or a small team: the simplest
  mechanism that works, no speculative options.
- Check changing facts about other tools (client file formats, gateway APIs) against their
  own docs, and write the date you checked next to the claim.
- A change to how Kitden reads or writes a client's files updates `docs/clients.md` in the same
  pull request.
- When you finish a task that changes what Kitden does or plans, update ROADMAP.md in the same
  change.
- Every release has a notes file; see [docs/development.md](docs/development.md).
- Commit messages: a short plain subject, one to three simple lines.
- Pull request titles say what changes for the user, in plain English, with no `fix:` or
  `feat(...)` prefix and no issue number. Fill in the checklist in the pull request form;
  see [CONTRIBUTING.md](CONTRIBUTING.md).
- Earlier plans, specs and research live in the git tags `dev-notes-2026-10-19` and
  `dev-notes-2026-11-09`, not in the tree.
