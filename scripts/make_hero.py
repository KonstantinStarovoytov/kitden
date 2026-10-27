"""Make the README hero: the logo with its one gesture, the door's light and the smoke from the d.

The values come from design/logo-motion.md (mockup: design/kitden-cloud-smoke.html), scaled to a
120-unit wordmark. Run it once after a change and commit the two files it writes:

    uv run --with fonttools --with brotli python scripts/make_hero.py
"""

from functools import cache
from pathlib import Path

ROOT = Path(__file__).parents[1]
FONT = ROOT / "src/kitden/web/static/fonts/inter-latin-wght-normal.woff2"
HOUSE_SVG = ROOT / "src/kitden/web/static/brand/kitden.svg"
OUT = ROOT / "docs/images"

WIDTH, HEIGHT = 880, 260
EM = 120  # the wordmark's font size
TRACKING = -0.055 * EM
HOUSE = 1.25 * EM  # 150
GAP = 13 / 48 * EM  # 32.5
WORD = "Kitden"
SLOGAN = "Your AI coding tools, under one roof."

COLOURS = {
    "light": {"word": "#161A21", "smoke": "#626977", "warm": "#E6B46D"},
    "dark": {"word": "#F2F3F5", "smoke": "#A5ADBA", "warm": "#F3CC8F"},
}
HOUSE_COLOUR = "#C85835"
CORE = "#FFF3DC"

# The smoke: twelve puffs 110 ms apart on one linear path, as a share of right .95 em, up .42 em.
PUFFS = 12
WIDTHS = [0.30, 0.32, 0.34, 0.36, 0.38]  # em, cycling
PATH = [(0, -0.12), (0.15, 0.40), (0.60, 0.78), (1, 0.92)]
AT = [0, 0.2, 0.6, 1]
FADE = [0, 0.31, 0.22, 0]
RIGHT, UP = 0.95 * EM, 0.42 * EM
GROW = (0.7, 1.4)
BLUR = (1.5, 2.5)  # px; .6 to 1 px at 48 px

# The times, in ms. One cycle is the gesture, then a rest; the first starts 400 ms after load.
START = 400
LEAD, STEP, FLIGHT = 500, 110, 2600
LIGHT_IN, LIGHT_OUT = 1200, 700
GESTURE = LEAD + (PUFFS - 1) * STEP + FLIGHT + 200  # 4510
CYCLE = GESTURE + 6000  # 10 510
EASE_IN = "cubic-bezier(.45, 0, .25, 1)"


def num(value: float) -> str:
    """A short number for the file: two decimals at most."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def stop(ms: float) -> str:
    return f"{round(100 * ms / CYCLE, 3):g}%"


def kerning(font, left: str, right: str) -> int:
    """The pair kerning of `left` then `right` from GPOS, in font units (0 when there is none)."""
    gpos = font["GPOS"].table
    indexes = sorted(
        {
            index
            for record in gpos.FeatureList.FeatureRecord
            if record.FeatureTag == "kern"
            for index in record.Feature.LookupListIndex
        }
    )
    total = 0
    for index in indexes:
        lookup = gpos.LookupList.Lookup[index]
        if lookup.LookupType != 2:
            continue
        for table in lookup.SubTable:
            covered = table.Coverage.glyphs
            if left not in covered:
                continue
            if table.Format == 1:
                pairs = table.PairSet[covered.index(left)].PairValueRecord
                record = next((pair for pair in pairs if pair.SecondGlyph == right), None)
                if record is None:
                    continue
                value = record.Value1
            else:
                first = table.ClassDef1.classDefs.get(left, 0)
                second = table.ClassDef2.classDefs.get(right, 0)
                value = table.Class1Record[first].Class2Record[second].Value1
            total += getattr(value, "XAdvance", 0) or 0
            break  # the first table that covers the pair decides, for this lookup
    return total


@cache
def wordmark() -> dict:
    """The word's outline at x 0 and its baseline at 0, its width, and the d's box (y up)."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = instancer.instantiateVariableFont(TTFont(FONT), {"wght": 600})
    scale = EM / font["head"].unitsPerEm
    glyphs = font.getGlyphSet()
    names = [font.getBestCmap()[ord(char)] for char in WORD]
    pen = SVGPathPen(glyphs, ntos=num)
    x = 0.0
    for i, name in enumerate(names):
        glyph = glyphs[name]
        if WORD[i] == "d":
            bounds = BoundsPen(glyphs)
            glyph.draw(bounds)
            x_min, y_min, x_max, y_max = bounds.bounds
            d_box = (x + x_min * scale, y_min * scale, x + x_max * scale, y_max * scale)
        glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, 0)))
        kern = kerning(font, name, names[i + 1]) if i + 1 < len(names) else 0
        x += (glyph.width + kern) * scale + TRACKING  # a browser adds the tracking after each one
    hhea = font["hhea"]
    # With line-height 1 the line box is one em tall and the font's height is centred in it.
    baseline = (EM - (hhea.ascent - hhea.descent) * scale) / 2 + hhea.ascent * scale
    return {"path": pen.getCommands(), "width": x, "baseline": baseline, "d": d_box}


