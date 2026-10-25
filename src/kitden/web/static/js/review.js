// Change review: a change in Details as it was previewed (a row of the tray, or Add missing's
// list before its row is added), what the page does after Apply all, and Undo.
import { postJson } from "./api.js";
import { backToDetails, clientName, KIND_WORDS } from "./details.js";
import { $, $$, button, el, joinWords, plural, reportError, shortPath, shortPaths, withFocusKey } from "./dom.js";
import { loadLibrary, morphOnNextRender } from "./library.js";
import { fold, transition } from "./motion.js";
import { closePanel, drawQuietly, header, hideToast, isPanelOpen, openPanel, panelState, toast } from "./panel.js";
import { allPutBack, callout, checkBox, CLIENT_ORDER, diffCounts, kitdenMove, mark, movedNames, notesSection, PLACE_IN_TITLE, ruleText, rulesText, skillRemoval, socket, strictText, targetWords } from "./parts.js";
import { busy, reload, render, setBusy, state } from "./store.js";
import { projectLabel, tools } from "./tools.js";
import { addToTray, changeOutcome, checkTrayStale, onTray, takeOut, tray } from "./tray.js";

// changeOutcome lives in tray.js; panel.js still exports it from here.
export { changeOutcome };

const DONE_WORDS = {
  "plugin.disable": "Turned off", "plugin.enable": "Turned on", "mcp.remove_direct": "Removed", "plugin.remove": "Removed",
  "skill.remove": "Removed",
  "gateway.connect": "Connected the gateway", "setup_server.register": "Connected", "client.disconnect": "Disconnected",
  "setup_server.update": "Updated show my setup to Kitden", "gateway.move": "Moved",
  "setup_server.enable": "Turned on the kitden entry",
  "gateway.switch": "Switched the gateway", "plugin.install": "Added", "marketplace.add": "Added the marketplace",
  "skill.install": "Added", "plugin.skills": "Added",
  "gateway.remove": "Removed", "gateway.put_back": "Put", "mcp.add": "Added",
  "gateway.keychain": "Moved",
};

// Actions whose words say "from" a client.
const REMOVES = ["mcp.remove_direct", "plugin.remove", "skill.remove"];
// Actions that add an item: the review names where it goes before the click. A marketplace, a
// gateway's entry and a server put back always go to all projects. app.py's ADD_ACTIONS has
// three more: Add missing names its project in its title already, setup_server.update changes an
// entry where it is, and setup_server.register says "to Kitden".
export const ADDS = ["mcp.add", "skill.install", "plugin.install", "plugin.skills", "marketplace.add", "gateway.connect", "gateway.put_back"];
// Where the steps go, as the title ends (parts.js, so the Changes page says it too).
export { PLACE_IN_TITLE, targetWords };
// No promise of Undo for every change: the server names the known limit (`undo_note`).
const LEDE = "Nothing is written until you press Apply. A backup is kept.";
// The twin of views/words.py UNCHANGED; said only when the server guarantees it.
const UNCHANGED = "Other projects are unchanged. ";

// Where an add goes, as its title ends: " in website" or " for all projects"; null for an
// action that is not an add. For a change from before the server named its target.
export function addScope(action, into) {
  if (!ADDS.includes(action)) return null;
  return into ? ` in ${projectLabel(into)}` : " for all projects";
}

// The review's lede. With All projects picked an add says it is for all projects (in a project
// the note above the result says where it goes); a change in one project says other projects
// are unchanged, only when the server guarantees it. Then the backup, and what Undo cannot bring
// back, when the server knows.
export function reviewLede(change, picked) {
  const target = change.target || null;
  const everywhere = !target || target.scope === "all";
  let first = "";
  if (ADDS.includes(change.action) && !picked && everywhere) first = "Adds for all projects. ";
  else if (target && target.others_unchanged) first = UNCHANGED;
  return `${first}${LEDE}${change.undo_note ? ` ${change.undo_note}` : ""}`;
}

