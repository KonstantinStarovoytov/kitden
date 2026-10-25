"""Words and parts the design review (2026-10-18) removed from the page stay removed."""

import re
from pathlib import Path

from kitden.views.words import (
    AFTER_WORDS,
    LOADS_PLUGINS,
    READS_FOLDER,
    ROUTE_WORDS,
    STALE,
    STATE_WORDS,
    UNCHANGED,
)

STATIC = Path(__file__).parents[2] / "src/kitden/web/static"
INDEX = (STATIC / "index.html").read_text()


def script(name: str) -> str:
    return (STATIC / "js" / name).read_text()


PANEL = ("panel.js", "details.js", "tools.js", "review.js")


def panel() -> str:
    """The side panel's modules as one text, so a pin does not depend on which file holds it. The
    review bar on a map shares its Apply, so it is read too, and so is the tray, which reads how
    an Apply or an Undo ended."""
    return "\n".join(script(name) for name in (*PANEL, "tray.js", "map-review.js"))


def reviews() -> str:
    """The change review and the review bar on a map as one text: one module until Part 4."""
    return script("review.js") + "\n" + script("map-review.js")


def gw() -> str:
    """The Gateway page's modules as one text."""
    names = ("gateway.js", "gateway-details.js", "gateway-drag.js")
    return "\n".join(script(name) for name in names)


def test_the_side_panel_is_four_modules():
    shell = script("panel.js")
    for name in PANEL[1:]:
        assert (STATIC / "js" / name).exists() and f'from "./{name}"' in shell, name
    assert "function trapFocus" in shell and "function showReview" not in shell
    assert "function showDetails" in script("details.js")
    assert "function showReview" in script("review.js")


def test_details_sit_beside_the_page_without_a_scrim():
    shell = script("panel.js")
    assert "export const DOCK_MIN = 1024;" in shell and 'removeAttribute("aria-modal")' in shell
    details = script("details.js")
    assert "export function factsBlock(" in details and "export function detailsCard(" in details
    assert "#drawer.docked" in CSS and ".shell.docked" in CSS and ".facts" in CSS


def test_rail_counts_only_attention_and_changes():
    assert 'id="nav-attention"' in INDEX and 'id="nav-changes"' in INDEX
    assert "nav-items" not in INDEX and "nav-around" not in INDEX
    assert "around" not in script("app.js")


def test_overview_has_no_pills_bar_or_recent_changes():
    overview = script("overview.js")
    assert "Recent changes" not in overview
    assert '"Tested"' not in overview and '"Found"' not in overview
    assert '"bar"' not in overview


def test_library_has_no_legend_or_counts():
    text = script("library.js")
    assert "legend" not in text.lower()
    assert "×" not in text
    assert "Choose a project in Where" not in text


def test_gateway_has_no_entry_name_field_or_paths():
    text = gw()
    assert "Entry name" not in text
    assert "key in $" not in text
    assert "shortPath" not in text


def test_changes_rows_have_no_details_button():
    assert '"Details"' not in script("changes.js")


def test_rail_says_let_agents_read_this_setup():
    assert "Let agents read this setup" in INDEX
    assert "Agents can ask" not in INDEX and "show my setup" not in INDEX


def test_shell_words():
    assert "Appearance" in INDEX and "Dark theme" not in INDEX
    assert ">Project<" in INDEX or "Project</span>" in INDEX
    assert "Let agents read this setup" in INDEX and "Rescan" in INDEX


def rule(selector, css=None):
    """The declarations of the rule that starts a line with `selector`."""
    found = re.search(rf"^{re.escape(selector)} \{{([^}}]*)\}}", css or CSS, re.MULTILINE)
    assert found, selector
    return found.group(1)


def test_the_theme_button_says_appearance_and_its_hover_names_the_other_theme():
    app = script("app.js")
    assert 'id="theme"' in INDEX and "Light theme" not in app and "Dark theme" not in app
    assert "Switch to light theme" in app and "Switch to dark theme" in app
    # The stored choice and the circle that spreads stay.
    assert 'const THEME_KEY = "kitden-theme";' in app
    assert "localStorage.setItem(THEME_KEY, next)" in app
    assert 'transition(() => applyTheme(next), "theme-switch")' in app
    # The button's words never change, so applyTheme must not rewrite its text (it holds the icon).
    assert '$("#theme").textContent' not in app


def test_the_shell_draws_its_icons_and_the_hint_line_sets_its_words_at_once():
    app, parts = script("app.js"), script("parts.js")
    for name in ("house", "library", "network", "history", "sun-moon", "search", "folder", "info"):
        assert f'icon("{name}"' in app + parts, name
    for name in ("chevron-down", "folder", "layers"):
        assert f'icon("{name}"' in parts, name
    assert 'id="hint"' in INDEX and "hidden" in INDEX.split('id="hint"')[1].split(">")[0]
    # setHint lives in parts.js, so a page can import it without a cycle (parts.test.mjs runs it).
    assert "export function setHint" in parts and "export function setHint" not in app
    assert re.search(r'import \{[^}]*\bsetHint\b[^}]*\} from "./parts.js"', app)
    # A page starts without its predecessor's hint.
    assert 'setHint("")' in app.split("function renderPlace")[1].split("\n}\n")[0]
    assert "pointer-events: none" in rule(".hint-dock")


def test_markers_re_seat_when_a_font_finishes_loading():
    # Pills and the rail marker are measured in text; a late font changes the widths. motion.js
    # puts every marker back on a resize, so a font that arrives sends one.
    app = script("app.js")
    resize = 'dispatchEvent(new Event("resize"))'
    assert f'document.fonts?.addEventListener("loadingdone", () => {resize})' in app
    assert 'addEventListener("resize"' in script("motion.js")


def test_the_page_hint_line_has_its_own_class_and_the_tool_word_stays_in_its_row():
    # tools.js calls a tool's "Read" or "Write" word `hint`. A page-wide `.hint` rule once pulled
    # every such word out of its row, so the page's line is `.hint-line` and `.hint` stays free.
    assert 'class="hint-line" id="hint"' in INDEX
    assert not re.search(r"^\.hint[ ,{]", CSS, re.MULTILINE)
    assert "position: absolute" in rule(".hint-line")
    assert "position" not in rule(".layer.tool .hint")
    for selectors, body in re.findall(r"^([^{}\n]*\.hint)\s*\{([^}]*)\}", CSS, re.MULTILINE):
        assert "position" not in body, selectors


def test_the_shell_is_a_frame_on_the_out_colour():
    assert "background: var(--out)" in rule("body") and "padding" in rule("body")
    assert "env(safe-area-inset-left" in rule("body")
    frame = rule(".shell")
    for part in (
        "148px",
        "1px solid var(--wire)",
        "border-radius: 12px",
        "overflow: hidden",
        "var(--canvas)",
    ):
        assert part in frame, part
    rail = rule(".rail")
    for part in ("background: var(--panel)", "gap: 26px", "padding: 20px 12px 18px"):
        assert part in rail, part
    assert "font-size: 19px" in rule(".brand") and "width: 28px" in rule(".brand-mark")
    link = rule(".nav a")
    for part in ("height: 38px", "padding: 0 10px", "border-radius: 8px", "gap: 10px"):
        assert part in link, part
    mark = rule(".nav .ink")
    assert (
        "color-mix(in srgb, var(--route) 30%, transparent)" in mark
        and "inset 2px 0 0 var(--brand)" in mark
    )
    assert "font-size: 11px" in rule(".rail-foot") and "font-size: 12px" in rule(".appearance")


def test_the_top_bar_and_the_page_head_have_the_mockups_sizes():
    bar = rule(".topbar")
    for part in ("height: 66px", "background: var(--panel)", "gap: 18px", "padding: 0 18px 0 22px"):
        assert part in bar, part
    assert "box-shadow" not in rule(".search") and "border: 0" in rule(".search")
    assert "font-size: 12px" in rule(".search input")
    assert "padding: 26px 22px 64px" in rule(".page")
    assert "font-size: 24px" in rule(".page h1") and "letter-spacing: -0.018em" in rule(".page h1")
    assert "font-size: 12px" in rule(".lede") and "color: var(--ink-3)" in rule(".lede")
    scope = rule(".scope-bar")
    assert "font-size: 11px" in scope and "gap: 6px" in scope
    # The List header sticks right under the top bar.
    assert "top: 66px" in rule(".map th")


def test_a_narrow_window_turns_the_rail_into_a_top_row_and_hides_the_labels():
    narrow = CSS.split("@media (max-width: 900px) {")[1].split("\n}\n")[0]
    assert "grid-template-rows: auto minmax(0, 1fr)" in narrow
    assert re.search(r"\.rail \{[^}]*flex-direction: row", narrow)
    # Hidden to the eye, still heard: the links keep their names.
    assert re.search(r"\.rail \.label[^{]*\{[^}]*clip", narrow)
    assert re.search(r"\.page \{[^}]*padding: 16px 16px 40px", narrow)


def test_buttons_have_the_mockups_look():
    btn = rule(".btn")
    for part in (
        "padding: 7px 12px",
        "border-radius: 7px",
        "border: 1px solid var(--wire)",
        "background: var(--panel-raised)",
        "font-size: 12px",
        "font-weight: 500",
        "transform 260ms var(--spring)",
    ):
        assert part in btn, part
    assert "color-mix(in srgb, var(--route) 40%, var(--wire))" in rule(".btn:hover:not(:disabled)")
    assert "scale(0.97)" in rule(".btn:active:not(:disabled)")
    assert "font-weight: 600" in rule(".btn.primary")
    # A small button is still at least 24 px tall, though its text is 11 px.
    small = rule(".btn.small")
    for part in ("padding: 4px 9px", "font-size: 11px", "min-height: 24px"):
        assert part in small, part
    # A ghost button keeps no line on hover; Applied is green all round.
    assert "border-color: transparent" in rule(".btn.ghost:hover:not(:disabled)")
    assert "border-color: var(--success)" in rule(
        ".btn.primary.done, .btn.primary.done:hover, .btn.primary.done:disabled"
    )


def test_the_pill_is_the_mockups_segmented_control_and_glides_in_280_ms():
    seg = rule(".seg")
    for part in (
        "gap: 2px",
        "padding: 2px",
        "background: var(--inset)",
        "border: 1px solid var(--wire)",
        "border-radius: 7px",
    ):
        assert part in seg, part
    choice = rule(".seg button")
    for part in (
        "padding: 4px 11px",
        "border-radius: 5px",
        "font-size: 12px",
        "color: var(--ink-3)",
    ):
        assert part in choice, part
    pressed = rule('.seg button[aria-pressed="true"]')
    assert "color: var(--ink)" in pressed and "font-weight: 500" in pressed
    marker = rule(".seg .ink")
    assert "background: var(--panel-raised)" in marker and "0 1px 2px rgb(0 0 0 / .25)" in marker
    # Every pill passes the pill time to glide (the rail and the tabs keep the 300 ms default).
    assert len(re.findall(r"\{ duration: 280 \}", script("gateway.js"))) == 1
    assert len(re.findall(r"\{ duration: 280 \}", script("library.js"))) == 2
    assert '"gateway-view", { duration: 280 }' in script("gateway.js")
    assert '"library-show", { duration: 280 }' in script("library.js")


