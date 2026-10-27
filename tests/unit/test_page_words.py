"""Words and parts the design review (2026-10-18) removed from the page stay removed."""

import re
from pathlib import Path

from kitden.clients.cursor import CURSOR_HINT
from kitden.views.skills import NEEDS_PLUGIN, NO_CLIENT
from kitden.views.words import (
    AFTER_WORDS,
    CODEX_NO_PROJECT,
    CURSOR_NO_SKILL_SWITCH,
    FOLLOWS_SHARED,
    KEEP_THEIR_RULES,
    KEEPS_ITS_RULE,
    NEW_LOCAL_FILE,
    NO_CLAUDE_FOLDER,
    NO_GATEWAY_CLIENT,
    NO_SKILL_MERGE,
    OWN_SKILL_SETTINGS,
    PLUGIN_ALL_PROJECTS,
    PLUGIN_SKILL,
    REPO_RULE,
    REPO_RULE_OUT,
    ROUTE_WORDS,
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
    tray reads how an Apply or an Undo ended, and its bar in the dock shares the review's words, so
    both are read too."""
    return "\n".join(script(name) for name in (*PANEL, "tray.js", "dock.js"))


def reviews() -> str:
    """The change review and the tray's bar in the dock as one text: they share their words."""
    return script("review.js") + "\n" + script("dock.js")


def gw() -> str:
    """The Gateway page's modules as one text."""
    names = ("gateway.js", "gateway-details.js", "gateway-drag.js")
    return "\n".join(script(name) for name in names)


def test_the_side_panel_is_four_modules():
    shell = script("panel.js")
    for name in PANEL[1:]:
        assert (STATIC / "js" / name).exists() and f'from "./{name}"' in shell, name
    assert "function trapFocus" in shell and "function showReview" not in shell
    assert "export function detailsCard" in script("details.js")
    assert "function showReview" in script("review.js")


def test_details_float_beside_the_page_without_a_scrim():
    shell = script("panel.js")
    assert "export const FLOAT_MIN = 1024;" in shell and 'removeAttribute("aria-modal")' in shell
    details = script("details.js")
    assert "export function factsBlock(" in details and "export function detailsCard(" in details
    assert "#drawer.floating" in CSS and ".facts" in CSS
    # The page keeps its width: no column beside it, and the map does not go narrow for Details.
    assert "docked" not in CSS and "docked" not in shell and "docked" not in gw()
    assert "export function isNarrow(width) {" in script("map.js")
    # The floating panel's look: 320 px, 10 px corners, padding 18, the panel fill, a line and the
    # shadow. Its skeleton's bars are still: nothing loops.
    floating = rule("#drawer.floating")
    looks = ("width: 320px;", "border-radius: 10px;", "border: 1px solid var(--wire);")
    for part in (*looks, "background: var(--panel);", "box-shadow: var(--shadow);"):
        assert part in floating, part
    assert "padding: 18px;" in floating and "gap: 16px;" in floating
    assert "animation" not in rule(".sk")
    # A list or a table keeps room on its right for the panel; the map keeps its width, and a block
    # under the panel scrolls beside it when it is selected or takes keyboard focus (WCAG 2.4.11).
    assert "padding-right: var(--float-room);" in rule("#main.floats:not(:has(> div.map))")
    assert 'view.box.addEventListener("focusin"' in gw() and "const { selected } = onMap;" in gw()
    # The panel follows the page's scroll at most once a frame.
    assert "requestAnimationFrame(placeFloat)" in shell


def test_rail_counts_only_attention_and_changes():
    assert 'id="nav-attention"' in INDEX and 'id="nav-changes"' in INDEX
    assert "nav-items" not in INDEX and "nav-around" not in INDEX
    assert "around" not in script("app.js")


def test_overview_has_no_pills_bar_or_recent_changes():
    overview = script("overview.js")
    assert "Recent changes" not in overview
    assert '"Tested"' not in overview and '"Found"' not in overview
    assert '"bar"' not in overview


def test_overview_says_your_setup_connected():
    overview = script("overview.js")
    for words in (
        '"Your setup, connected."',
        "Hover a card to see it on the map · a button adds a preview · click Kitden gateway or "
        "Library to open it",
        '"Everything looks fine: "',
        '"thing needs" : "things need"} your attention. Everything else looks fine: `',
        '"Needs attention"',
        '"Can improve"',
        '"Your setup"',
        '"Kitden gateway"',
        '"Library"',
        '"Not found"',
        '"Could not read its settings"',
        '"All projects"',
        "`Project ${folder}`",
        '"has its own rules" : "have their own rules"',
    ):
        assert words in overview, words
    # The setup map's places, as decided (Phase 7).
    assert '{ id: "clients", w: 160, h: 54, top: 22, rowGap: 18 }' in overview
    assert '{ id: "pages", w: 220, h: 60, colGap: 90, top: 40, rowGap: 48 }' in overview
    # No path on the page, and no floating Details.
    assert "shortPath" not in overview and "openInfo" not in overview


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
    assert "pointer-events: none" in rule(".hint-band, .hint-dock")


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
    assert "position" not in rule(".sw-tx small")
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
    # The Library List's header sticks right under the top bar.
    assert "top: 66px" in rule(".library-list > .tg-head")


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
    # A ghost button keeps no line on hover; the tray's Applied is green all round.
    assert "border-color: transparent" in rule(".btn.ghost:hover:not(:disabled)")
    assert "border-color: var(--success)" in rule(".dock .btn.ok, .dock .btn.ok:hover")


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
    # Map | List glides through the shared pill (map-page.js), under each page's own key.
    assert len(re.findall(r"\{ duration: 280 \}", script("map-page.js"))) == 1
    assert "glide(seg, choice, key, { duration: 280 })" in script("map-page.js")
    assert len(re.findall(r"\{ duration: 280 \}", script("library.js"))) == 2
    assert '"gateway-view")' in script("gateway.js")
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
    # A lamp that turns on or off pops, on the calm curve: from 2.2 times its size, a client's from
    # 2.4 and a tool's mark from 1.9.
    # The map pops them with Web Animations (map-view.js), reading --pop: no CSS animation.
    assert "lamp-pop" not in CSS and ".lamp.pop" not in CSS
    assert 'getPropertyValue?.("--pop")' in script("map-view.js")
    assert "--pop: 2.2" in lamp and "--pop: 1.9" in rule(".mark")
    assert "--pop: 2.4" in rule("div.map .block.client .lamp")
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
    # A picker row (the move-out step's clients) is framed, and takes the accent once picked.
    row = rule(".pick")
    assert "padding: 9px 10px" in row and "border-radius: 8px" in row
    picked_row = rule(".pick.on")
    assert "background: var(--route-soft)" in picked_row and "var(--route)" in picked_row
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


def test_the_projects_step_has_the_menus_rows():
    # The "in some projects" step names, counts and orders projects as the project menu does.
    assert "export function menuItems(" in script("parts.js")
    assert "menuItems(" in gw()


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
    for name in (
        "gateway.js",
        "gateway-details.js",
        "gateway-drag.js",
        "map.js",
        "map-view.js",
        "map-drag.js",
    ):
        assert "flow" not in script(name), name


def test_a_link_says_what_its_x_does():
    assert "} from the gateway`" in gw() and "`Turn off ${" in gw()
    view = script("map-view.js")
    assert "} to ${" in view and '"Connections"' in view
    assert '"aria-keyshortcuts": tip ? "Delete" : null' in view
    # The hits of lines that skip the gateway sit under the others and are narrower.
    assert 'link.kind === "direct"' in view and "div.map .hit.direct { stroke-width: 8; }" in CSS
    assert '"A plugin\'s files"' in gw()


def test_the_follows_live_region_stays_in_the_page():
    # It is never hidden, so what it says is heard; empty, it takes no row of the panel's grid.
    assert "follows.hidden" not in gw()
    assert "position: absolute" in rule(".drawer .body > .follows:empty")


def test_a_pointed_link_keeps_its_look_in_a_search():
    rule = "div.map.finding .link.hov, div.map.finding .link.picked { stroke-opacity: 1; }"
    assert rule in CSS
    assert CSS.index("div.map.finding .link { stroke-opacity: 0.2; }") < CSS.index(rule)


def test_a_hovered_bypass_link_in_a_search_shows_at_full():
    # A lit bypass line dims with the others, but only while it is not pointed at or picked: its
    # rule is more specific than the one that gives a pointed link full strength.
    lit = rule("div.map.finding .link.direct.lit:not(.hov):not(.picked)")
    assert "stroke-opacity: 0.2" in lit
    assert "div.map.finding .link.direct.lit {" not in CSS


def test_a_focused_block_keeps_its_ring_in_a_search():
    # The dim of a search does not touch a block with keyboard focus, so its ring keeps 3:1. The
    # rule is after the dim and more specific.
    keep = "div.map.finding .block:not(.found):focus-visible { filter: none; }"
    assert keep in CSS
    assert CSS.index("div.map.finding .block:not(.found) {") < CSS.index(keep)


def test_a_search_dims_blurs_and_desaturates_what_does_not_match():
    # gateway-notes 7.3: 30 %, half the colour and a 1.2 px blur, over the block's 300 ms filter
    # transition. A caption is no thing to find and is never dimmed. Every link goes to 20 %.
    dims = "div.map.finding .block:not(.found) { filter: opacity(0.3) saturate(0.5) blur(1.2px); }"
    assert dims in CSS
    assert "filter 300ms ease" in rule("div.map .block")
    assert "div.map.finding .caption" not in CSS.replace("div.map.finding .caption.found", "")


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
    # A redraw of the same page does not lift the head again; one while it still rises (its data
    # came) goes on lifting it, and one later leaves it still (riseHead, motion.js).
    assert "riseHead(head, lede, scope, { again })" in script("gateway.js")
    assert "if (since >= headRise.wait + HEAD_DELAYS[2] + HEAD_MS) return;" in script("motion.js")


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
    # A group over six pages five at a time: "N more", on its last page "Show the first 5", and
    # its caption says which ones show; the outside group says why it is apart.
    assert '"Outside the gateway · calls skip Kitden\'s rules"' in script("gateway.js")
    assert " more`" in script("map.js")
    assert "firstPage = (size) => `Show the first ${size}`" in script("map.js")
    assert "`${block.pageName || block.name} · ${page * size + 1}–${" in script("map.js")
    # While the Outside group pages its caption drops "drag one in" for the range, and a caption
    # never runs into the next column: what does not fit ends in "…".
    assert 'const OUTSIDE_PAGED = "Outside the gateway";' in script("gateway.js")
    assert "max-width: 236px;" in rule("div.map div.caption")
    assert "text-overflow: ellipsis;" in rule("div.map .caption .quiet")
    # The map shows no state word; a screen reader hears one, the same as the words it shows.
    states = 'STATE_SAID = { on: "On", off: "Off", unk: "Not known", preview: "In preview" }'
    assert states in script("map.js")


def test_the_map_blocks_look_like_the_mockup():
    # docs/mockup/gateway-notes.md 1: words, sizes and times of each block.
    text = gw()
    assert '"Outside the gateway · drag one in"' in text
    assert '"In preview. Click to take it out."' in text
    # A screen reader hears what a tool's folder tag means.
    assert '"own rule in this project"' in text and "`own rule in ${" in text
    # The Kitden gateway says where it runs, in the words of the gateway view.
    assert '"where": "On this Mac"' in (STATIC.parents[1] / "views/gateway_view.py").read_text()
    assert "gateway.where" in script("gateway.js")
    # Names are Inter, not mono; a block's edge is the line color.
    assert "--mono" not in rule("div.map .block-name")
    assert "border: 1px solid var(--wire);" in rule("div.map .block")
    # The count is a 20 px round button of its own, after its block (never inside it), that stays
    # while the block is open and takes the accent edge; the right port of a block that folds shows
    # only while it is open. Its words are the same in the page's script.
    badge = rule("div.map .block-count")
    for part in (
        "min-width: 20px",
        "height: 20px",
        "border-radius: 10px",
        "cursor: pointer",
        "scale 300ms var(--spring)",
    ):
        assert part in badge, part
    assert "opacity" not in rule('div.map .block-count[aria-expanded="true"]')
    assert "border-color: var(--route)" in rule('div.map .block-count[aria-expanded="true"]')
    assert "padding-right: 16px" in rule("div.map .block.counted")
    assert "outline: 2px solid var(--focus)" in rule("div.map .block-count:focus-visible")
    assert "filter: opacity(0.4)" in rule("div.map.focus .block-count:not(.lit):not(.selected)")
    assert "filter: opacity(0.3)" in rule("div.map.finding .block-count:not(.found)")
    view = script("map-view.js")
    assert 'const unit = block.unit || "tool";' in view
    assert "open ? `Hide ${unit}s` : `Show ${plural(block.count, unit, `${unit}s`)}`" in view
    assert 'unit: "item"' in script("library-map.js")
    assert "opacity: 0; scale: 0.4;" in rule('div.map .block[aria-expanded="false"] > .port.r')
    assert "border-color: var(--lamp-off)" in rule(".port.out")
    # A preview: dashed preview line on the preview fill, accent words, an 18 px × on hover or
    # keyboard focus.
    preview = rule("div.map .block.preview")
    assert "1px dashed var(--preview-line)" in preview and "var(--preview-fill)" in preview
    cross = rule("div.map .block-x")
    for part in (
        "width: 18px",
        "height: 18px",
        "opacity: 0",
        "scale: 0.5",
        "opacity 180ms ease",
        "scale 320ms var(--spring)",
        "pointer-events: none",
    ):
        assert part in cross, part
    assert "opacity: 1; scale: 1;" in rule(
        "div.map .block:hover > .block-x, div.map .block:focus-visible > .block-x"
    )
    # Leaving: dimmed and dashed; a block that leaves the map is no Tab stop while it fades.
    assert "filter: opacity(0.45); border-style: dashed;" in rule("div.map .block.leaving")
    # A leaving block that still takes focus keeps its ring at full strength (3:1).
    assert "filter: none;" in rule("div.map .block.leaving:focus-visible")
    assert CSS.index("div.map .block.leaving:focus-visible {") > CSS.index(
        "div.map .block.leaving {"
    )
    assert 'setAttribute("tabindex", "-1")' in script("map-view.js")
    # The gateway: 150 x 124, its stats 11 px with icons, its numbers roll.
    assert "rollTo(" in script("map-view.js")
    assert "margin-top: 7px" in rule("div.map .block-stats")


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
    assert "stroke-opacity: 0.2" in rule("div.map.finding .link")
    assert "stroke-opacity: 0.2" in rule("div.map.finding .link.direct.lit:not(.hov):not(.picked)")
    # Lit preview and leaving lines dim in a search too; a pointed or picked one stays full.
    lit = (
        "div.map.finding .link.leaving.lit:not(.hov):not(.picked), "
        "div.map.finding .link.direct.preview.lit:not(.hov):not(.picked)"
    )
    assert "stroke-opacity: 0.2" in rule(lit)
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


def test_plugin_switch_adds_its_change_and_does_not_flip_itself():
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


def test_controls_press_and_the_switch_waits_in_the_tray():
    assert ".switch.pending" in CSS
    assert ".seg button:active" in CSS
    # The pending look follows the tray: on while the switch's change waits there.
    text = panel()
    assert 'node.classList.toggle("pending", waiting);' in text and "onTray(syncTray);" in text


def test_an_overview_item_opens_after_its_library_tab_is_read():
    # The tab is read before the place changes, so the Library draws its rows inside the change.
    overview = script("overview.js")
    card = overview.split("async function follow")[1].split("\n}\n")[0]
    assert card.index("await loadLibraryFor(libraryChoice(sel));") < card.index('goTo("library"')


def test_review_counts_the_diff_and_folds_the_file_change():
    text = panel()
    assert "diffCounts" in text and "fold(files)" in text
    assert "Show file change" in text and "Show file changes" in text


def test_apply_turns_green_only_after_verified_and_only_ok_toasts_get_a_check():
    text = panel()
    # The tray is "applied" only when the server says verified; only then is its Apply green.
    applied = 'Object.assign(tray, { change: after, phase: "applied" });'
    assert text.index('if (after && after.state === "verified") {') < text.index(applied)
    assert 'apply.classList.toggle("ok", applied);' in text
    assert "{ ok: true, label: many" in text
    assert 'toast("Undone. The previous settings are back.", null, { ok: true })' in text
    assert "Undone. The previous settings are back." in text
    assert 'toast("Undo stopped' in text  # a stopped undo gets no check


def test_one_mark_slides_between_the_choices_of_a_group():
    assert 'glide($(".nav")' in script("app.js")
    text = script("library.js")
    assert '"library-tabs-map"' in text and '"library-show"' in text
    assert "tab-ink" not in CSS and "tab-ink" not in text


def test_gateway_list_is_a_tree_grid_the_keys_move_through():
    # The List is a tree grid: the arrows move, Right opens, Left closes (dom.js gridKey).
    text = script("gateway.js")
    assert 'setAttribute("role", "treegrid")' in text and "gridKey(" in text
    # "Connect clients" folds smoothly in a registered gateway's Details.
    assert "fold(box)" in gw()


def test_library_shows_one_flag_per_wording():
    text = script("library.js")
    assert "findIndex((o) => o.text === f.text)" in text and "name.append(flag(f))" in text


def test_scope_switch_marks_the_project_picker_and_the_lede():
    assert 'classList.toggle("project"' in script("app.js")
    assert ".where-box.project" in CSS
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


def test_library_lede_names_the_project_folder_not_its_path():
    # The List has the Map's lede, and its scope bar names the project's folder.
    text = script("library.js")
    assert 'el("p", "lede", LEDE), tabs, scopeBar(folderName(projectPath()))' in text
    assert "shortPath" not in text


def test_changes_rows_open_the_panel_and_keep_paths_off_the_page():
    text = script("changes.js")
    assert "openChange" in text
    assert "change-detail" not in text and "aria-expanded" not in text


def test_overview_notes_are_sentences_with_an_info_icon():
    text = script("overview.js")
    assert 'node.append(icon("info", 13), el("span", null, noteSentence(group)));' in text
    assert "`${group.name} ${joinWords(group.notes)}.`" in text
    assert "(nothing to fix)" in text and "`Hide ${plural(count" in text
    assert "shortPaths" not in text and "flag(" not in text
    assert '.ov-fold[aria-expanded="true"] svg { rotate: 90deg; }' in CSS


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
    assert '"marketplace.add"' in offer
    # Adding a marketplace lives in the add panel now; the List has no New or All.
    assert '"Add a marketplace…"' in script("library-add.js")
    assert '"Add a marketplace…"' not in library and '["new", "New"]' not in library
    assert '<a href="#library" data-view="library"><span class="label">Library</span></a>' in INDEX


def test_library_rows_say_what_each_client_has_or_can_add_without_details():
    text = script("library.js")
    # One cell per client: the server's state, or the one button for what it can add.
    assert (
        "socket({ state: cell.state, where: cell.where, word: cell.word, label: cell.reason, "
        "stale: Boolean(cell.stale_at) })" in text
    )
    assert "button(cell.add.label" in text and '"btn small add"' in text
    assert 'via: "Via Claude Code", done: "Has its skills"' in script("parts.js")
    # The List is a tree grid; the category filter went with New and All (the add panel).
    assert 'el("div", "treegrid library-list")' in text
    assert '"All categories"' not in text and "answer.categories" not in text
    # The row opens Details, so there is no Details button on it; only the box shown when no
    # client is found has one.
    assert text.count('"Details"') == 1 and 'button("Details", showLookFor' in text


# Skills beside Plugins ---------------------------------------------------------------------


def test_library_tabs_share_one_grid_and_the_add_flow():
    text = script("library.js")
    assert '[["plugin", "Plugins and skills"], ["instructions", "Instructions"]]' in text
    # One row builder for every row, one grid.
    assert text.count("listRow(") == 2 and text.count('el("div", "treegrid library-list")') == 1
    assert 'show: s.show === "mine" ? "" : s.show' in script("store.js")


def test_skill_rows_say_where_each_skill_comes_from_and_how_each_client_loads_it():
    # Same-name rows name their source in a Details title and a button's name.
    assert "row.same_name && row.source ? `${row.name} · ${row.source}`" in script("library.js")


def test_a_skill_copy_names_every_client_it_reaches():
    code = panel()
    assert "s.reaches || [s.client]" in code and "Add ${names} to ${clients}" in code
    assert "for (const note of notes) box.append(callout(note))" in code  # Cursor loads it twice
    assert '"skill.install": "Added skill"' in script("parts.js")


def test_library_rows_keep_the_name_and_the_source_readable():
    text, css = script("library.js"), (STATIC / "style.css").read_text()
    # The name takes the rest of the row; each client's column is 150 px. A long name is cut
    # with "…" and said whole in its title.
    assert "`minmax(0, 1fr) repeat(${columns.length}, ${CELL_W}px)`" in text
    assert "const CELL_W = 150;" in text and "words.title = row.name;" in text
    assert ".tg-name .words { min-width: 3ch; white-space: nowrap;" in css
    # The server marks rows that share a name; the page does not count names itself.
    assert "names.get" not in text
    # A cell's button names its row's source too, or twin rows would give two buttons one name.
    assert "addName(row, client, cell.add, state.project)" in text


def test_offer_details_and_add_form_follow_what_the_server_says_about_cursor():
    text = script("offer.js")
    # A form's note sits inside the form, before Preview.
    assert "[checks, note, submit, message]" in text


def test_a_lost_apply_answer_is_checked_not_guessed():
    text = panel()
    assert "Nothing was changed by this page" not in text
    assert "Could not confirm the result. Check Changes before trying again." in text
    assert "readChange(" in text


def test_changes_and_the_library_say_saved_settings_and_scope():
    changes = script("changes.js")
    assert "To take effect" in changes and 'user: "all projects"' in changes
    assert "global settings" not in changes
    assert '"everywhere"' not in changes
    assert "Tools · ${where || ALL_PROJECTS}" in panel()


def test_changes_show_restart_notes_only_for_changes_that_happened():
    changes = script("changes.js")
    # The server leaves the notes out of a change that wrote nothing (views/changes_view.py).
    assert "entry.takes_effect" in changes
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
    # The drag left gateway.js; it holds no such retry either, nor does the shared engine.
    assert "render(); })" not in script("gateway-drag.js")
    assert "render(); })" not in script("map-drag.js")


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
    assert '{ id: "improve", words: "Can improve", icon: "sparkles", look: "btn" }' in overview
    code = panel()
    assert 'action: "gateway.move"' in code
    # Without a gateway that takes servers, the Gateway page says so.
    assert "Add the server in the gateway first" in script("parts.js")
    assert "GATEWAY_NOTE" in gw()
    # An option is quieter than a problem: a plain button, not the primary one.
    attention = 'words: "Needs attention", icon: "triangle-alert", look: "btn primary" }'
    assert attention in overview


def test_rows_say_they_open_details_and_search_names_its_scope():
    assert "opens()" in script("changes.js")
    assert ".sr-only" in CSS
    # The chevron is quiet, and takes the accent when the row is hovered or focused.
    assert re.search(r"\n\.opens \{[^}]*color: var\(--ink-3\)", CSS)
    assert re.search(r"\.tg-row:hover \.opens[^{]*\{ color: var\(--route\)", CSS)
    assert "li:hover .opens" in CSS and ".tg-row:focus-visible .opens" in CSS
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
            '"filter:attention"',
            "`add:${row.key}:${client}`",
            '"add:missing"',
            "`hide:${column.id}`",
            '"hidden:show"',
            "`row:${row.id}`",
        ),
    }.items():
        text = script(name)
        for key in keys:
            assert f"dataset.focus = {key}" in text, (name, key)
        assert "gridKey(" in text


