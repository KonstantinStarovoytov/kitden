"""Words and parts the design review (2026-10-18) removed from the page stay removed."""

import re
from pathlib import Path

STATIC = Path(__file__).parents[2] / "src/kitden/web/static"
INDEX = (STATIC / "index.html").read_text()


def script(name: str) -> str:
    return (STATIC / "js" / name).read_text()


def test_rail_counts_only_attention_and_changes():
    assert 'id="nav-attention"' in INDEX and 'id="nav-changes"' in INDEX
    assert "nav-items" not in INDEX and "nav-around" not in INDEX
    assert "around" not in script("app.js")


def test_overview_has_no_pills_bar_or_recent_changes():
    overview = script("overview.js")
    assert "Recent changes" not in overview
    assert '"Tested"' not in overview and '"Found"' not in overview
    assert '"bar"' not in overview


def test_load_map_has_no_legend_or_counts():
    text = script("map.js")
    assert "legend" not in text.lower()
    assert "×" not in text
    assert "Choose a project in Where" not in text


def test_gateway_has_no_entry_name_field_or_paths():
    text = script("gateway.js")
    assert "Entry name" not in text
    assert "key in $" not in text
    assert "shortPath" not in text


def test_changes_rows_have_no_details_button():
    assert '"Details"' not in script("changes.js")


def test_rail_says_let_agents_read_this_setup():
    assert "Let agents read this setup" in INDEX
    assert "Agents can ask" not in INDEX and "show my setup" not in INDEX


def test_changes_say_why_a_change_stopped():
    text = script("changes.js")
    assert "Can't undo: the file changed after this" in text
    assert "Not applied: the file changed before Apply" in text
    assert "Stopped: file changed" not in text and "Undo stopped" not in text


def test_project_picker_says_project_not_where():
    assert "Project:" in INDEX and "Where:" not in INDEX
    assert 'aria-label="Project"' in INDEX
    app = script("app.js")
    assert 'new Option("Global", "")' in app and "No project" not in app
    assert '<option value="">Global</option>' in INDEX
    assert "outside any project" not in script("map.js")


def test_gateway_names_the_remove_action_and_draws_no_idle_wire():
    text = script("gateway.js")
    assert "Remove direct entry…" in text
    assert "wire idle" not in text
    assert "goes around" not in text


def test_gateway_rows_keep_addresses_behind_a_details_button():
    text = script("gateway.js")
    assert '"Details"' in text
    assert "row.summary" not in text


def test_gateway_says_its_lists_are_mcp_servers():
    assert "MCP servers not in the gateway" in script("gateway.js")


def test_gateway_wires_do_not_fake_traffic():
    # A wire draws once when its connection appears; nothing loops, Kitden cannot see traffic.
    css = (STATIC / "style.css").read_text()
    assert not any(".routes" in line and "infinite" in line for line in css.splitlines())
    assert "flow" not in script("gateway.js")


def test_plugin_switch_opens_a_review_and_does_not_flip_itself():
    text = script("panel.js")
    assert 'setAttribute("role", "switch")' in text
    assert text.count('"aria-checked"') == 1


# Motion pass 2 (2026-10-18): each page keeps the parts the design brief asked for.
CSS = (STATIC / "style.css").read_text()


def test_controls_press_and_the_switch_waits_for_the_preview():
    assert ".switch.pending" in CSS
    assert ".seg button:active" in CSS and ".tabs button:active" in CSS
    text = script("panel.js")
    assert 'classList.add("pending")' in text and 'setAttribute("aria-busy", "true")' in text


def test_client_tile_flies_to_its_load_map_column():
    assert "fly(tile, `client-${clientId}`)" in script("overview.js")
    assert "land(tile, `client-${column.id}`)" in script("map.js")


def test_review_counts_the_diff_and_folds_the_file_change():
    text = script("panel.js")
    assert "diffCounts" in text and "fold(files)" in text
    assert "Show file change" in text and "Show file changes" in text


def test_apply_turns_green_only_after_verified_and_only_ok_toasts_get_a_check():
    text = script("panel.js")
    assert text.index('after.state !== "verified"') < text.index('apply.classList.add("done")')
    assert text.count("{ ok: true }") == 2
    assert "Undone. The previous settings are back." in text
    assert 'toast("Undo stopped' in text  # a stopped undo gets no check


def test_one_mark_slides_between_the_choices_of_a_group():
    assert 'glide($(".nav")' in script("app.js")
    text = script("map.js")
    assert '"map-tabs"' in text and '"map-filter"' in text
    assert "tab-ink" not in CSS and "tab-ink" not in text