def test_the_chip_is_the_mockups_label_and_a_client_with_its_name_is_a_who():
    chip = rule(".chip")
    for part in (
        "font-size: 11px",
        "color: var(--ink-3)",
        "border: 1px solid var(--wire)",
        "border-radius: 6px",
        "padding: 3px 8px",
    ):
        assert part in chip, part
    assert "display: inline-flex" in rule(".who")
    for name in ("agents.js", "details.js", "overview.js", "library.js", "review.js"):
        assert '"chip"' not in script(name), name
    assert 'el("div", "who")' in script("agents.js") and 'el("span", "who")' in script("review.js")


def test_lamps_marks_and_ports_follow_one_lamp_language():
    lamp = rule(".lamp, .mark")
    for part in (
        "width: 6px",
        "height: 6px",
        "border-radius: 50%",
        "background: var(--lamp-off)",
        "background-color 400ms ease",
    ):
        assert part in lamp, part
    assert "background: var(--lamp-on)" in rule(".lamp.on, .mark.on")
    assert "background: var(--lamp-warn)" in rule(".lamp.warn, .mark.warn")
    preview = rule(".lamp.pv, .mark.pv")
    assert "background: transparent" in preview and "1.5px dashed var(--route)" in preview
    outside = rule(".lamp.out, .mark.out")
    assert "background: transparent" in outside and "1.5px solid var(--lamp-off)" in outside
    # A lamp that turns on pops from 2.2 times its size, on the calm curve.
    pop = rule(".lamp.pop, .mark.pop")
    assert "200ms var(--calm)" in pop and "lamp-pop" in pop
    assert "@keyframes lamp-pop { from { transform: scale(2.2); } }" in CSS
    port = rule(".port")
    for part in (
        "width: 9px",
        "height: 9px",
        "1.5px solid var(--link)",
        "background: var(--canvas)",
    ):
        assert part in port, part
    assert "scale 300ms var(--spring)" in port
    # --lamp-off fails 4.5:1 as text: it is a fill and a line here, never a text color.
    assert not re.search(r"[^-]color: var\(--lamp-off\)", lamp + preview + outside + port)


def test_the_switch_is_a_34_by_20_track_in_a_24_px_button_with_a_14_px_knob():
    button = rule(".switch")
    for part in ("width: 34px", "height: 24px", "background: none"):
        assert part in button, part
    track = rule(".switch::before")
    for part in (
        "inset: 2px 0",
        "border-radius: 10px",
        "border: 1px solid var(--wire)",
        "background: var(--inset)",
        "background-color 250ms ease",
    ):
        assert part in track, part
    knob = rule(".switch .thumb")
    for part in (
        "width: 14px",
        "height: 14px",
        "top: 5px",
        "left: 3px",
        "background: var(--ink-3)",
        "transform 340ms var(--spring)",
    ):
        assert part in knob, part
    on_track = rule('.switch[aria-checked="true"]::before')
    assert "background: var(--route)" in on_track and "border-color: var(--route)" in on_track
    on_knob = rule('.switch[aria-checked="true"] .thumb')
    assert "translateX(14px)" in on_knob and "background: #fff" in on_knob
    # Waiting for the preview: a dashed track on the accent tint, the knob half-way, in the accent.
    wait_track = rule('.switch.pending::before, .switch[aria-checked="true"].pending::before')
    for part in (
        "border-style: dashed",
        "background: var(--route-soft)",
        "border-color: var(--route)",
    ):
        assert part in wait_track, part
    wait_knob = rule('.switch.pending .thumb, .switch[aria-checked="true"].pending .thumb')
    assert "translateX(7px)" in wait_knob and "background: var(--route)" in wait_knob
    # The thumb no longer widens under a press: the knob's own move is the answer.
    assert ".switch:active" not in CSS


def test_checks_and_radios_follow_the_mockup():
    chk = rule(".chk")
    for part in (
        "width: 16px",
        "height: 16px",
        "border-radius: 4px",
        "border: 1.5px solid var(--lamp-off)",
    ):
        assert part in chk, part
    tick = rule(".chk .ic")
    for part in ("opacity: 0", "scale(0.5)", "opacity 160ms", "transform 320ms var(--spring)"):
        assert part in tick, part
    ticked = rule("input:checked + .chk, .pick.on .chk")
    assert "background: var(--route)" in ticked and "border-color: var(--route)" in ticked
    assert "opacity: 1" in rule("input:checked + .chk .ic, .pick.on .chk .ic")
    radio = rule(".radio")
    for part in (
        "width: 14px",
        "height: 14px",
        "border-radius: 50%",
        "border: 1.5px solid var(--lamp-off)",
    ):
        assert part in radio, part
    picked = rule(".pick.on .radio")
    assert "background: var(--route)" in picked and "inset 0 0 0 3px var(--panel)" in picked
    # The unticked edge is --lamp-off, which keeps 3:1 (test_contrast.py); --link is for map lines.
    assert "--link" not in chk + radio
    # The picker row's own box waits for the tool picker; only the ticked looks are here.
    assert not re.search(r"^\.pick( |:)", CSS, re.MULTILINE)
    assert "accent-color" not in CSS
    # A real checkbox keeps its input for the keys; only its box is drawn. Add missing uses it too.
    assert "checkBox(" in script("review.js") and 'type = "checkbox"' not in script("review.js")


def test_changes_say_why_a_change_stopped():
    text = script("changes.js")
    assert "Can't undo: the file changed after this" in text
    assert "Not applied: the file changed before Apply" in text
    assert "Stopped: file changed" not in text and "Undo stopped" not in text


def test_project_picker_says_project_not_where():
    assert 'aria-label="Project"' in INDEX and "Where:" not in INDEX and "<select" not in INDEX
    app, parts = script("app.js"), script("parts.js")
    assert "projectMenu(" in app and "No project" not in app and "Global" not in app
    for words in (
        '"Find a project…"',
        '"What applies in every project"',
        '"own rule", "own rules"',
        '"Folder missing"',
        '"No longer on the list"',
    ):
        assert words in parts, words
    assert 'export const ALL_PROJECTS = "All projects";' in parts
    assert "outside any project" not in script("library.js")


def test_the_project_menu_keeps_paths_off_the_page_and_the_keys_in_the_find_box():
    menu = script("parts.js").split("export function projectMenu")[1].split("\n}\n")[0]
    assert "path" not in menu and "title" not in menu
    for part in ('role", "listbox"', "aria-activedescendant", "stopPropagation()", "pointerdown"):
        assert part in menu, part
    assert ".where-box select" not in CSS


def test_the_project_menu_looks_like_the_mockups():
    menu = rule(".where-menu")
    for part in (
        "width: 300px",
        "padding: 6px",
        "border: 1px solid var(--wire)",
        "border-radius: 10px",
        "background: var(--panel)",
        "box-shadow: var(--shadow)",
    ):
        assert part in menu, part
    option = rule(".where-option")
    for part in ("padding: 8px 10px", "border-radius: 7px", "gap: 10px", "color: var(--ink-2)"):
        assert part in option, part
    assert "background: var(--dim)" in rule(".where-option:hover, .where-option.active")
    # The dim fill is faint, so the option the arrows are on also gets a ring that keeps 3:1.
    assert "inset 0 0 0 1px var(--lamp-off)" in rule(".where-option.active")
    picked = rule('.where-option[aria-selected="true"]')
    assert "background: var(--route-soft)" in picked and "color: var(--ink)" in picked
    # The count is accent at 11 px, the sub line quiet at 11 px, the check accent.
    count = rule(".where-count")
    assert "color: var(--route)" in count and "font-size: 11px" in count
    sub = rule(".where-sub")
    assert "color: var(--ink-3)" in sub and "font-size: 11px" in sub
    assert "color: var(--route)" in rule(".where-check")


def test_the_project_button_is_drawn_in_one_place():
    # index.html keeps only the words for the first paint. The icons come from parts.js, for the
    # button the page draws before the list is read and for the one projectMenu draws.
    app, parts = script("app.js"), script("parts.js")
    assert "export function projectButton(" in parts
    drawn = app.split("function drawIcons")[1].split("\n}\n")[0]
    assert "projectButton(" in drawn
    assert '"folder"' not in drawn and '"chevron-down"' not in drawn


def test_the_details_choice_has_the_menus_rows():
    # The project choice in a Details column builds its rows with the menu's own parts.
    assert "export function optionParts(" in script("parts.js")
    assert "optionParts(" in script("details.js")


def test_python_and_page_state_words_agree():
    parts = script("parts.js")
    for state, word in STATE_WORDS.items():
        assert f'{state}: "{word}"' in parts, state


def test_one_phrase_says_cursor_loads_claude_codes_plugins():
    from kitden.views import after, commands
    from kitden.views.words import LOADS_PLUGINS

    notes = (after.CURSOR_IMPORT["note"], after.CURSOR_REMOVE["note"], after.CURSOR_KEEPS)
    for text in (*notes, commands.CURSOR_LOADS_CLAUDE):
        assert text.startswith(f"{LOADS_PLUGINS},") or text.startswith(f"{LOADS_PLUGINS} "), text
    # Built on the one phrase, not a copy of it.
    assert "Claude Code's plugins" not in Path(commands.__file__).read_text()


def test_python_and_page_origin_words_agree():
    from kitden.views.words import ORIGIN_WORDS

    parts = script("parts.js")
    assert ORIGIN_WORDS == {"override": "This project", "project": "Only this project"}
    for origin, word in ORIGIN_WORDS.items():
        assert f'{origin}: "{word}"' in parts, origin
    # The old tag word is gone; only the scope bar's sentence (S.7) says "project overrides".
    text = parts + script("library.js") + panel()
    assert "project override" not in text.replace("project overrides stay separate", "")


def test_a_cell_draws_its_tag_in_the_accent_family():
    assert 'el("span", "tag", where)' in script("parts.js")
    css = (STATIC / "style.css").read_text()
    assert ".socket .tag { color: var(--route); background: var(--route-soft);" in css
    assert ".socket .where" not in css