def test_client_checkboxes_come_from_one_named_part():
    check = script("parts.js").split("export function clientCheck")[1].split("\n}")[0]
    assert 'setAttribute("aria-label"' in check and "box.value = client" in check
    for name in ("offer.js", "gateway-details.js"):
        text = script(name)
        assert "clientCheck(" in text and 'type = "checkbox"' not in text


def test_apply_waits_for_work_not_for_a_timer():
    # The review in Details and the tray's Apply; the tray's bar in the dock rests and shakes on
    # purpose (dock.js).
    code = "\n".join(script(name) for name in (*PANEL, "tray.js"))
    css = (STATIC / "style.css").read_text()
    assert "520 - (performance.now()" not in code and "wait(450)" not in code
    assert "shake(" not in code
    assert ".drawer.open .body > *:nth-child(2)" not in css and "line-in" not in css
    assert "--t-panel: 240ms" in css
    assert ".socket .swap { opacity: 0; }" in css


def test_apply_sets_its_label_at_once_and_a_failure_focuses_the_button():
    # The tray's Apply: tray.js waits for work, never a timer; its bar in the dock rests on purpose
    # (dock.js). Details have no Apply of their own.
    code = "\n".join(script(name) for name in (*PANEL, "tray.js"))
    assert "setTimeout" not in script("tray.js") and "const wait" not in code
    dock = script("dock.js")
    assert 'apply: stepText("Applying", t.done, t.total)' in dock
    # A failure moves focus to the button that comes next, and a refusal clears at the next action.
    assert "(shown.apply || shown.changes || shown.cancel).focus(" in dock
    assert ".label.swap" not in CSS
    started = 'Object.assign(tray, { phase: "applying", refused: null, failure: null'
    assert started in script("tray.js")


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
    assert 'stepText("Applying", t.done, t.total)' in code and '"kitden:progress"' in code
    assert ".btn .meter" in css
    # The scan line shows only when a scan takes a while, so quick scans never blink.
    assert ".topbar.scanning::after { opacity: 1; transition-delay: 400ms;" in css


