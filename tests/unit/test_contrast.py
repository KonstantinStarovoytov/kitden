"""Text on the action and success fills stays readable in both themes (WCAG AA, 4.5:1)."""

import re
from pathlib import Path

CSS = (Path(__file__).parents[2] / "src/kitden/web/static/style.css").read_text()


def tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))


def block(selector_start: str) -> str:
    """The text between the braces of the rule that starts at `selector_start`."""
    start = CSS.index(selector_start) + len(selector_start)
    return CSS[start : CSS.index("}", start)]


LIGHT = tokens(block(":root {"))
DARK_RULE = tokens(block(':root[data-theme="dark"] {'))
DARK_AUTO = tokens(block(':root:not([data-theme="light"]) {'))
DARK = {**LIGHT, **DARK_RULE}


def luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_matches_known_values():
    assert round(contrast("#ffffff", "#000000"), 1) == 21.0
    assert round(contrast("#777777", "#ffffff"), 2) == 4.48


def test_success_and_action_labels_are_readable_in_both_themes():
    for theme in (LIGHT, DARK):
        assert contrast(theme["--on-success"], theme["--success"]) >= 4.5
        assert contrast(theme["--on-action"], theme["--action"]) >= 4.5


def test_the_applied_label_is_drawn_at_full_strength_at_once():
    # A disabled button is drawn at 0.5 opacity, which would take the label below 4.5:1, and
    # a fill that fades passes through colors the label was not checked on.
    assert ".btn:disabled { cursor: not-allowed; opacity: 0.5; }" in CSS
    rule = block(".btn.primary.done, .btn.primary.done:hover, .btn.primary.done:disabled {")
    assert "background: var(--success);" in rule and "color: var(--on-success);" in rule
    assert "opacity: 1;" in rule and "transition: none;" in rule
    # No later rule draws the done button fainter.
    later = CSS[CSS.index(rule) :]
    assert not re.search(r"\.done[^{]*\{[^}]*opacity: 0", later)


def test_the_cell_tag_is_readable_on_its_fill_in_both_themes():
    # "This project" and "Only this project" sit on the accent tint.
    for theme in (LIGHT, DARK):
        assert contrast(theme["--route"], theme["--route-soft"]) >= 4.5


def test_system_dark_theme_has_the_same_success_tokens():
    for name in ("--success", "--on-success"):
        assert DARK_AUTO[name] == DARK_RULE[name]


def over(color: str, share: float, base: str) -> str:
    """`color` at `share` opacity on `base`, as color-mix(color share, transparent) draws."""
    mixed = (
        round(share * int(color[i : i + 2], 16) + (1 - share) * int(base[i : i + 2], 16))
        for i in (1, 3, 5)
    )
    return "#" + "".join(f"{c:02x}" for c in mixed)


def test_diff_text_is_readable_on_its_tint_and_on_the_panel():
    # Diff lines sit on a 9% tint of their lamp over the inset; the counts sit on the drawer.
    for lamp in ("--lamp-on", "--danger"):
        assert f"color-mix(in srgb, var({lamp}) 9%, transparent)" in CSS
    assert "pre.diff .add { color: var(--diff-add);" in CSS
    assert "pre.diff .del { color: var(--diff-del);" in CSS
    assert ".diff-count .plus { color: var(--diff-add); }" in CSS
    assert ".diff-count .minus { color: var(--diff-del); }" in CSS
    for theme in (LIGHT, DARK):
        for text, lamp in (("--diff-add", "--lamp-on"), ("--diff-del", "--danger")):
            tint = over(theme[lamp], 0.09, theme["--inset"])
            assert contrast(theme[text], tint) >= 4.5, (text, theme[text], tint)
            assert contrast(theme[text], theme["--panel-raised"]) >= 4.5, (text, theme[text])
    for name in ("--diff-add", "--diff-del"):
        assert DARK_AUTO[name] == DARK_RULE[name]


def test_text_on_the_dim_fill_is_readable_in_both_themes():
    # Outside blocks and off tools sit on --dim; their words are --ink-2 and --ink-3.
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        for ink in ("--ink-2", "--ink-3"):
            assert contrast(theme[ink], theme["--dim"]) >= 4.5, ink


def blend(fill: str, base: str) -> str:
    """A see-through #rrggbbaa fill drawn over an opaque #rrggbb base, as #rrggbb."""
    alpha = int(fill[7:9], 16) / 255
    mix = (
        int(fill[i : i + 2], 16) * alpha + int(base[i : i + 2], 16) * (1 - alpha) for i in (1, 3, 5)
    )
    return "#" + "".join(f"{round(c):02x}" for c in mix)


def test_the_first_run_slot_is_readable_in_both_themes():
    # "No gateway yet" sits on --preview-fill over the canvas. Its name is --ink and its sentence
    # --ink-2.
    assert "div.map .block.slot .block-meta { color: var(--ink-2); }" in CSS
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        fill = blend(theme["--preview-fill"], theme["--canvas"])
        for ink in ("--ink", "--ink-2"):
            assert contrast(theme[ink], fill) >= 4.5, (ink, fill)