def test_python_and_page_route_words_agree():
    parts = script("parts.js")
    for route, words in ROUTE_WORDS.items():
        assert f'{route}: "{words}"' in parts, route


def test_after_words_come_from_the_one_table():
    from kitden.views import after

    assert not hasattr(after, "WORDS")
    assert AFTER_WORDS["plugin.enable"] == ("on", "On")
    assert AFTER_WORDS["gateway.move"] == ("gw", STATE_WORDS["gw"])
    assert after.CURSOR_IMPORT["word"] == "On"


def test_gateway_names_the_remove_action_and_draws_no_idle_wire():
    text = gw()
    assert "Remove direct entry…" in text
    assert "wire idle" not in text
    assert "goes around" not in text


def test_gateway_rows_keep_addresses_behind_a_details_button():
    # A List row ends with the quiet chevron; its address waits in Details.
    assert "opens()" in script("gateway.js")
    assert "row.summary" not in gw()


def test_gateway_says_its_lists_are_mcp_servers():
    assert '"Outside the gateway · calls skip Kitden\'s rules"' in gw()


def test_gateway_wires_do_not_fake_traffic():
    # A link moves only when it comes, goes or changes look; nothing loops, as Kitden cannot
    # see traffic.
    css = (STATIC / "style.css").read_text()
    assert not any(
        ("map" in line or ".routes" in line) and "infinite" in line for line in css.splitlines()
    )
    for name in ("gateway.js", "gateway-details.js", "gateway-drag.js", "map.js", "map-view.js"):
        assert "flow" not in script(name), name


def test_a_link_says_what_its_x_does():
    assert "} from the gateway`" in gw() and "`Turn off ${" in gw()
    view = script("map-view.js")
    assert "} to ${" in view and '"Connections"' in view and '"aria-keyshortcuts", "Delete"' in view


def test_a_pointed_link_keeps_its_look_in_a_search():
    rule = "div.map.finding .link.hov, div.map.finding .link.picked { stroke-opacity: 1; }"
    assert rule in CSS
    assert CSS.index("div.map.finding .link { stroke-opacity: 0.25; }") < CSS.index(rule)


def test_a_dragged_block_takes_the_pointer_off_every_link():
    # While a block is dragged no link takes the pointer, or the × would show under the block.
    assert "pointer-events: none" in rule(".grabbing .map-hits .hit")


def test_a_new_map_reads_its_width_before_its_first_draw():
    # Else the observer's first report flips it to narrow with no motion in its entrance.
    gateway = script("gateway.js")
    body = gateway.split("function gatewayMap(")[1].split("\n}\n")[0]
    assert (
        body.index("main.append(onMap.view.box)")
        < body.index("contentWidth(")
        < body.index("drawOnMap(")
    )


def test_the_gateway_rises_on_its_own_when_the_place_changes():
    assert "html.map-entrance::view-transition-new(page) { animation: none; }" in CSS
    # The old and new root do not cross-fade either: only the head and the map rise.
    root = (
        "html.map-entrance::view-transition-old(root), html.map-entrance::view-transition-new(root)"
    )
    assert root + " { animation: none; }" in CSS
    assert '"map-entrance"' in script("store.js")
    # A redraw of the same page does not lift the head again.
    assert "if (!again) riseHead(" in script("gateway.js")


def test_the_map_rules_never_reach_the_library_table():
    # The Library's table has the class "map" too, so every rule of the map names its box.
    css = (STATIC / "style.css").read_text()
    block = css.split("/* Map (map.js)")[1].split("\n\n")[0]
    rules = [line for line in block.splitlines() if "{" in line]
    assert rules and all(line.startswith("div.map") for line in rules)
    assert not re.search(r"^\.map\s*\{", css, re.MULTILINE)


def test_the_gateway_page_takes_the_whole_width():
    assert '.page[data-place="gateway"] { max-width: none; }' in CSS
    assert "main.dataset.place = state.view" in script("app.js")


def test_the_map_marks_when_it_is_drawn():
    assert '"kitden:map-drawn"' in script("map-view.js") and '"kitden:gateway-drawn"' in script(
        "gateway.js"
    )


def test_the_map_words():
    # A group over six shows five and "N more"; the outside group says why it is apart.
    assert '"Outside the gateway · calls skip Kitden\'s rules"' in script("gateway.js")
    assert " more`" in script("map.js")
    # The map shows no state word; a screen reader hears one, the same as the words it shows.
    states = 'STATE_SAID = { on: "On", off: "Off", unk: "Not known", preview: "Preview" }'
    assert states in script("map.js")


def test_the_map_says_the_link_is_the_state():
    text = gw() + script("map.js")
    for words in (
        '"Clients"',
        '"Gateway"',
        '"Servers"',
        '"Tools"',
        '"Connected"',
        '"Not connected"',
        "Found · ${",
        '"Found"',
        '"No gateway yet"',
        '"One place for servers, rules and logins."',
        '"Set up…"',
        "more`",
        "In ${",
    ):
        assert words in text, words
    assert "ResizeObserver" in script("gateway.js") and "unfoldDelays(" in script("map.js")
    # A line that skips the gateway is grey dots, amber under the pointer.
    direct = rule("div.map .link.direct")
    assert "var(--lamp-off)" in direct and "stroke-dasharray: 1.5 4" in direct
    assert "stroke-opacity: 0.8" in direct
    assert "var(--lamp-warn)" in rule("div.map .link.direct.hov, div.map .link.direct.picked")
    preview = rule("div.map .link.preview")
    assert "stroke-dasharray: 4 4" in preview and "stroke-opacity: 0.65" in preview
    assert "stroke-opacity: 0.4" in rule("div.map .link.leaving")
    # A search dims every link, a lit bypass line too (it is lit at full strength otherwise).
    assert "stroke-opacity: 0.25" in rule("div.map.finding .link")
    assert "stroke-opacity: 0.25" in rule("div.map.finding .link.direct.lit")
    # A line to a server Kitden does not know to be on is dashed: it does not say "on".
    assert "div.map .link.direct.unk { stroke-dasharray: 3 3; }" in CSS
    assert 'const NOT_KNOWN = "Not known";' in script("gateway.js")
    # A block says whether it is open by what is open, not by what shows yet.
    assert 'setAttribute("aria-expanded", String(open.has(' in script("map-view.js")


def test_a_selection_dims_what_is_off_its_path():
    assert "filter: opacity(0.4) saturate(0.6)" in rule(
        "div.map.focus .block:not(.lit):not(.selected)"
    )
    assert "stroke-opacity: 0.16" in rule("div.map.focus .link:not(.lit)")
    assert "stroke-width: 2.1" in rule("div.map .link-over")
    # A block that is dragged, and a block with keyboard focus, keep their ring and look at full
    # strength. Both repeat the dim rule's selector, or it would win.
    for selector in (
        "div.map.focus .block.dragging:not(.lit):not(.selected)",
        "div.map.focus .block:focus-visible:not(.lit):not(.selected)",
    ):
        assert "filter: none" in rule(selector)
        assert CSS.index(selector + " {") > CSS.index(
            "div.map.focus .block:not(.lit):not(.selected) {"
        )
    # An overlay's wait is a real time, scaled back so that the animation scales it only once.
    assert "delay: unscaled(" in script("map-view.js")


def test_a_press_scales_a_block_about_its_own_middle():
    # The `scale` of a press turns about the block's middle only when the block's place is the
    # `translate` property (map-view.test.mjs checks that `put` writes it so).
    assert "scale: 0.98" in rule("div.map .block:active")


def test_plugin_switch_opens_a_review_and_does_not_flip_itself():
    text = panel()
    assert 'setAttribute("role", "switch")' in text
    assert text.count('"aria-checked"') == 1


def test_details_offer_remove_for_plugins_and_skills():
    text = panel()
    # A Remove names every client it reaches: "Remove from Codex and Cursor…".
    assert '"plugin.remove": (clients) => `Remove from ${clients}…`' in text
    assert '"skill.remove": (clients) => `Remove from ${clients}…`' in text
    assert "def.affects.clients" in script("details.js")


# Motion pass 2 (2026-10-18): each page keeps the parts the design brief asked for.
CSS = (STATIC / "style.css").read_text()


def test_controls_press_and_the_switch_waits_for_the_preview():
    assert ".switch.pending" in CSS
    assert ".seg button:active" in CSS and ".tabs button:active" in CSS
    text = panel()
    assert 'classList.add("pending")' in text and 'setAttribute("aria-busy", "true")' in text


def test_client_tile_flies_to_its_library_column():
    overview = script("overview.js")
    assert "fly(tile, `client-${clientId}`)" in overview
    assert "land(tile, `client-${column.id}`)" in script("library.js")
    # The tab is read before the place changes, so its table is drawn where the tile can land.
    count = overview.split("function loadsLine")[1].split("\n}\n")[0]
    assert count.index("await loadLibraryFor(choice);") < count.index("fly(tile")
    card = overview.split("async function follow")[1].split("\n}\n")[0]
    assert card.index("await loadLibraryFor(libraryChoice(sel));") < card.index('goTo("library"')


def test_review_counts_the_diff_and_folds_the_file_change():
    text = panel()
    assert "diffCounts" in text and "fold(files)" in text
    assert "Show file change" in text and "Show file changes" in text


def test_apply_turns_green_only_after_verified_and_only_ok_toasts_get_a_check():
    text = panel()
    assert text.index('after.state !== "verified"') < text.index('apply.classList.add("done")')
    assert text.count("{ ok: true }") == 2
    assert "Undone. The previous settings are back." in text
    assert 'toast("Undo stopped' in text  # a stopped undo gets no check


def test_one_mark_slides_between_the_choices_of_a_group():
    assert 'glide($(".nav")' in script("app.js")
    text = script("library.js")
    assert '"library-tabs"' in text and '"library-show"' in text
    assert "tab-ink" not in CSS and "tab-ink" not in text


def test_gateway_list_is_a_tree_grid_the_keys_move_through():
    # The List is a tree grid: the arrows move, Right opens, Left closes (dom.js gridKey).
    text = script("gateway.js")
    assert 'setAttribute("role", "treegrid")' in text and "gridKey(" in text
    # "Connect clients" folds smoothly in a registered gateway's Details.
    assert "fold(box)" in gw()


def test_library_shows_one_flag_per_wording_and_resolved_flags_shrink_away():
    text = script("library.js")
    assert "findIndex((o) => o.text === f.text)" in text
    assert 'classList.add("gone")' in text and ".flag.gone" in CSS


