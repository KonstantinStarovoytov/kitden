# Contract: checks and releases

One workflow, `.github/workflows/release.yml`. Every push and pull request runs the checks. A
pushed tag `v<version>` that matches `kitden.__version__` also builds and releases.

```mermaid
flowchart LR
    T[git push tag v0.1.0] --> B[build: tests, uv build, checks]
    B --> R[release: gh release create with dist files]
```

| Job | Runner | Permissions | Steps | Fails when |
| --- | --- | --- | --- | --- |
| `build` | macOS | `contents: read` | checkout; `astral-sh/setup-uv` (pinned); `uv sync --locked`; `uv run ruff check .`; `uv run pytest -q`; on a tag: the tag equals `v$(uv version --short)`; `uv build`; the wheel lists `kitden/web/static/index.html` and the sdist lists no `tests/`, `docs/`, `specs/`; `uv run --isolated --no-project --with dist/*.whl -- kitden --version` prints the version; upload `dist/` | any step fails |
| `release` (tags only) | Linux | `contents: write` | checkout; download `dist/`; `gh release create <tag> dist/* --generate-notes --verify-tag` with `GH_TOKEN: ${{ github.token }}` | the tag is missing on the remote, or the release exists |

Rules:

- A tag push with failing tests publishes nothing (FR-001). `release` needs `build`.
- No secret is stored.
- The version string, the tag and the two plugin manifests carry the same number (FR-015); the
  build job checks the tag against the package version.
- The release notes are generated from the commits since the previous tag.
- Running the workflow again for the same tag fails at `release` and changes nothing.

Later, when the owner opens PyPI: a `publish` job between `build` and `release` with
`environment: pypi`, `permissions: id-token: write` and `uv publish` (Trusted Publishing, no
token); the one-time setup is in research R11.
