# Kitden branding direction

Reviewed: 2026-10-18. Status: historical exploration; Quiet Den + Graphite light/dark was selected by the owner. Current implementation rules: [DESIGN.md](../../DESIGN.md).

## Owner feedback: confirmed constraints

- The owner prefers the Quiet Den asymmetric house concept, with Open Door second. Earlier K proposals below are historical exploration, not the current recommendation.
- The house shape and brand color must stay identical in light and dark themes. Backgrounds change; the logo must not automatically become white or a lighter orange.
- Choose the primary brand color first. A later interface redesign should build its palette around that color. The owner subsequently selected Graphite light/dark and authorized implementation, using the displayed terracotta #C85835.
- Current proposed colors: Terracotta `#C85835`, Ember `#D9653B`, Clay `#C96A4A`, Copper `#C77745`. Generated boards are approximate previews; exact colors and contrast must be checked in vector/browser samples before final selection.

## Product meaning

Kitden is a local companion for coding agents. Its identity should suggest a clear, reliable home for a user's tools. Suggested descriptor: **Your coding setup, in one place.**

The existing interface uses neutral gray surfaces, dark text, and blue accents, with light and dark themes. Preserve this system while exploring a distinctive mark. The current CSS mark is a small rounded square with two horizontal lines; treat it as a placeholder.

## Proposed logo directions

| Direction | Mark | Strength | Risk |
| --- | --- | --- | --- |
| Kit / recommended | Three simple modules arranged into a compact K | Relates to tools and the name; can work at small sizes | Must avoid looking like a generic grid |
| Den | A compact open enclosure holding one module | Expresses a home for the setup | Can look like a house or storage app |
| Companion | A minimal animal silhouette, with a separate wordmark | More character for launch material | Can imply a chatbot or virtual pet |

Start with Kit. Test in one color at 16, 24, and 32 pixels before adding blue. Use the same underlying shape for favicon, app icon, repository avatar, and website. Keep the wordmark readable as Kitden. Do not combine vendor logos into the Kitden mark.

These are verbal directions, not finished logo assets. No originality or trademark clearance has been established.

## Client identity inside the product

Show a client icon and its full name in client selectors, client cards, and source details. Preserve a stable icon size and optical weight. Keep status in a separate badge; do not recolor a vendor mark to show an error or disabled state. Use a consistent generic icon family for MCP servers, skills, plugins, hooks, and settings.

| Client | Source and verification | Release action |
| --- | --- | --- |
| Cursor | [Official brand kit](https://cursor.com/brand) offers logos, app icons, and avatars | Select the appropriate official light/dark asset and follow its guidelines |
| Claude Code | [Official product page](https://claude.com/product/claude-code) establishes product identity; this review did not locate a dedicated redistribution kit | Verify the chosen product asset and applicable use terms; do not assume the Anthropic company logo is the Claude Code icon |
| Codex | [OpenAI brand guidelines](https://openai.com/brand/) provide OpenAI marks and usage terms; they do not establish that every OpenAI mark is a Codex product icon | Verify the current Codex-specific asset before packaging; do not label a generic ChatGPT icon as Codex |

Ship verified assets locally so the local app does not need a logo service. Record each asset's origin, review date, permitted variants, and applicable terms. A library's code license does not itself grant trademark rights. Until an asset is verified, a text label remains a usable fallback.

## Small first deliverable

1. Compare three drawn variants of the Kit mark in the existing sidebar and browser tab.
2. Select one and prepare SVG, favicon, and light/dark exports.
3. Add verified client marks in a consistent component, with accessible text labels.
4. Record the chosen identity in a short brand guide for future Claude and Codex UI work.

No application code or vendor assets were changed by this research.
