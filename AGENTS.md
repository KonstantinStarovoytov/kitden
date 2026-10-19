# Working on Kitden

- Talk to the owner in simple Russian until asked otherwise.
- Write code, comments, UI text and documentation in simple English, short and plain.
- Kitden reads and changes what AI coding clients load. Every change goes through preview →
  Apply with a backup → verify → Undo. Never write a client's settings any other way.
- Main pages show only a name, the client and an action; paths, addresses and commands go
  behind Details.
- Follow [docs/design.md](docs/design.md) for how the page looks and moves.
- Tests use sandbox homes and never touch the real home folder. Run `uv run pytest -q`,
  `uv run ruff check .` and `node --test tests/frontend/motion.test.mjs` before each commit.
- Keep work proportional to a self-hosted tool for one person or a small team: the simplest
  mechanism that works, no speculative options.
- Check changing facts about other tools (client file formats, gateway APIs) against their
  own docs, and write the date you checked next to the claim.
- Commit messages: a short plain subject, one to three simple lines.
- Earlier specs and research live in the git tag `dev-notes-2026-10-19`.
