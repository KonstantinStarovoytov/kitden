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


def test_the_applied_label_is_drawn_at_full_strength():
    # A disabled button is drawn at 0.5 opacity, which would take the label below 4.5:1. The tray's
    # Apply waits with aria-disabled, which the dock draws no fainter, and Applied is green with its
    # own label color (it turns green in 180 ms, docs/design.md Tray Apply).
    assert ".btn:disabled { cursor: not-allowed; opacity: 0.5; }" in CSS
    rule = block(".dock .btn.ok, .dock .btn.ok:hover {")
    assert "background: var(--success);" in rule and "color: var(--on-success);" in rule
    # No later rule draws the Applied button fainter, and the dock's waiting Apply is never dimmed.
    later = CSS[CSS.index(rule) :]
    assert not re.search(r"\.ok[^{]*\{[^}]*opacity: 0", later)
    assert not re.search(r'\.dock \.btn\[aria-disabled="true"\][^{]*\{[^}]*opacity', CSS)


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
            # The modal drawer is the raised panel; the floating one is the panel.
            for fill in ("--panel-raised", "--panel"):
                assert contrast(theme[text], theme[fill]) >= 4.5, (text, theme[text], fill)
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


def test_a_preview_on_the_map_is_readable_in_both_themes():
    # A preview block's "Preview" is the accent on the preview fill.
    assert "div.map .block.preview .block-meta { color: var(--route); }" in CSS
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        fill = blend(theme["--preview-fill"], theme["--canvas"])
        assert contrast(theme["--route"], fill) >= 4.5


def test_lamps_and_marks_keep_3_to_1_on_every_block_fill_in_both_themes():
    # WCAG 1.4.11: a lamp or a tool's mark says on (green), off or outside the gateway (grey) or
    # preview (an accent ring). Each keeps 3:1 on every fill a block takes: the panel, the
    # gateway's raised panel, an outside block's dim fill, a selected block's tint and a preview.
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        fills = [theme[f] for f in ("--panel", "--panel-raised", "--dim", "--route-soft")]
        fills.append(blend(theme["--preview-fill"], theme["--canvas"]))
        for lamp in ("--lamp-on", "--lamp-off", "--route"):
            for fill in fills:
                assert contrast(theme[lamp], fill) >= 3.0, (lamp, fill)


def test_the_preview_tokens_are_the_frames_values():
    assert (LIGHT["--preview-fill"], LIGHT["--preview-line"]) == ("#a4422612", "#a4422680")
    assert (DARK["--preview-fill"], DARK["--preview-line"]) == ("#f09a7c10", "#f09a7c80")
    for name in ("--dim", "--preview-fill", "--preview-line"):
        assert DARK_AUTO[name] == DARK_RULE[name]


def test_facts_text_is_readable_in_details_in_both_themes():
    # A fact's label is --ink-3 and an accent value is --route, on the modal drawer (the raised
    # panel) and on the floating panel (the panel).
    for theme in (LIGHT, DARK):
        for ink in ("--ink-3", "--route"):
            for fill in ("--panel-raised", "--panel"):
                assert contrast(theme[ink], theme[fill]) >= 4.5, (ink, fill)


def test_a_fact_in_amber_is_readable_in_details_in_both_themes():
    # A tool that may write says so in amber (--lamp-warn), on both panels.
    assert ".facts dd.warn { color: var(--lamp-warn); }" in CSS
    for theme in (LIGHT, DARK):
        for fill in ("--panel-raised", "--panel"):
            assert contrast(theme["--lamp-warn"], theme[fill]) >= 4.5, fill


def test_the_find_chip_and_a_lit_list_row_are_readable_in_both_themes():
    # The chip sits on the search box (--inset); a lit List row's quiet words sit on the accent
    # tint and are --ink-2 there.
    assert ".tg-row.found .meta, .tg-row.found .tg-tools { color: var(--ink-2); }" in CSS
    # A match's own words stay --ink, never weaker than the rest. A group row is never a match, so
    # it needs no rule of its own.
    assert ".tg-row.group.found" not in CSS
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


def test_the_edge_of_an_unticked_check_or_radio_keeps_3_to_1_in_both_themes():
    # WCAG 1.4.11: the boundary of a control needs 3:1. --lamp-off draws it on every fill a control
    # can sit on (the drawer is --panel-raised); --link is for map lines and is under 3:1 on the
    # panel.
    for theme in (LIGHT, DARK):
        for fill in ("--panel", "--panel-raised", "--inset", "--dim", "--canvas", "--route-soft"):
            assert contrast(theme["--lamp-off"], theme[fill]) >= 3.0, (fill, theme["--lamp-off"])
    for selector in (".chk {", ".radio {"):
        assert "border: 1.5px solid var(--lamp-off);" in block(selector), selector


def test_mockup_tokens_are_there():
    assert DARK["--out"] == "#0d0f13" and LIGHT["--out"] == "#e4e7ec"
    assert DARK["--wire"] == "#3b424d" and LIGHT["--wire"] == "#e1e4e9"
    assert DARK["--link"] == "#59616f" and LIGHT["--link"] == "#c3c8d0"
    assert DARK["--lamp-warn"] == "#eac27c" and LIGHT["--lamp-warn"] == "#97590a"
    # The dark off lamp is a hair lighter than the mockup's #6b7381, so an empty box keeps 3:1.
    assert DARK["--lamp-off"] == "#707886" and LIGHT["--lamp-off"] == "#80868f"
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