// The review title names the exact entry; the toast uses the short name ("superpowers").
// `previewBody` is what the review asked for; Add skills names its plugin and a tool rule its
// tool and project from it.
export function changeWords(change, previewBody) {
  if (change.action === "gateway.rule") {
    const params = (previewBody && previewBody.params) || {};
    return ruleText(params, params.project ? projectLabel(params.project) : null);
  }
  if (change.action === "gateway.strict") {
    const params = (previewBody && previewBody.params) || {};
    return strictText(params);
  }
  if (change.action === "gateway.rules") {
    const params = (previewBody && previewBody.params) || {};
    return rulesText({ ...params, tools: params.tools || [] }, params.project ? projectLabel(params.project) : null);
  }
  // A move names the servers it takes; the Kitden gateway's own steps are not a client.
  const kitden = kitdenMove(change);
  const steps = change.steps.filter((s) => s.client !== "gateway" && s.client !== "kitden");
  const listed = change.action === "gateway.move" ? movedNames(change.steps) : [...new Set(steps.map((s) => s.name))];
  const names = joinWords(listed);
  const short = joinWords([...new Set(listed.map((name) => name.split("@")[0]))]);
  // A copied skill folder reaches every client that reads that folder, not only its owner.
  const reached = [...new Set(steps.flatMap((s) => s.reaches || [s.client]))];
  reached.sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  const clients = joinWords(reached.map(clientName));
  const plugin = ((previewBody && previewBody.params && previewBody.params.plugin) || "the plugin").split("@")[0];
  const server = (previewBody && previewBody.params && previewBody.params.server) || (change.steps[0] && change.steps[0].name);
  let title = {
    "gateway.move": kitden ? `Move ${names} into the Kitden gateway` : `Move ${names} into the gateway`,
    "plugin.disable": `Turn off ${names} in ${clients}`,
    "plugin.enable": `Turn on ${names} in ${clients}`,
    "mcp.remove_direct": `Remove ${names} from ${clients}`,
    "plugin.remove": `Remove ${short} from ${clients}`,
    "gateway.connect": `Connect the gateway to ${clients}`,
    "plugin.install": `Add ${joinWords([...new Set(steps.filter((s) => s.name.includes("@")).map((s) => s.name))])} to ${clients}`,
    "marketplace.add": `Add the ${names} marketplace to ${clients}`,
    "skill.install": `Add ${names} to ${clients}`,
    "mcp.add": `Add ${names} to ${clients}`,
    "plugin.skills": `Add ${plugin}'s skills to ${clients}`,
    // Each client's last step adds the new entry; it is named after the gateway.
    "gateway.switch": `Use ${steps.length ? steps[steps.length - 1].name : "the new gateway"} in ${clients}`,
    "setup_server.register": `Connect ${clients} to Kitden`,
    "client.disconnect": `Disconnect ${clients} from Kitden`,
    "setup_server.update": `Update “show my setup” to Kitden in ${clients}`,
    "setup_server.enable": `Turn on the kitden entry in ${clients}`,
    "gateway.remove": `Remove ${server} from the Kitden gateway`,
    "gateway.put_back": `Put ${server} back in ${clients}`,
    "gateway.keychain": `Move the secrets of ${server} to the Keychain`,
  }[change.action] || change.action;
  const verb = DONE_WORDS[change.action] || change.action;
  let what = `${verb} ${short} ${REMOVES.includes(change.action) ? "from" : "in"} ${clients}`;
  // Never "removed" alone for a client that still loads another copy of the skill.
  if (change.action === "skill.remove") {
    const { clients: lose, oneCopy } = skillRemoval(steps);
    const words = `${oneCopy ? "one copy of " : ""}${names} from ${joinWords(lose.map(clientName))}`;
    title = `Remove ${words}`;
    what = `${verb} ${words}`;
  }
  if (change.action === "plugin.install") {
    what = `${verb} ${joinWords([...new Set(steps.filter((s) => s.name.includes("@")).map((s) => s.name.split("@")[0]))])} to ${clients}`;
  } else if (["marketplace.add", "skill.install", "mcp.add"].includes(change.action)) {
    what = `${verb} ${short} to ${clients}`;
  } else if (["gateway.connect", "gateway.switch", "setup_server.update", "setup_server.enable"].includes(change.action)) {
    what = `${verb} ${["setup_server.update", "setup_server.enable", "gateway.switch"].includes(change.action) ? "in" : "to"} ${clients}`;
  } else if (change.action === "setup_server.register") {
    what = `${verb} ${clients} to Kitden`;
  } else if (change.action === "client.disconnect") {
    what = `${verb} ${clients} from Kitden`;
  } else if (change.action === "gateway.move") {
    what = `${verb} ${short} into ${kitden ? "the Kitden gateway" : "the gateway"}`;
  } else if (change.action === "gateway.remove") {
    what = `${verb} ${server} from the Kitden gateway`;
  } else if (change.action === "gateway.put_back") {
    what = `${verb} ${server} back in ${clients}`;
  } else if (change.action === "gateway.keychain") {
    what = `${verb} the secrets of ${server} to the Keychain`;
  } else if (change.action === "plugin.skills") {
    what = `${verb} ${plural(steps.length, "skill", "skills")} to ${clients}`;
  } else if (change.action === "project.align") {
    const folder = projectLabel(previewBody && previewBody.params && previewBody.params.project);
    const chosen = ((change.align && change.align.candidates) || []).filter((c) => c.chosen);
    title = `Add what ${folder} is missing`;
    what = `Added ${plural(chosen.length, "item", "items")} for ${folder}`;
  }
  // The title says where the steps go: into one project, or for all projects. A title that
  // names its place keeps it once; a change from before the server said so names an add's.
  const target = change.target && !PLACE_IN_TITLE.includes(change.action) ? change.target : null;
  const scope = target ? targetWords(target) : addScope(change.action, previewBody && previewBody.params && previewBody.params.project);
  if (scope) {
    title = `${title}${scope}`;
    what = `${what}${scope}`;
  }
  const notes = [...new Set(change.steps.map((s) => s.restart_note).filter(Boolean))]
    .map((note) => note.replace(/,? for this to take effect\.?$/, ""));
  const after = notes.length > 1 ? [`Restart or reload ${clients}`] : notes;
  return { title, done: [what, ...after].join(" · ") };
}