def test_gateway_routes_light_their_rows_and_take_keyboard_focus():
    text = script("gateway.js")
    assert "node.dataset.clients" in text and '"lit"' in text
    assert 'setAttribute("tabindex", "0")' in text
    assert "fold(box)" in text and "fold(more)" in text


def test_load_map_shows_one_flag_per_wording_and_resolved_flags_shrink_away():
    text = script("map.js")
    assert "findIndex((o) => o.text === f.text)" in text
    assert 'classList.add("gone")' in text and ".flag.gone" in CSS


def test_scope_switch_marks_the_project_picker_and_the_lede():
    assert 'classList.toggle("project"' in script("app.js")
    assert ".where-box.project" in CSS
    assert 'classList.add("fresh")' in script("map.js")


def test_reduced_motion_turns_every_animation_off():
    assert "prefers-reduced-motion: reduce" in CSS
    assert "reducedMotion.matches" in script("motion.js")


def test_a_plugin_the_page_cannot_change_shows_a_locked_switch():
    text = script("panel.js")
    assert "node.disabled = true" in text
    assert "Not changed from here." in text


def test_load_map_lede_names_the_project_folder_not_its_path():
    text = script("map.js")
    assert "in the project" in text
    assert "shortPath" not in text


def test_changes_rows_open_the_panel_and_keep_paths_off_the_page():
    text = script("changes.js")
    assert "openChange" in text
    assert "change-detail" not in text and "aria-expanded" not in text


def test_overview_notes_are_rows_with_a_details_button():
    text = script("overview.js")
    assert '"Details"' in text
    assert "shortPaths" not in text


# Feature 006: the gateway is managed from here --------------------------------------------


def test_gateway_offers_move_and_keeps_the_side_door_small():
    text = script("gateway.js")
    assert "Move into the gateway…" in text
    assert "Move all ${movable.length}…" in text
    assert "In the gateway" in text
    assert 'link.classList.add("small", "ghost")' in text


def test_gateway_form_never_takes_the_password_itself():
    text = script("gateway.js")
    assert "Password variable name (not the password)" in text
    assert 'type: "password"' not in text


def test_moves_are_named_on_changes_and_in_the_review():
    assert '"gateway.move": "Moved into the gateway"' in script("parts.js")
    panel = script("panel.js")
    assert "Move ${names} into the gateway" in panel
    assert "into the gateway" in panel


# Feature 007: an Obot gateway beside MetaMCP ---------------------------------------------


def test_gateway_form_takes_an_obot_key_variable_never_the_key():
    text = script("gateway.js")
    assert 'path.startsWith("/mcp-connect/")' in text
    assert "Obot API key variable name (not the key)" in text
    assert "ok1-" not in text
    assert "model.gateways.find((g) => g.movable)" in text


def test_held_rows_say_remote_hosted_or_sse_and_keep_addresses_behind_details():
    text = script("gateway.js")
    assert 'return "Hosted";' in text and 'return "Remote";' in text
    assert "Nothing yet. Add servers in ${gatewayName(gateway)} itself." in text


def test_a_gateway_the_clients_do_not_use_offers_to_take_them_over():
    text = script("gateway.js")
    assert "Use this gateway…" in text and '"gateway.switch"' in text
    assert "model.used.includes(b.id)" in text  # the used gateway gets the card with the routes


def test_diagram_nodes_open_the_client_apps_and_the_gateway():
    text = script("gateway.js")
    # The scheme comes from the installed app, read by the server; none is hard-coded.
    for scheme in ('"claude://"', '"codex://"', '"cursor://"'):
        assert scheme not in text
    assert "found.app_url" in text and "if (url) opens(group" in text
    assert 'window.open(page, "_blank", "noopener")' in text


def test_discover_adds_plugins_and_marketplaces_in_one_review():
    text = script("discover.js")
    assert '"plugin.install"' in text and '"marketplace.add"' in text
    assert "Add a marketplace…" in text
    assert '<a href="#discover" data-view="discover">Discover</a>' in INDEX
    assert '["new", "Not added"]' in text and "match “${asked.q}”" in text


def test_discover_rows_say_where_each_plugin_can_go_without_details():
    text = script("discover.js")
    # One cell per client, like the Load map: a filled dot is there, a ring can be added.
    assert '"Installed"' in text and '"Can add"' in text and '"Via Claude Code"' in text
    assert 'el("table", "map offers")' in text and '"desc"' in text
    # Filters by category and marketplace, fed by the counts the server sends.
    assert '"All categories"' in text and '"All marketplaces"' in text
    assert "answer.facets" in text
    # Plugins found only by their description are grouped apart, so the reason is clear.
    assert "Also mention “${cache.asked.q}” in the description" in text
    # The row opens Details, so there is no Details button on it.
    assert '"Details"' not in text