def test_scope_switch_marks_the_project_picker_and_the_lede():
    assert 'classList.toggle("project"' in script("app.js")
    assert ".where-box.project" in CSS
    assert 'classList.add("fresh")' in script("library.js")
    # The Gateway says the scope under its head; the bar is accent with a project.
    assert "scopeBar(" in script("gateway.js") and ".scope-bar.project" in CSS
    parts = script("parts.js")
    # Kitden counts only the gateway's rules: it never claims a project follows the shared setup.
    assert "follows the shared setup" not in parts
    for words in (
        '"Shared setup · project overrides stay separate"',
        '"rule differs", "rules differ"',
        "· no rules of its own`",
        "· rules not known`",
    ):
        assert words in parts, words


def test_reduced_motion_turns_every_animation_off():
    assert "prefers-reduced-motion: reduce" in CSS
    assert "reducedMotion.matches" in script("motion.js")
    # A changed Library cell shows its new word at once (parts.test.mjs checks the swap).
    assert "reducedMotion.matches ? 0 : 260" in script("library.js")


def test_a_plugin_the_page_cannot_change_shows_a_locked_switch():
    text = panel()
    assert "node.disabled = true" in text
    assert "Not changed from here." in text


def test_library_lede_names_the_project_folder_not_its_path():
    text = script("library.js")
    assert "in the project" in text
    assert "shortPath" not in text


def test_item_details_ask_for_the_full_name_so_a_plugin_shows_only_its_own_marketplace():
    assert "name: row.lookup || row.name" in panel()


def test_changes_rows_open_the_panel_and_keep_paths_off_the_page():
    text = script("changes.js")
    assert "openChange" in text
    assert "change-detail" not in text and "aria-expanded" not in text


def test_overview_notes_are_rows_with_a_details_button():
    text = script("overview.js")
    assert '"Details"' in text
    assert "shortPaths" not in text


def test_note_flags_wrap_under_the_name_and_not_under_details():
    # An item with several notes puts the flags that do not fit on a second line.
    rule = next(line for line in CSS.splitlines() if line.startswith(".list-row .what {"))
    assert "flex-wrap: wrap;" in rule


# Feature 006: the gateway is managed from here --------------------------------------------


def test_gateway_offers_move_and_keeps_the_side_door_small():
    text = gw()
    assert "Move into the gateway…" in text
    assert "Move all ${" in text
    # A registered gateway's own page is one plain action in its Details, never the primary one.
    assert "`Open ${name} ↗`" in text


def test_gateway_form_never_takes_the_password_itself():
    text = gw()
    assert "Password variable name (not the password)" in text
    assert 'type: "password"' not in text


def test_moves_are_named_on_changes_and_in_the_review():
    assert '"gateway.move": "Moved into the gateway"' in script("parts.js")
    code = panel()
    assert "Move ${names} into the gateway" in code
    assert "into the gateway" in code


# Feature 007: an Obot gateway beside MetaMCP ---------------------------------------------


def test_gateway_form_takes_an_obot_key_variable_never_the_key():
    text = gw()
    assert 'path.startsWith("/mcp-connect/")' in script("parts.js")
    assert "Obot API key variable name (not the key)" in text
    assert "ok1-" not in text
    # The gateways that take a server are offered in order, never one picked silently.
    assert "moveTargets(model, key)" in text and "model.gateways.find((g) => g.movable)" not in text


def test_held_rows_say_remote_hosted_or_sse_and_keep_addresses_behind_details():
    text = gw()
    assert 'return "Hosted";' in text and 'return "Remote";' in text
    assert "Nothing yet. Add servers in ${gatewayName(gateway)} itself." in text


def test_a_gateway_the_clients_do_not_use_offers_to_take_them_over():
    text = gw()
    assert "Use this gateway…" in text and '"gateway.switch"' in text
    # The registered gateway the clients use comes first under the Kitden one (gatewayTree).
    assert "model.used.includes(b.id)" in script("gateway.js")


def test_diagram_nodes_open_the_client_apps_and_the_gateway():
    text = gw()
    # The scheme comes from the installed app, read by the server; none is hard-coded.
    for scheme in ('"claude://"', '"codex://"', '"cursor://"'):
        assert scheme not in text
    assert "found.app_url" in text
    assert 'window.open(page, "_blank", "noopener")' in text


def test_library_adds_plugins_and_marketplaces_in_one_review():
    offer, library = script("offer.js"), script("library.js")
    assert '"plugin.install"' in offer and '"marketplace.add"' in offer
    # Adding a marketplace lives on the Marketplaces tab.
    assert '"Add a marketplace…"' in library and 'kind === "marketplace"' in library
    assert '<a href="#library" data-view="library"><span class="label">Library</span></a>' in INDEX
    assert '["new", "New"]' in library and 'row.mine ? "Installed" : "New"' in library


def test_library_rows_say_what_each_client_has_or_can_add_without_details():
    text = script("library.js")
    # One cell per client: the server's state, or the one button for what it can add.
    assert (
        "socket({ state: cell.state, where: cell.where, word: cell.word, label: cell.reason, "
        "stale: Boolean(cell.stale_at) })" in text
    )
    assert "button(cell.add.label" in text and '"btn small add"' in text
    assert 'via: "Via Claude Code", done: "Has its skills"' in script("parts.js")
    assert 'el("table", "map library")' in text and '"desc"' in text
    # A category filter, fed by the counts the server sends.
    assert '"All categories"' in text and "answer.categories" in text
    # The row opens Details, so there is no Details button on it; only the box shown when no
    # client is found has one.
    assert text.count('"Details"') == 1 and 'button("Details", showLookFor' in text


# Skills beside Plugins ---------------------------------------------------------------------


def test_library_tabs_share_one_table_and_the_add_flow():
    text = script("library.js")
    assert '["plugin", "Plugins"], ["skill", "Skills"]' in text
    assert '"skill.install"' in script("offer.js") and '"Add skill"' in script("offer.js")
    # One row builder for every kind, one table.
    assert text.count("buildRow(") == 2 and text.count('el("table", "map library")') == 1
    assert 'show: s.show === "mine" ? "" : s.show' in script("store.js")


def test_skill_rows_say_where_each_skill_comes_from_and_how_each_client_loads_it():
    # Same-name rows show their source, so two skills or plugins with one name differ.
    assert "row.same_name ? row.source : null" in script("library.js")
    text = script("offer.js")
    assert '"Needs its plugin"' in text and '"Can add"' in text
    # The refusal, in the owner's words, and a way to the plugin that holds the skill.
    assert "This skill needs the rest of its plugin. Add the plugin instead." in text
    assert '"Find the plugin"' in text
    # Details list the files and mark the scripts the agent may run; paths stay in Details,
    # folded under Technical details.
    assert '"What it brings"' in text and '"script"' in text
    assert 'technical([{ title: "Skill folder", path: skill.path }])' in text
    assert '"Details"' not in text


def test_a_skill_copy_names_every_client_it_reaches():
    code = panel()
    assert "s.reaches || [s.client]" in code and "Add ${names} to ${clients}" in code
    assert "for (const note of notes) box.append(callout(note))" in code  # Cursor loads it twice
    assert '"skill.install": "Added skill"' in script("parts.js")


def test_add_forms_name_the_source_and_every_client_the_change_reaches():
    text = script("offer.js")
    # The server says whether Cursor loads what Claude Code has; the page does not guess.
    assert "offer.inherits" in text and "Source: " in text
    assert "Cursor will also load this through Claude Code." in text
    assert "Cursor will also load it from Claude Code's folder." in text


def test_library_rows_keep_the_name_and_the_source_readable():
    text, css = script("library.js"), (STATIC / "style.css").read_text()
    assert '["42%"' in text and 'el("small", "meta", meta)' in text
    assert ".library .desc" in css and "-webkit-line-clamp: 1" in css
    # The name takes its whole width first; the meta text gives way. (Flex shrank the name by a
    # fraction of a pixel too, which cut it with "…".)
    assert ".library .item { display: grid; grid-template-columns: minmax(3ch, max-content)" in css
    # The server marks rows that share a name; the page does not count names itself.
    assert "names.get" not in text
    # A cell's button names its row's source too, or twin rows would give two buttons one name.
    assert "addName(row, client, cell.add, state.project)" in text


def test_offer_details_and_add_form_follow_what_the_server_says_about_cursor():
    text = script("offer.js")
    # Details no longer claim a Cursor setting; the line shows only when Cursor would load it.
    assert "Cursor: loads it through Claude Code." in text and "Cursor: has it." in text
    assert "Cursor: gets it through Claude Code once you add it there." in text
    assert "cursorLine(offer, inherits(offer))" in text
    assert "Cursor: loads Claude Code plugins when" not in text
    assert "Cursor will also load it from the shared skills folder." in text
    # The note is a polite live region inside the form, before Preview.
    assert 'also.setAttribute("aria-live", "polite")' in text
    assert "[checks, note, submit, message]" in text


def test_a_lost_apply_answer_is_checked_not_guessed():
    text = panel()
    assert "Nothing was changed by this page" not in text
    assert "Could not confirm the result. Check Changes before trying again." in text
    assert "readChange(" in text


def test_changes_and_the_library_say_saved_settings_and_scope():
    assert "Based on saved settings." in script("library.js")
    changes = script("changes.js")
    assert "To take effect" in changes and 'user: "all projects"' in changes
    assert "global settings" not in changes
    assert '"everywhere"' not in changes
    assert "Tools · ${where || ALL_PROJECTS}" in panel()
    assert '"Nothing on here."' in script("overview.js")
    assert "Loads nothing" not in script("overview.js")


def test_changes_show_restart_notes_only_for_changes_that_happened():
    changes = script("changes.js")
    assert '["verified", "undone", "undo_blocked"].includes(entry.state)' in changes
    assert 'project: "this project"' in changes


def test_a_failed_refresh_says_when_the_shown_data_was_read():
    assert "Could not refresh. Showing what Kitden read at ${clock}." in script("parts.js")
    for name, model in (("overview.js", "overview"), ("gateway.js", "gateway")):
        text = script(name)
        assert f'current("{model}")' in text and f"staleNote(data.readAt.{model})" in text
    # The Library keeps its own answer, never another project's, and says when it was read.
    library = script("library.js")
    assert "cache.asked.project === state.project" in library
    assert "staleNote(cache.readAt)" in library
    assert '" · could not refresh"' in script("app.js")


def test_a_banner_retry_reads_everything_again():
    # So the rail's time and its "could not refresh" note are right after it (store.test.mjs).
    for name in ("library.js", "overview.js", "gateway.js", "changes.js", "agents.js"):
        text = script(name)
        assert re.search(r"banner\([^;]*, retry\)", text), name
        assert "render(); })" not in text, name
    # The drag left gateway.js; it holds no such retry either.
    assert "render(); })" not in script("gateway-drag.js")


