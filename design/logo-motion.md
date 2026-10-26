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
- Each puff takes 2600 ms; they start 110 ms apart, the first at 500 ms. Twelve puffs this
  close melt into one ribbon. The last fades at 4310 ms.
- The door's light comes first: it grows over 1200 ms, slowly at first like a fire catching
  (cubic-bezier(.45, 0, .25, 1)), holds while any smoke is in the air, and goes out over the
  last 700 ms, 200 ms after the last puff (4510 ms in all). The
  door is lit like a hearth: shaped to the arch (radius 8 of a 16 × 22 door), a radial gradient
  from near-white (#FFF3DC) at the bottom middle to the warm colour (#E6B46D light / #F3CC8F
  dark) at .92, with a soft shadow of the same colour spilling 2 px down. A glow of the warm
  colour lies on the ground under the door at .42: a radial ellipse 56 × 42 % of the house, its
  middle on the house's bottom edge, so its brightest part shows just under the door, blurred
  1.5 px.
- Plays once when the page opens, and again when the pointer or keyboard focus has stayed on
  the logo for 200 ms (one that only passes starts nothing), never twice at once. In the app the
  logo is a link to the Overview. Under reduced motion nothing moves and the door does not glow.