// Add missing: the candidates as checkboxes, one group per client that lacks them, in client
// order. Each label says what, from which client, and where it goes; `note` says when the
// client has the name in another case, or a client would load it twice. Those start unchecked.
const PLACE_WORDS = { project: "this project", all: "all projects" };
export function alignGroups(align) {
  return CLIENT_ORDER.map((client) => ({
    client,
    name: clientName(client),
    items: align.candidates.filter((c) => c.to === client).map((c) => ({
      key: c.key,
      label: `${c.name} · ${KIND_WORDS[c.kind]} · from ${clientName(c.from)} · ${PLACE_WORDS[c.place]}`,
      note: c.note || null,
      chosen: c.chosen,
    })),
  })).filter((group) => group.items.length);
}

// The chosen keys once one box changes, in candidate order.
export function chosenKeys(align, key, checked) {
  return align.candidates.filter((c) => (c.key === key ? checked : c.chosen)).map((c) => c.key);
}

// The Add missing checklist, ticked as the change says. A changed tick calls `onChoose(keys)` with
// the keys ticked now, in candidate order; with none it says to choose one. The change itself is
// left as it is: the caller asks for the new one.
function alignSection(change, onChoose) {
  const section = el("section", "align");
  const align = { ...change.align, candidates: change.align.candidates.map((c) => ({ ...c })) };
  const none = () => {
    if (!section.querySelector(".none")) section.append(el("p", "note none", "Choose at least one item."));
  };
  for (const group of alignGroups(align)) {
    const set = el("fieldset", "checks list");
    set.append(el("legend", null, `Add to ${group.name}`));
    for (const item of group.items) {
      const label = el("label");
      const [box, tick] = checkBox();
      box.checked = item.chosen;
      box.dataset.key = item.key;
      box.addEventListener("change", async () => {
        const chosen = chosenKeys(align, item.key, box.checked);
        for (const c of align.candidates) c.chosen = chosen.includes(c.key);
        if (!chosen.length) none();
        await onChoose(chosen);
        const again = $$("#drawer input[type=checkbox]").find((b) => b.dataset.key === item.key);
        if (again) again.focus();
      });
      label.append(box, tick, el("span", null, item.label));
      if (item.note) label.append(el("span", "muted", ` · ${item.note}`));
      set.append(label);
    }
    section.append(set);
  }
  // Every add would make a duplicate, so none starts ticked.
  if (!align.candidates.some((c) => c.chosen)) none();
  const notSame = align.not_same || [];
  if (notSame.length) {
    const list = el("ul", "checklist");
    for (const n of notSame) list.append(el("li", null, `${n.name} · ${KIND_WORDS[n.kind]} · ${n.clients.map(clientName).join(", ")}`));
    section.append(el("h2", null, "Not the same; not touched"), list);
  }
  const leftOut = leftOutText(align.left_out);
  if (leftOut) section.append(el("p", "muted", leftOut));
  return section;
}

