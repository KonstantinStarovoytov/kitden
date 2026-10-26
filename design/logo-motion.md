# Logo motion: smoke from the d (chosen 2026-10-26)

The wordmark plays one short gesture, as if the stove is lit: the door glows, and a soft
stream of smoke leaves the top of the **d**, rises a little, and the wind carries it right over
"en", where it thins out. Mockup: [kitden-cloud-smoke.html](kitden-cloud-smoke.html).
In the app since 2026-10-26: `startLogo` in `src/kitden/web/static/js/logo.js` builds and plays
it on the rail's logo (19 px: right .9 em, up .4 em, blur .24 → .4 px); the styles sit next to
`.brand-mark` in `style.css`, and the door's colour is the `--hearth` token.

## The smoke

- One soft puff, drawn twelve times: a rounded body (22 × 14.4, r 7) with two round bumps on
  top (at 8, 1.8, r 7.5 × 6.75 and at 19.5, 4, r 8.5 × 6.3) in a 28 × 20 box. One colour, the
  muted text grey (`--ink-3`: #626977 light, #A5ADBA dark). No outline, no gradient.
- Widths, in em of the wordmark's font size, cycling: .30, .32, .34, .36, .38 (14–18 px at
  48 px; 6–8 px at 20 px). A puff is born at 70 % of that and grows to 140 %.
- Soft: a blur of .6 px at birth growing to 1 px at the end (40 % of that at sidebar size).
- Faint: opacity 0 → .31 at 20 % of the path → .22 at 60 % → 0. The puffs overlap, so the
  stream reads darker than one puff.

## Where and how it moves

- Anchor: a point at 80 % of the d's width and 89 % of its height (just right of the stem's
  top). A puff sits with its left edge .06 em left of that point and its bottom on it; it
  scales around 30 % / 85 % of its own box. No tilt.
- Path, as a share of the full move (right ≈ .95 em, up ≈ .42 em): at 0 % (0, −.12) · 20 %
  (.15, .40) · 60 % (.60, .78) · 100 % (1, .92). It rises first, then the air carries it right.
  Linear timing on one clock, so the path reads as a drift, not a bounce.
- Each puff takes 2600 ms; they start 110 ms apart, the first at 200 ms. Twelve puffs this
  close melt into one ribbon. The last fades at 4010 ms.
- The door's light comes first: it rises in 500 ms (CALM), holds while any smoke is in the
  air, and goes out over the last 700 ms, 200 ms after the last puff (4210 ms in all). The
  light is the door's warm colour (#E6B46D light / #F3CC8F dark) at .68, shaped to the arch
  (radius 8 of a 16 × 22 door), with a faint blurred glow on the ground under it at .27.
- Plays once when the page opens, and again when the pointer or keyboard focus comes to the
  logo, never twice at once. In the app the logo is a link to the Overview. Under reduced motion
  nothing moves and the door does not glow.