def test_while_a_change_is_written_the_tray_offers_nothing_to_stop_it():
    dock = script("dock.js")
    # Cancel and every × are off while the change is written: it cannot stop halfway.
    assert 'shown.cancel.disabled = t.phase === "applying" || t.phase === "applied";' in dock
    assert "item.out.disabled = working;" in dock
    # The line says what is written, and Apply takes no press until it ends.
    assert "line: writingLine(t.change.steps)" in dock and "applyWaits: true" in dock
    css = (STATIC / "style.css").read_text()
    # A button that is off never lights up on hover and says so with the pointer.
    assert ".btn:hover:not(:disabled)" in css
    assert ".btn:disabled { cursor: not-allowed; opacity: 0.5; }" in css


# Library: one page in place of Load map and Discover ---------------------------------------


def test_library_replaces_load_map_and_discover():
    assert "Load map" not in INDEX and "Discover" not in INDEX
    assert not (STATIC / "js" / "discover.js").exists()
    text = script("library.js")
    assert 'el("h1", null, "Library")' in text
    assert '[["mine", "Installed"], ["diff", "Differences"]]' in text
    # "Differs between clients" went away: the columns show it already.
    assert "Differs between clients" not in text
    # Old addresses open the Library; the Overview's links go there too.
    assert 'OLD_VIEWS = ["map", "discover"]' in script("store.js")
    overview = script("overview.js")
    assert 'kind: selected.kind, show: "mine"' in script("store.js")
    # An old New or All, and an old kind, land on their tab, as installed; the Library's MCP
    # servers are on the Gateway's List.
    store = script("store.js")
    assert (
        'const SHOWS = ["mine", "diff"];' in store
        and 'show: !old && SHOWS.includes(show) ? show : "mine"' in store
    )
    assert 'libraryKind = (kind) => (kind === "instructions" ? "instructions" : "plugin");' in store
    assert (
        'params.kind === "mcp_server") return { view: "gateway", params: { ...params, kind:'
        in store
    )
    assert 'goTo("library", sel)' in overview
    # A note's Details opens the item the note row names.
    assert 'follow({ view: "map", kind: row.kind, name: row.lookup })' in overview


def test_library_says_why_when_there_is_nothing_to_do():
    text = script("library.js")
    # A dash names its reason, after the scope and the route; no found client points to the
    # Overview.
    assert "[cell.where, cell.route, cell.reason].filter(Boolean)" in text
    assert "Kitden found no AI coding clients." in text and '"Open Overview"' in text
    # An empty search, filter or Differences says how to go back.
    assert '"Clear search"' in text and '"Show all"' in text and '"Show installed"' in text
    assert 'const NO_DIFFERENCES = "No differences between your clients";' in text
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
    # Every add in a project view says so, a marketplace too.
    assert "{ note: projectNote(state.project), back }" in offer
    code = panel()
    assert "export async function review(previewBody, { note = null, back = null } = {})" in code
    assert "if (note && !afterNotes.includes(note)) body.append(callout(note));" in code
    # The row keeps the note, and its review shows it.
    assert "addToTray(previewBody, { note })" in code
    # An add's choice of a row with a repeated name names its source.
    assert "rowTitle(row)" in text


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
    store = text.split("export function hiddenClients")[1].split("// The tab shown")[0]
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
    ):
        assert call in library
    assert ".table-scroll.waiting { opacity: 0.5; pointer-events: none; }" in css
    # A redraw of the same place notes where its rows were; the Library moves them from there.
    assert "snapshot: snapshotRows, settle: settleRows" in app
    assert "const before = samePlace && place.snapshot ? place.snapshot() : null;" in app
    # A place change: only the page moves, and the Library's rows are read first.
    # The Gateway and the Library's map rise on their own; the List moves as one page.
    assert 'RISES_ON_ITS_OWN(state) ? "map-entrance" : "place-change");' in store
    assert '(s.view === "library" && s.mode !== "list")' in store
    assert "html.place-change #main, html.map-entrance #main { view-transition-name: page; }" in css
    assert "::view-transition-new(page) { animation: 260ms var(--ease-out) both page-in; }" in css
    assert 'if (view === "library" && state.view !== "library") await raceSlow(' in app


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
    code = panel() + gw()
    for words in (
        '"Whole server"',
        "`Differs from ${row.follows} · `",
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
    # Details are drawn again after Apply all, the switch in its new state; the thumb slides once.
    assert "await detailsAgain();" in code
    assert 'toggle.classList.add("flipped")' in code
    assert ".switch.flipped .thumb" in CSS and "@keyframes thumb-on" in CSS
    # A refused change stays as a callout in Details, and focus goes back to the switch.
    assert "await back({ error: baseNames(tray.refused.reason) });" in code
    assert 'callout(error, "error")' in code


def test_a_tool_description_wraps_to_two_lines():
    # A tool's description wraps to two lines, so it can be read without a pointer.
    rule = CSS.split(".sw-tx small.about {")[1].split("}")[0]
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


def test_adding_a_marketplace_server_names_the_kitden_gateway():
    review, parts, tray = reviews(), script("parts.js"), script("tray.js")
    assert "`Add ${added} to the Kitden gateway`" in review
    assert "`${verb} ${added} to the Kitden gateway`" in review
    assert '"gateway.add": "Added"' in review and '"gateway.add": "Added"' in parts
    assert "to the Kitden gateway`" in parts.split('entry.action === "gateway.add"')[1]
    assert '"gateway.add"' in parts.split("export const PLACE_IN_TITLE")[1].split("\n")[0]
    assert 'if (action === "gateway.add") return `add:${params.server}`;' in tray
    assert AFTER_WORDS["gateway.add"] == ("gw", STATE_WORDS["gw"])
    assert NO_GATEWAY_CLIENT == "No client uses the Kitden gateway yet."


def test_a_skill_rule_says_what_it_turns_off_and_where():
    review, parts, tray = reviews(), script("parts.js"), script("tray.js")
    assert '"skill.rule": off ? `Turn off ${short}` : `Use the shared rule for ${short}`' in review
    assert "`${short} uses the shared rule`" in review
    assert '"skill.rule": "Turned off"' in review and '"skill.rule": "Changed how"' in parts
    assert '`${verb} ${names.join(", ")} loads${place} · ${clients.join(", ")}`' in parts
    key = '`skill:${one.client}:${one.item}@${params.project || ""}`;'
    assert f'if (action === "skill.rule") return {key}' in tray
    assert AFTER_WORDS["skill.rule"] == ("off", STATE_WORDS["off"])
    assert CURSOR_NO_SKILL_SWITCH == "Cursor has no switch to turn off one skill."
    assert NO_SKILL_MERGE == (
        "Claude Code may not merge skill settings across files; turn it off for all projects "
        "instead."
    )
    assert OWN_SKILL_SETTINGS == "{folder} has its own skill settings; it may keep this skill on."
    assert CODEX_NO_PROJECT == "Codex has no switch for one project; turn it off for all projects."
    assert FOLLOWS_SHARED == "Follows all projects"
    assert KEEPS_ITS_RULE == "It stays on in {folders}, which has its own rule."
    assert KEEP_THEIR_RULES == "It stays on in {folders}, which have their own rules."
    assert PLUGIN_SKILL == "A plugin's skill follows its plugin; turn the plugin off instead."
    assert PLUGIN_ALL_PROJECTS == "Turn a plugin off for all projects with its own switch."
    assert NO_CLAUDE_FOLDER == (
        "{folder} has no Claude Code settings yet; start Claude Code there once first."
    )


def test_the_add_a_server_panel_says_what_the_mockup_says():
    add, details = script("gateway-add.js"), script("gateway-details.js")
    # The search, the failed read and Try again are the shared panel's (add-panel.js).
    shared = script("add-panel.js")
    assert 'export const ADD_TITLE = "Add a server";' in add
    assert 'export const ADD_SERVER = "Add a server…";' in add
    assert "{ label: ADD_SERVER, run: () => openAdd() }" in details
    assert 'const SEARCH = "Search the marketplaces";' in shared
    assert "input.placeholder = `${SEARCH}…`;" in shared
    assert 'const FOOT = "Click a server or drag it onto the map to preview it.";' in add
    assert 'const NO_MATCH = "No servers match.";' in add
    assert 'const NONE = "No marketplace on this computer offers an MCP server.";' in add
    assert 'const FAILED = "Could not read the marketplaces.";' in shared
    assert 'button("Try again", retry, "btn ghost small")' in shared
    assert "return openAddPanel(GATEWAY, options);" in add
    statuses = '{ added: "Added", held: "In the gateway", preview: "In preview" }'
    assert f"export const STATUS = {statuses};" in add
    assert 'const KIND_WORDS = { remote: "Remote", local: "Local" };' in add
    assert 'const PILL = [["all", "All"], ["remote", "Remote"], ["local", "Local"]];' in add
    assert 'add: "Gateway" }' in details
    # No tool count and no sign-in words (D23, D24); no path, address or command.
    for word in ("tools", "Sign-in", "Sign in", "Community", "Team"):
        assert word not in add.split("export const ADD_TITLE")[1], word


def test_overview_cards_add_a_preview_or_open_a_page():
    overview = script("overview.js")
    # A change goes to the tray through the shared preview button, which says "In preview".
    assert "previewButton(action.label, action.body" in overview
    assert "button(action.label, () => openPlace(action.go), look)" in overview
    assert "No gateway yet." not in overview and "gatewayCardWords" not in overview
    # The card leaves only once the page has read the result of the applied change.
    assert 'if (t.phase !== "applied") return;' in overview
    assert "if (read < at) continue;" in overview
    # After Apply or Undo the Overview draws in place, so its card's motion is the one motion.
    assert 'view === "library" || view === "overview" ||' in script("review.js")


def test_library_says_the_add_scope_in_a_project():
    assert "Adding puts an item in all projects." in script("library.js")
    assert "all your projects" not in script("library.js") + script("offer.js")


def test_a_projects_own_skill_adds_into_the_project():
    assert "add.project_only" in script("library.js")
    assert '"This project\'s own skills add into this project."' in script("library.js")


def test_an_add_review_names_its_scope():
    code = panel()
    # With All projects picked the lede says it; in a project the note callout says it. A row's
    # review says it for the project the row was asked in.
    assert '"Adds for all projects. "' in code
    assert "reviewLede(change, picked)" in code and "picked: row.picked," in code
    assert '" for all projects"' in code


def test_the_review_leads_with_the_outcome_and_keeps_undo_honest():
    review = reviews()
    assert "Other projects are unchanged." in review and "A backup is kept." in review
    # One words table: the page's sentence is the twin of views/words.py's.
    assert f'const UNCHANGED = "{UNCHANGED} ";' in review
    assert "so you can undo" not in panel()
    # The toast after Apply says the row's own words, the same place as its title.
    assert "changeWords(rows[0].part, rows[0].body).done" in review
    # The Undo limit comes from the server (views/words.py REMOVE_NOTE), said once.
    assert "saved options" not in panel()
    assert "change.undo_note" in review


def test_add_missing_and_a_refused_list_go_back_to_details():
    review, shell, details = reviews(), script("panel.js"), script("details.js")
    assert "from && panelState.from === from ? backToDetails() : closePanel()" in review
    assert "backToDetails({ error: reason })" in review
    assert "panelState.from = null" in shell
    # Details, and the Gateway's cards of a held server and a tool, keep how to draw themselves
    # again (details.test.mjs tests keepFrom and backToDetails).
    assert "keepFrom(" in details
    assert "keepFrom(draw, nodes, read)" in gw()
    redraw = "() => drawHeld(name, detail, { warning }), () => showHeld(name), step)"
    assert redraw in gw()
    assert "() => showTool(serverName, name), step)" in gw()
    assert 'more.dataset.focus = "more";' in details
    # Add missing's own list is never applied, so the server forgets it at once.
    assert "if (id) postJson(`/api/changes/${encodeURIComponent(id)}/cancel`)" in review


def test_the_tray_says_when_its_settings_changed():
    # After a rescan the tray asks the server about its preview (tray.test.mjs).
    assert "checkTrayStale().catch(reportError);" in script("app.js")
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
    assert "startAdd(cell.add, client, row)" in library


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
        '"Turn off in some projects…"',
        '"On in this project"',
        '"Off · server off"',
        '"Reads only"',
        '"May write"',
        '"Not reported"',
        '"New · waits"',
        '"On by default"',
        "of ${",
        " on`",
    ):
        assert words in text, words
    assert "Allowed" not in text and "Blocked" not in text and "Sign in" not in text
    # With All projects a card says "in every project" or "in any project", then each known project
    # that decides otherwise ("Except atlas, where it is on."); never "Other projects follow".
    assert "Other projects follow" not in gw() and '"Read only"' not in gw()