def test_a_quiet_flag_in_a_selected_row_is_readable_in_both_themes():
    # The row is on the accent tint, and the flag's soft fill is a 60% mix of the line over that
    # tint. --ink-3 falls just under 4.5:1 there in the light theme, so the flag uses --ink-2.
    assert '.tg-row[aria-selected="true"] .flag.info { color: var(--ink-2); }' in CSS
    for theme in (LIGHT, DARK):
        fill = over(theme["--wire"], 0.6, theme["--route-soft"])
        assert contrast(theme["--ink-2"], fill) >= 4.5, fill
    assert contrast(LIGHT["--ink-3"], over(LIGHT["--wire"], 0.6, LIGHT["--route-soft"])) < 4.5


def test_the_tray_bar_is_readable_in_both_themes():
    # A row sits on the preview fill over the panel: its icon is the accent, its line --ink-3 and
    # its check the success green. A refusal in the bar's line sits on the panel itself.
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        row = blend(theme["--preview-fill"], theme["--panel"])
        for ink in ("--ink", "--ink-3", "--route", "--success"):
            assert contrast(theme[ink], row) >= 4.5, (ink, row)
        for ink in ("--ink-3", "--route"):
            assert contrast(theme[ink], theme["--panel"]) >= 4.5, ink
    assert ".dock .bar small.bad { color: var(--route); }" in CSS
    # Applied is green with the label that was checked for it.
    rule = block(".dock .btn.ok, .dock .btn.ok:hover {")
    assert "background: var(--success);" in rule and "color: var(--on-success);" in rule


def test_a_tools_read_or_write_word_is_readable_on_a_lit_or_selected_row():
    # It is quiet (--ink-3) on the row, one step darker on the accent tint.
    quiet = '.tg-row.found .hint, .tg-row[aria-selected="true"] .hint'
    assert f"{quiet} {{ color: var(--ink-2); }}" in CSS
    for theme in (LIGHT, DARK):
        assert contrast(theme["--ink-3"], theme["--panel"]) >= 4.5
        assert contrast(theme["--ink-2"], theme["--route-soft"]) >= 4.5


def test_the_add_panel_rows_are_readable_in_both_themes():
    # A row sits on the panel fill; one in preview (.on) on the accent tint with an accent edge.
    # A greyed row (.off) fades only its tile: its name and its small line (a refusal's reason)
    # are --ink-3, so they stay readable. "Added" is green text (--diff-add).
    assert ".res { display: flex;" in CSS and "background: var(--panel);" in block(".res {")
    assert ".res.on { border-color: var(--route); background: var(--route-soft); }" in CSS
    assert ".res.on .st { color: var(--route); }" in CSS
    assert ".res.off .itile { opacity: 0.55; }" in CSS
    assert ".res.off .tx b { color: var(--ink-3); }" in CSS
    assert ".res .tx small { color: var(--ink-3); font-size: 11px; }" in CSS
    assert ".res .st { flex: none; color: var(--ink-4); font-size: 11px; }" in CSS
    assert ".res.done .st { color: var(--diff-add); }" in CSS
    # No rule draws a whole row, or its words, fainter, but a row while it is dragged: its ghost,
    # at full strength, carries its words then.
    assert not re.search(r"\.res(\.off)?(:hover)?\s*(,[^{]*)?\{[^}]*opacity", CSS)
    assert [m.group(0) for m in re.finditer(r"\.res[^{]*\{[^}]*opacity[^}]*\}", CSS)] == [
        ".res.off .itile { opacity: 0.55; }",
        ".res.dragging { opacity: 0.4; }",
    ]
    assert ".res.ghost.over { border-color: var(--route); background: var(--route-soft); }" in CSS
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        for ink in ("--ink", "--ink-3", "--route"):
            assert contrast(theme[ink], theme["--route-soft"]) >= 4.5, ink
        for ink in ("--ink", "--ink-3", "--ink-4", "--diff-add"):
            assert contrast(theme[ink], theme["--panel"]) >= 4.5, ink
        # The accent edge of a row in preview keeps 3:1 on the panel round it.
        for fill in ("--panel", "--panel-raised"):
            assert contrast(theme["--route"], theme[fill]) >= 3.0, fill


def test_the_unknown_lamp_keeps_3_to_1_on_every_block_fill_in_both_themes():
    # The Library map's Unknown lamp is a dashed --lamp-warn ring, on the same fills as the others.
    unk = ".lamp.unk, .mark.unk { background: transparent; border: 1.5px dashed var(--lamp-warn); }"
    assert unk in CSS
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        fills = [theme[f] for f in ("--panel", "--panel-raised", "--dim", "--route-soft")]
        fills.append(blend(theme["--preview-fill"], theme["--canvas"]))
        for fill in fills:
            assert contrast(theme["--lamp-warn"], fill) >= 3.0, fill


def test_the_overview_cards_and_captions_are_readable_in_both_themes():
    # A card's name is --ink and its line --ink-3 on the panel; the client tiles' and the icon
    # tile's edges are --wire. The "Needs attention" caption's icon is amber on the canvas, and
    # the notes and the foot are --ink-3 on the canvas.
    assert ".ov-card .ln { color: var(--ink-3);" in CSS
    assert '.ov-group[data-group="attention"] .ov-cap svg { color: var(--lamp-warn); }' in CSS
    assert "margin: 0 0 8px; color: var(--ink-2);" in block(".ov-cap {")
    for theme in (LIGHT, DARK, {**LIGHT, **DARK_AUTO}):
        for ink in ("--ink", "--ink-2", "--ink-3"):
            assert contrast(theme[ink], theme["--panel"]) >= 4.5, ink
            assert contrast(theme[ink], theme["--canvas"]) >= 4.5, ink
        assert contrast(theme["--lamp-warn"], theme["--canvas"]) >= 3.0
