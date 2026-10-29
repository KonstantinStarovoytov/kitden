"""The README hero: an animated SVG made by scripts/make_hero.py, one file per theme.

GitHub and PyPI show it through <img>, so it must load nothing and run no script. The gesture is
the logo's (design/logo-motion.md) on a 10 510 ms cycle: 4510 ms of gesture, then 6000 ms of rest.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from tests.unit.test_contrast import contrast

ROOT = Path(__file__).parents[2]
FILES = {"light": ROOT / "docs/images/hero.svg", "dark": ROOT / "docs/images/hero-dark.svg"}
NS = "{http://www.w3.org/2000/svg}"
CYCLE = 10510
START = 400
GESTURE = 4510
GROW = "cubic-bezier(.45, 0, .25, 1)"


def root(theme: str) -> ET.Element:
    return ET.parse(FILES[theme]).getroot()


def css(theme: str) -> str:
    return "".join(root(theme).find(f"{NS}style").itertext())


def by_id(svg: ET.Element, name: str) -> ET.Element:
    found = [node for node in svg.iter() if node.get("id") == name]
    assert len(found) == 1, name
    return found[0]


def rule(text: str, selector: str) -> str:
    """The body of the first plain rule for `selector`, outside any @media or @keyframes."""
    outside = re.sub(r"@[^{]+\{(?:[^{}]*\{[^}]*\})*[^{}]*\}", "", text)
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", outside)
    assert match, selector
    return match.group(1)


def keyframes(text: str, name: str) -> list[tuple[float, dict[str, str]]]:
    """The frames of `@keyframes name`, as (percent, {property: value}), in order."""
    match = re.search(r"@keyframes " + name + r"\s*\{((?:[^{}]*\{[^}]*\})*)\s*\}", text)
    assert match, name
    frames = []
    for stops, body in re.findall(r"([\d.%,\s]+)\{([^}]*)\}", match.group(1)):
        props = dict(
            (key.strip(), value.strip())
            for key, value in (part.split(":", 1) for part in body.split(";") if part.strip())
        )
        for stop in stops.split(","):
            frames.append((float(stop.strip().rstrip("%")), props))
    return sorted(frames, key=lambda frame: frame[0])


def percent(ms: float) -> float:
    return 100 * ms / CYCLE


def test_the_hero_loads_nothing_and_draws_its_words_as_paths():
    for theme, path in FILES.items():
        text = path.read_text()
        svg = root(theme)
        tags = {node.tag.removeprefix(NS) for node in svg.iter()}
        assert not tags & {"text", "script", "foreignObject", "image"}, theme
        assert "@import" not in text and "url(http" not in text
        hrefs = [
            value
            for node in svg.iter()
            for key, value in node.attrib.items()
            if key.endswith("href")
        ]
        assert hrefs and all(href.startswith("#") for href in hrefs), hrefs
        assert svg.get("viewBox") == "0 0 880 260"
        assert svg.find(f"{NS}title").text == "Kitden"
        assert svg.get("role") == "img"
        assert svg.get("aria-label") == "Kitden: Your AI coding tools, under one roof."
        assert by_id(svg, "word").tag == f"{NS}path"


def test_the_hero_has_twelve_puffs_with_the_logo_times():
    for theme in FILES:
        svg, text = root(theme), css(theme)
        puffs = [node for node in svg.iter() if node.get("class") == "puff"]
        assert len(puffs) == 12
        for i, node in enumerate(puffs):
            assert node.get("style") == f"animation-delay: {START + 500 + 110 * i}ms"
        for selector, name in ((".puff", "puff"), (".light", "light")):
            body = rule(text, selector)
            assert f"animation: {name} {CYCLE}ms" in body and "infinite" in body
        assert "linear" in rule(text, ".puff")
        assert f"{START}ms" in rule(text, ".light")

        puff = keyframes(text, "puff")
        stops = [at for at, _ in puff]
        expected = [0, percent(520), percent(1560), percent(2600), 100]
        assert [round(at, 3) for at in stops] == [round(at, 3) for at in expected]
        assert [float(props["opacity"]) for _, props in puff] == [0, 0.31, 0.22, 0, 0]
        assert puff[0][1]["filter"] == "blur(1.5px)" and puff[3][1]["filter"] == "blur(2.5px)"
        # The path, as a share of right .95 em and up .42 em at 120 units.
        moves = [(0, 6.05), (17.1, -20.16), (68.4, -39.31), (114, -46.37), (114, -46.37)]
        sizes = [0.7, 0.84, 1.12, 1.4, 1.4]
        for (_, props), (x, y), size in zip(puff, moves, sizes, strict=True):
            assert props["transform"] == f"translate({x:g}px, {y:g}px) scale({size:g})"

        light = keyframes(text, "light")
        stops = [round(at, 3) for at, _ in light]
        expected = [0, percent(1200), percent(GESTURE - 700), percent(GESTURE), 100]
        assert stops == [round(at, 3) for at in expected]
        assert [float(props["opacity"]) for _, props in light] == [0, 1, 1, 0, 0]
        assert light[0][1]["animation-timing-function"] == GROW
        assert light[1][1]["animation-timing-function"] == "linear"
        assert light[2][1]["animation-timing-function"] == "ease-in-out"


def test_between_plays_the_hero_is_the_plain_logo():
    for theme in FILES:
        text = css(theme)
        puff, light = keyframes(text, "puff"), keyframes(text, "light")
        assert float(puff[0][1]["opacity"]) == 0 and float(light[0][1]["opacity"]) == 0
        flight = next(at for at, props in puff if at > 0 and float(props["opacity"]) == 0)
        for at, props in puff:
            if at >= flight:
                assert float(props["opacity"]) == 0, at
        out = next(at for at, props in light if at > 0 and float(props["opacity"]) == 0)
        for at, props in light:
            if at >= out:
                assert float(props["opacity"]) == 0, at
        # The last puff is gone before the light goes out, so the rest starts clean.
        delays = [
            int(node.get("style").removeprefix("animation-delay: ").removesuffix("ms"))
            for node in root(theme).iter()
            if node.get("class") == "puff"
        ]
        assert max(delays) + flight / 100 * CYCLE <= START + out / 100 * CYCLE


def test_reduced_motion_stills_the_hero():
    for theme in FILES:
        text = css(theme)
        media = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?\})\s*\}", text, re.S)
        assert media, theme
        body = re.search(r"([^{]+)\{([^}]*)\}", media.group(1))
        assert {part.strip() for part in body.group(1).split(",")} == {".puff", ".light"}
        assert "animation: none" in body.group(2)
        for selector in (".puff", ".light"):
            assert re.search(r"(^|;)\s*opacity: 0\s*(;|$)", rule(text, selector)), selector


def test_the_hero_colours_follow_the_theme():
    colours = {
        "light": {"word": "#161A21", "smoke": "#626977", "warm": "#E6B46D", "page": "#FFFFFF"},
        "dark": {"word": "#F2F3F5", "smoke": "#A5ADBA", "warm": "#F3CC8F", "page": "#0D1117"},
    }
    for theme, want in colours.items():
        svg = root(theme)
        assert by_id(svg, "house").get("fill") == "#C85835"
        assert by_id(svg, "word").get("fill") == want["word"]
        assert by_id(svg, "smoke").get("fill") == want["smoke"]
        door = [stop.get("stop-color") for stop in by_id(svg, "door-light").iter(f"{NS}stop")]
        assert door == ["#FFF3DC", want["warm"]]
        glow = {stop.get("stop-color") for stop in by_id(svg, "glow-light").iter(f"{NS}stop")}
        assert glow == {want["warm"]}
        assert by_id(svg, "door-shadow").get("fill") == want["warm"]
        # The light's peaks, as the app's lightFrames(0.92) and lightFrames(0.42).
        assert by_id(svg, "door").get("opacity") == ".92"
        assert by_id(svg, "glow").get("opacity") == ".42"
        assert contrast(want["word"], want["page"]) >= 3
    text = {theme: path.read_text() for theme, path in FILES.items()}
    assert "#C85835" in text["dark"] and "#161A21" not in text["dark"]
    assert "#F2F3F5" not in text["light"]


def test_the_readme_shows_the_hero_and_the_slogan():
    readme = (ROOT / "README.md").read_text()
    base = "https://raw.githubusercontent.com/KonstantinStarovoytov/kitden/main/docs/images/"
    top = readme[: readme.index("See and change what")]
    picture = re.search(r"<picture>.*?</picture>", top, re.S)
    assert picture, "the hero comes first"
    slogan = "Your AI coding tools, under one roof."
    dark = '<source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.svg">'
    light = f'<img src="{base}hero.svg" width="640" alt="Kitden: {slogan}">'
    assert dark in picture.group(0) and light in picture.group(0)
    assert f'<p align="center"><strong>{slogan}</strong></p>' in top
    assert top.count("<h1") == 1 and "logo.svg" not in top
    assert (ROOT / "docs/images/logo.svg").exists()


def test_the_smoke_leaves_the_d_where_the_mockup_has_it():
    # The mockup and the app put the anchor 89 % up the d's 1-em line box: 0.754 em, 90.45 units
    # above the baseline at 120. A puff's bottom sits on the anchor; it grows around 85 % down.
    for theme in FILES:
        svg = root(theme)
        baseline = float(
            re.search(r"translate\(\S+ (\S+)\)", by_id(svg, "word").get("transform"))[1]
        )
        first = next(node for node in svg.iter() if node.get("class") == "puff")
        holder = next(node for node in svg.iter() if first in list(node))
        puff_y = float(re.search(r"translate\(\S+ (\S+)\)", holder.get("transform"))[1])
        height = 0.30 * 120 * 20 / 28
        assert abs(baseline - (puff_y + 0.15 * height) - 90.45) <= 0.5