def test_the_rail_time_follows_every_render_not_only_a_refresh():
    app = script("app.js")
    shell = app.split("function renderShell()")[1].split("\n}\n")[0]
    refresh = app.split("async function refresh(")[1].split("\n}\n")[0]
    assert '$("#scanned").textContent' in shell and "lastGoodRead" in shell
    assert "#scanned" not in refresh


def test_another_project_closes_the_panel():
    # Picked at the top, or by Back or an edited address (panel.test.mjs tests closeForProject).
    app = script("app.js")
    picker = app.split("function refreshForProject(")[1].split("\n}\n")[0]
    address = app.split("function fromAddress()")[1].split("\n}\n")[0]
    assert "closeForProject();" in picker and "closeForProject();" in address
    assert "setSwitcher(refreshForProject)" in app


def test_a_project_switch_marks_the_old_page_as_waiting():
    app = script("app.js")
    assert 'main.classList.add("pending")' in app
    assert 'main.setAttribute("aria-busy", "true")' in app
    assert ".finally(" in app and 'main.classList.remove("pending")' in app
    style = (STATIC / "style.css").read_text()
    assert ".page.pending { opacity: 0.5; pointer-events: none;" in style


def test_gateway_connect_form_serves_its_own_card_only():
    text = script("gateway-details.js")
    # The form is for the card's gateway; a client in any gateway is not offered again.
    assert "connectForm(gateway, waiting)" in text
    # The Kitden gateway holds other servers: its clients can connect to a registered one too.
    assert 'Object.entries(model.connections).filter(([id]) => id !== "kitden")' in text
    assert "connectForm(model.gateways" not in text


def test_direct_servers_are_options_and_details_offers_move_first():
    overview = script("overview.js")
    assert '"Can improve"' in overview and "model.suggestions" in overview
    assert ".issue.suggestion" in CSS
    code = panel()
    assert "Move into the gateway…" in code and 'action: "gateway.move"' in code
    # Without a gateway that takes servers, the panel says the same as the Gateway page.
    assert "Add the server in the gateway first" in script("parts.js")
    assert "GATEWAY_NOTE" in code and "GATEWAY_NOTE" in gw()
    # A gateway that could not be read says so, instead of hiding Move.
    assert "Could not read the gateway, so Move is not offered." in code
    # An option is quieter than a problem: a plain button, not the primary one.
    assert 'option ? "btn" : "btn primary"' in overview


def test_rows_say_they_open_details_and_search_names_its_scope():
    for name in ("library.js", "changes.js"):
        assert "opens()" in script(name)
    assert ".sr-only" in CSS
    # The chevron is quiet, and takes the accent when the row is hovered or focused.
    assert re.search(r"\n\.opens \{[^}]*color: var\(--ink-3\)", CSS)
    assert re.search(r"tr:hover \.opens[^{]*\{ color: var\(--route\)", CSS)
    assert "li:hover .opens" in CSS and "tr:focus-visible .opens" in CSS
    # One search for every place: the Library searches the setup and the marketplaces.
    # The placeholder trails off; the accessible name does not repeat the dots.
    assert 'placeholder="Search your setup and marketplaces…"' in INDEX
    assert 'aria-label="Search your setup and marketplaces"' in INDEX
    assert "Search plugins and skills to add" not in script("app.js")
    assert 'go("library", { q })' in script("app.js")
    assert "Find an item" not in INDEX


def test_focus_returns_to_the_control_and_the_review_reaches_its_summary():
    # The key and the tab keys live in dom.js, so every place shares them.
    assert "focusKey(" in script("app.js") and "dataset.focus" in script("dom.js")
    for key in ('"ArrowRight"', '"ArrowLeft"', '"Home"', '"End"'):
        assert key in script("dom.js")
    trap = panel().split("function trapFocus")[1].split("\n}")[0]
    assert "summary" in trap and "textarea" in trap and "getClientRects" in trap


def test_every_control_a_render_replaces_names_itself_for_focus():
    for name, keys in {
        "library.js": (
            "`tab:${id}`",
            "`show:${id}`",
            '"filter:category"',
            '"filter:attention"',
            "`add:${row.key}:${client}`",
            '"more:all"',
            '"add:marketplace"',
            "`hide:${column.id}`",
            '"hidden:show"',
        ),
    }.items():
        text = script(name)
        for key in keys:
            assert f"dataset.focus = {key}" in text, (name, key)
        assert "tabKeys(" in text


def test_client_checkboxes_come_from_one_named_part():
    check = script("parts.js").split("export function clientCheck")[1].split("\n}")[0]
    assert 'setAttribute("aria-label"' in check and "box.value = client" in check
    for name in ("offer.js", "gateway-details.js"):
        text = script(name)
        assert "clientCheck(" in text and 'type = "checkbox"' not in text


def test_apply_waits_for_work_not_for_a_timer():
    code, css = panel(), (STATIC / "style.css").read_text()
    assert "520 - (performance.now()" not in code and "wait(450)" not in code
    assert "shake(" not in code
    assert ".drawer.open .body > *:nth-child(2)" not in css and "line-in" not in css
    assert "--t-panel: 240ms" in css
    assert ".socket .swap { opacity: 0; }" in css


def test_apply_sets_its_label_at_once_and_a_failure_focuses_the_button():
    code = panel()
    flow = code.split("function brokeAfterAnswer")[1].split("function showEffect")[0]
    # No timer in the Apply flow, so a late label cannot land on a button already reset.
    assert "setTimeout" not in flow and "const wait" not in code
    assert 'label.textContent = "Applying…"' in flow
    assert "next.focus()" in flow
    assert ".label.swap" not in CSS
    # An error from the last try goes when Apply is pressed again, so it never sits next to Applied.
    apply = flow.split("async function applyChange")[1]
    clear = 'for (const old of body.querySelectorAll(".callout.error")) old.remove();'
    assert apply.index(clear) < apply.index('changeOutcome(change.id, "apply")')


def test_every_view_reads_project_data_through_current():
    # current() drops another project's data, so a view never shows it under this one's name.
    for path in (STATIC / "js").glob("*.js"):
        if path.name != "store.js":
            assert not re.search(r"\bdata\.(map|gateway|overview)\b", path.read_text()), path.name


def test_buttons_show_progress_and_the_scan_line_no_longer_blinks():
    css = (STATIC / "style.css").read_text()
    # A button that waits shows a small spinner in its own place, words kept for the size.
    assert ".btn.busy::after" in css and ".btn.busy { color: transparent; }" in css
    assert 'node.addEventListener("click", (event) => {' in script("dom.js")
    assert "busyWhile(node" in script("dom.js")
    for name in ("offer.js", "gateway-details.js"):
        assert "busyWhile(submit" in script(name)
    assert 'busyWhile($("#rescan")' in script("app.js")
    # A change with several steps counts them in the Apply button, from the server's events.
    assert '"change_progress"' in script("app.js") and '"kitden:progress"' in script("app.js")
    code = panel()
    assert 'stepText("Applying", done, total)' in code and '"kitden:progress"' in code
    assert ".btn .meter" in css
    # The scan line shows only when a scan takes a while, so quick scans never blink.
    assert ".topbar.scanning::after { opacity: 1; transition-delay: 400ms;" in css


def test_while_a_change_is_written_the_review_says_so_and_offers_nothing_to_press():
    code = panel()
    lock = code.split("function lockReview(")[1].split("\n}\n")[0]
    # Cancel and the close button go away while the change is written, and come back after.
    assert "cancel.hidden = locked" in lock and "close.hidden = locked" in lock
    # The note under the buttons says what is happening instead of the Apply shortcut.
    assert "WRITING" in lock and "APPLY_KEY" in lock
    writing = (
        "Writing the change. It can't stop halfway: if a step fails, Kitden puts everything back."
    )
    assert writing in code
    css = (STATIC / "style.css").read_text()
    # A button that is off never lights up on hover and says so with the pointer.
    assert ".btn:hover:not(:disabled)" in css
    assert ".btn:disabled { cursor: not-allowed; opacity: 0.5; }" in css
    assert ".btn.primary.apply:disabled { opacity: 1; cursor: progress; }" in css


# Library: one page in place of Load map and Discover ---------------------------------------


def test_library_replaces_load_map_and_discover():
    assert "Load map" not in INDEX and "Discover" not in INDEX
    assert not (STATIC / "js" / "discover.js").exists()
    text = script("library.js")
    assert 'el("h1", null, "Library")' in text
    assert "What each client loads, and what you can add to it. Based on saved settings." in text
    assert '[["mine", "Installed"], ["new", "New"], ["all", "All"]]' in text
    # "Differs between clients" went away: the columns show it already.
    assert "Differs between clients" not in text
    # Old addresses open the Library; the Overview's links go there too.
    assert 'OLD_VIEWS = { map: "mine", discover: "new" }' in script("store.js")
    overview = script("overview.js")
    assert 'kind: selected.kind, show: "mine"' in script("store.js")
    assert 'goTo("library", sel)' in overview
    # A note's Details opens the item the note row names.
    assert 'follow({ view: "map", kind: row.kind, name: row.lookup })' in overview


def test_library_says_why_when_there_is_nothing_to_do():
    text = script("library.js")
    # A dash names its reason, after the scope and the route; no found client points to the
    # Overview.
    assert "[cell.where, cell.route, cell.reason].filter(Boolean)" in text
    assert "Kitden found no AI coding clients." in text and '"Open Overview"' in text
    # Search keeps the choice and says what it hides.
    assert '"in New"' in text and '"Show all"' in text
    # The line goes away with the choice; focus moves to that choice.
    assert """document.querySelector('#main [data-focus="show:all"]')""" in text
    # A morph into a dash keeps its reason for a screen reader.
    assert "label: cell.reason" in text and 'label || "Not set up"' in script("parts.js")
    assert "`Needs attention · ${answer.attention}`" in text
    # Marketplace notes stay above the table, once each, never in the cells.
    assert 'el("p", "note", note)' in text


def test_a_cell_add_reviews_one_client_and_the_review_shows_its_note():
    text = script("library.js")
    assert "startAdd(cell.add, client, row)" in text
    assert "review(previewFor(add, client), { note: noteFor(add, state.project) })" in text
    offer = script("offer.js")
    assert '"Adds for all projects."' in offer
    # Every add in a project view says so, a marketplace too. The plugin form adds the
    # warnings of the checked clients, as their cells do.
    assert offer.count("{ note: projectNote(state.project) }") == 2
    assert "{ note: formNote(row, clients, state.project) }" in offer
    code = panel()
    assert "export async function review(previewBody, { note = null, back = null } = {})" in code
    assert "if (note) body.append(callout(note));" in code
    # Preview again keeps the note, and the Details a tool switch came from.
    assert "review(previewBody, { note, back })" in code
    # Details of a row with a repeated name name its source.
    assert "rowTitle(row)" in code


