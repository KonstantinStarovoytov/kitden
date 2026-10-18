# Data model: One-line install

Reviewed: 2026-10-18. Most of this feature is files and a pipeline; the only runtime change is
one new state on the Agents place.

## Release

| Field | Value |
| --- | --- |
| Version | `kitden.__version__`, set with `uv version`; equal in both plugin manifests |
| Tag | `v<version>`, pushed by the owner |
| Built files | `dist/kitden-<version>.tar.gz`, `dist/kitden-<version>-py3-none-any.whl` |
| Where it ends | GitHub release `v<version>` with the two files and generated notes; the PyPI project `kitden` later |

A release exists only when the tests passed and the upload succeeded. A repeated tag or version
fails without changing anything.

## Install script run

| Step | Does | Stops with |
| --- | --- | --- |
| 1 System | `uname -s` is `Darwin` | exit 1, "Kitden does not support <system> yet" |
| 2 uv | find `uv` on PATH or in uv's folder; else run uv's installer | exit 2, "could not install uv" |
| 3 Kitden | `uv tool install "git+https://github.com/<owner>/kitden@<release tag>"` | exit 3, "could not install Kitden" |
| 4 Open | run `<tool folder>/kitden` | Kitden's own exit code 4, "the page did not start" |
| 5 PATH | if the tool folder is not on PATH, print `uv tool update-shell` | — |

Nothing in a client changes at any step.

## Plugin package

See [contracts/plugin-package.md](contracts/plugin-package.md) for every file. Identity: entry
name `kitden`, manifest name `kitden`, marketplace name `kitden`, so the install id is
`kitden@kitden` in both clients. Version: the package version.

## Setup server state (feature 002, extended)

Per client, from the inventory:

| State | Meaning | Agents place shows |
| --- | --- | --- |
| `not_installed` | the client is not on this computer | nothing to do |
| `missing` | no `kitden` server | "Add…" |
| `added` | a user-level `kitden` entry that runs `kitden mcp` | "Added", on/off |
| `old` | an `agentsetup` entry from the working version | "Update to Kitden…" |
| `plugin` (new) | a `kitden` server whose source is a plugin (Claude Code, Codex) | "Provided by the kitden plugin"; no Add button |

When a client has both a plugin server and a user-level entry, the state is `added` and the
findings list the pair as a duplicate. Cursor never has the `plugin` state.