def test_tool_and_server_details_say_what_they_know():
    text = gw()
    for words in (
        '"Off in this project"',
        '"Not reported · its name suggests it writes"',
        "call this tool through Kitden by the shared rule.`",
        "is off ${place}, so none of its tools can be called.${others}`",
        '"No client uses the Kitden gateway yet."',
        "`Open ${server.name}`",
        '"Not known yet"',
        '"by the shared rule"',
        '` ${plural(k, "project decides", "projects decide")} otherwise.`',
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


def test_the_server_panel_says_the_mockups_words():
    # The server panel of the mockup (gateway-notes 3.3, 4.2): a list of switches, Move out, and
    # every other action under More (D18). No sign-in words (D23).
    text, tools = gw(), script("tools.js")
    for words in (
        'server: "Server"',
        "· in the Kitden gateway`",
        '"Move out of the gateway…"',
        "`Server · ${name}`",
        "`Move ${name} out of the gateway`",
        "`Pick the client that keeps it.${drag}`",
        "` You can also drag ${name} onto a client on the map.`",
        '"Uses the gateway now"',
        '"Not connected to the gateway"',
        "`The other clients lose ${name}'s tools.`",
    ):
        assert words in text, words
    for words in (
        "`${on} of ${all} tools on`",
        '"Every tool is off"',
        'reads: "Reads only"',
        'writes: "May write"',
        "`Differs from ${row.follows} · `",
        "`Use ${row.follows}`",
        "Tools · ${where || ALL_PROJECTS}",
    ):
        assert words in tools, words
    assert "Sign in" not in text and "Signed in" not in text
    # A server off by the shared rule is never "off in all projects": projects may turn it on.
    assert "is off by the shared rule, so none of its tools are offered.${otherwise}`" in tools
    assert 'off in ${where || "all projects"}' not in tools
    # A server moves out to one client: a second pick replaces the first row.
    assert "`moveout:${params.server}`" in script("tray.js")


def test_the_tool_panel_says_the_mockups_words():
    # The tool panel and its "in some projects" step (gateway-notes 3.4 and 5), with the real
    # clients' names. Each ticked project is its own row in the tray (D13).
    text = gw()
    for words in (
        'label: "Permission"',
        '"On in this project"',
        "· from ${",
        '"all projects"',
        '"Projects with a rule of their own"',
        '"Show"',
        "`Show ${",
        "call this tool through Kitden, in every project.`",
        "call this tool through Kitden, in any project.`",
        " Except ${",
        ", where it is ${",
        " follows the shared rule: ",
        "'s rule: ",
        "call this tool in ${folder}.`",
        "Every other project has it on",
        "Every other project still has it off",
        '"Turn on in some projects…"',
        '"Turn off in some projects…"',
        " in the projects you pick`",
        "`The shared rule stays ${",
        "follows ${p.name} and changes with it.`",
        "follow ${p.name} and change with it.`",
        "FIND_PROJECT",
        '"No project matches."',
        '"Tick projects. Each one waits in preview until Apply."',
        " in preview. Apply them from the tray.`",
        '"Done"',
        "`already ${",
        " now`",
        "`Tool · ${",
    ):
        assert words in text, words
    # The project choice of one project is gone from the Gateway: the step ticks several. The step
    # never says every other project keeps the shared rule: one may keep its own, or follow another.
    assert "projectChoice" not in text and "projectChoice" not in script("details.js")
    assert "Every other project keeps" not in text
    # While a project's rows wait, the map's tool block names the project, or how many.
    assert "`in preview for ${" in script("gateway.js")
    for selector in (".pick.multi", ".own-row", ".facts dd.warn", ".find-project"):
        assert selector in CSS, selector


def test_the_client_gateway_link_and_outside_panels_say_the_mockups_words():
    # The client, gateway, connection and outside panels of the mockup (gateway-notes 3.5-3.8).
    # What Kitden does not know stays out (D23, D24): no "Running", no "not tested", no sign-in,
    # no Library counts, no drag that is not there yet, and no rules file of its own: a rule is
    # written in the gateway's file.
    text = gw()
    for words in (
        "· on this Mac`",
        '"Connect to the gateway…"',
        '"Disconnect from the gateway…"',
        '"See what it loads in Library"',
        '"Through Kitden"',
        '"On its own"',
        '"Nothing yet"',
        '"Nothing"',
        '" · change in preview"',
        '" · in preview"',
        '"Connect…"',
        '"Disconnect…"',
        "in the gateway · ${",
        " through Kitden, so Kitden's rules apply to them.`",
        " on its own and skip",
        "gets Kitden from a plugin: turn the plugin off to disconnect it.`",
        " loses the Kitden gateway's servers and Kitden's own read of your setup. Servers it"
        " sets up on its own stay.`",
        "`Kitden did not find ${",
        'connection: "Connection"',
        '"Route through the gateway"',
        '"Held by the gateway"',
        '"Tool on"',
        '"Direct route"',
        '"Written in"',
        "'s settings`",
        '"Kitden\'s gateway file"',
        '"In place"',
        '"This link is a change in preview. Nothing is written until you Apply."',
        '"Take it out of the preview"',
        "`Disconnect ${",
        "· outside the gateway`",
        '"Set up in"',
        '"Direct, on its own"',
        '"Kitden\'s rules"',
        '"Don\'t reach it"',
        " on ${own}, so Kitden can't turn its tools on or off.",
        '"Move it into the gateway to manage them here."',
        " it either way.`",
        '"Update the Kitden entry…"',
        '"Update…"',
        '"from a plugin"',
        '"not on this Mac"',
        '"its entry is off"',
        '"settings not readable"',
        "`Remove ${to.name} from ${from.name}`",
        '"Version not known · on this Mac"',
    ):
        assert words in text, words
    review, parts = script("review.js"), script("parts.js")
    assert '"setup_server.update": `Update Kitden in ${clients}`' in review
    done = '"setup_server.update": "Updated Kitden"'
    assert done in review and done in parts
    assert "show my setup” to Kitden" not in review
    assert "Updated show my setup" not in review + parts
    # A link with no removal still takes the pointer, with no × and no Delete.
    view = script("map-view.js")
    assert '"aria-keyshortcuts": tip ? "Delete" : null' in view
    for words in ('"Kitden entry"', "Running", "not tested", "Drag it onto", "Kitden's rules file"):
        assert words not in text, words
    for selector in (".chip-s", "header.has-tile", ".p-tile", ".client-rows", ".facts dd.quiet"):
        assert selector in CSS, selector


def test_connect_and_disconnect_say_kitden():
    # The `kitden` entry is how a client reaches Kitden: Gateway and Agents say it the same way.
    review, parts = script("review.js"), script("parts.js")
    for words in (
        "`Connect ${clients} to Kitden`",
        "`Disconnect ${clients} from Kitden`",
        "`${verb} ${clients} to Kitden`",
        "`${verb} ${clients} from Kitden`",
        '"setup_server.register": "Connected"',
        '"client.disconnect": "Disconnected"',
    ):
        assert words in review, words
    assert '"setup_server.register": "Connected to Kitden"' in parts
    assert '"client.disconnect": "Disconnected from Kitden"' in parts
    place = parts.split("export const PLACE_IN_TITLE")[1].split("\n")[0]
    assert '"setup_server.register"' in place and '"client.disconnect"' in place
    # The old words are gone; the update of an old entry keeps its own.
    for old in ("Add “show my setup”", "Added show my setup"):
        assert old not in review and old not in parts, old


def test_move_out_says_where_the_server_goes():
    # A server leaves the Kitden gateway for one client's own file.
    review, parts, tray = script("review.js"), script("parts.js"), script("tray.js")
    for words in (
        "`Move ${server} out of the gateway into ${clients}`",
        "`${verb} ${server} into ${clients}`",
        '"gateway.move_out": "Moved"',
    ):
        assert words in review, words
    assert '"gateway.move_out": "Moved out of the gateway"' in parts
    # Its title names its place, so it takes no scope words and is not one of the page's ADDS.
    place = parts.split("export const PLACE_IN_TITLE")[1].split("\n")[0]
    assert '"gateway.move_out"' in place
    adds = review.split("export const ADDS = [")[1].split("]")[0]
    assert "gateway.move_out" not in adds
    assert '"gateway.move_out"' in tray and '"log-out"' in tray


def test_the_tool_list_has_a_strict_switch():
    assert 'action: "gateway.strict"' in gw()


def test_the_tool_list_says_reads_and_writes_and_has_a_batch_switch():
    code = panel() + gw()
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


def test_a_server_can_be_added_to_another_client():
    assert '"mcp.add": `Add ${names} to ${clients}`' in panel()
    assert '"mcp.add": "Added"' in script("parts.js")
    assert 'add.action === "mcp.add" ? { item: add.item }' in script("library.js")


def test_a_project_can_be_aligned_in_one_review():
    library = script("library.js")
    assert 'const ADD_MISSING = "Add missing plugins and skills…";' in library
    assert '"add:missing"' in library
    code = panel()
    assert "Not the same; not touched" in code and '"project.align"' in code


def test_add_missing_works_under_all_projects_too():
    # The List offers it in any scope; with no project the review is for all projects.
    library = script("library.js")
    assert "params: { project: state.project || null, chosen: null }" in library
    code = panel()
    assert '"Add what your clients are missing"' in code
    assert (
        '`Added ${plural(chosen.length, "item", "items")} for ${folder || "all projects"}`' in code
    )
    # Nothing missing is an answer, said plainly with only Close.
    assert 'const NOTHING_MISSING = "Nothing is missing";' in code
    assert 'header("Add missing", reason, null, null)' in code
    align = (STATIC.parents[1] / "changes/align.py").read_text()
    assert 'raise ValueError(f"Nothing is missing{where}.")' in align


def test_the_add_forms_and_the_add_choice_say_in_preview():
    offer = script("offer.js")
    assert 'const PREVIEW = "Preview";' in offer
    assert "showInPreview(submit, words, PREVIEW, keyFor(bodyOf()))" in offer
    assert 'form.addEventListener("change", follow);' in offer
    library = script("library.js")
    assert "previewButton(choice.label, previewFor(add, client, choice.scope)" in library


def test_a_failed_change_does_not_claim_a_restore_on_the_page():
    # The engine's error says "The original settings were restored." only when it is true.
    assert "were put back" not in panel()
    assert "The change did not check out. Kitden put the files back." in panel()
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
    # Its List has one row per file; a cell says "Reads it" or nothing (views/library.py).
    assert 'READS_IT = "Reads it"' in (STATIC.parents[1] / "views/library.py").read_text()


def test_details_shows_an_instruction_files_first_lines():
    assert 'el("pre", "preview"' in panel()
    assert "pre.preview" in (STATIC / "style.css").read_text()


def test_details_answer_in_order_and_fold_the_evidence():
    details = script("details.js")
    assert '"Technical details"' in details and "fold(" in details
    assert 'el("pre", "preview"' in details  # the first lines, inside the fold
    assert "details.tech" in CSS
    # The route words are Part 2's.
    assert "ROUTE_WORDS.folder" in details


def test_pages_import_the_side_panel_through_panel_js():
    for name in ("gateway.js", "gateway-details.js", "gateway-drag.js", "offer.js"):
        assert 'from "./details.js"' not in script(name), name
    shell = script("panel.js")
    for word in ("detailsCard", "technical"):
        assert re.search(rf"export \{{[^}}]*\b{word}\b[^}}]*\}} from \"./details.js\"", shell), word


def test_a_demo_says_so_quietly_in_the_rail():
    assert 'getJson("/api/about")' in script("app.js")
    parts = script("parts.js")
    assert '"Demo"' in parts
    hover = "A sample setup in a temporary folder. Your own settings are not read or changed."
    assert hover in parts
    assert "Demo" not in INDEX  # only a demo's answer adds it


def test_a_card_without_a_button_keeps_its_words_in_the_wide_column():
    # An unreadable file has no action; its words take the room the button would.
    assert ".ov-card .tx { flex: 1; min-width: 0;" in CSS


def test_a_client_kitden_could_not_read_says_so_under_its_name():
    assert "column.note" in script("library.js")


def test_a_cell_kept_from_the_last_good_read_has_a_dashed_dot():
    assert ".socket.stale .dot { border-style: dashed; }" in CSS


def test_needs_review_is_an_amber_ring_with_a_small_dot():
    assert ".s-review { color: var(--lamp-warn); }" in CSS
    assert ".s-review .dot::after { transform: scale(0.5); border-radius: 50%; }" in CSS


def test_overview_notes_say_same_name_another_source():
    text = script("overview.js")
    assert 'same_name_other_source: "has the same name as an entry from another source"' in text


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
        # Its form closes again: a quiet Cancel beside Save gateway (Escape in the form too).
        'el("h2", null, "Add another gateway")',
        'button("Cancel", () => onCancel(), "btn")',
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
    ):
        assert words in text, words
    assert "projects have its" not in text


