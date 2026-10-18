# Kitden visual system

Approved direction: 2026-10-18. Quiet Den + Graphite, light and dark.

## Identity

Kitden is a calm local home for a developer's coding tools. The mark is a soft asymmetric house with an off-center arched door. The wordmark is Kitden in the existing system sans, medium-bold, with slightly tight tracking.

Canonical asset: `src/kitden/web/static/brand/kitden.svg`. The sidebar and favicon reuse this file. It was hand-authored as vector geometry from the owner's selected Quiet Den concept; it contains no third-party mark or external resource. The generated exploration is not a production asset.

**The house is always #C85835.** Never recolor it for dark mode, use a white fallback, apply opacity, or add gradients. Use the same silhouette in both themes. Keep clear space around it. The sidebar renders at 30 px; favicon has a 64-unit viewBox and a simple silhouette for small sizes.

## Color roles

| Role | Light | Dark |
| --- | --- | --- |
| Brand mark | #C85835 | #C85835 |
| Canvas | #F5F6F8 | #171A20 |
| Panel | #FFFFFF | #20242C |
| Raised panel | #FFFFFF | #282D36 |
| Inset | #F0F2F5 | #12151A |
| Main text | #161A21 | #F2F3F5 |
| Secondary text | #464D5B | #C1C6CF |
| Muted text | #646B79 | #A5ADBA |
| Action fill | #B34B2D | #B34B2D |
| Action text | #FFFFFF | #FFFFFF |
| Action hover | #9F4025 | #9F4025 |
| Accent text / links | #A44226 | #F09A7C |
| Selection surface | #F6E8E2 | #382A27 |
| Focus | #B34B2D | #F09A7C |

The brand mark is fixed; functional shades adapt for text contrast. Do not use the logo color for every small label. Success stays green, warnings amber and errors red, paired with text/shape. Gateway routes use the accent family and square state indicators. Vendor marks must retain their own permitted colors when verified; Claude, Cursor and Codex use local vendor icons (see the asset attribution). Neutral monograms are used only for unknown clients or failed image loads.

## Client marks

Every client mark is the same rounded tile (24 px, radius 6, raised-panel background, thin border), so the row of clients reads as one family. The Codex and Cursor icons fill the tile and switch to the vendor's own dark version in the dark theme; the Claude glyph sits inside it with 4 px padding and works on both. The tile grows to 28 px where the client is the headline: the Clients card on Overview and the title of a detail panel. The Gateway route diagram draws the same tile in SVG. Do not tint, recolor or shrink a vendor icon to show a state; state lives in the badge next to it.

## Components

Preserve the compact information layout. Use restrained neutral panels, fine borders and the existing 6–10 px corner radii. Primary actions use the action fill. Selected navigation uses a tinted background, accent text and a brand-colored inset bar. Tabs and selected filters use the same accent family. Tables, drawer, forms, loading, toast and empty states inherit shared tokens; no page-specific blue accents.

Keep existing system fonts and motion, keyboard focus, and reduced-motion support. Search and project controls show a visible focus outline. Preserve explicit Apply, backup and Undo semantics. Brand color must not imply success or a safe action.

## Motion

Motion explains a change to the person's setup; it never decorates. Research and audit:
[motion design review](docs/research/motion-design-2026-10-18.md).

| Token | Value | Use |
| --- | --- | --- |
| Press | 80 ms in, 260 ms `--spring` out | Buttons, switches, client marks |
| `--t-fast` | 180 ms | Hover colour, label swaps |
| `--t-panel` | 320 ms, `--ease-drawer` | Drawer, toast |
| `--spring` | CSS `linear()` critically damped spring, no overshoot; falls back to `--ease-out` | Things the hand moves |
| Stagger | 45 ms between blocks, 18 ms between diff lines (14 at most) | First visit, diff |

Rules:

- **Truth first.** A success look (check mark, switch flip, new state) appears only after the server says the write is verified. A switch shows the real state; pressing it opens the review and it flips only after Apply.
- **No fake activity.** No looping animation that suggests traffic, scanning or work Kitden cannot see. A gateway wire draws once when its connection first appears, then stays still.
- **Errors stay.** An error is a callout that stays until the next action; the button that failed gives one short shake (10 px, 360 ms).
- **Calm, not bouncy.** No overshoot anywhere: press scales to 0.98, the switch thumb slides with ease-in-out.
- **Point, don't move.** To show where something is, light it (row glow, socket ping, route focus) instead of moving the layout.
- Animate `transform` and `opacity` only, except the client counts row, which opens with `grid-template-rows`.
- `prefers-reduced-motion: reduce` turns all animation off; every end state is the resting style, so nothing is lost.

## Authority

This file and `src/kitden/web/static/style.css` are the current identity. Earlier portal mockups and generated boards are historical explorations, not implementation references. Feature scope and verification live in `specs/005-den-brand/`.