def test_typing_waits_before_the_library_asks_the_server():
    text = script("library.js")
    assert "const TYPING_MS = 200;" in text and "load(); }, TYPING_MS);" in text
    # A newer request wins, and a change waits for the new rows before the cells morph.
    assert "order === sent && at >= cache.at" in text and "if (latest()) cache =" in text
    assert "await Promise.all([reload(), loadLibrary()]);" in script("app.js")
    assert "await Promise.all([reload().catch(() => {}), loadLibrary()]);" in panel()


def test_library_columns_hide_with_a_quiet_minus_kept_in_this_browser():
    text, css = script("library.js"), (STATIC / "style.css").read_text()
    # The choice lives in this browser; every read and write is inside try/catch.
    assert 'const HIDDEN_KEY = "kitden-hidden-clients"' in text
    store = text.split("export function hiddenClients")[1].split("// The kind tab shown")[0]
    assert store.count("localStorage.") == 2
    assert store.count("try {") == 2 and store.count("catch") == 2
    # A named button per column, not drawn when no other readable column would stay; the
    # server gets the sorted list.
    assert 'button("−"' in text and "`Hide ${column.name}`" in text
    assert "shown.some((c) => !c.note && c.id !== column.id)" in text
    assert 'hidden: hiddenClients().sort().join(",")' in text
    assert '`Hidden: ${gone.map((c) => c.name).join(", ")} · `' in text
    # Always there, in quiet gray, so it can be found; it darkens on hover and focus.
    rule = re.search(r"\.btn\.hide-col \{([^}]*)\}", css).group(1)
    assert "width: 24px" in rule and "color: var(--ink-3)" in rule and "opacity" not in rule
    assert ".map th:hover .hide-col" not in css
    assert (
        ".btn.hide-col:hover:not(:disabled), .btn.hide-col:focus-visible { color: var(--ink); }"
        in css
    )


def test_details_show_what_the_item_is_and_every_way_to_add_it():
    code, offer = panel(), script("offer.js")
    # The marketplace's entry is read beside the definitions; when it fails the rest still shows.
    assert "row.offer ? getJson(`/api/offer${query({ kind: row.kind, id: row.offer })}`)" in code
    assert ".catch(() => null)" in code
    assert 'if (offer) blocks.set("about", about(offer));' in code
    # A Details button opens the same review as the cell's own button.
    assert "startAdd(option.add, option.client, row)" in offer
    assert '"Add…"' in offer and 'button("Add…", () => addForm(offer), "btn primary")' not in offer
    # With nothing to do, the line that says why waits with the next steps, after the Why and
    # what each client loads; a row not on this computer still says it first.
    assert 'if (why) next.push(el("p", "muted", why));' in code
    assert 'if (why) body.prepend(el("p", "muted", why));' in offer


def test_the_start_says_what_it_still_reads_and_fills_a_line_as_steps_end():
    app, css = script("app.js"), (STATIC / "style.css").read_text()
    assert '<span class="scan-status" id="scan-status" role="status"></span>' in INDEX
    assert 'events.addEventListener("scan_progress"' in app
    # On every (re)connect the page reads where the scan is: steps sent before are lost.
    assert 'events.addEventListener("open", readScan);' in app
    assert 'getJson("/api/progress").then(showScan)' in app
    # The words appear with the line, never before, and the note hangs below: nothing moves.
    assert '$("#scan-status").textContent = scanning.text;' in app.split("function drawScan")[1]
    assert re.search(r"\.scan-status \{ position: absolute; top: calc\(100% \+ 6px\);", css)
    assert ".topbar.scanning:not(.progress)::after { transform: none; opacity: 0.6; }" in css
    assert "const SCAN_LINE_DELAY_MS = 1000;" in app
    assert "transform: scaleX(var(--scan-done, 0)); transform-origin: left;" in css
    assert ".topbar.progress::after { transition: none; }" in css


def test_tabs_and_filters_read_first_then_the_list_settles():
    library, app, store = script("library.js"), script("app.js"), script("store.js")
    css = (STATIC / "style.css").read_text()
    # Tabs and filters read their rows before the page changes; a slow answer dims the old list.
    assert "const SWAP_WAIT_MS = 300;" in library
    # The pressed tab or choice is marked at once; the list follows when its rows are in.
    assert "markChoice(pressed);" in library.split("async function choose")[1]
    for call in (
        "choose({ kind: id,",
        "choose({ show: id,",
        "choose({ attention:",
        "choose({ category:",
    ):
        assert call in library
    assert ".table-scroll.waiting { opacity: 0.5; pointer-events: none; }" in css
    # A redraw of the same place notes where its rows were; the Library moves them from there.
    assert "snapshot: snapshotRows, settle: settleRows" in app
    assert "const before = samePlace && place.snapshot ? place.snapshot() : null;" in app
    # A place change: only the page moves, and the Library's rows are read first.
    assert 'state.view === "gateway" ? "map-entrance" : "place-change");' in store
    assert "html.place-change #main, html.map-entrance #main { view-transition-name: page; }" in css
    assert "::view-transition-new(page) { animation: 260ms var(--ease-out) both page-in; }" in css
    assert 'if (view === "library" && state.view !== "library") await raceSlow(' in app


def test_add_a_marketplace_sits_where_the_filters_sit_on_other_tabs():
    # Pushed to the right, it left an empty band between the tabs and the table.
    library = script("library.js")
    assert 'bar.append(el("span", "grow"), add);' not in library
    assert "bar.append(add);" in library


# The Kitden gateway (2026-10-21) ----------------------------------------------------------


def test_the_kitden_gateway_card_comes_first_and_sets_up_missing_clients():
    # The Kitden block comes first (gateway.test.mjs); a client's Details sets it up.
    text = gw()
    # Who it reaches and the setup offers: one rule in parts.js (the Affects line uses it too).
    parts = script("parts.js")
    assert "`Set up in ${CLIENT_NAMES[entry.client]}…`" in parts
    assert '"setup_server.register"' in parts and '"setup_server.update"' in parts
    assert "kitdenClients(setup)" in text and "setup: data.setupServer" in text
    assert "Nothing yet. Move a server in from the outside group." in text
    # Its rows show a name and what it is; commands and env stay out of the page.
    assert "server.command" not in text and "server.env" not in text


def test_a_held_server_lists_its_tools_with_a_switch_each():
    code = panel()
    for words in (
        '"Whole server"',
        "`Differs from ${row.follows}`",
        "`Use ${row.follows}`",
        '"Refresh tools"',
        "ALL_PROJECTS",
        "Kitden does not know its tools yet.",
    ):
        assert words in code, words
    # Refresh tools waits for the server's own word that it is done, never a timer of its own.
    assert '"/api/gateway/tools/refresh"' in code and '"kitden:tools"' in code
    assert '"gateway_tools"' in script("app.js") and '"kitden:tools"' in script("app.js")


def test_a_tool_switch_flips_only_after_the_change_is_verified():
    code = panel()
    # Details comes back after Apply with the switch drawn in its new state; the thumb slides once.
    assert "await back({ verified: true })" in code
    assert 'toggle.classList.add("flipped")' in code
    assert ".switch.flipped .thumb" in CSS and "@keyframes thumb-on" in CSS
    # A refused preview stays as a callout in Details, and focus goes back to the switch.
    assert "await back({ error: reason })" in code
    assert 'callout(error, "error")' in code


def test_tool_list_reads_again_and_keeps_focus_after_a_refresh_or_an_undo():
    code = panel()
    # Without the event stream the refresh still ends with the list read again.
    assert "if (await ended) reloadTools();" in code
    # Undo with Details open puts focus back on the switch it changed.
    assert "focus: tools.flipped" in code
    # Only an open tool list's Details skips the page's usual effect after an Undo; a closed
    # drawer keeps its old content, so "connected" alone would reopen it.
    assert "if (isPanelOpen() && tools && tools.section.isConnected) {" in code
    # A tool's description wraps to two lines, so it can be read without a pointer.
    rule = CSS.split(".layer.tool .why {")[1].split("}")[0]
    assert "-webkit-line-clamp: 2" in rule and "nowrap" not in rule


def test_the_kitden_card_says_only_what_it_knows_about_clients():
    text = gw()
    assert "Kitden could not read which clients use it." in text
    # Settings it cannot read are a problem, not an empty gateway.
    assert "if (gateway.problem)" in text
    assert "has the kitden entry turned off" in text


def test_moves_into_the_kitden_gateway_name_it():
    code = panel()
    assert "Move ${names} into the Kitden gateway" in code
    # Two gateways can take a server: the panel asks which, never picks one silently.
    assert 'openInfo("Move into the gateway", title, body' in code
    # The Changes page names the server first: "Moved files into the Kitden gateway · …".
    assert "into the Kitden gateway${place} · ${clients.join" in script("parts.js")


def test_overview_offers_set_up_only_without_a_gateway():
    overview = script("overview.js")
    assert overview.count('"No gateway yet."') == 1
    assert "gatewayCardWords" in overview


def test_library_says_the_add_scope_in_a_project():
    assert "Adding puts an item in all projects." in script("library.js")
    assert "all your projects" not in script("library.js") + script("offer.js")


def test_a_projects_own_skill_adds_into_the_project():
    assert "add.project_only" in script("library.js")
    assert '"This project\'s own skills add into this project."' in script("library.js")


def test_an_add_review_names_its_scope():
    code = panel()
    # With All projects picked the lede says it; in a project the note callout says it.
    assert '"Adds for all projects. "' in code
    assert "reviewLede(change, state.project)" in code
    assert '" for all projects"' in code


def test_the_review_leads_with_the_outcome_and_keeps_undo_honest():
    review = reviews()
    assert "Other projects are unchanged." in review and "A backup is kept." in review
    # One words table: the page's sentence is the twin of views/words.py's.
    assert f'const UNCHANGED = "{UNCHANGED} ";' in review
    assert "so you can undo" not in panel()
    # The applied change keeps the target, so the toast says the same place as the title.
    assert "after.target = change.target" in review
    # The Undo limit comes from the server (views/words.py REMOVE_NOTE), said once.
    assert "saved options" not in panel()
    assert "change.undo_note" in review