# Discover, phase 2: a Skills tab beside Plugins ------------------------------------------


def test_discover_has_a_skills_tab_that_reuses_the_table_and_the_add_flow():
    text = script("discover.js")
    assert '[["plugin", "Plugins"], ["skill", "Skills"]]' in text
    assert '"skill.install"' in text and '"Add skill"' in text
    # One row builder for both kinds, one table, one Add… flow.
    assert text.count("tableRow(") == 3 and text.count('el("table", "map offers")') == 1
    assert 'params.kind = s.kind === "skill" ? "skill" : ""' in script("store.js")


def test_skill_rows_say_where_each_skill_comes_from_and_how_each_client_loads_it():
    text = script("discover.js")
    # A plugin's skill shows name@marketplace, so same-name plugins in two marketplaces differ.
    assert "skill.plugin || skill.from" in text and 'skill.plugin.split("@")[0] :' not in text
    assert '"Needs its plugin"' in text and '"Can add"' in text
    # The refusal, in the owner's words, and a way to the plugin that holds the skill.
    assert "This skill needs the rest of its plugin. Add the plugin instead." in text
    assert '"Find the plugin"' in text
    # Details list the files and mark the scripts the agent may run; paths stay in Details.
    assert '"What it brings"' in text and '"script"' in text
    assert "shortPath(skill.path)" in text
    assert '"Details"' not in text


def test_a_skill_copy_names_every_client_it_reaches():
    panel = script("panel.js")
    assert "s.reaches || [s.client]" in panel and "Add ${names} to ${clients}" in panel
    assert "filter(Boolean))) box.append(callout(note))" in panel  # Cursor loads it twice
    assert '"skill.install": "Added skill"' in script("parts.js")


def test_add_forms_name_the_source_and_every_client_the_change_reaches():
    text = script("discover.js")
    # The server says whether Cursor loads what Claude Code has; the page does not guess.
    assert "answer.inherits" in text and "Source: " in text
    assert "Cursor will also load this through Claude Code." in text
    assert "Cursor will also load it from Claude Code's folder." in text


def test_discover_rows_keep_the_name_and_the_source_readable():
    text, css = script("discover.js"), (STATIC / "style.css").read_text()
    assert '["42%"' in text and 'el("div", "meta")' in text
    assert ".offers .desc" in css and "-webkit-line-clamp: 2" in css
    assert ".offers .from { flex: none" in css
    # Every row names its source, so the twin check is gone.
    assert "twin" not in text and "names.get" not in text
    # So does its Add button, or twin rows would give two buttons one name.
    assert "addLabel(offer.name, offer.marketplace)" in text
    assert "addLabel(skill.name, from)" in text


def test_discover_details_and_add_form_follow_what_the_server_says_about_cursor():
    text = script("discover.js")
    # Details no longer claim a Cursor setting; the line shows only when Cursor would load it.
    assert "Cursor: loads it through Claude Code." in text and "Cursor: has it." in text
    assert "Cursor: gets it through Claude Code once you add it there." in text
    assert "cursorLine(offer, cursorInherits())" in text
    assert "Cursor: loads Claude Code plugins when" not in text
    assert "Cursor will also load it from the shared skills folder." in text
    # The note is a polite live region inside the form, before Preview.
    assert 'also.setAttribute("aria-live", "polite")' in text
    assert "[checks, note, submit, message]" in text


def test_a_lost_apply_answer_is_checked_not_guessed():
    text = script("panel.js")
    assert "Nothing was changed by this page" not in text
    assert "Could not confirm the result. Check Changes before trying again." in text
    assert "readChange(" in text


def test_changes_and_the_load_map_say_saved_settings_and_scope():
    assert "Based on saved settings." in script("map.js")
    changes = script("changes.js")
    assert "To take effect" in changes and "global settings" in changes
    assert '"everywhere"' not in changes


def test_changes_show_restart_notes_only_for_changes_that_happened():
    changes = script("changes.js")
    assert '["verified", "undone", "undo_blocked"].includes(entry.state)' in changes
    assert 'project: "this project"' in changes


def test_a_failed_refresh_says_when_the_shown_data_was_read():
    assert "Could not refresh. Showing what Kitden read at ${clock}." in script("parts.js")
    for name, model in (("map.js", "map"), ("overview.js", "overview"), ("gateway.js", "gateway")):
        text = script(name)
        assert f'current("{model}")' in text and f"staleNote(data.readAt.{model})" in text
    assert '" · could not refresh"' in script("app.js")


def test_the_rail_time_follows_every_render_not_only_a_refresh():
    app = script("app.js")
    shell = app.split("function renderShell()")[1].split("\n}\n")[0]
    refresh = app.split("async function refresh(")[1].split("\n}\n")[0]
    assert '$("#scanned").textContent' in shell and "lastGoodRead" in shell
    assert "#scanned" not in refresh


