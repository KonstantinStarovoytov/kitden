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


def test_library_has_no_legend_or_counts():
    text = script("library.js")
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
    assert "outside any project" not in script("library.js")


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


def test_client_tile_flies_to_its_library_column():
    overview = script("overview.js")
    assert "fly(tile, `client-${clientId}`)" in overview
    assert "land(tile, `client-${column.id}`)" in script("library.js")
    # The tab is read before the place changes, so its table is drawn where the tile can land.
    count = overview.split("function loadsLine")[1].split("\n}\n")[0]
    assert count.index("await loadLibraryFor(choice);") < count.index("fly(tile")
    card = overview.split("async function follow")[1].split("\n}\n")[0]
    assert card.index("await loadLibraryFor(choice);") < card.index('go("library"')


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
    text = script("library.js")
    assert '"library-tabs"' in text and '"library-show"' in text
    assert "tab-ink" not in CSS and "tab-ink" not in text


def test_gateway_routes_light_their_rows_and_take_keyboard_focus():
    text = script("gateway.js")
    assert "node.dataset.clients" in text and '"lit"' in text
    assert 'setAttribute("tabindex", "0")' in text
    assert "fold(box)" in text and "fold(more)" in text


def test_library_shows_one_flag_per_wording_and_resolved_flags_shrink_away():
    text = script("library.js")
    assert "findIndex((o) => o.text === f.text)" in text
    assert 'classList.add("gone")' in text and ".flag.gone" in CSS


def test_scope_switch_marks_the_project_picker_and_the_lede():
    assert 'classList.toggle("project"' in script("app.js")
    assert ".where-box.project" in CSS
    assert 'classList.add("fresh")' in script("library.js")


def test_reduced_motion_turns_every_animation_off():
    assert "prefers-reduced-motion: reduce" in CSS
    assert "reducedMotion.matches" in script("motion.js")
    # A changed Library cell shows its new word at once (parts.test.mjs checks the swap).
    assert "reducedMotion.matches ? 0 : 260" in script("library.js")


def test_a_plugin_the_page_cannot_change_shows_a_locked_switch():
    text = script("panel.js")
    assert "node.disabled = true" in text
    assert "Not changed from here." in text


def test_library_lede_names_the_project_folder_not_its_path():
    text = script("library.js")
    assert "in the project" in text
    assert "shortPath" not in text


def test_item_details_ask_for_the_full_name_so_a_plugin_shows_only_its_own_marketplace():
    assert "name: row.lookup || row.name" in script("panel.js")


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


def test_library_adds_plugins_and_marketplaces_in_one_review():
    offer, library = script("offer.js"), script("library.js")
    assert '"plugin.install"' in offer and '"marketplace.add"' in offer
    # Adding a marketplace lives on the Marketplaces tab.
    assert '"Add a marketplace…"' in library and 'kind === "marketplace"' in library
    assert '<a href="#library" data-view="library">Library</a>' in INDEX
    assert '["new", "Can add"]' in library and '"Not on this Mac yet"' in library


def test_library_rows_say_what_each_client_has_or_can_add_without_details():
    text = script("library.js")
    # One cell per client: the server's state, or the one button for what it can add.
    assert (
        "socket({ state: cell.state, where: cell.where, word: cell.word, label: cell.reason })"
        in text
    )
    assert "button(cell.add.label" in text and '"btn small add"' in text
    assert 'via: "Via Claude Code", done: "Has its skills"' in script("parts.js")
    assert 'el("table", "map library")' in text and '"desc"' in text
    # A category filter, fed by the counts the server sends.
    assert '"All categories"' in text and "answer.categories" in text
    # The row opens Details, so there is no Details button on it.
    assert '"Details"' not in text


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
    assert "addName(row, client, cell.add)" in text


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
    text = script("panel.js")
    assert "Nothing was changed by this page" not in text
    assert "Could not confirm the result. Check Changes before trying again." in text
    assert "readChange(" in text


def test_changes_and_the_library_say_saved_settings_and_scope():
    assert "Based on saved settings." in script("library.js")
    changes = script("changes.js")
    assert "To take effect" in changes and "global settings" in changes
    assert '"everywhere"' not in changes


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
    # A gateway that could not be read says so, instead of hiding Move.
    assert "Could not read the gateway, so Move is not offered." in panel
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
    trap = script("panel.js").split("function trapFocus")[1].split("\n}")[0]
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
    for name in ("offer.js", "gateway.js"):
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
    for name in ("offer.js", "gateway.js"):
        assert "busyWhile(submit" in script(name)
    assert 'busyWhile($("#rescan")' in script("app.js")
    # A change with several steps counts them in the Apply button, from the server's events.
    assert '"change_progress"' in script("app.js") and '"kitden:progress"' in script("app.js")
    panel = script("panel.js")
    assert 'stepText("Applying", done, total)' in panel and '"kitden:progress"' in panel
    assert ".btn .meter" in css
    # The scan line shows only when a scan takes a while, so quick scans never blink.
    assert ".topbar.scanning::after { opacity: 1; transition-delay: 400ms;" in css


