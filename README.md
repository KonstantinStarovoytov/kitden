<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.svg">
    <source srcset="docs/images/hero.svg">
    <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/hero.svg" width="640" alt="Kitden: Your AI coding tools, under one roof.">
  </picture>
</h1>

<p align="center"><strong>Your AI coding tools, under one roof.</strong></p>

<p align="center">See and share the MCP servers, plugins and skills<br>
that <b>Claude Code, Codex and Cursor</b> load.</p>

<p align="center">
  <a href="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml"><img src="https://github.com/KonstantinStarovoytov/kitden/actions/workflows/release.yml/badge.svg?branch=main" alt="Checks on main"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/releases/latest"><img src="https://img.shields.io/github/v/release/KonstantinStarovoytov/kitden?label=latest%20release" alt="Latest release"></a>
  <a href="https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="License: Apache-2.0"></a>
</p>

### Find it, drop it in

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme/find-dark.webp">
  <source srcset="docs/images/readme/find-light.webp">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/readme/find-light.webp" width="880" alt="Search the catalog for context7, drag it onto the Kitden gateway, press Apply. Claude Code, Codex and Cursor all get it.">
</picture>

### Move many at once

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme/pick-dark.webp">
  <source srcset="docs/images/readme/pick-light.webp">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/readme/pick-light.webp" width="880" alt="Draw a band around three servers from different clients, drag them onto the gateway together, Apply all. Every client now has all three.">
</picture>

### One token, every agent

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/readme/token-dark.webp">
  <source srcset="docs/images/readme/token-light.webp">
  <img src="https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/readme/token-light.webp" width="880" alt="Drag Stripe onto the gateway. It waits for a token; paste it, Kitden checks it works, then Apply. Every client can use Stripe.">
</picture>

## Get started

Needs macOS and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Try it on a sample first. Your own settings are not read or changed:

<!-- Release checklist: docs/readme-media.md -->
```bash
uvx --python 3.13 kitden demo
```

Then install it for your own setup and open it:

```bash
uv tool install --python 3.13 kitden && kitden
```

Every change shows a preview first, keeps a backup for Undo, and stays on your Mac.
Secrets live in the macOS Keychain. Add only servers and plugins you trust: they run with
your permissions.

[Guide](https://github.com/KonstantinStarovoytov/kitden/blob/main/docs/guide.md) ·
[Roadmap](https://github.com/KonstantinStarovoytov/kitden/blob/main/ROADMAP.md) ·
[Releases](https://github.com/KonstantinStarovoytov/kitden/releases) ·
[Issues](https://github.com/KonstantinStarovoytov/kitden/issues) ·
[Contributing](https://github.com/KonstantinStarovoytov/kitden/blob/main/CONTRIBUTING.md) ·
[Apache-2.0](https://github.com/KonstantinStarovoytov/kitden/blob/main/LICENSE)
