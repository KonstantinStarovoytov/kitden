# Fonts

Kitden ships its fonts as local files, so the page loads nothing from another site.

| File | Font | Package | Used for |
| --- | --- | --- | --- |
| `inter-latin-wght-normal.woff2` | Inter (variable) | `@fontsource-variable/inter@5.2.5` | text |
| `inter-latin-ext-wght-normal.woff2` | Inter (variable) | `@fontsource-variable/inter@5.2.5` | text with accents |
| `jetbrains-mono-latin-wght-normal.woff2` | JetBrains Mono (variable) | `@fontsource-variable/jetbrains-mono@5.2.5` | code and names |

Each file comes from `https://cdn.jsdelivr.net/npm/<package>@5.2.5/files/<file>`.
The `unicode-range` values in `style.css` are from the same package's `wght.css`.
Checked 2026-10-24.

Both fonts use the SIL Open Font License 1.1. The licence text of each package is kept
as `OFL-Inter.txt` and `OFL-JetBrainsMono.txt`.