// What Add skills does not copy, as one plain line; empty when it copies every skill.
export function leftOutText(leftOut) {
  if (!leftOut || !leftOut.length) return "";
  return `Left out: ${leftOut.map((s) => `${s.name} (${s.why})`).join(", ")}.`;
}

// A preview answer the review can show: a change, or an Add missing list with nothing chosen
// (no change yet, so no id; "Add to preview" waits for a box).
export function canShowReview(result) {
  const data = result && result.ok ? result.data : null;
  return Boolean(data && (data.id || (data.align && Array.isArray(data.steps))));
}

// Every change waits in the tray: a press adds its row there and opens nothing (the tray's bar says
// why when the server refuses it). Add missing is the one change asked with nothing chosen yet, so
// its list opens in Details first. `note` goes with the row, shown above its review. `back`, from a
// tool list, hears how the add went: `{ queued: true }`, or `{ error }` with the reason.
export async function review(previewBody, { note = null, back = null } = {}) {
  const params = previewBody.params || {};
  if (previewBody.action === "project.align" && !params.chosen) {
    await chooseMissing(previewBody, note);
    return;
  }
  // A refusal of this add is a new `tray.refused`; an add that could not even be asked (a change
  // is being written) leaves the one before as it was, and says nothing of it.
  const before = tray.refused;
  const joined = await addToTray(previewBody, { note });
  if (!back) return;
  if (joined) await back({ queued: true });
  else if (tray.refused && tray.refused !== before) await back({ error: tray.refused.reason });
}

// Add missing's list: the server says what each client lacks and ticks what would not make a
// duplicate. The preview behind it is never applied (the tray is), so the server forgets it at once.
// The list shows in Details; a refusal goes back to the Details it was asked from, if still there.
async function chooseMissing(previewBody, note) {
  const asked = state.project;
  const from = panelState.from;
  const result = await postJson("/api/changes/preview", { ...previewBody, picked: asked || null });
  const id = result && result.data && result.data.id;
  if (id) postJson(`/api/changes/${encodeURIComponent(id)}/cancel`).catch(() => {});
  // Another project was picked while it was prepared: it opens nothing.
  if (state.project !== asked) return;
  if (!canShowReview(result)) {
    const reason = (result.data && result.data.detail) || `Could not prepare this change (${result.status}).`;
    if (from && panelState.from === from) {
      backToDetails({ error: reason });
      return;
    }
    panelState.current = { type: "error" };
    const footer = el("footer");
    footer.append(button("Close", () => closePanel(), "btn"));
    const body = el("div", "body");
    body.append(callout(reason, "error"));
    openPanel([header("Review change", "Could not prepare this change", null, null), body, footer]);
    return;
  }
  showChooser(result.data, previewBody, note, from);
}

// The list in Details: the review of what is ticked now, the ticks, Cancel and "Add to preview".
// A changed tick asks for the list again with that choice. "Add to preview" adds the row with the
// ticks; it and Cancel go back to the Details the list was opened from, else the panel closes.
function showChooser(change, previewBody, note, from) {
  const leave = () => (from && panelState.from === from ? backToDetails() : closePanel());
  let chosen = change.align.candidates.filter((c) => c.chosen).map((c) => c.key);
  const add = button("Add to preview", () => {
    const body = { ...previewBody, params: { ...previewBody.params, chosen } };
    leave();
    return addToTray(body, { note });
  }, "btn primary");
  add.disabled = !chosen.length;
  const onChoose = (keys) => {
    chosen = keys;
    add.disabled = true;
    if (keys.length) return chooseMissing({ ...previewBody, params: { ...previewBody.params, chosen: keys } }, note);
    return null;
  };
  showReview(change, previewBody, note, {
    current: { type: "align", change, previewBody, note },
    picked: state.project,
    buttons: [button("Cancel", leave, "btn"), add],
    onChoose,
  });
}

// The after line's client chips, and its notes, each once. An entry may have only a note (a
// tool rule when no client uses the Kitden gateway yet).
export function afterParts(entries) {
  return { chips: entries.filter((e) => e.client), notes: [...new Set(entries.map((e) => e.note).filter(Boolean))] };
}