def test_search_on_a_map_page_finds_on_that_page():
    app = script("app.js")
    assert 'MAP_PAGES = ["gateway", "library"]' in app and 'go("library", { q })' in app
    # The chip's words are shared by every map page, so they live in map.js.
    assert '"match", "matches"' in script("map.js") and '"No matches"' in script("map.js")
    assert '<span class="find-chip" id="find-chip" role="status"></span>' in INDEX
    # The empty chip stays in the page (a live region that is drawn announces its first words);
    # it only gives back the gap before it.
    empty = re.search(r"\.find-chip:empty \{([^}]*)\}", CSS)
    assert empty and "margin-left: -8px;" in empty.group(1) and "display" not in empty.group(1)
    # Matches are lit; on the map the other blocks dim to 30% with less colour and a blur, their
    # links to 20%; in the List the other rows dim to 35%.
    assert ".map.finding" in CSS
    dims = r"div\.map\.finding \.block:not\(\.found\)[^{]*\{ filter: opacity\(0\.3\) "
    assert re.search(dims + r"saturate\(0\.5\) blur\(1\.2px\); \}", CSS)
    assert "div.map.finding .link { stroke-opacity: 0.2; }" in CSS
    assert ".treegrid.finding .tg-row:not(.found) { opacity: 0.35; }" in CSS


def test_finding_keeps_the_place_and_the_details():
    app = script("app.js")
    # Escape in the search clears it on a map page, and only then keeps Details open.
    assert 'event.key !== "Escape" || !MAP_PAGES.includes(state.view)' in app
    assert "event.stopPropagation();" in app.split('$("#q").addEventListener("keydown"')[1]
    # "/" works beside floating Details, not under the modal drawer.
    assert '!$("#drawer").classList.contains("floating")' in app
    assert 'if (event.key === "/" && !typing && !modal) {' in app
    # The Gateway only lights, dims and opens blocks for the view: it asks nothing of a client.
    text = script("gateway.js")
    # A press on a block the search holds open changes nothing (map.js pressOpen), in the map and
    # the List.
    assert "onMap.open = pressOpen(model, onMap.open, onMap.found, id);" in text
    assert "if (row.kept) return;" in text.split("function toggleRow(")[1].split("\n}\n")[0]
    find = text.split("export function findRows(")[1].split("\n}\n")[0]
    assert "postJson" not in find and "review(" not in find and "setState" not in find


def test_the_map_previews_are_tray_rows():
    # The map has no review of its own any more: a link's ×, a drop, and a press on a preview block
    # or a link the tray draws add or take out rows of the one tray (dock.js draws its bar).
    assert not (STATIC / "js" / "map-review.js").exists()
    for path in (STATIC / "js").glob("*.js"):
        assert "map-review" not in path.read_text(), path.name
    review = script("review.js")
    assert "setMapReview" not in review and "mapReview" not in review
    text = gw()
    for words in (
        'const TAKE_OUT = "Take it out of the preview";',
        "addToTray(removal.body, { icon: removalIcon(removal.body) })",
        '(body.action === "client.disconnect" ? iconFor(body) : "x")',
        "addToTray(body)",
        "takeOut(",
        "onTray(trayChanged);",
    ):
        assert words in text, words
    assert "review(removal.body)" not in text
    assert '"Drop to add"' in text and "dropBody(" in text and "moveBody(" in script("details.js")
    # The bar the map's rows join says what is written, and what Apply did, in dock.js.
    dock = script("dock.js")
    assert "A backup is kept." in dock and '"Nothing was changed"' in dock
    assert "Sign in after Apply" not in review + dock


def test_the_map_previews_connect_disconnect_and_move_out():
    # gateway-notes 4.1, 4.2, 4.4: a connect waits as a preview link and the client says so; a
    # disconnect, a removed entry and a removal from the gateway leave; a move out waits outside.
    text = gw()
    for words in (
        'wait: "\\u00a0· in preview"',
        "meta: `Moves to ${CLIENT_NAMES[move.client]}`",
        'kind: "direct", preview: true',
    ):
        assert words in text, words
    assert 'block.leaving && "Leaving"' in script("map.js")
    assert 'const LINK_FLAGS = ["unk", "leaving", "preview"];' in script("map.js")
    # The waiting words are in the accent and wrap under the state words, beside the lamp.
    assert "color: var(--route);" in rule("div.map .block-wait")
    words = rule("div.map .block-words:has(> .block-wait), div.map .block.preview .block-words")
    assert "white-space: normal" in words and "text-wrap: balance" in words
    assert "padding-right: 2px" in rule("div.map .block.client:has(.block-wait)")
    # A preview or leaving line keeps its look when lit; a move out's line is accent when pointed.
    left = rule("div.map .link.leaving.lit:not(.hov):not(.picked)")
    assert "stroke: var(--ink-3)" in left and "stroke-opacity: 0.4" in left
    added = rule("div.map .link.direct.preview.lit:not(.hov):not(.picked)")
    assert "stroke: var(--route)" in added and "stroke-opacity: 0.65" in added
    pointed = rule("div.map .link.direct.preview.hov, div.map .link.direct.preview.picked")
    assert "stroke: var(--route)" in pointed
    assert CSS.index("div.map .link.direct.preview.hov") > CSS.index("div.map .link.direct.hov")
    # Outside the gateway an icon has no tile, a move out's preview too.
    assert "border: 0" in rule("div.map .block-icon.bare")
    assert "div.map .block.outside .block-icon" not in CSS


def test_the_map_preview_words_and_look():
    dock = script("dock.js")
    # What is written, in the owner's words; the step count comes from the server.
    assert "`Writing ${names[0]}'s settings. A backup is kept.`" in dock
    assert "`Writing the settings of ${joinWords(names)}. A backup is kept.`" in dock
    assert '"the Kitden gateway"' in dock and 'stepText("Applying", t.done, t.total)' in dock
    # A refusal says why; the bar is a region with a status line.
    assert '"Could not prepare this change"' in dock
    assert 'setAttribute("role", "region")' in dock and 'setAttribute("role", "status")' in dock
    # The preview block says it is a preview; it sits on the preview fill with the preview line.
    assert '"Preview"' in script("gateway.js")
    look = r"div\.map \.block\.preview \{[^}]*var\(--preview-line\)[^}]*var\(--preview-fill\)"
    assert re.search(look, CSS)
    # The map's own review bar went with map-review.js.
    assert ".review-bar" not in CSS
    # A drag starts after 5 px (the engine every map shares); the keyboard path stays "Move in…".
    assert "export const DRAG_START = 5;" in script("map-drag.js")
    assert '"Move in…"' in script("gateway.js")


def test_a_drag_keeps_its_press_lights_its_target_and_has_a_tip():
    # gateway-notes 6.0 and 1.9: the dragged block keeps the .98 press while the pointer is down; a
    # drop target takes the accent edge, the selection fill and 1.05 on the spring; the tip is an
    # 11 px pill on the panel fill with a line edge and the shadow, in the accent when a drop works.
    assert "scale: 0.98" in rule("div.map .block.dragging.pressed")
    target = rule("div.map .block.drop")
    for words in ("border-color: var(--route)", "background: var(--route-soft)", "scale: 1.05"):
        assert words in target, words
    assert "scale 260ms var(--spring)" in rule("div.map .block")
    tip = rule("div.map .dragtip")
    for words in (
        "font-size: 11px",
        "background: var(--panel)",
        "border: 1px solid var(--wire)",
        "box-shadow: var(--shadow)",
        "pointer-events: none",
        "color: var(--ink-3)",
    ):
        assert words in tip, words
    on = rule("div.map .dragtip.on")
    accent = ("background: var(--route-soft)", "border-color: var(--route)", "color: var(--route)")
    for words in accent:
        assert words in on, words
    # The drag holds the pointer on its block and is one engine for every drag of every map.
    drag = script("map-drag.js")
    assert "setPointerCapture(" in drag
    assert "export function startDrag(event, block, kind, { hooks, map, onStart" in drag
    assert "setPointerCapture(" not in script("gateway-drag.js")
    assert 'from "./map-drag.js"' in script("gateway-drag.js") + script("library-map.js")
    assert "div.map.dropping" not in CSS
    # The slot a dropped block flies onto hides at once; looks never set a block's opacity.
    assert "visibility: hidden" in rule("div.map .block.covered")


def test_a_server_drags_onto_a_client():
    # gateway-notes 6.2: the tip asks for a client, then says where a drop moves the server; a
    # client that cannot take it says why before the drop, in the tip's plain look.
    drag = script("gateway-drag.js")
    assert 'export const ON_CLIENT = "Drop on a client";' in script("map-drag.js")
    for words in (
        "`Move into ${CLIENT_NAMES[client.client]}`",
        "`${who} already has ${name}.`",
        "`${who} is not on this Mac.`",
    ):
        assert words in drag, words
    # Its client's box is widened 24 px left, 40 right and 16 up and down (map-drag.js).
    assert "const NEAR_CLIENT = { left: 24, right: 40, up: 16, down: 16 };" in script("map-drag.js")