def test_a_preview_on_the_map_and_its_bar_are_readable_in_both_themes():
    # A preview block's "Preview" is --ink-2 on the preview fill; the review bar's outcome line is
    # --ink-2 on the raised panel.
    assert "div.map .block.preview .block-meta { color: var(--ink-2); }" in CSS
    assert ".review-bar .bar-outcome { margin: 0; color: var(--ink-2);" in CSS
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        fill = blend(theme["--preview-fill"], theme["--canvas"])
        assert contrast(theme["--ink-2"], fill) >= 4.5
        for ink in ("--ink", "--ink-2"):
            assert contrast(theme[ink], theme["--panel-raised"]) >= 4.5, ink


def test_the_preview_tokens_are_the_frames_values():
    assert (LIGHT["--preview-fill"], LIGHT["--preview-line"]) == ("#a4422612", "#a4422680")
    assert (DARK["--preview-fill"], DARK["--preview-line"]) == ("#f09a7c10", "#f09a7c80")
    for name in ("--dim", "--preview-fill", "--preview-line"):
        assert DARK_AUTO[name] == DARK_RULE[name]


def test_facts_text_is_readable_on_the_details_column_in_both_themes():
    # A fact's label is --ink-3 and an accent value is --route, on the raised panel.
    for theme in (LIGHT, DARK):
        for ink in ("--ink-3", "--route"):
            assert contrast(theme[ink], theme["--panel-raised"]) >= 4.5, ink


def test_the_find_chip_and_a_lit_list_row_are_readable_in_both_themes():
    # The chip sits on the search box (--inset); a lit List row's quiet words sit on the accent
    # tint and are --ink-2 there.
    assert ".tg-row.found .meta, .tg-row.found .tg-tools { color: var(--ink-2); }" in CSS
    # Only a group row's words need it: a match's own words stay --ink, never weaker than the rest.
    assert ".tg-row.group.found { color: var(--ink-2); }" in CSS
    assert ".tg-row.found { background: var(--route-soft); }" in CSS
    for theme in (LIGHT, DARK):
        assert contrast(theme["--ink-2"], theme["--inset"]) >= 4.5
        assert contrast(theme["--ink-2"], theme["--route-soft"]) >= 4.5


TEXT = ("--ink", "--ink-2", "--ink-3", "--ink-4", "--route")
FILLS = ("--canvas", "--panel", "--panel-raised", "--inset", "--dim", "--route-soft")


def test_text_tokens_are_readable_on_every_fill_in_both_themes():
    # Every text token on every fill, the selected block's tint (--route-soft) included.
    for theme in (LIGHT, DARK):
        for t in TEXT:
            for f in FILLS:
                assert contrast(theme[t], theme[f]) >= 4.5, (t, f, theme[t], theme[f])


def test_mockup_tokens_are_there():
    assert DARK["--out"] == "#0d0f13" and LIGHT["--out"] == "#e4e7ec"
    assert DARK["--wire"] == "#3b424d" and LIGHT["--wire"] == "#e1e4e9"
    assert DARK["--link"] == "#59616f" and LIGHT["--link"] == "#c3c8d0"
    assert DARK["--lamp-warn"] == "#eac27c" and LIGHT["--lamp-warn"] == "#97590a"
    assert DARK["--lamp-off"] == "#6b7381" and LIGHT["--lamp-off"] == "#80868f"
    assert DARK["--shadow"] == "0 18px 44px -14px rgb(0 0 0 / .7)"
    assert LIGHT["--shadow"] == "0 18px 44px -18px rgb(26 31 42 / .28)"


def test_the_two_dark_blocks_are_the_same():
    assert DARK_AUTO == DARK_RULE


def test_wire_is_solid_and_its_soft_and_strong_follow_it():
    # --wire, --link and --out are plain colors. The soft and strong lines are made from them in
    # :root only, so both themes get the mix of their own --wire.
    for theme in (LIGHT, DARK):
        for name in ("--out", "--wire", "--link"):
            assert re.fullmatch(r"#[0-9a-f]{6}", theme[name]), name
    soft = "color-mix(in srgb, var(--wire) 60%, transparent)"
    strong = "color-mix(in srgb, var(--ink) 18%, var(--wire))"
    assert LIGHT["--wire-soft"] == soft and LIGHT["--wire-strong"] == strong
    assert DARK["--wire-soft"] == soft and DARK["--wire-strong"] == strong


def test_a_map_link_is_drawn_in_the_link_color():
    assert "div.map .link { fill: none; stroke: var(--link);" in CSS
    # No other stroke takes a line color: lines that frame things use --wire.
    assert not re.search(r"stroke:\s*var\(--wire", CSS)


def test_quiet_text_on_the_soft_line_fill_is_readable_in_both_themes():
    # A quiet flag (.flag.info) and a winning layer's reason sit on --wire-soft, a 60% mix of the
    # line over the panel or the drawer.
    for theme in (LIGHT, DARK):
        for base in ("--panel", "--panel-raised"):
            fill = over(theme["--wire"], 0.6, theme[base])
            assert contrast(theme["--ink-3"], fill) >= 4.5, (base, fill)