def test_a_project_switch_marks_the_old_page_as_waiting():
    app = script("app.js")
    assert 'main.classList.add("pending")' in app
    assert 'main.setAttribute("aria-busy", "true")' in app
    assert ".finally(" in app and 'main.classList.remove("pending")' in app
    style = (STATIC / "style.css").read_text()
    assert ".page.pending { opacity: 0.5; pointer-events: none;" in style


def test_gateway_connect_form_serves_its_own_card_only():
    text = script("gateway.js")
    # The form is for the card's gateway; a client in any gateway is not offered again.
    assert "connectForm(gateway, waiting)" in text
    assert "Object.values(model.connections).some" in text
    assert "connectForm(model.gateways" not in text


def test_direct_servers_are_options_and_details_offers_move_first():
    overview = script("overview.js")
    assert '"Can improve"' in overview and "model.suggestions" in overview
    assert ".issue.suggestion" in CSS
    panel = script("panel.js")
    assert "Move into the gateway…" in panel and 'action: "gateway.move"' in panel
    # Without a gateway that takes servers, the panel says the same as the Gateway page.
    assert "Add the server in the gateway first" in script("parts.js")
    assert "GATEWAY_NOTE" in panel and "GATEWAY_NOTE" in script("gateway.js")
    # An option is quieter than a problem: a plain button, not the primary one.
    assert 'option ? "btn" : "btn primary"' in overview


def test_rows_say_they_open_details_and_search_names_its_scope():
    for name in ("map.js", "discover.js", "changes.js"):
        assert "opens()" in script(name)
    assert ".sr-only" in CSS
    # The chevron is quiet, and takes the accent when the row is hovered or focused.
    assert re.search(r"\n\.opens \{[^}]*color: var\(--ink-3\)", CSS)
    assert re.search(r"tr:hover \.opens[^{]*\{ color: var\(--route\)", CSS)
    assert "li:hover .opens" in CSS and "tr:focus-visible .opens" in CSS
    app = script("app.js")
    assert '"Search your setup"' in app and '"Search plugins and skills to add"' in app
    # The placeholder trails off; the accessible name does not repeat the dots.
    assert "placeholder = `${scope}…`" in app and 'setAttribute("aria-label", scope)' in app
    assert 'placeholder="Search your setup…"' in INDEX
    assert 'aria-label="Search your setup"' in INDEX
    assert "Find an item" not in INDEX


def test_focus_returns_to_the_control_and_the_review_reaches_its_summary():
    # The key and the tab keys live in dom.js, so the Load map and Discover share them.
    assert "focusKey(" in script("app.js") and "dataset.focus" in script("dom.js")
    for key in ('"ArrowRight"', '"ArrowLeft"', '"Home"', '"End"'):
        assert key in script("dom.js")
    trap = script("panel.js").split("function trapFocus")[1].split("\n}")[0]
    assert "summary" in trap and "textarea" in trap and "getClientRects" in trap


def test_every_control_a_render_replaces_names_itself_for_focus():
    for name, keys in {
        "map.js": ("`tab:${kind}`", "`show:${id}`"),
        "discover.js": ("`tab:${id}`", "`show:${id}`", "`filter:${key}`"),
    }.items():
        text = script(name)
        for key in keys:
            assert f"dataset.focus = {key}" in text, (name, key)
        assert "tabKeys(" in text


def test_client_checkboxes_come_from_one_named_part():
    check = script("parts.js").split("export function clientCheck")[1].split("\n}")[0]
    assert 'setAttribute("aria-label"' in check and "box.value = client" in check
    for name in ("discover.js", "gateway.js"):
        text = script(name)
        assert "clientCheck(" in text and 'type = "checkbox"' not in text


def test_apply_waits_for_work_not_for_a_timer():
    panel, css = script("panel.js"), (STATIC / "style.css").read_text()
    assert "520 - (performance.now()" not in panel and "wait(450)" not in panel
    assert "shake(" not in panel
    assert ".drawer.open .body > *:nth-child(2)" not in css and "line-in" not in css
    assert "--t-panel: 240ms" in css
    assert ".socket .swap { opacity: 0; }" in css


def test_apply_sets_its_label_at_once_and_a_failure_focuses_the_button():
    panel = script("panel.js")
    flow = panel.split("function brokeAfterAnswer")[1].split("function showEffect")[0]
    # No timer in the Apply flow, so a late label cannot land on a button already reset.
    assert "setTimeout" not in flow and "const wait" not in panel
    assert 'label.textContent = "Applying…"' in flow
    assert "next.focus()" in flow
    assert ".label.swap" not in CSS