def test_a_client_drags_onto_the_gateway():
    # gateway-notes 6.3: the tip asks for the gateway, then says a drop connects the client; a
    # client a plugin connects says why it cannot be dragged.
    drag = script("gateway-drag.js")
    for words in (
        'const ON_GATEWAY = "Drop on the gateway";',
        "`Connect ${CLIENT_NAMES[drag.block.client]}`",
        "`${name} gets Kitden from a plugin.`",
    ):
        assert words in drag, words
    # The gateway's box is widened 24 px each side and 16 up and down.
    assert "const NEAR_GATEWAY = { side: 24, up: 16, down: 16 };" in drag


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
    # The line says whether a click on the map takes a row out, so it follows the place (a redraw
    # of the page never takes the dock from a toast); the page keeps room under the bar; the small
    # buttons have the press.
    assert "drawTray(tray, { toastStays: true });" in script("app.js")
    assert 'state.view === "gateway" && Boolean($("#main .map"))' in dock
    assert "--dock-room" in script("toast.js") and "makeRoom" in script("dock.js")
    assert "var(--dock-room, 0px)" in CSS
    assert ".dock .ib:active, .dock .x:active:not(:disabled) {" in CSS


def test_a_screen_reader_hears_the_tray_change():
    dock, toast = script("dock.js"), script("toast.js")
    # Each change that joins or leaves the tray is said through the page's quiet live region, and
    # why an add was refused when the bar comes in with it. The bar names a file, never its path.
    assert "export function say(text) {" in toast
    assert 'from "./toast.js"' in dock and "say(news)" in dock
    for words in (
        ": in the preview.",
        " changes taken out of the preview.",
        ": taken out of the preview.",
    ):
        assert words in dock, words
    assert "export function baseNames(text) {" in script("parts.js")
    assert "baseNames" in script("review.js") and "baseNames" in dock
    # A switch whose change waits says so in its name: its checked state stays the real one.
    assert "(in preview)" in script("details.js")
    # A row's review cannot take its row out while the tray is written.
    assert 'node.setAttribute("aria-disabled", "true");' in script("review.js")


def test_every_change_waits_in_the_tray():
    review, details, shell = script("review.js"), script("details.js"), script("panel.js")
    # Add missing's chooser adds its row with the ticks; a row's review can take it out again.
    assert '"Add to preview"' in review and '"Take it out"' in review
    # A Details button whose change waits in the tray says so and takes no press.
    assert 'const IN_PREVIEW = "In preview";' in details
    assert "export function previewButton(label, body," in details
    # Details have no Apply of their own: the tray's bar writes everything, and the key presses it.
    for name in PANEL:
        assert "Enter to apply" not in script(name), name
    gone = ("function applyChange", "function showApplied", "function checkStale", "APPLY_KEY")
    for name in gone:
        assert name not in review, name
    assert '$("#dock .apply")' in shell and 'tray.phase !== "ready"' in shell
    # Closing Details never cancels a change on the server: the tray holds every preview.
    assert "/cancel" not in shell
    # After a rescan the tray asks whether its preview is stale.
    assert "checkTrayStale()" in script("app.js")


def test_the_toast_lives_in_the_dock_and_is_its_own_module():
    toast = script("toast.js")
    # The centred toast is gone from the shell and the style sheet.
    assert 'id="toast"' not in INDEX
    assert ".toast.show" not in CSS and "@keyframes countdown" not in CSS
    assert "shell.docked ~ .toast" not in CSS and ".toast .check" not in CSS
    # The dock holds it. A live region that is always on the page says its words; the toast is not
    # a second one, so a screen reader does not say it twice.
    assert '<div class="sr-only" id="said" role="status" aria-live="polite"></div>' in INDEX
    assert ".dock .toast {" in CSS and ".dock .toast .life {" in CSS
    assert '$("#said")' in toast and 'setAttribute("role"' not in toast
    # Its life is 9 s, a linear line toward the left, and reduced motion does not shorten it.
    assert "LIFE_MS = 9000" in toast and 'easing: "linear"' in toast
    assert "D(LIFE_MS) || LIFE_MS" in toast

    # It imports only dom.js, motion.js and store.js (which imports none of the panel's modules),
    # so panel.js can hand it on without an import cycle.
    def imports(text: str) -> list[str]:
        return sorted(re.findall(r'from "(\./[^"]+)"', text))

    assert imports(toast) == ["./dom.js", "./motion.js", "./store.js"]
    assert imports(script("store.js")) == ["./api.js", "./motion.js"]
    shell = script("panel.js")
    assert 'export { hideToast, toast } from "./toast.js";' in shell
    assert "TOAST_MS" not in shell and "#toast" not in shell
    # Nothing reads the old element any more.
    for name in sorted(path.name for path in (STATIC / "js").glob("*.js")):
        assert '"#toast"' not in script(name), name


def test_the_dock_stands_above_the_scrim_and_the_drawer_keeps_its_room():
    # The page frame keeps no stacking context of its own: the dock (the bar and the toast) is
    # above the scrim (20) and the Details drawer (21), so Apply and Undo can always be pressed.
    assert "isolation" not in rule(".content")
    assert "z-index: 22" in rule(".hint-dock")
    assert "z-index: 20" in rule(".scrim") and "z-index: 21" in rule(".drawer")
    # The room kept under the dock is on the page root, so the page and the modal drawer read it.
    makeRoom = script("toast.js")
    assert "const root = document.documentElement;" in makeRoom
    assert 'root.style.setProperty("--dock-room"' in makeRoom
    # The room is measured from the frame's content, 17 px above the window's bottom (the 16 px
    # gutter and the frame's 1 px line): + 25 px ends the drawer 8 px above the dock. With an empty
    # dock the room is -9 px, so the drawer ends 16 px above the window, like the frame.
    assert "bottom: max(16px, calc(var(--dock-room, -9px) + 25px));" in rule(".drawer")
    # The Tab loop of the modal drawer takes the dock's buttons, the bar's and the toast's.
    shell = script("panel.js")
    assert 'const dock = $("#dock");' in shell and '"button:not([disabled])", dock' in shell


def test_the_map_views_draw_puts_its_hits_in_order_with_a_helper():
    # `draw` does not grow (the plan's rule): the hit order is its own small helper beside it.
    view = script("map-view.js")
    assert "  function orderHits(layout) {" in view
    assert "    orderHits(layout);\n" in view


def test_the_list_has_the_mockups_columns_and_quiet_read_and_write_words():
    # gateway-notes 7.2: Name, Used by, Tools and a last column with no title (a screen reader
    # hears "Action"); a tool's Read or Write is quiet text, not a flag.
    text = gw()
    assert 'for (const name of ["Name", "Used by", "Tools", ""])' in text
    assert 'el("span", "sr-only", "Action")' in text
    assert 'el("span", "hint", row.tag)' in text and "flag(" not in text
    assert "--tg-cols: minmax(0, 1fr) 130px 150px 100px; max-width: 912px;" in CSS
    for words in ("Sign in", "Signed in", "Running"):
        assert words not in text, words


def test_the_view_switch_goes_out_in_120_and_comes_in_in_260():
    # gateway-notes 7.1: the view that shows goes up 4 px and out (120 ease-in), the page draws
    # the other, which comes in from 6 px below (rise: 260 CALM). The selection lets go.
    # The switch is shared by the map pages (map-page.js).
    shared = script("map-page.js")
    assert 'animateTo(node, keyframes, { dur: 120, ease: "ease-in", fill: "forwards" })' in shared
    assert '{ opacity: 0, transform: "translateY(-4px)" }' in shared
    assert "if (switched) rise([" in gw() and "if (switched) rise([" in script("library-map.js")
    switch = shared.split("function switchView(")[1].split("\n}\n")[0]
    assert "letGo();" in switch and "!D(1)" in shared.split("function leaveThen(")[1]
    assert "letGo: letGoIfSelected" in gw()


def test_the_dot_grid_lies_under_the_page_below_the_top_bar_and_takes_no_pointer():
    # The one effect taken from the mockup's Rich mode, with the spotlight (Task 4.10): a canvas in
    # the page column, below the top bar, not read by a screen reader, and under the page.
    assert re.search(r'<canvas class="dots" id="dots" aria-hidden="true"></canvas>', INDEX)
    assert INDEX.index('id="topbar"') < INDEX.index('id="dots"') < INDEX.index('id="main"')
    dots = rule(".dots")
    assert "pointer-events: none" in dots and "position: sticky" in dots
    assert "z-index: 0" in dots and "var(--glow-top" in dots and "var(--glow-h" in dots
    assert "z-index: 1" in rule(".page") and "position: relative" in rule(".page")
    assert 'startGlow($("#content"))' in script("app.js")


def test_the_glow_colour_is_the_mockups_in_both_themes_and_no_text_uses_it():
    assert CSS.count("--glow: 196 84 50;") == 1 and CSS.count("--glow: 240 154 124;") == 2
    assert CSS.index("--glow: 196 84 50;") < CSS.index("--glow: 240 154 124;")
    assert not re.search(r"(?<!-)color:\s*rgb\(var\(--glow", CSS)


def media_blocks(query: str) -> list[tuple[int, str]]:
    """Each `@media` block that starts with `query`: where it starts and its text."""
    found = []
    for start in [m.start() for m in re.finditer(re.escape(query), CSS)]:
        depth = 0
        for at in range(CSS.index("{", start), len(CSS)):
            depth += CSS[at] == "{"
            depth -= CSS[at] == "}"
            if depth == 0:
                found.append((start, CSS[start : at + 1]))
                break
    return found


def test_the_stylesheets_braces_balance_and_never_go_below_zero():
    text = re.sub(r"/\*.*?\*/", "", CSS, flags=re.DOTALL)
    depth = 0
    for char in text:
        depth += char == "{"
        depth -= char == "}"
        assert depth >= 0, "a closing brace with nothing open"
    assert depth == 0


def test_the_spotlight_is_calmer_than_the_mockups_and_off_under_reduced_motion():
    # The mockup's edge glow is 130 px at .85 and its fill 200 px at .08; Kitden's is .35 and .04,
    # fading in 250 ms on hover. Only map blocks and Overview cards have it.
    [(start, spot)] = media_blocks("@media (prefers-reduced-motion: no-preference) {")
    assert "130px circle at var(--mx, -300px) var(--my, -300px), rgb(var(--glow) / .35)" in spot
    assert "200px circle at var(--mx, -300px) var(--my, -300px), rgb(var(--glow) / .04)" in spot
    assert "opacity: 0; transition: opacity 250ms" in spot
    assert "div.map .block::before" in spot and 'data-place="overview"' in spot
    assert ".85" not in spot and ".08" not in spot
    assert "pointer-events: none" in spot
    # The block ends before the tray's rules and holds none of them or the map's other rules.
    assert start < CSS.index("/* The preview tray's bar") and start + len(spot) < CSS.index(
        ".dock {"
    )
    for outside in (".dock {", "div.map .block-tile", ".scrim {", "#drawer.floating"):
        assert outside not in spot, outside
    assert CSS.index("div.map .block-tile") < start
    # The glow shows only where a pointer hovers, so a tap leaves none stuck.
    [(_, hover)] = media_blocks(
        "@media (prefers-reduced-motion: no-preference) and (hover: hover) {"
    )
    assert ":hover::before" in hover and ":hover::after" in hover and "opacity: 1" in hover
    assert ":hover" not in spot
    assert ".dock {" not in hover and hover.count("{") == 2
    # Nothing loops: no beam, dash march, ripple, spark or sheen from Rich mode.
    for word in ("beam", "march", "ripple", "spark", "sheen"):
        assert word not in spot and word not in script("glow.js"), word
    glow = script("glow.js")
    for banned in ("innerHTML", "cssText", 'setAttribute("style"'):
        assert banned not in glow, banned


def test_a_control_that_waits_for_another_change_says_why():
    # Apply, the toast's Undo and a link's × keep focus while another change is written: they are
    # aria-disabled, show the busy cursor and say why in their title (dom.js showWaits).
    dom = script("dom.js")
    assert 'export const WAITS = "Another change is being written.";' in dom
    for name in ("dock.js", "toast.js", "map-view.js"):
        assert "showWaits(" in script(name), name
    assert '.dock .btn[aria-disabled="true"] { cursor: progress; }' in CSS
    assert 'div.map .link-x[aria-disabled="true"] { cursor: progress; }' in CSS
    # During the tray's own Apply a link's × says the change is the person's own.
    assert 'export const OWN_WAITS = "Your change is being written.";' in script("gateway.js")