def test_cancel_and_a_refused_preview_go_back_to_details():
    review, shell, details = reviews(), script("panel.js"), script("details.js")
    assert "cancelTarget(" in review and "backToDetails({ error: reason })" in review
    assert "panelState.from = null" in shell
    # Details, and the Gateway's cards of a held server and a tool, keep how to draw themselves
    # again (details.test.mjs tests keepFrom and backToDetails).
    assert "keepFrom(" in details
    assert "keepFrom(draw, nodes, read)" in gw()
    assert "() => drawHeld(name, detail, { choosing }), () => showHeld(name))" in gw()
    assert "() => showTool(serverName, name))" in gw()
    for key in ("`offer:", '"move"', "`add:", '"add:form"', "`held:", '"more"', '"commands"'):
        assert key in panel() + script("offer.js"), key
    assert "`switch:${def.id}`" in details
    # The review is cancelled once: Cancel's own request, not again when the panel closes.
    cancel = shell.split("export function cancelPreview(")[1].split("\n}\n")[0]
    assert 'change.state = "cancelled"' in cancel


def test_a_review_says_when_its_settings_changed():
    # After a rescan the page asks the server about the open review (review.test.mjs).
    assert '"kitden:rescanned"' in script("app.js") and '"kitden:rescanned"' in script("panel.js")
    review = reviews()
    assert "Settings changed since this preview." in review and '"Preview again"' in review


def test_no_clients_says_what_kitden_looks_for_and_offers_the_demo():
    library = script("library.js")
    assert "Kitden found no AI coding clients." in library and '"Open Overview"' in library
    assert "It looks for Claude Code, Codex and Cursor." in library
    # The folders and the command sit behind Details (AGENTS.md).
    assert '"What Kitden looks for"' in library and "lookFor(" in library
    assert "It finds a client by that folder or by its command." in library
    assert '"kitden demo"' in library
    overview = script("overview.js")
    assert "noClients({ overview: false })" in overview and '"No clients found"' in overview
    # A source still read: a quiet line on the tab it changes, shown with the top bar's line
    # and drawn again in place.
    assert "sourceLines(" in library and "showSources(data.progress)" in script("app.js")


def test_a_project_no_longer_on_the_list_is_said_not_swapped():
    assert 'export const GONE_PROJECT = "This project is no longer on the list.";' in script(
        "parts.js"
    )
    app = script("app.js")
    assert '"No longer on the list"' in script("parts.js") and "projectGone()" in app
    shared = script("store.js").split("export async function loadShared()")[1].split("\n}\n")[0]
    assert 'state.project = ""' not in shared


def test_an_add_in_a_project_offers_two_choices():
    library = script("library.js")
    for words in (
        '"Add to this project…"',
        '"Add for all projects…"',
        '"An Add asks: this project, or all projects.',
        "only, or in all projects.`",
    ):
        assert words in library
    assert "startAdd(" in script("offer.js")


def test_the_kitden_card_says_what_the_gateway_governs():
    text = gw()
    words = "The gateway controls only the servers in it. "
    assert words + "Direct entries and terminal tools are outside it." in text


def test_agents_lede_says_held_servers_add_their_tools():
    text = script("agents.js")
    assert "Servers moved into the gateway add their tools, which do what those servers do." in text


def test_tool_and_server_details_use_the_owner_words():
    text = gw() + script("parts.js")
    for words in (
        '"Use the shared rule…"',
        "'s rule…",
        '"Turn on for all projects…"',
        '"Turn off in one project…"',
        '"On in this project"',
        '"Off · server off"',
        '"Read only"',
        '"May write"',
        '"Not reported"',
        '"New · waits"',
        '"On by default"',
        "of ${",
        " on`",
    ):
        assert words in text, words
    assert "Allowed" not in text and "Blocked" not in text and "Sign in" not in text
    # With All projects a card says what the shared rule does, never "in any project":
    # a project's own rule may decide otherwise.
    assert "in any project" not in gw() and "Other projects follow" not in gw()


def test_tool_and_server_details_say_what_they_know():
    text = gw()
    for words in (
        '"Off in this project"',
        '"Not reported · its name suggests it writes"',
        "can call this tool through Kitden ${place}.`",
        "can't call this tool through Kitden ${place}.`",
        "is off ${place}, so none of its tools can be called.${others}`",
        '"No client uses the Kitden gateway yet."',
        "`Open ${server.name}`",
        '"In the Kitden gateway"',
        '"Local · runs on this Mac"',
        '"Not known yet"',
        "reach it through the Kitden gateway ${place}.${others}`",
        "`It is off ${place}, so no client can call its tools.${others}`",
        '"by the shared rule"',
        '` ${plural(k, "project decides", "projects decide")} otherwise.`',
        '"These switches also apply in folders Kitden does not know."',
        '"Strict: a new tool waits until you turn it on."',
        '"Turn strict mode on…"',
        '"Turn strict mode off…"',
        '"Turn off every writing tool…"',
        '"Refresh tools"',
    ):
        assert words in text, words
    # The kitden entry back on: a review where the docs name the key, else where to do it.
    assert "`Turn it on in ${name}…`" in text
    # Strict mode applies in every project: its review says so, also in a project view.
    assert "`Turn strict mode ${state} for ${server} in all projects`" in script("parts.js")
    assert "`This project · ${folder}`" in script("parts.js")
    assert "`From ${origin_from}`" in script("parts.js")
    assert "`Turn it on in ${name}'s own MCP settings.`" in text
    review, parts = reviews(), script("parts.js")
    assert "`Turn on the kitden entry in ${clients}`" in review
    assert '"setup_server.enable": "Turned on the kitden entry"' in parts
    assert '"setup_server.enable"' in parts.split("export const PLACE_IN_TITLE")[1].split("\n")[0]
    # The calls fact, in the spec's words.
    assert '`${plural(calls.count, "call", "calls")} · last ${day} ${time}`' in panel()


def test_the_tool_list_has_a_strict_switch():
    code = panel()
    assert "Strict: only tools that are on" in code
    assert "Only tools that are on are offered; a new tool waits." in code
    assert "Set for all projects" in code
    assert 'action: "gateway.strict"' in code


def test_all_projects_says_unknown_folders_follow_it():
    assert "These switches also apply in folders Kitden does not know." in panel()


def test_the_tool_list_says_reads_and_writes_and_has_a_batch_switch():
    code = panel()
    assert "Turn off every writing tool…" in code
    assert "from the server" in code and "by its name" in code
    assert 'action: "gateway.rules"' in code


def test_a_held_server_can_be_removed_or_put_back():
    code = panel()
    assert '"Remove from the Kitden gateway…"' in code
    assert "`Put back in ${CLIENT_NAMES[client]}…`" in code
    assert "heldActions(" in gw()


def test_a_held_server_can_move_its_secrets_to_the_keychain():
    assert '"Move secrets to the Keychain…"' in panel()
    assert "server.plain_secrets" in gw()
    assert 'plainSecrets(currentModel("gateway"), row.name)' in panel()


def test_a_server_can_be_added_to_another_client():
    assert '"mcp.add": `Add ${names} to ${clients}`' in panel()
    assert '"mcp.add": "Added"' in script("parts.js")
    assert 'add.action === "mcp.add" ? { item: add.item }' in script("library.js")


def test_a_project_can_be_aligned_in_one_review():
    library = script("library.js")
    assert "Add missing…" in library and '"add:missing"' in library
    code = panel()
    assert "Not the same; not touched" in code and '"project.align"' in code


def test_a_failed_change_does_not_claim_a_restore_on_the_page():
    # The engine's error says "The original settings were restored." only when it is true.
    assert "were put back" not in panel()
    assert '"The change did not check out."' in panel()
    assert "Failed, put back" not in script("changes.js")


def test_the_clients_card_hears_when_versions_arrive():
    assert 'addEventListener("versions"' in script("app.js")
    assert "kitden:versions" in script("app.js")
    overview = script("overview.js")
    assert "kitden:versions" in overview and "/api/clients" in overview
    assert "versionWords(" in overview and '"version unknown"' not in overview


def test_a_change_whose_backup_holds_a_secret_says_so():
    assert "This change's backup or record holds a secret." in script("parts.js")
    assert "backupNote(entry)" in script("changes.js")


def test_library_has_an_instructions_tab():
    text = script("library.js")
    assert '["instructions", "Instructions"]' in text


def test_details_shows_an_instruction_files_first_lines():
    assert 'el("pre", "preview"' in panel()
    assert "pre.preview" in (STATIC / "style.css").read_text()


def test_details_answer_in_order_and_fold_the_evidence():
    details = script("details.js")
    assert "for (const id of detailsOrder(" in details
    assert '"Technical details"' in details and "fold(" in details
    assert 'el("pre", "preview"' in details  # the first lines, now inside the fold
    assert "details.tech" in CSS and ".why-lines" in CSS
    # The Why names a folder several clients read; the route words are Part 2's.
    assert "`One folder, read by ${joinWords(" in details
    assert "ROUTE_WORDS.folder" in details and "ROUTE_WORDS.kitden" in details
    # A layer shows no path, command or file lines of its own: they wait in the fold.
    layer = details.split("function layer(def, said)")[1].split("\n}\n")[0]
    assert "shortPath" not in layer and "def.summary" not in layer and "preview" not in layer


def test_details_say_what_the_lead_changes_and_link_to_the_other_pages():
    details = script("details.js")
    for words in (
        '"Compare across clients"',
        '"Manage tools"',
        '"In this project."',
        '"You choose this project or all projects next."',
        '"All projects."',
        '"All projects except this one."',
        '"Its tool switches change"',
    ):
        assert words in details, words
    assert "affectsText(affectsFor(" in details
    # A move into the Kitden gateway names the clients whose kitden entry is on, by the rule the
    # Gateway card uses, without details.js reading gateway.js.
    assert "kitdenClients(data.setupServer).linked" in details
    assert 'from "./gateway.js"' not in details
    assert ".affects" in CSS and ".links" in CSS
    # A link closes the panel first, reads the Library's rows like the rail, then goes there.
    follow = details.split("export async function followLink(link)")[1].split("\n}\n")[0]
    assert follow.index("closePanel(") < follow.index("goTo(")
    assert "raceSlow(loadLibraryFor(libraryChoice(" in follow
    assert "dataset.focus = `link:${link.view}`" in details
    # The Details of a server in the Kitden gateway link back to the Library.
    assert "contextLinks(" in gw()


def test_the_page_and_the_server_say_why_an_add_reaches_cursor_alike():
    # The words live with the other page words, in parts.js.
    parts, offer = script("parts.js"), script("offer.js")
    for owner in ("Codex", "Claude Code"):
        assert f'"{READS_FOLDER.format(reader="Cursor", owner=owner)}"' in parts, owner
    assert f'"{LOADS_PLUGINS}"' in parts
    assert "REACH_NOTES" in offer and "const REACH_NOTES" not in offer
    # One rule: the Add form's Cursor line asks addReach too.
    also = offer.split("export function alsoLoads(")[1].split("\n}\n")[0]
    assert "addReach(" in also