def house_path() -> str:
    text = HOUSE_SVG.read_text()
    start = text.index(' d="') + 4
    return text[start : text.index('"', start)]


def puff_frames() -> str:
    """The keyframes of one puff: the 2600 ms flight, then nothing until the next cycle."""
    frames = []
    for (x, y), t, fade in zip(PATH, AT, FADE, strict=True):
        size = round(GROW[0] + (GROW[1] - GROW[0]) * t, 3)
        blur = round(BLUR[0] + (BLUR[1] - BLUR[0]) * t, 3)
        at = stop(FLIGHT * t) if t < 1 else f"{stop(FLIGHT)}, 100%"
        frames.append(
            f"  {at} {{ opacity: {fade:g}; "
            f"transform: translate({num(RIGHT * x)}px, {num(-UP * y)}px) scale({size:g}); "
            f"filter: blur({blur:g}px); }}"
        )
    return "@keyframes puff {\n" + "\n".join(frames) + "\n}"


def light_frames() -> str:
    """The keyframes of the door's light: it grows, holds while smoke is in the air, goes out."""
    return (
        "@keyframes light {\n"
        f"  0% {{ opacity: 0; animation-timing-function: {EASE_IN}; }}\n"
        f"  {stop(LIGHT_IN)} {{ opacity: 1; animation-timing-function: linear; }}\n"
        f"  {stop(GESTURE - LIGHT_OUT)} {{ opacity: 1; animation-timing-function: ease-in-out; }}\n"
        f"  {stop(GESTURE)}, 100% {{ opacity: 0; }}\n"
        "}"
    )


