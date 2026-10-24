// Change review: the preview, Apply and its motion, and Undo.
import { getJson, postJson } from "./api.js";
import { backToDetails, clientName, KIND_WORDS } from "./details.js";
import { $, $$, button, el, joinWords, plural, reportError, shortPath, shortPaths } from "./dom.js";
import { loadLibrary, morphOnNextRender } from "./library.js";
import { fold, transition } from "./motion.js";
import { cancelPreview, checkMark, closePanel, header, hideToast, isPanelOpen, openPanel, panelState, restoreFocus, toast } from "./panel.js";
import { callout, CLIENT_ORDER, diffCounts, kitdenMove, mark, movedNames, notesSection, PLACE_IN_TITLE, ruleText, rulesText, skillRemoval, socket, stepText, strictText, targetWords } from "./parts.js";
import { busy, reload, render, setBusy, state } from "./store.js";
import { projectLabel, tools } from "./tools.js";

// Node before 21 (the tests) has no navigator.
const APPLY_KEY = typeof navigator !== "undefined" && /Mac/.test(navigator.platform) ? "⌘ Enter to apply" : "Ctrl Enter to apply";
// While a change is written nothing in the review can stop it; the note says what happens.
const WRITING = "Writing the change. It can't stop halfway: if a step fails, Kitden puts everything back.";

const DONE_WORDS = {
  "plugin.disable": "Turned off", "plugin.enable": "Turned on", "mcp.remove_direct": "Removed", "plugin.remove": "Removed",
  "skill.remove": "Removed",
  "gateway.connect": "Connected the gateway", "setup_server.register": "Added show my setup",
  "setup_server.update": "Updated show my setup to Kitden", "gateway.move": "Moved",
  "setup_server.enable": "Turned on the kitden entry",
  "gateway.switch": "Switched the gateway", "plugin.install": "Added", "marketplace.add": "Added the marketplace",
  "skill.install": "Added", "plugin.skills": "Added",
  "gateway.remove": "Removed", "gateway.put_back": "Put", "mcp.add": "Added",
  "gateway.keychain": "Moved",
};

