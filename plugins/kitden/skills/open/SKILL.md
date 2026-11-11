---
name: open
description: Use when the user asks to open Kitden, the Kitden page, or wants to see or change their setup in the browser.
---

Run `kitden open`. It starts the local page if needed, opens it in the browser, prints the link
and returns at once. Give the user the link.

To only print the link, run `kitden open --no-browser`.

If `kitden` is not found or the command fails as unknown, follow the kitden `install` skill.