def test_skill_and_plugin_details_fold_paths_commands_and_versions():
    offer = script("offer.js")
    show = offer.split("export function showSkill(")[1].split("\n}\n")[0]
    assert "technical([" in show
    assert 'el("li", "mono", shortPath(skill.path))' not in show
    # A plugin's MCP commands, its source and its pinned version wait in the fold too; the
    # list says only the servers' names.
    plugin = offer.split("export function showOffer(")[1].split("\n}\n")[0]
    assert "const rows = [...sourceRows(offer), ...mcpRows(offer)];" in plugin
    assert "technical(rows)" in plugin
    assert "Pinned to ${" not in plugin and '"mono", where' not in plugin
    assert "${server.runs}" not in offer and 'add("MCP servers"' in offer
    assert "...(offer ? mcpRows(offer) : [])" in script("details.js")


def test_pages_import_the_side_panel_through_panel_js():
    for name in ("gateway.js", "gateway-details.js", "gateway-drag.js", "offer.js"):
        assert 'from "./details.js"' not in script(name), name
    shell = script("panel.js")
    for word in ("contextLinks", "linksRow", "technical"):
        assert re.search(rf"export \{{[^}}]*\b{word}\b[^}}]*\}} from \"./details.js\"", shell), word


def test_a_demo_says_so_quietly_in_the_rail():
    assert 'getJson("/api/about")' in script("app.js")
    parts = script("parts.js")
    assert '"Demo"' in parts
    hover = "A sample setup in a temporary folder. Your own settings are not read or changed."
    assert hover in parts
    assert "Demo" not in INDEX  # only a demo's answer adds it


def test_an_issue_card_without_a_button_keeps_its_words_in_the_wide_column():
    # An unreadable file has no action; left to the grid, its title fell into a 0 px column.
    for selector in (".issue h3", ".issue p"):
        rule = re.search(rf"^{re.escape(selector)} \{{([^}}]*)\}}", CSS, re.MULTILINE)
        assert rule and "grid-column: 1;" in rule.group(1), selector


def test_a_client_kitden_could_not_read_says_so_under_its_name():
    assert "column.note" in script("library.js")


def test_a_cell_kept_from_the_last_good_read_has_a_dashed_dot():
    assert ".socket.stale .dot { border-style: dashed; }" in CSS


def test_needs_review_is_an_amber_ring_with_a_small_dot():
    assert ".s-review { color: var(--lamp-warn); }" in CSS
    assert ".s-review .dot::after { transform: scale(0.5); border-radius: 50%; }" in CSS


def test_details_says_when_a_kept_definition_was_read_in_the_server_words():
    assert STALE.format("${") in panel()


def test_overview_notes_say_same_name_another_source():
    assert 'same_name_other_source: "Same name, another source"' in script("overview.js")


def test_the_gateway_opens_and_keeps_the_selected_server():
    text = gw()
    # Details of a server, in the gateway's own panel or outside it, puts it in the address.
    assert 'setState({ selected: { kind: "mcp_server", name } })' in text
    assert 'setState({ selected: { kind: "tool", name: `${server}/${name}` } })' in text
    assert 'setState({ selected: { kind: "mcp_server", name: row.name } })' in text
    assert "takeArrival()" in text


def test_saving_a_gateway_drops_an_arrival_still_waiting():
    # The person's own action wins: a server picked by Back must not open after the save.
    save = gw().split("async function save() {")[1].split("\n  }\n")[0]
    assert "arrival.pending = false;" in save


def test_the_gateway_lists_by_group_and_keeps_every_action():
    text = gw()
    for words in (
        '"Outside the gateway · calls skip Kitden\'s rules"',
        '"Move in…"',
        '"Move into the gateway…"',
        '"Remove direct entry…"',
        "Move all ${",
        '"Add another gateway…"',
        '"Use this gateway…"',
        "Set up in",
        '"Connect your agents. Shape what they can use."',
        "The gateway controls only the servers in it. "
        "Direct entries and terminal tools are outside it.",
    ):
        assert words in text, words
    assert '"/api/map"' not in text and "loadMap(" not in text
    assert 'role", "treegrid"' in script("gateway.js") and "gridKey(" in script("gateway.js")


def test_the_gateway_says_what_it_could_not_read():
    # A read that failed is not a state: no "Not connected", "0 servers" or "No project".
    text = gw()
    for words in (
        '"Not known"',
        '"Could not read its settings."',
        '"project has its", "projects have their"',
    ):
        assert words in text, words
    assert "projects have its" not in text


def test_search_on_a_map_page_finds_on_that_page():
    app = script("app.js")
    assert 'MAP_PAGES = ["gateway"]' in app and 'go("library", { q })' in app
    # The chip's words are shared by every map page, so they live in map.js.
    assert '"match", "matches"' in script("map.js") and '"No matches"' in script("map.js")
    assert '<span class="find-chip" id="find-chip" role="status"></span>' in INDEX
    # The empty chip stays in the page (a live region that is drawn announces its first words);
    # it only gives back the gap before it.
    empty = re.search(r"\.find-chip:empty \{([^}]*)\}", CSS)
    assert empty and "margin-left: -8px;" in empty.group(1) and "display" not in empty.group(1)
    # Matches are lit; the other blocks dim to 35% and their links to 25%, in the map and the List.
    assert ".map.finding" in CSS
    dims = r"div\.map\.finding \.block:not\(\.found\)[^{]*\{ filter: opacity\(0\.35\); \}"
    assert re.search(dims, CSS)
    assert "div.map.finding .link { stroke-opacity: 0.25; }" in CSS
    assert ".treegrid.finding .tg-row:not(.found) { opacity: 0.35; }" in CSS


def test_finding_keeps_the_place_and_the_details():
    app = script("app.js")
    # Escape in the search clears it on a map page, and only then keeps Details open.
    assert 'event.key !== "Escape" || !MAP_PAGES.includes(state.view)' in app
    assert "event.stopPropagation();" in app.split('$("#q").addEventListener("keydown"')[1]
    # "/" works beside docked Details, not under the modal drawer.
    assert '!$("#drawer").classList.contains("docked")' in app
    assert 'if (event.key === "/" && !typing && !modal) {' in app
    # The Gateway only lights, dims and opens blocks for the view: it asks nothing of a client.
    text = script("gateway.js")
    # A press on a block the search holds open changes nothing (map.js pressOpen), in the map and
    # the List.
    assert "onMap.open = pressOpen(model, onMap.open, onMap.found, id);" in text
    assert "if (row.kept) return;" in text.split("function toggleRow(")[1].split("\n}\n")[0]
    find = text.split("export function findRows(")[1].split("\n}\n")[0]
    assert "postJson" not in find and "review(" not in find and "setState" not in find


def test_the_map_review_bar_waits_for_verified():
    review, bar = script("review.js"), script("map-review.js")
    for words in (
        '"Show changes"',
        '"Try again"',
        "export function reviewBar(",
        "previewOnMap(",
    ):
        assert words in bar, words
    # What is written is said in dock.js, which the tray's bar shares.
    assert "A backup is kept." in script("dock.js") and 'from "./dock.js"' in bar
    # The bar says it with the one word of review.js (barWords).
    assert '"Nothing was changed."' in review and "`${refused} ${NOTHING}`" in bar
    assert '"Drop to add"' in gw() and "dropBody(" in gw() and "moveBody(" in script("details.js")
    assert "Sign in after Apply" not in review + bar


def test_the_map_review_bar_words_and_look():
    review, bar = script("review.js"), script("map-review.js")
    # What is written, in the owner's words (dock.js, shared with the tray's bar); the step count
    # comes from the server.
    dock = script("dock.js")
    assert "`Writing ${names[0]}'s settings. A backup is kept.`" in dock
    assert "`Writing the settings of ${joinWords(names)}. A backup is kept.`" in dock
    assert '"the Kitden gateway"' in dock and 'stepText("Applying", done, total)' in bar
    # A refusal says why and keeps only Cancel; the bar is a region with a status line.
    assert '"Could not prepare this change"' in bar
    assert 'setAttribute("role", "region")' in bar and 'setAttribute("role", "status")' in bar
    # Both reviews end with the one toast that offers Undo.
    assert "appliedToast(after, previewBody);" in review and "appliedToast(after, body);" in bar
    # An end that is not verified reads the same in Details and on the bar; "Nothing was changed."
    # only when the engine put everything back. Off the map, a toast says it, with Changes.
    assert 'callout(stoppedWords(after, failure), "error")' in review
    assert "outcome: stoppedWords(" in bar and "allPutBack(after.error)" in review
    # The bar and its toast leave out the engine's words (paths, commands): they stay in Details.
    assert "{ detail: false }" in bar
    assert '"Not everything was put back. Check Changes before trying again."' in review
    assert '{ label: "Open Changes" }' in bar and 'go("changes")' in bar
    # The preview block says it is a preview; it sits on the preview fill with the preview line.
    assert '"Preview"' in script("gateway.js")
    look = r"div\.map \.block\.preview \{[^}]*var\(--preview-line\)[^}]*var\(--preview-fill\)"
    assert re.search(look, CSS)
    assert ".review-bar {" in CSS
    # A drag starts after 4 px; the keyboard path stays "Move in…".
    assert "const DRAG_START = 4;" in script("gateway-drag.js")
    assert '"Move in…"' in script("gateway.js")


def test_the_map_review_reads_no_gateway_module():
    # Part 5 puts the review bar on the Library map, so it reads no Gateway module. review.js never
    # reads it back (no import cycle): the map review tells it how they take turns.
    bar = script("map-review.js")
    for name in ("gateway.js", "gateway-details.js", "gateway-drag.js"):
        assert f'from "./{name}"' not in bar, name
    assert 'from "./map-review.js"' not in script("review.js")
    assert "setMapReview(TURNS)" in bar and "export function setMapReview(" in script("review.js")


def test_the_tray_bar_sits_in_the_dock_and_says_its_words():
    dock = script("dock.js")
    for words in (
        "Applied ",
        "Undo all",
        "changes in preview",
        "Nothing is written until you Apply.",
        "Click one on the map to take it out.",
        "Take it out of the preview",
        "Show changes",
        "Cancel all",
        "Apply all",
        "All applied",
        "Could not prepare the preview",
        "Not everything was put back",
        "Kitden put the files back.",
    ):
        assert words in dock, words
    # A row's review in Details has no Apply of its own; the person can take the row out there.
    assert '"Take it out"' in script("review.js")
    assert 'type: "row-review"' in script("review.js")
    # The bar lives in the page's dock, at the bottom left of the content.
    assert '<div class="dock" id="dock"></div>' in INDEX
    assert ".dock {" in CSS and ".tray-list {" in CSS
    assert "initDock();" in script("app.js")