// Actions whose words say "from" a client.
const REMOVES = ["mcp.remove_direct", "plugin.remove", "skill.remove"];
// Actions that add an item: the review names where it goes before the click. A marketplace, the
// setup entry, a gateway's entry and a server put back always go to all projects. app.py's
// ADD_ACTIONS has two more: Add missing names its project in its title already, and
// setup_server.update changes an entry where it is.
export const ADDS = ["mcp.add", "skill.install", "plugin.install", "plugin.skills", "marketplace.add", "setup_server.register", "gateway.connect", "gateway.put_back"];
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
    "setup_server.register": `Add “show my setup” to ${clients}`,
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
  } else if (["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update", "setup_server.enable"].includes(change.action)) {
    what = `${verb} ${["setup_server.update", "setup_server.enable", "gateway.switch"].includes(change.action) ? "in" : "to"} ${clients}`;
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

// The Add missing checklist. A change cancels this preview and asks for a new one with the new
// choice; with nothing chosen there is nothing to preview, so Apply waits for a box.
function alignSection(change, previewBody, note, apply) {
  const section = el("section", "align");
  for (const group of alignGroups(change.align)) {
    const set = el("fieldset", "checks list");
    set.append(el("legend", null, `Add to ${group.name}`));
    for (const item of group.items) {
      const label = el("label");
      const box = el("input");
      box.type = "checkbox";
      box.checked = item.chosen;
      box.dataset.key = item.key;
      box.addEventListener("change", async () => {
        const chosen = chosenKeys(change.align, item.key, box.checked);
        cancelPreview();
        apply.disabled = true;
        change.align.candidates = change.align.candidates.map((c) => ({ ...c, chosen: chosen.includes(c.key) }));
        change.state = "cancelled";
        if (!chosen.length) {
          if (!section.querySelector(".none")) section.append(el("p", "note none", "Choose at least one item."));
          return;
        }
        await review({ ...previewBody, params: { ...previewBody.params, chosen } }, { note });
        const again = $$("#drawer input[type=checkbox]").find((b) => b.dataset.key === item.key);
        if (again) again.focus();
      });
      label.append(box, el("span", null, item.label));
      if (item.note) label.append(el("span", "muted", ` · ${item.note}`));
      set.append(label);
    }
    section.append(set);
  }
  // Every add would make a duplicate, so none starts checked: Apply waits for a box.
  if (!change.align.candidates.some((c) => c.chosen)) {
    apply.disabled = true;
    section.append(el("p", "note none", "Choose at least one item."));
  }
  const notSame = change.align.not_same || [];
  if (notSame.length) {
    const list = el("ul", "checklist");
    for (const n of notSame) list.append(el("li", null, `${n.name} · ${KIND_WORDS[n.kind]} · ${n.clients.map(clientName).join(", ")}`));
    section.append(el("h2", null, "Not the same; not touched"), list);
  }
  const leftOut = leftOutText(change.align.left_out);
  if (leftOut) section.append(el("p", "muted", leftOut));
  return section;
}

// What Add skills does not copy, as one plain line; empty when it copies every skill.
export function leftOutText(leftOut) {
  if (!leftOut || !leftOut.length) return "";
  return `Left out: ${leftOut.map((s) => `${s.name} (${s.why})`).join(", ")}.`;
}

// Ask the server for a preview and show it. Used by the Library, Gateway and Agents places.
// `note` shows as a callout above the result, for example that an add is for every project.
// `back({ error, verified })` returns to the Details the review came from (a tool switch):
// after Cancel, after Apply is verified, or with the reason the preview was refused.
// A preview answer the review can show: a change, or an Add missing list with nothing chosen
// (no change yet, so no id; Apply waits for a box).
export function canShowReview(result) {
  const data = result && result.ok ? result.data : null;
  return Boolean(data && (data.id || (data.align && Array.isArray(data.steps))));
}

export async function review(previewBody, { note = null, back = null } = {}) {
  // One preview at a time: one on the map that is only previewed goes first; while the map's change
  // is written nothing else is asked. Its own review in Details asks again with `mapBack`.
  if (back !== mapBack && mapPreview.phase !== "idle") {
    if (mapWriting()) return;
    dropMapPreview();
    redrawMap();
  }
  const asked = state.project;
  // The Details this review is asked from, if any: Cancel and a refusal go back only there.
  const from = panelState.from;
  // The project picked at the top: the server says when its own definition wins there.
  const result = await postJson("/api/changes/preview", { ...previewBody, picked: asked || null });
  // Another project was picked while it was prepared: it opens nothing, and the server forgets it.
  if (state.project !== asked) {
    const id = result && result.data && result.data.id;
    if (id) postJson(`/api/changes/${encodeURIComponent(id)}/cancel`).catch(() => {});
    return;
  }
  if (!canShowReview(result)) {
    const reason = (result.data && result.data.detail) || `Could not prepare this change (${result.status}).`;
    if (back) {
      await back({ error: reason });
      return;
    }
    // From Details, the reason shows there, as for a tool switch.
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
  showReview(result.data, previewBody, note, back, from);
}

// Where Cancel goes: "back" (a tool switch's own way back), "details" (the Details the review
// was opened from) or "close".
export function cancelTarget({ back, from }) {
  if (back) return "back";
  return from ? "details" : "close";
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
      const chip = el("span", "chip");
      chip.append(mark(entry.client), el("span", null, clientName(entry.client)), socket({ state: entry.state, word: entry.word }));
      line.append(chip);
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

export function showReview(change, previewBody, note, back = null, from = null) {
  panelState.current = { type: "review", change, previewBody, note, back, from };
  const words = changeWords(change, previewBody);
  const body = el("div", "body");
  if (note) body.append(callout(note));
  if (change.after && change.after.length) body.append(afterLine(change.after));
  if (change.shared_file_warning) body.append(callout("This edits a project file that is usually shared through git."));
  const apply = el("button", "btn primary apply");
  if (change.align) body.append(alignSection(change, previewBody, note, apply));
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

  const footer = el("footer");
  footer.append(el("span", "note", APPLY_KEY));
  // Cancel goes back to where the review came from: a tool switch's Details, the Details it was
  // opened from, or nowhere (the panel closes).
  const cancel = button("Cancel", () => {
    cancelPreview();
    const to = cancelTarget({ back, from: from && panelState.from === from ? from : null });
    if (to === "back") return back();
    if (to === "details") return backToDetails();
    return closePanel();
  }, "btn");
  apply.type = "button";
  const label = el("span", "label", "Apply");
  apply.append(label);
  apply.addEventListener("click", () => applyChange(change, { apply, cancel, label, body }).catch(brokeAfterAnswer));
  footer.append(cancel, apply);
  // A review whose change is being written stays: this preview is dropped at once.
  if (!openPanel([header("Review change", words.title, reviewLede(change, state.project), null), body, footer])) {
    cancelPreview({ type: "review", change });
  }
}

// Something broke after the server answered (a render, the toast). The answer stands, so
// the page says nothing new about the change; it only frees itself and logs the error.
function brokeAfterAnswer(error) {
  setBusy(false);
  reportError(error);
}

// While a change is written, Cancel and the close button are gone (nothing could stop it)
// and the note under the buttons says what is happening; they come back if it stops.
function lockReview(locked, apply, cancel) {
  apply.disabled = locked;
  cancel.disabled = locked;
  for (const box of $$("#drawer .align input")) box.disabled = locked;
  cancel.hidden = locked;
  const close = $("#drawer header .top button");
  if (close) {
    close.disabled = locked;
    close.hidden = locked;
  }
  const note = $("#drawer footer .note");
  if (note) note.textContent = locked ? WRITING : APPLY_KEY;
}

function resetApply(apply, cancel, label) {
  for (const extra of apply.querySelectorAll(".spinner, .check")) extra.remove();
  apply.classList.remove("done");
  label.textContent = "Apply";
  lockReview(false, apply, cancel);
}

const STOPPED = {
  stale: "A file changed after the preview, so nothing was written. Preview again to see the current state.",
  restored: "The change did not check out.",
};
// The states a change can end in after each verb. Read back in any other state it has not
// ended, so the page cannot say how it went.
const ENDED = {
  apply: ["verified", "stale", "restored", "cancelled", "undone", "undo_blocked"],
  undo: ["undone", "undo_blocked"],
};
const LOST = "Could not confirm the result. Check Changes before trying again.";

// The change as the server holds it now, or null when it cannot be read.
async function readChange(id) {
  try {
    return await getJson(`/api/changes/${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}

// How the change ended, read back from the server, when the answer cannot say.
async function readOutcome(id, verb) {
  const read = await readChange(id);
  return { after: read && ENDED[verb].includes(read.state) ? read : null, failure: LOST };
}

// How an Apply or an Undo ("apply", "undo") ended: the change as the server holds it, or why
// it failed.
export async function changeOutcome(id, verb) {
  const name = verb === "undo" ? "Undo" : "Apply";
  let result;
  try {
    result = await postJson(`/api/changes/${encodeURIComponent(id)}/${verb}`);
    if (!result.data) throw new Error(`The ${name} answer had no body (${result.status}).`);
  } catch (error) {
    // No answer, or one with no body, yet the change may have run: ask the server how it ended.
    console.error(error);
    return readOutcome(id, verb);
  }
  if (result.data.id) return { after: result.data, failure: null };
  // 409 with no change: it had moved on already, for example by an Apply whose answer was lost.
  if (result.status === 409) return readOutcome(id, verb);
  return { after: null, failure: result.data.detail || `${name} failed (${result.status}).` };
}

// Apply → Applying… (spinner) → Applied (the check draws); then the panel leaves and the
// page shows the effect where it happened. Each step waits for work, never for a timer.
async function applyChange(change, { apply, cancel, label, body }) {
  if (busy.change) return;
  const previewBody = panelState.current && panelState.current.previewBody;
  const note = panelState.current && panelState.current.note;
  const back = panelState.current && panelState.current.back;
  setBusy(true);
  lockReview(true, apply, cancel);
  label.textContent = "Applying…";
  apply.prepend(el("span", "spinner"));
  // A change with several steps counts them as the server finishes each one, and a thin bar
  // along the button's bottom edge fills to match. Both show only what the server reported.
  const meter = el("span", "meter");
  meter.setAttribute("aria-hidden", "true");
  apply.append(meter);
  const onProgress = (event) => {
    const { id, done, total } = event.detail || {};
    if (id !== change.id || !(total > 1)) return;
    label.textContent = stepText("Applying", done, total);
    meter.style.transform = `scaleX(${done / total})`;
  };
  document.addEventListener("kitden:progress", onProgress);
  // The last try's error stays until now, the next action.
  for (const old of body.querySelectorAll(".callout.error")) old.remove();
  let outcome;
  try {
    outcome = await changeOutcome(change.id, "apply");
  } finally {
    document.removeEventListener("kitden:progress", onProgress);
    meter.remove();
  }
  const { after, failure } = outcome;
  if (after && change.align) after.align = change.align;
  // The toast says the same place as the title.
  if (after) after.target = change.target;
  if (after && panelState.current) panelState.current.change = after;

  if (!after || after.state !== "verified") {
    setBusy(false);
    resetApply(apply, cancel, label);
    const reason = after ? STOPPED[after.state] || `The change stopped: ${after.state}.` : failure;
    const detail = after && after.error ? ` (${shortPaths(after.error)})` : "";
    body.prepend(callout(`${reason}${detail}`, "error"));
    // Focus goes to the button in Apply's place; the callout says what went wrong.
    let next = apply;
    if (after && after.state !== "previewed") {
      next = button("Preview again", () => review(previewBody, { note, back }), "btn primary");
      apply.replaceWith(next);
    }
    next.focus();
    reload().then(render).catch(() => {});
    return;
  }
  await showApplied(after, apply, label, previewBody, back);
}

// After a rescan, an open review asks whether its files changed since the preview. Only a
// previewed change with an id (Add missing with nothing chosen has none), and never while a
// change is written: that rescan is the change's own.
export function staleCheckWanted(current, busy) {
  const change = current && current.type === "review" ? current.change : null;
  return Boolean(change && change.id && change.state === "previewed" && !busy.change);
}

const STALE_NOTE = "Settings changed since this preview.";

// The server compares the files with the preview's own hashes. When they changed and the same
// review is still open, the warning comes first and stays until the next action, and Apply
// gives way to "Preview again", which drops this preview and asks for a new one. Focus moves
// only when it was on Apply. The Details the review came from is out of date too: Cancel, also
// after "Preview again", reads it again (details.js backToDetails).
export async function checkStale() {
  const current = panelState.current;
  // Apply gave way to "Preview again" already: nothing to ask.
  if (!staleCheckWanted(current, busy) || !$("#drawer .apply")) return;
  const read = await readChange(current.change.id);
  if (!read || !read.stale || panelState.current !== current || !staleCheckWanted(current, busy)) return;
  const apply = $("#drawer .apply");
  const body = $("#drawer .body");
  if (!apply || !body) return;
  const warning = callout(STALE_NOTE);
  warning.setAttribute("role", "alert");
  body.prepend(warning);
  const { previewBody, note, back } = current;
  const again = button("Preview again", () => {
    cancelPreview();
    return review(previewBody, { note, back });
  }, "btn primary");
  const focused = document.activeElement === apply;
  apply.replaceWith(again);
  if (focused) again.focus();
  if (current.from) current.from.stale = true;
}

// The server said `verified`: the button turns green while the page reloads, then the panel
// leaves at once and the toast offers Undo. From a tool switch, its Details comes back instead,
// with the switch flipped, and the page behind shows the new state. A preview from the map ends
// before the page is drawn, so the map shows the block solid and its new link draws once.
async function showApplied(after, apply, label, previewBody, back) {
  for (const spin of apply.querySelectorAll(".spinner")) spin.remove();
  apply.prepend(checkMark());
  apply.classList.add("done");
  label.textContent = "Applied";
  await reloadAll();
  const fromMap = back === mapBack;
  if (fromMap) Object.assign(mapPreview, IDLE);
  if (back && !fromMap) {
    // The change is done: this review lets its place go to the Details `back` draws again.
    if (panelState.current) panelState.current.handingBack = true;
    render();
    await back({ verified: true });
  } else {
    panelState.current = null;
    closePanel({ keepSelection: true, focus: false, force: true });
    showEffect();
    restoreFocus();
  }
  setBusy(false);
  appliedToast(after, previewBody);
}

// The toast after a verified change, the same for every review: what was done, and Undo.
export function appliedToast(after, previewBody) {
  toast(changeWords(after, previewBody).done, () => undoChange(after), { ok: true });
}

// Everything the page shows, the Library's rows too, read again after a change.
async function reloadAll() {
  await Promise.all([reload().catch(() => {}), loadLibrary()]);
}

// The page shows the effect where it happened: the Library morphs its cells, every other
// place cross-fades to its new state.
function showEffect() {
  if (state.view === "library") {
    morphOnNextRender();
    render();
  } else {
    transition(render);
  }
}

// Undo, from the toast or the Changes page. Whatever the answer, the page reloads first: the
// server may have put the files back even when its answer was lost.
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
    }
    if (after && after.state === "undone") toast("Undone. The previous settings are back.", null, { ok: true });
    else if (after && after.state === "undo_blocked") toast("Undo stopped: " + (after.error ? shortPaths(after.error) : "the file changed after the change was applied."));
    else toast(failure);
  } finally {
    setBusy(false);
  }
}

// The map's review (S.8) -----------------------------------------------------------------

// A preview started on the map (a drag, later a marketplace result) shows there: a preview block
// and a review bar on the canvas. `phase`: "idle", "loading" (asked), "ready", "applying" or
// "failed". `body` is the preview request and `change` the server's preview; `done` and `total`
// count Apply's steps; `failure` is how Apply ended ({ state, text }); `refused` holds the server's
// words when it would not prepare it. `project` is the project it was asked in, and `inDetails`
// says "Show changes" moved it into Details, where its own review shows it.
const IDLE = { body: null, change: null, phase: "idle", done: 0, total: 0, failure: null, refused: null, project: "", inDetails: false };
export const mapPreview = { ...IDLE };
// The newest request on the map: an answer to an older one is dropped.
let asking = 0;
// How the page draws the map again (gateway.js), as the last call gave it.
let redrawMap = () => {};

const NOTHING = "Nothing was changed.";
const REFUSED = "Could not prepare this change";
// Why Apply stopped when the engine wrote nothing or put every file back.
const BAR_STOPPED = { stale: STALE_NOTE, restored: STOPPED.restored };

// Every client the steps write, as the bar says it while Apply runs. Not the one being written:
// the engine's count names no step, and it does not write them in the preview's order.
export function writingLine(steps) {
  const names = [...new Set(steps.map((s) => s.client))].map((c) => (c === "kitden" ? "the Kitden gateway" : clientName(c)));
  if (names.length === 1) return `Writing ${names[0]}'s settings. A backup is kept.`;
  return `Writing the settings of ${joinWords(names)}. A backup is kept.`;
}

// What the change will do, in one line: the After chips by word ("Claude Code and Codex: Via
// gateway."), or with no chip the first sentence of the first note.
export function outcomeLine(change) {
  const { chips, notes } = afterParts(change.after || []);
  if (!chips.length) return notes.length ? (notes[0].match(/^.*?[.!?](?=\s|$)/) || [notes[0]])[0] : "";
  const byWord = new Map();
  for (const chip of chips) byWord.set(chip.word, [...(byWord.get(chip.word) || []), clientName(chip.client)]);
  return [...byWord].map(([word, names]) => `${joinWords(names)}: ${word}.`).join(" ");
}

// The bar's words for a preview (mapPreview's shape): the title with its scope, one outcome line
// and what Apply says. While Apply runs it counts the steps and Cancel waits. An error says
// "Nothing was changed." only when the engine wrote nothing or put every file back, and offers
// "Try again". A refusal has no change, so only Cancel stays: trying again would be refused for
// the same reason.
export function barWords({ phase, change, body, done, total, failure, refused }) {
  if (refused) return { title: REFUSED, outcome: `${refused} ${NOTHING}`, apply: null, cancelWaits: false, retry: false };
  const title = changeWords(change, body).title;
  if (phase === "applying") return { title, outcome: writingLine(change.steps), apply: stepText("Applying", done, total), cancelWaits: true, retry: false };
  if (phase === "failed") {
    const ended = failure && failure.state;
    let outcome = (failure && failure.text) || LOST;
    if (BAR_STOPPED[ended]) outcome = `${BAR_STOPPED[ended]} ${NOTHING}`;
    else if (ended) outcome = `The change stopped: ${ended}.`;
    return { title, outcome, apply: "Try again", cancelWaits: false, retry: true };
  }
  return { title, outcome: outcomeLine(change), apply: "Apply", cancelWaits: false, retry: false };
}

// The review bar on the map: the title with its scope, the outcome line (read out when it
// changes), then "Show changes" (the full review in Details), Cancel and Apply, or "Try again"
// after an error. While Apply runs, Cancel and Apply stay in place and wait. `change` is the
// preview (null for a refusal), `body` its request; the rest comes from mapPreview.
export function reviewBar(change, { onApply, onCancel, onShow, body }) {
  const words = barWords({ ...mapPreview, change, body });
  const bar = el("section", mapPreview.phase === "failed" ? "review-bar failed" : "review-bar");
  bar.setAttribute("role", "region");
  bar.setAttribute("aria-label", words.title);
  const text = el("div", "bar-words");
  const outcome = el("p", "bar-outcome", words.outcome);
  outcome.setAttribute("role", "status");
  text.append(el("strong", "bar-title", words.title), outcome);
  const actions = el("div", "bar-actions");
  const writing = words.cancelWaits;
  const add = (label, key, run, look) => {
    const node = el("button", look, label);
    node.type = "button";
    node.dataset.focus = `bar:${key}`;
    if (writing) node.setAttribute("aria-disabled", "true");
    node.addEventListener("click", () => { if (!writing) run(); });
    actions.append(node);
  };
  if (mapPreview.phase === "ready") add("Show changes", "show", onShow, "btn ghost");
  add("Cancel", "cancel", onCancel, "btn");
  if (words.apply) add(words.apply, "apply", onApply, "btn primary apply");
  bar.append(text, actions);
  return bar;
}

// Focus one of the bar's buttons ("apply", "cancel") once the page drew it.
function focusBar(key) {
  const node = typeof document !== "undefined" && document.querySelector ? document.querySelector(`[data-focus="bar:${key}"]`) : null;
  if (node) node.focus();
}

// The map's change is being written: from the bar, or by its review in Details.
function mapWriting() {
  return mapPreview.phase === "applying" || (mapPreview.inDetails && busy.change);
}

// The map's preview shows in Details now, in its own review.
function mapReviewShown() {
  const current = panelState.current;
  return isPanelOpen() && Boolean(current) && current.type === "review" && current.back === mapBack;
}

// Forget the preview on the map. One that is only previewed is cancelled on the server, and its
// review leaves Details; an answer still coming is dropped.
function dropMapPreview() {
  const { change, inDetails } = mapPreview;
  if (change && change.state === "previewed") {
    postJson(`/api/changes/${encodeURIComponent(change.id)}/cancel`).catch(() => {});
    change.state = "cancelled";
  }
  asking += 1;
  Object.assign(mapPreview, IDLE);
  if (inDetails && mapReviewShown()) closePanel({ focus: false });
}

// The map is left (another place, the List, another project): a preview on it that is only
// previewed goes; one being written goes on and ends as usual.
export function leaveMap() {
  if (mapPreview.phase !== "idle" && !mapWriting()) dropMapPreview();
}

// A preview moved into Details ends when its review leaves without Apply: Escape, or other
// Details in its place (panel.js cancels it on the server then). True when it just ended.
export function mapReviewLeft() {
  if (!mapPreview.inDetails || mapReviewShown() || busy.change) return false;
  asking += 1;
  Object.assign(mapPreview, IDLE);
  return true;
}

// The way back from the map's review in Details (its `back`): Cancel ends the preview, and a
// "Preview again" the server refused shows why in the bar. A verified Apply ends in showApplied.
function mapBack({ error = null } = {}) {
  const { body, project } = mapPreview;
  Object.assign(mapPreview, IDLE);
  if (error) Object.assign(mapPreview, { body, project, phase: "failed", refused: error });
  closePanel({ focus: false });
  redrawMap();
  if (error) focusBar("cancel");
}

// Ask the server for a preview started on the map (`body`, with the picked project) and show it
// there; `redraw` draws the page's map again. A preview on the map already goes first: one at a
// time, and nothing starts while a change is written. A refusal keeps the server's words. With
// another project picked, or the map left, meanwhile, the answer shows nothing and the server
// forgets it. Focus goes to Apply, or to Cancel after a refusal.
export async function previewOnMap(body, redraw) {
  if (mapWriting() || busy.change) return;
  redrawMap = redraw;
  dropMapPreview();
  const ticket = asking;
  const asked = state.project;
  Object.assign(mapPreview, { body, phase: "loading", project: asked });
  redraw();
  let result;
  try {
    result = await postJson("/api/changes/preview", { ...body, picked: asked || null });
  } catch (error) {
    reportError(error);
    result = { ok: false, status: 0, data: null };
  }
  const id = result.data && result.data.id;
  if (ticket !== asking || state.project !== asked) {
    if (id) postJson(`/api/changes/${encodeURIComponent(id)}/cancel`).catch(() => {});
    if (ticket === asking) {
      Object.assign(mapPreview, IDLE);
      redraw();
    }
    return;
  }
  if (id && canShowReview(result)) Object.assign(mapPreview, { phase: "ready", change: result.data });
  else Object.assign(mapPreview, { phase: "failed", refused: (result.data && result.data.detail) || `${REFUSED} (${result.status}).` });
  redraw();
  focusBar(mapPreview.refused ? "cancel" : "apply");
}

// Cancel in the bar: the server forgets the preview. It waits while the change is written.
export async function cancelOnMap(redraw) {
  if (mapWriting()) return;
  redrawMap = redraw;
  dropMapPreview();
  redraw();
}

// Apply in the bar: the button counts the steps as the server reports them, the bar says what is
// written, and Cancel waits. Only `verified` ends it: the page reads everything again, the preview
// goes (its block turns solid and its new link draws once) and the toast offers Undo. Any other
// end stays in the bar with "Try again", focus on it, and the page reads again behind it.
export async function applyOnMap(redraw) {
  if (mapPreview.phase !== "ready" || busy.change) return;
  redrawMap = redraw;
  const { change, body } = mapPreview;
  setBusy(true);
  try {
    Object.assign(mapPreview, { phase: "applying", done: 0, total: 0 });
    redraw();
    const onProgress = (event) => {
      const { id, done, total } = event.detail || {};
      if (id !== change.id || !(total > 1)) return;
      Object.assign(mapPreview, { done, total });
      redraw();
    };
    document.addEventListener("kitden:progress", onProgress);
    let outcome;
    try {
      outcome = await changeOutcome(change.id, "apply");
    } finally {
      document.removeEventListener("kitden:progress", onProgress);
    }
    const { after, failure } = outcome;
    if (after && after.state === "verified") {
      // The toast says the same place as the title.
      after.target = change.target;
      await reloadAll().catch(reportError);
      Object.assign(mapPreview, IDLE);
      redraw();
      setBusy(false);
      appliedToast(after, body);
      return;
    }
    change.state = after ? after.state : "unknown";
    Object.assign(mapPreview, { phase: "failed", failure: { state: after ? after.state : null, text: failure } });
    setBusy(false);
    redraw();
    focusBar("apply");
    reloadAll().then(render).catch(() => {});
  } finally {
    if (busy.change) setBusy(false);
  }
}

// "Show changes": the same preview moves into Details as its full review and the bar hides, so
// one change never has two Apply buttons. Cancel there ends it; its Apply ends as the bar's does.
export function showMapReview(redraw) {
  if (mapPreview.phase !== "ready" || mapPreview.inDetails || busy.change) return;
  redrawMap = redraw;
  mapPreview.inDetails = true;
  showReview(mapPreview.change, mapPreview.body, null, mapBack);
  redraw();
}