def test_a_gateway_kitden_cannot_reach_says_a_short_state_and_no_block_words_run_out():
    # The reason (it may name a variable) waits in the gateway's Details; the map and the List say
    # a short state (2026-10-26 owner screenshot: Obot's error ran out of its block).
    assert 'export const NOT_REACHED = "Not connected";' in script("gateway-details.js")
    assert "? NOT_REACHED :" in script("gateway.js")
    # A block's lines end in "…" inside it, also where the gateway centres them.
    assert "div.map .block-text > *, div.map .block-stats { max-width: 100%; min-width: 0; }" in CSS
    for rule in ("div.map .block-name {", "div.map .block-words {"):
        body = CSS.split(rule, 1)[1].split("}", 1)[0]
        for part in ("overflow: hidden", "text-overflow: ellipsis", "white-space: nowrap"):
            assert part in body, (rule, part)


def test_a_rail_count_always_fits_whole():
    # 2026-10-26 owner screenshot: ten changes showed "1C", cut by the rail's edge. The count never
    # shrinks; the words beside it give way first and end in "…".
    assert ".nav .count { flex: none; margin: 0 -5px; }" in CSS
    label = CSS.split(".nav .label {", 1)[1].split("}", 1)[0]
    for part in ("flex: 1", "min-width: 0", "text-overflow: ellipsis", "white-space: nowrap"):
        assert part in label, part
    assert ".shell { display: grid; grid-template-columns: 148px minmax(0, 1fr);" in CSS


def test_figures_are_of_one_width_only_in_counts():
    # Tabular figures on the whole page gave Inter's hyphen a figure's width ("langfuse - docs").
    body = CSS.split("\nbody {", 1)[1].split("}", 1)[0]
    assert "font-variant-numeric" not in body
    assert ".count, .num { font-variant-numeric: tabular-nums; }" in CSS


def test_the_gateway_map_has_its_hint_line_and_the_last_words_and_looks():
    gateway = script("gateway.js")
    # The map names how to use it, as the mockup does (gateway-notes 8); the List has none.
    assert (
        '"Point at a link and press × to remove it · click anything for its Details · several '
        'changes wait in preview, then Apply all · drag a server onto a client"'
    ) in gateway
    assert 'setHint(mode === "map" ? MAP_HINT : "");' in gateway
    assert "flex: none" in rule(".hint-line svg")
    # A client whose settings cannot be read says so, as its panel does; so does a plugin entry
    # that is off.
    drag = script("gateway-drag.js")
    assert "`${who}'s settings are not readable.`" in drag
    assert "`${name}'s entry is off.`" in drag
    # A plain button beside the 30 px inputs of the Add forms is as tall as they are.
    assert "height: 30px;" in rule(".form .btn:not(.small)")
    # The gateway card counts a server that is moving out as it leaves.
    assert "function serverCounts(" in script("gateway-details.js")


def test_gateway_forms_say_in_preview_while_their_row_waits():
    details, gateway = script("details.js"), script("gateway-details.js")
    # One look for a button whose row waits: previewButton and the Connect clients button use it.
    assert "export function showInPreview(node, words, label, key) {" in details
    assert details.count("showInPreview(node, words, label, key);") == 1
    assert "showInPreview(submit, words, PREVIEW, keyFor(body()))" in gateway
    assert 'const PREVIEW = "Preview";' in gateway
    # A project pick says it on its small line and in its name for a screen reader.
    assert "`${text} · in preview`" in gateway
    assert "`${name}, ${said}`" in gateway


def test_the_library_map_words_and_looks():
    text = script("library-map.js")
    for words in (
        '"Follow the source. Connect only what you need."',
        '"Point at a link and press × to remove it · drag a plugin onto a client to add it there '
        '· + adds it for all projects · click anything for its Details"',
        '[["plugins", "Plugins and skills"], ["instructions", "Instructions"]]',
        'caption: "Clients"',
        'caption: "Plugins and skills"',
        'caption: "Inside"',
        'plural(item.count, "item", "items")',
        '["skills", "Skill", "sparkles"], ["commands", "Command", "square-terminal"]',
        '["agents", "Agent", "bot"]',
        '["hooks", "Hook", "webhook"], ["mcp_servers", "MCP server", "server"]',
        'hook: { icon: "webhook", words: "Hook" }',
    ):
        assert words in text, words
    # The scope bar names only the project on the map; the Library's head keeps its title.
    assert "if (count === undefined) return `Project ${folder}`;" in script("parts.js")
    assert 'el("h1", null, "Library")' in script("library.js")
    # The map never says "N of M on", and its entrance waits as the page says.
    assert " of ${" not in text and "enterDelay: afterOldPage()" in text
    assert "enterDelay: afterOldPage()" in gw() and "afterOldPage()" not in script("map-view.js")
    # Library map looks: the kind word, slim rows like tools, and the Unknown lamp.
    assert "color: var(--ink-3); font-size: 10.5px;" in rule("div.map .block-label")
    unk = ".lamp.unk, .mark.unk { background: transparent; border: 1.5px dashed var(--lamp-warn); }"
    assert unk in CSS
    assert ".seg.map-tabs { margin: -6px 0 18px; }" in CSS
    assert 'const MAP_PAGES = ["gateway", "library"];' in script("app.js")


def test_the_library_map_details_words():
    text = script("library-details.js")
    for words in (
        'const OFF_ALL = "Turn off for all projects…";',
        'const OFF_SOME = "Turn off in some projects…";',
        'const OFF_HERE = "Turn off in this project…";',
        'const FOLLOWS = "Follows its plugin.";',
        'const NO_PLUGIN = "None, a skill on its own";',
        'const NO_PROJECT_SWITCH = "Codex has no switch for one project.";',
        'const NO_CURSOR_SWITCH = "Cursor has no switch to turn off one skill.";',
        '"This turns it off in Claude Code. Codex and Cursor have no switch for one project."',
        'own: "Has its own skill settings", new: "No Claude Code settings yet"',
        '["skills", "skill", "skills"], ["commands", "command", "commands"]',
        '["mcp_servers", "MCP server", "MCP servers"]',
        '`Add to ${names(clients).join(" or ")}…`',
        "`Turn off ${plugin.name} in this project…`",
        '"in every project"',
        '`${joinWords(names(readers))} ${verb(readers, "gets", "get")} it through '
        "${CLIENT_NAMES[owner]}.`",
        "`It is off in ${joinWords(names(off))}.`",
        '"Cursor gets it once Claude Code adds it."',
        '"No client loads it."',
        '`Plugin · ${plural(item.count, "item", "items")}`',
        "`Loads in ${c.folder}`",
        '"Loads in every project"',
        '"Nothing yet"',
        "`${owner}'s settings`",
        "`${owner}'s skills folder`",
        '"The plugin\'s files"',
        '"Inside the plugin"',
        '"Loaded by the client"',
        "`Through ${ownerName}`",
        "`${client} loads ${item.name} through ${ownerName}'s folder.`",
        '"Plugins on the map"',
        '"Has it already" : "Not added"',
        '"Each client you tick waits in preview until Apply."',
        "`Add ${item.name} to the clients you pick`",
        "`Turn off ${item.name} in the projects you pick`",
        '{ title: "Plugin folder", path: tech.path }',
        '{ title: "Marketplace", summary: tech.marketplace }',
        '{ title: "Skill file", path:',
        'const ALL_FIRST = "Apply the rule for all projects first";',
        '"Apply the project rules in preview first; then Claude Code can turn it off for all '
        'projects."',
        'value: "None yet"',
        "onLine: IN_PREVIEW",
        '{ title: "Settings file", path:',
    ):
        assert words in text, words
    # Cursor is never a choice for a plugin (D26), and a plugin's parts have no switch (D25).
    assert '["claude_code", "codex"].filter((client) => item.can.add.includes(client)' in text
    # The project checklist is the Gateway's own (D13), shared, not a copy.
    assert "export function projectChecklist(" in gw() and "projectChecklist({" in text
    assert "export function tickRow(" in gw()
    # A ticked row says "In preview" when it has no line of its own, or its `onLine`.
    assert 'onLine || (text ? `${text} · in preview` : "In preview")' in gw()
    # The Inside rows grow out of their plugin, and fold back in 160 ms.
    view = script("map-view.js")
    assert "const GROW_STEP = 15;" in view and "const FOLD_BACK_MS = 160;" in view
    assert (
        'caption: "Inside", w: 200, h: 34, colGap: 70, top: 26, rowGap: 8, grows: true'
        in script("library-map.js")
    )
    assert ".sw-row > .p-tile.p-icon { width: 24px; height: 24px; flex: none; }" in CSS


def test_a_plugin_or_skill_drags_onto_a_client():
    # decisions "Drag a plugin or skill onto a client" (library-notes §4): the tip's words, the
    # refusals in order, and the look of an add that waits.
    text = script("library-map.js")
    for words in (
        "`Add to ${CLIENT_NAMES[client.client]}`",
        'const CURSOR_GETS = "Cursor gets plugins through Claude Code";',
        "`Already in ${who}`",
        'const WAITS_ALREADY = "Already in preview";',
        "`${who} cannot get ${item.name}`",
        "const meta = `Preview · ${wait.all ? ALL_PROJECTS : joinWords(wait.names)}`;",
        'const ALL_PROJECTS = "all projects";',
        'const CLICK_OUT = "Click to take it out.";',
        "takeOut: `${meta}. ${CLICK_OUT}`",
        "pinned: true, parent: marketGroup(model, offer.marketplace)",
        "details: true, group };",
        'const INSTALLS = { plugin: "plugin.install", skill: "skill.install" };',
        'kind: "preview", row: add.key',
        "addsOf(item, tray.rows).some((add) => add.clients.includes(client))",
    ):
        assert words in text, words
    order = [
        text.index(w)
        for w in ("CURSOR_GETS;", "`Already in ${who}`", "WAITS_ALREADY;", "cannot get")
    ]
    assert order == sorted(order)
    # It looks like the Gateway's preview block; its words are in the accent.
    look = rule('div.map .block:is(.plugin, .skill)[data-state="preview"]')
    assert "var(--preview-line)" in look and "var(--preview-fill)" in look
    assert "color: var(--route);" in rule(
        'div.map .block:is(.plugin, .skill)[data-state="preview"] .block-meta'
    )


def test_the_library_add_panel_says_the_decided_words():
    # decisions "The add panel for plugins and skills" (frame L4).
    text = script("library-add.js")
    for words in (
        'export const LIBRARY_ADD_TITLE = "Add a plugin or skill";',
        'const FOOT = "Click to preview, or drag onto a client.";',
        'const NO_MATCH = "No plugins or skills match.";',
        'const NONE = "No marketplace on this computer offers a plugin or skill.";',
        'const ADD_MARKETPLACE = "Add a marketplace…";',
        'export const LIBRARY_STATUS = { added: "Added", every: "In every client", '
        'preview: "In preview" };',
        'const PILL = [["all", "All"], ["plugin", "Plugins"], ["skill", "Skills"]];',
        "`Plugin · ${plural(row.count, row.unit, `${row.unit}s`)}`",
        'return "Skill";',
        'const ADD_KEY = "add:plugins";',
        "return openAddPanel(LIBRARY, options);",
    ):
        assert words in text, words
    # First match wins: Added, In every client, the refusal, In preview.
    order = [
        text.index(w)
        for w in ("LIBRARY_STATUS.added, off", "LIBRARY_STATUS.every", "line: row.refusal")
    ]
    assert order == sorted(order)
    # The map's caption carries "+ Add", and a row of the panel drags onto a client.
    lib_map = script("library-map.js")
    assert 'caption: "Plugins and skills", add: true,' in lib_map
    assert "row: { still: true, begin: beginRow, over: overRow, drop: dropRow }," in lib_map
    assert "liftGhost" in script("gateway-drag.js") and "export function liftGhost(" in script(
        "map-drag.js"
    )
    # Why the panel offers a plugin to no client, beside it in views/skills.py.
    assert NO_CLIENT == "No client here can get {name}."
    assert NEEDS_PLUGIN == "This skill needs the rest of its plugin. Add the plugin instead."
    # A card the tray adds is never behind "N more" (map.js), and an add of a plugin or skill is one
    # row whatever order its clients come in (tray.js).
    assert "const pinned = (child) => Boolean(child.pinned) || PINNED.includes(child.kind);" in (
        script("map.js")
    )
    assert 'const ADD_ORDER = ["plugin.install", "skill.install"];' in script("tray.js")