// "After: [CC] Claude Code ● Off · [CU] Cursor ● Loads once", in the Library's sockets.
// An entry with a note (a client that would load a skill twice) gets its one line below.
function afterLine(entries) {
  const { chips, notes } = afterParts(entries);
  const box = el("div");
  if (chips.length) {
    const line = el("div", "after");
    line.append(el("span", "note", "After:"));
    for (const entry of chips) {
      const who = el("span", "who");
      who.append(mark(entry.client), el("span", null, clientName(entry.client)), socket({ state: entry.state, word: entry.word }));
      line.append(who);
    }
    box.append(line);
  }
  for (const note of notes) box.append(callout(note));
  return box;
}

// Only the lines that change show; the diff's own header lines say nothing a person needs.
// Each line is a block, so removed and added lines carry their own tint.
function diffLines(text) {
  const pre = el("pre", "diff");
  for (const line of String(text || "").split("\n")) {
    if (line === "--- before" || line === "+++ after" || /^@@ /.test(line)) continue;
    let look = "line";
    if (line.startsWith("+")) look = "line add";
    else if (line.startsWith("-")) look = "line del";
    pre.append(el("span", look, line || " "));
  }
  return pre;
}

// What a review shows under its title: the note, the result, Add missing's ticks (with
// `onChoose`), the file changes behind one summary and what follows.
function reviewBody(change, previewBody, note, onChoose) {
  const body = el("div", "body");
  if (note) body.append(callout(note));
  if (change.after && change.after.length) body.append(afterLine(change.after));
  if (change.shared_file_warning) body.append(callout("This edits a project file that is usually shared through git."));
  if (change.align && onChoose) body.append(alignSection(change, onChoose));
  // The result comes first; the file change and the command wait behind one summary.
  const files = el("details", "file-change");
  const summary = el("summary", null, change.steps.length > 1 ? "Show file changes" : "Show file change");
  const counts = change.steps.map((s) => diffCounts(s.diff)).reduce((a, b) => ({ added: a.added + b.added, removed: a.removed + b.removed }), { added: 0, removed: 0 });
  if (counts.added || counts.removed) {
    const count = el("span", "diff-count");
    count.setAttribute("aria-label", `${plural(counts.added, "line", "lines")} added, ${counts.removed} removed`);
    if (counts.added) count.append(el("span", "plus", `+${counts.added}`));
    if (counts.removed) count.append(el("span", "minus", `−${counts.removed}`));
    summary.append(count);
  }
  files.append(summary);
  for (const step of change.steps) {
    const box = el("div", "step");
    const head = el("div", "step-head");
    const file = el("span", "file mono", shortPath(step.path));
    file.title = step.path || "";
    head.append(mark(step.client), el("strong", null, clientName(step.client)), file);
    box.append(head, diffLines(step.diff));
    files.append(box);
    if (step.command) files.append(el("p", "muted", `Runs ${clientName(step.client)}'s own command: ${step.command}`));
  }
  body.append(fold(files));
  const leftOut = leftOutText(change.left_out);
  if (leftOut) body.append(el("p", "muted", leftOut));
  const after = notesSection("After you apply", change.steps);
  if (after) body.append(after);
  return body;
}

// A change in Details as it was previewed, with no Apply of its own: the tray's bar writes every
// change at once. `current` is what the panel shows (panelState), `picked` the project it was
// asked in (for the lede), `buttons` the footer's, and `onChoose` takes Add missing's ticks.
function showReview(change, previewBody, note, { current, picked, buttons, onChoose = null }) {
  panelState.current = current;
  const footer = el("footer");
  footer.append(...buttons);
  const words = changeWords(change, previewBody);
  openPanel([header("Review change", words.title, reviewLede(change, picked), null), reviewBody(change, previewBody, note, onChoose), footer]);
}

// "Show changes" on a row of the tray: that row's review, as it was asked. Closing it asks the
// server nothing; "Take it out" leaves the tray, Close leaves everything as it is. An Add missing
// row shows its ticks: a changed one adds the row again with the new choice.
export function showRowReview(row) {
  showReview(row.part, row.body, row.note, {
    current: { type: "row-review", row },
    picked: row.picked,
    buttons: [takeOutButton(row), button("Close", () => closePanel(), "btn")],
    onChoose: row.part.align ? (keys) => chooseAgain(row, keys) : null,
  });
}

