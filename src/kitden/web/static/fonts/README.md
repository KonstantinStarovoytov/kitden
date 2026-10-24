# Fonts

Kitden ships its fonts as local files, so the page loads nothing from another site.

| File | Font | Package | Used for |
| --- | --- | --- | --- |
| `inter-latin-wght-normal.woff2` | Inter (variable) | `@fontsource-variable/inter@5.2.5` | text |
| `inter-latin-ext-wght-normal.woff2` | Inter (variable) | `@fontsource-variable/inter@5.2.5` | text with accents |
| `inter-cyrillic-wght-normal.woff2` | Inter (variable) | `@fontsource-variable/inter@5.2.5` | Cyrillic text |
| `jetbrains-mono-latin-wght-normal.woff2` | JetBrains Mono (variable) | `@fontsource-variable/jetbrains-mono@5.2.5` | code and names |
| `jetbrains-mono-cyrillic-wght-normal.woff2` | JetBrains Mono (variable) | `@fontsource-variable/jetbrains-mono@5.2.5` | Cyrillic code and names |

Each file comes from `https://cdn.jsdelivr.net/npm/<package>@5.2.5/files/<file>`.
The `unicode-range` values in `style.css` are from the same package's `wght.css`.
Checked 2026-10-24; the Cyrillic files 2026-10-25.

Both fonts use the SIL Open Font License 1.1. The licence texts come from the font projects,
not from the packages (the packages carry a generic copy without the authors' names):

- `OFL-Inter.txt`: https://raw.githubusercontent.com/rsms/inter/master/LICENSE.txt
- `OFL-JetBrainsMono.txt`: https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/OFL.txt
