<!--
Title: say what changes for the user, in plain English.
  Good: Name the client when it refuses a change
  Not:  fix(dock): name client when a change is refused in toast (#23)
No `fix:` or `feat(...)` prefix and no issue number in the title. The title becomes the
commit subject when the pull request is merged.
-->

Fixes #

## What changes for the user

## How I checked it

## Checklist

- [ ] The title says what changes for the user, with no prefix and no issue number.
- [ ] [ROADMAP.md](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) has a line under "Not released yet" if what Kitden does changes.
- [ ] User docs ([docs/guide.md](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/guide.md)) are updated if what the user sees changes.
- [ ] I ran all three checks: `uv run pytest -q`, `uv run ruff check .`, `node --test tests/frontend/*.test.mjs`.
- [ ] Visible changes have before/after screenshots, checked in both themes.