def make_hero(theme: str) -> str:
    """The hero SVG for `theme`, "light" or "dark"."""
    colours = COLOURS[theme]
    word = wordmark()
    k = HOUSE / 64  # the house's own box is 64 units
    lockup = HOUSE + GAP + word["width"]
    left = (WIDTH - lockup) / 2
    word_x = left + HOUSE + GAP

    # The smoke's anchor, from the d's outline, above the baseline: 80 % across, 89 % up.
    d_left, d_bottom, d_right, d_top = word["d"]
    anchor_x = word_x + d_left + 0.8 * (d_right - d_left)
    anchor_up = d_bottom + 0.89 * (d_top - d_bottom)

    # Room above for the highest puff at its end (widest, grown, blurred) and below for the glow.
    widest = max(WIDTHS) * EM * 20 / 28
    smoke_top = 0.15 * widest + GROW[1] * 0.85 * widest + UP * PATH[-1][1] + 3 * BLUR[1] * GROW[1]
    top = -EM / 2 + word["baseline"] - anchor_up - smoke_top  # from the lockup's middle
    glow_y = -HOUSE / 2 + 58 * k  # the house's bottom edge
    bottom = glow_y + 0.21 * HOUSE
    middle = (HEIGHT - top - bottom) / 2
    house_x, house_y = left, middle - HOUSE / 2
    baseline = middle - EM / 2 + word["baseline"]
    anchor_y = baseline - anchor_up

    # The door: 16 x 22 at (12, 36) in the house's box, with an arch of radius 8.
    x1, x2 = house_x + 12 * k, house_x + 28 * k
    arch_y, foot_y, radius = house_y + 44 * k, house_y + 58 * k, 8 * k
    door = (
        f"M{num(x1)} {num(foot_y)}V{num(arch_y)}"
        f"A{num(radius)} {num(radius)} 0 0 1 {num(x2)} {num(arch_y)}V{num(foot_y)}Z"
    )

    puffs = []
    for i in range(PUFFS):
        width = WIDTHS[i % len(WIDTHS)] * EM
        height = width * 20 / 28
        # Left edge .06 em left of the anchor, bottom on it; it grows around 30 % / 85 % of its box.
        origin_x = anchor_x - 0.06 * EM + 0.3 * width
        origin_y = anchor_y - 0.15 * height
        puffs.append(
            f'    <g transform="translate({num(origin_x)} {num(origin_y)})">'
            f'<g class="puff" style="animation-delay: {START + LEAD + i * STEP}ms">'
            f'<use href="#puff" x="{num(-0.3 * width)}" y="{num(-0.85 * height)}" '
            f'width="{num(width)}" height="{num(height)}"/></g></g>'
        )

    css = "\n".join(
        [
            f".light {{ opacity: 0; animation: light {CYCLE}ms {START}ms infinite; }}",
            f".puff {{ opacity: 0; transform-origin: 0 0; "
            f"animation: puff {CYCLE}ms linear infinite; }}",
            light_frames(),
            puff_frames(),
            "@media (prefers-reduced-motion: reduce) {\n  .light, .puff { animation: none; }\n}",
        ]
    )
    warm = colours["warm"]
    opening = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="Kitden: {SLOGAN}">'
    )
    door_gradient = (
        '<radialGradient id="door-light" cx=".5" cy="1" r=".8" '
        'gradientTransform="translate(.5 1) scale(1 .875) translate(-.5 -1)">'
    )
    # The ground glow: its middle on the house's bottom edge, under the door.
    glow = (
        f'<ellipse cx="{num(house_x + 20 * k)}" cy="{num(foot_y)}" '
        f'rx="{num(0.28 * HOUSE)}" ry="{num(0.21 * HOUSE)}" '
        'fill="url(#glow-light)" opacity=".42" filter="url(#glow-blur)"/>'
    )
    # The door's soft shadow spills 5 units down, like the app's box-shadow at this size.
    shadow = (
        f'<path id="door-shadow" d="{door}" fill="{warm}" stroke="{warm}" stroke-width="5" '
        'stroke-linejoin="round" transform="translate(0 5)" filter="url(#shadow-blur)"/>'
    )
    house = (
        f'<path id="house" fill="{HOUSE_COLOUR}" '
        f'transform="translate({num(house_x)} {num(house_y)}) scale({k:g})" d="{house_path()}"/>'
    )
    text = (
        f'<path id="word" fill="{colours["word"]}" '
        f'transform="translate({num(word_x)} {num(baseline)})" d="{word["path"]}"/>'
    )
    return f"""{opening}
  <title>Kitden</title>
  <style>
{css}
  </style>
  <defs>
    {door_gradient}
      <stop offset="0" stop-color="{CORE}"/>
      <stop offset=".75" stop-color="{warm}"/>
    </radialGradient>
    <radialGradient id="glow-light">
      <stop offset="0" stop-color="{warm}"/>
      <stop offset="1" stop-color="{warm}" stop-opacity="0"/>
    </radialGradient>
    <filter id="shadow-blur" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="7.5"/>
    </filter>
    <filter id="glow-blur" x="-25%" y="-25%" width="150%" height="150%">
      <feGaussianBlur stdDeviation="3.75"/>
    </filter>
    <symbol id="puff" viewBox="0 -5 28 20" overflow="visible">
      <rect width="22" height="14.4" rx="7"/>
      <ellipse cx="8" cy="1.8" rx="7.5" ry="6.75"/>
      <ellipse cx="19.5" cy="4" rx="8.5" ry="6.3"/>
    </symbol>
  </defs>
  <g class="light">
    {glow}
    <g opacity=".92">
      {shadow}
      <path d="{door}" fill="url(#door-light)"/>
    </g>
  </g>
  {house}
  {text}
  <g id="smoke" fill="{colours["smoke"]}">
{chr(10).join(puffs)}
  </g>
</svg>
"""


def main() -> None:
    for theme, name in (("light", "hero.svg"), ("dark", "hero-dark.svg")):
        (OUT / name).write_text(make_hero(theme))
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
