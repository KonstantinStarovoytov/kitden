"""Words and parts the design review (2026-10-18) removed from the page stay removed."""

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
    assert "Add a marketplace…" in text and '"Details"' in text
    assert '<a href="#discover" data-view="discover">Discover</a>' in INDEX
    assert '["new", "Not added"]' in text and "match “${state.q}”" in text