def test_a_library_link_x_removes_or_turns_off():
    # decisions "Link ×" (library-notes §5): the × words, the rows, and what has no ×.
    rules = script("library-rules.js")
    for words in (
        "`Remove ${name} from ${who}`",
        "`Turn off ${name} in ${who}`",
        # One remove row for the × and Details' "Remove from …" (removeBody).
        'item.kind === "plugin" ? "plugin.remove" : "skill.remove", targets: [{ item: target }]',
        "const body = removeBody(item, client);",
        "skillOffBodies(item, answer).find(",
        'action: "skill.rule", targets: [{ client, item: target }], params: { scope: "all", ',
    ):
        assert words in rules, words
    # Cursor's plugin has no x (D26); a Cursor skill is removed, not turned off.
    assert "!((item.can && item.can.remove) || []).includes(client)) return null;" in rules
    assert 'if (client === "cursor") {' in rules
    text = script("library-map.js")
    for words in (
        'const TAKE_OUT = "Take it out of the preview";',
        'const OWN_WAITS = "Your change is being written.";',
        "const LINKS = { canHit: () => true, tip: linkTip, waits: linksWait, onClick: pressLink, "
        "onRemove: removeLink };",
        "inTray(keyFor(change.body)) ? TAKE_OUT : change.tip",
        "Object.assign(link, { leaving: true, row: row.key })",
        "WAITS",
    ):
        assert words in text, words
    # The Details of a Cursor plugin's link say where to remove it (words of CURSOR_HINT, checked
    # 2026-10-22).
    details = script("library-details.js")
    words = (
        "Cursor keeps its plugins in its own database. Remove it in Cursor: Customize → Plugins."
    )
    assert f'const CURSOR_REMOVES = "{words}";' in details
    assert CURSOR_HINT.startswith(f"{words} ")
    assert "CURSOR_PLUGINS" not in details + text
    # The rows Details' Turn off adds live with the x's, in one place.
    assert "export function offBodies(" in rules and "export function offBodies(" not in details


def test_the_instructions_map_words():
    # decisions "Instructions" (library-notes §6, frames I1 and M8·4–M8·5): the tab only reads.
    text = script("library-map.js")
    for words in (
        'const INSTRUCTIONS_HINT = "Kitden only reads instruction files. It never changes them.";',
        'const TAB_BANNERS = { plugins: "the library map", instructions: "the instruction '
        'files" };',
        'const TAB_KINDS = { plugins: "plugin", instructions: "instructions" };',
        'caption: "Files", w: 190, h: 54, colGap: 100, top: 37, rowGap: 4',
        'caption: "Pulls in", w: 200, h: 40, colGap: 60, top: 60, rowGap: 16',
        'const FILE_GROUPS = { all: "layers", project: "folder", commands: "square-terminal" };',
        'const FILE_KINDS = { command: "command", agent: "agent" };',
        'const NO_FILES = "No instruction files here.";',
        "const filesGroup = (key) => `group:files:${key}`;",
        "`${who} · ${FILE_KINDS[file.kind]}`",
        "title: `${file.name} · ${meta}`",
        'const MISSING = { icon: "triangle-alert", words: "Missing" };',
        "const TAB_FROM = { x: 150, y: 200 };",
        '`${who} · ${plural(file.count, "rule", "rules")}`',
        '`${who} · ${plural(pulls, "import", "imports")}`',
        '`${who} · ${group.key === "project" ? "this project" : ALL_PROJECTS}`',
        'file: ["block-icon", "file-text", 15], import: ["block-icon bare", "scroll-text", 13]',
        "const importsOf = (file) => ((file.by || {}).claude_code ? file.imports || [] : []);",
    ):
        assert words in text, words
    details = script("library-details.js")
    for words in (
        'const FILE_KIND = "Instruction file";',
        'const IMPORT_KIND = "Imported file";',
        'const READS_FILE = "Kitden only reads this file.";',
        'const READS_IT = "Kitden only reads it.";',
        'const IMPORTS_NOTHING = "It imports nothing.";',
        'const MAY_ASK = "Claude Code may ask before it reads this.";',
        'const NOT_FOUND = "Kitden could not find this file.";',
        '{ label: "Read by", value:',
        '{ label: "Through", value: file.through }',
        '{ label: "Size", value: plural(file.size, "line", "lines") }',
        "`It brings in ${pulls} more.`",
        '"Rules folder" : "File"',
        "`Brought in by ${joinWords(by)}`",
        'line: COMMAND_KINDS[file.kind] || "File"',
        'const COMMAND_KINDS = { command: "Command", agent: "Agent" };',
        "kind: command || FILE_KIND",
        '"Read by the client"',
        "`${from.name} reads ${to.name}. ${READS_FILE}`",
        '"An import"',
        "`${from.name} brings in ${to.name}. ${READS_IT}`",
    ):
        assert words in details, words
    # Another tab grows out of the gap right of the clients, 15 ms apart, and shrinks back in
    # 160 ms.
    view = script("map-view.js")
    assert "({ x: tabPoint.x, y: tabPoint.y, s: GROW_SCALE, o: 0, turn })" in view
    assert "start: start + D(turn * GROW_STEP)" in view
    assert "(tabPoint || (item.grows && item.folds) ? FOLD_BACK_MS : GO_MS)" in view
    assert "font-family: var(--mono); font-size: 11px;" in rule("div.map .block.import .block-name")
    # Commands and agents, read only, in a group of their own (views/instructions_map.py).
    views = (STATIC.parents[1] / "views/instructions_map.py").read_text()
    assert 'COMMANDS = {"key": "commands", "name": "Commands and agents"}' in views
    assert 'const COMMAND_WORDS = { command: "Command", agent: "Agent" };' in script("library.js")


def test_commands_in_library_details_say_the_page_never_runs_them():
    # FR-029: "Commands…" under More on a plugin or a marketplace's caption, from /api/commands.
    details = script("library-details.js")
    for words in (
        'const COMMANDS = "Commands…";',
        'const RUN_YOURSELF = "You run these yourself. This page never runs them.";',
        'const NO_COMMANDS = "No commands for this item.";',
        'const NOT_LOADED = "Could not load the commands.";',
        'const COPY = "Copy";',
        'const COPIED = "Copied";',
        'const NOT_COPIED = "Could not copy";',
        "getJson(`/api/commands${query({ item })}`)",
        'copy.setAttribute("aria-label", `${COPY} ${command.label}`);',
    ):
        assert words in details, words
    # The old Details and their offer chain are gone; the page reads no /api/offer.
    assert "/api/offer" not in "\n".join(script(f.name) for f in (STATIC / "js").glob("*.js"))


# The Library List (Phase 6B Task 6, spec 5.4, frame L3) ------------------------------------------


def test_the_library_list_words_and_looks():
    text = script("library.js")
    # The Map's tabs, Installed | Differences, and the hint line, verbatim.
    assert (
        'const TABS = [["plugin", "Plugins and skills"], ["instructions", "Instructions"]];' in text
    )
    assert 'const SHOW = [["mine", "Installed"], ["diff", "Differences"]];' in text
    assert (
        'const LIST_HINT = "One row per item, one column per client. Right opens a plugin, '
        'Enter opens Details.";' in text
    )
    assert 'setHint(kind === "plugin" ? LIST_HINT : INSTRUCTIONS_HINT);' in text
    # A plugin row says what Kitden read inside it; a part says what kind it is.
    assert 'item.count ? `Plugin · ${plural(item.count, "item", "items")}` : "Plugin"' in text
    assert 'const KIND_WORDS = { skill: "Skill", hook: "Hook" };' in text
    assert (
        'const PART_WORDS = { skill: "Skill", command: "Command", agent: "Agent", hook: "Hook", '
        'mcp_server: "MCP server" };' in text
    )
    # An empty tab, and an empty cell, say so plainly.
    for words in (
        '"No plugins or skills in any client"',
        '"Plugins and skills you add in Claude Code, Codex or Cursor will show up here."',
        '"No instruction files in any client"',
        '"Instruction files you add for Claude Code, Codex or Cursor will show up here."',
        'cell.reason || "Not added"',
    ):
        assert words in text, words
    # A row opens the map's Details; the keys are the tree grid's.
    assert "libraryDetails(id);" in text and "gridKey(rows," in text
    assert "export function libraryDetails(id, how)" in script("library-map.js")
    # The look: the Gateway List's grid, a sticky 30 px head, a 34 px part row.
    assert ".tg-row.part { min-height: 34px; }" in CSS
    # A narrow window hides the Gateway List's tiles, never the Library List's first client.
    assert ".tg-used, .treegrid:not(.library-list) > .tg-head > :nth-child(2)" in CSS
    assert "min-width: 0; overflow: hidden; padding-left: calc(8px" in rule(".tg-row > .tg-name")
    # Library Details turn a plugin on again and remove an entry, as the old Details did.
    details = script("library-details.js")
    assert "`Turn on in ${CLIENT_NAMES[client]}…`" in details
    assert "`Remove from ${CLIENT_NAMES[client]}…`" in details
    assert "more: removeActions(item)" in details
    # They act only on a client's own entry for all projects; where the project decides, one quiet
    # line says so (`can.project`, views/library_map.py).
    assert (
        "`${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s own settings.`"
        in details
    )
    assert '"project": project_decides,' in (STATIC.parents[1] / "views/library_map.py").read_text()
    # A part the map does not draw opens its plugin; the account row opens its own small card.
    assert 'if (row.kind === "part") return row.parent;' in text
    assert 'if (block.kind === "account") return accountCard(block);' in details
    assert ".tg-row.arrive { animation: arrive 1200ms var(--ease-out) both; }" in CSS
    # The server's words for Differences and the tabs (views/library.py).
    server = (STATIC.parents[1] / "views/library.py").read_text()
    assert 'LIST_TABS = ("plugin", "instructions")' in server
    assert 'LIST_SHOWS = ("mine", "diff")' in server
    assert '"/api/library-list"' in (STATIC.parents[1] / "web/app.py").read_text()


def test_the_last_skill_rule_notes_say_what_they_do():
    details, rules = script("library-details.js"), script("library-rules.js")
    assert 'const USE_SHARED = "Use the shared rule…";' in details
    assert 'const OFF_COPY = "Turn off this copy in Codex…";' in details
    assert 'const ALREADY_OFF = "Already off there";' in details
    assert (
        "`Claude Code keeps this project's local settings in ${folder}, where Kitden does not "
        "write.`" in details
    )
    # The page asks the engine's own test of where a change may write.
    assert (
        "writable(path, home, writable_roots(home, inventory))"
        in (STATIC.parents[1] / "views/library_map.py").read_text()
    )
    # The project-only skill's reason: the server guard, in words that offer nothing refused.
    reason = (
        "Claude Code may not merge skill settings across files, so Kitden cannot turn it off in "
        "this project."
    )
    assert f'const NO_MERGE = "{reason}";' in details
    assert "turn it off for all projects instead" in NO_SKILL_MERGE
    # The quiet line tells the project's local file from its shared, committed one.
    assert (
        "`${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s local settings.`"
        in details
    )
    assert (
        "`${CLIENT_NAMES[client]}'s setting for this comes from ${folder}'s shared settings.`"
        in details
    )
    assert 'params: { scope: "project", project: c.project, off: false }' in details
    assert 'params: { scope: "all", off: true } }));' in rules
    # `here` is per client (views/library_map.py).
    assert "export const decidedHere = (item, client = null)" in script("library-map.js")
    assert "if (decidedHere(item)) block.tag = ORIGIN_WORDS.override;" in script("library-map.js")
    assert NEW_LOCAL_FILE == (
        "Kitden creates .claude/settings.local.json in {folder}. If git lists it, add it to "
        ".gitignore."
    )
    assert REPO_RULE == (
        "Claude Code keeps this rule in {folder}'s local settings, so it holds in all of {folder}."
    )
    assert REPO_RULE_OUT == (
        "Claude Code takes this rule out of {folder}'s local settings, so it changes all of "
        "{folder}."
    )