// "Take it out" of a row's review: the row leaves the tray, and the review closes with it (the dock
// hands focus on to the bar). While the tray is written it is off and does nothing, as the bar's ×:
// a change cannot stop halfway. It follows the tray while it is on the page.
function takeOutButton(row) {
  const writing = () => tray.phase === "applying" || tray.phase === "applied";
  const node = button("Take it out", () => {
    if (writing()) return null;
    const taken = takeOut(row.key);
    closePanel();
    return taken;
  }, "btn");
  const follow = () => {
    if (writing()) node.setAttribute("aria-disabled", "true");
    else node.removeAttribute("aria-disabled");
  };
  follow();
  const stop = onTray(() => (node.isConnected ? follow() : stop()));
  return node;
}

// A changed tick in an Add missing row's review: the row is added again with the new choice (the
// same key, so it takes the old row's place), and the review shows the row the tray has now, the
// new one, or the old one when the server refused the choice (the bar says why). With nothing
// ticked there is nothing to add: the row stays as it is.
async function chooseAgain(row, keys) {
  if (!keys.length) return;
  await addToTray({ ...row.body, params: { ...row.body.params, chosen: keys } }, { note: row.note, icon: row.icon, picked: row.picked });
  const now = tray.rows.find((r) => r.key === row.key && r.part);
  const open = panelState.current;
  if (now && open && open.type === "row-review" && open.row.key === row.key && isPanelOpen()) showRowReview(now);
}

// The engine put back everything a change that did not check out wrote: its words then end "The
// original settings were restored.".
export function nothingChanged(after) {
  return after.state === "stale" || (after.state === "restored" && allPutBack(after.error));
}

// Everything the page shows, the Library's rows too, read again after a change.
export async function reloadAll() {
  await Promise.all([reload().catch(() => {}), loadLibrary()]);
}

// The page shows the effect where it happened: the Library morphs its cells, every other
// place cross-fades to its new state.
export function showEffect() {
  if (state.view === "library") {
    morphOnNextRender();
    render();
  } else {
    transition(render);
  }
}

// After Apply all or an Undo, the Details open now are drawn again from what the files say: a tool
// list by its own redraw, other Details by reading again. Focus in the dock or on the page stays
// there; focus in Details stays on its control, found again by its key (a control that is gone
// gives way, as backToDetails and the tool list say). The switch pressed last springs into its new
// state when its row is among the applied ones (`keys`). Anything else in the panel (a row's review,
// Add missing's list) is left alone: a row's review closes with its row.
export async function detailsAgain(keys) {
  const from = panelState.from;
  if (!isPanelOpen() || !from || !from.shown()) return;
  const active = document.activeElement;
  const inside = $("#drawer").contains(active);
  const held = inside && active.dataset ? active.dataset.focus || null : null;
  await drawQuietly(async () => {
    if (tools && tools.section.isConnected) {
      const pressed = withFocusKey(tools.section, from.focus);
      const flip = pressed && keys.includes(pressed.dataset.tray) ? from.focus : null;
      await tools.again({ focus: inside ? held || from.focus : null, flip });
      return;
    }
    if (held) from.focus = held;
    from.stale = true;
    await backToDetails({ refocus: inside });
  });
}

// Undo, from the toast or the Changes page. Whatever the answer, the page reloads first: the
// server may have put the files back even when its answer was lost. Details that cannot be read
// again never keep the toast from saying how it went. Then the tray asks whether its preview is
// stale: the Undo may have changed its files.
export async function undoChange(change) {
  if (busy.change) return;
  hideToast();
  setBusy(true);
  try {
    const { after, failure } = await changeOutcome(change.id, "undo");
    await reloadAll();
    // With a tool list's Details still open, the page behind just redraws and Details is drawn
    // again from the files as they are now, focus on the switch the Undo changed back.
    if (isPanelOpen() && tools && tools.section.isConnected) {
      render();
      const undone = after && after.state === "undone";
      await tools.again({ focus: tools.flipped, flip: undone ? tools.flipped : null });
    } else {
      showEffect();
      // Other Details open now show the files as they are after the Undo too.
      try {
        await detailsAgain([]);
      } catch (error) {
        reportError(error);
      }
    }
    if (after && after.state === "undone") toast("Undone. The previous settings are back.", null, { ok: true });
    else if (after && after.state === "undo_blocked") toast("Undo stopped: " + (after.error ? shortPaths(after.error) : "the file changed after the change was applied."));
    else toast(failure);
  } finally {
    setBusy(false);
  }
  await checkTrayStale();
}