def test_while_a_change_is_written_the_review_says_so_and_offers_nothing_to_press():
    panel = script("panel.js")
    lock = panel.split("function lockReview(")[1].split("\n}\n")[0]
    # Cancel and the close button go away while the change is written, and come back after.
    assert "cancel.hidden = locked" in lock and "close.hidden = locked" in lock
    # The note under the buttons says what is happening instead of the Apply shortcut.
    assert "WRITING" in lock and "APPLY_KEY" in lock
    writing = (
        "Writing the change. It can't stop halfway: if a step fails, Kitden puts everything back."
    )
    assert writing in panel
    css = (STATIC / "style.css").read_text()
    # A button that is off never lights up on hover and says so with the pointer.
    assert ".btn:hover:not(:disabled)" in css
    assert ".btn:disabled { cursor: not-allowed; opacity: 0.5; }" in css
    assert ".btn.primary.apply:disabled { opacity: 1; cursor: progress; }" in css


# Library: one page in place of Load map and Discover ---------------------------------------


def test_library_replaces_load_map_and_discover():
    assert "Load map" not in INDEX and "Discover" not in INDEX
    assert not (STATIC / "js" / "map.js").exists() and not (STATIC / "js" / "discover.js").exists()
    text = script("library.js")
    assert 'el("h1", null, "Library")' in text
    assert "What each client loads, and what you can add to it. Based on saved settings." in text
    assert '[["mine", "On this Mac"], ["new", "Can add"], ["all", "All"]]' in text
    # "Differs between clients" went away: the columns show it already.
    assert "Differs between clients" not in text
    # Old addresses open the Library; the Overview's links go there too.
    assert 'OLD_VIEWS = { map: "mine", discover: "new" }' in script("store.js")
    overview = script("overview.js")
    assert 'kind: target.kind, show: "mine"' in overview
    assert 'go("library", { ...choice, selected: target.row })' in overview


def test_library_says_why_when_there_is_nothing_to_do():
    text = script("library.js")
    # A dash names its reason; no found client points to the Overview.
    assert "node.title = cell.reason" in text
    assert "Kitden found no AI coding clients." in text and '"Open Overview"' in text
    # Search keeps the choice and says what it hides.
    assert "more not on this Mac" in text and '"Show all"' in text
    # The line goes away with the choice; focus moves to that choice.
    assert """document.querySelector('#main [data-focus="show:all"]')""" in text
    # A morph into a dash keeps its reason for a screen reader.
    assert "label: cell.reason" in text and 'label || "Not set up"' in script("parts.js")
    assert "`Needs attention · ${answer.attention}`" in text
    # Marketplace notes stay above the table, once each, never in the cells.
    assert 'el("p", "note", note)' in text


def test_a_cell_add_reviews_one_client_and_the_review_shows_its_note():
    text = script("library.js")
    review = "review(previewFor(cell.add, client), { note: noteFor(cell.add, state.project) })"
    assert review in text
    offer = script("offer.js")
    assert '"Adds for all your projects."' in offer
    # Every add in a project view says so, a marketplace too.
    assert offer.count("{ note: projectNote(state.project) }") == 3
    panel = script("panel.js")
    assert "export async function review(previewBody, { note = null } = {})" in panel
    assert "if (note) body.append(callout(note));" in panel
    # Preview again keeps the note.
    assert "review(previewBody, { note })" in panel
    # Details of a row with a repeated name name its source.
    assert "rowTitle(row)" in panel


def test_typing_waits_before_the_library_asks_the_server():
    text = script("library.js")
    assert "const TYPING_MS = 200;" in text and "load(); }, TYPING_MS);" in text
    # A newer request wins, and a change waits for the new rows before the cells morph.
    assert "order === sent && at >= cache.at" in text and "if (latest()) cache =" in text
    assert "await Promise.all([reload(), loadLibrary()]);" in script("app.js")
    assert "await Promise.all([reload().catch(() => {}), loadLibrary()]);" in script("panel.js")


def test_library_columns_hide_with_a_quiet_minus_kept_in_this_browser():
    text, css = script("library.js"), (STATIC / "style.css").read_text()
    # The choice lives in this browser; every read and write is inside try/catch.
    assert 'const HIDDEN_KEY = "kitden-hidden-clients"' in text
    store = text.split("export function hiddenClients")[1].split("// The kind tab shown")[0]
    assert store.count("localStorage.") == 2
    assert store.count("try {") == 2 and store.count("catch") == 2
    # A named button per column, not drawn for the last one; the server gets the sorted list.
    assert 'button("−"' in text and "`Hide ${column.name}`" in text and "shown.length < 2" in text
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
    panel, offer = script("panel.js"), script("offer.js")
    # The marketplace's entry is read beside the definitions; when it fails the rest still shows.
    assert "row.offer ? getJson(`/api/offer${query({ kind: row.kind, id: row.offer })}`)" in panel
    assert ".catch(() => null)" in panel
    assert "body.append(...about(offer))" in panel
    # A Details button opens the same review as the cell's own button.
    assert "review(previewFor(option.add, option.client), {" in offer
    assert "note: noteFor(option.add, state.project) })" in offer
    assert '"Add…"' in offer and 'button("Add…", () => addForm(offer), "btn primary")' not in offer
    # With nothing to do, the first line of the body says why, quietly.
    first = 'const body = el("div", "body");\n  if (why) body.append(el("p", "muted", why));'
    assert first in panel
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
