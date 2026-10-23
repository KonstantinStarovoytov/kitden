// Change review: the preview, Apply and its motion, and Undo.
import { getJson, postJson } from "./api.js";
import { clientName, KIND_WORDS } from "./details.js";
import { $, $$, button, el, joinWords, plural, reportError, shortPath, shortPaths } from "./dom.js";
import { loadLibrary, morphOnNextRender } from "./library.js";
import { fold, transition } from "./motion.js";
import { cancelPreview, checkMark, closePanel, header, hideToast, isPanelOpen, openPanel, panelState, restoreFocus, toast } from "./panel.js";
import { callout, CLIENT_ORDER, diffCounts, kitdenMove, mark, movedNames, notesSection, ruleText, rulesText, skillRemoval, socket, stepText, strictText } from "./parts.js";
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
const LEDE = "Nothing is written until you press Apply. A backup is kept, so you can undo.";

// Where an add goes, as its title ends: " in website" or " for all projects"; null for an
// action that is not an add.
export function addScope(action, into) {
  if (!ADDS.includes(action)) return null;
  return into ? ` in ${projectLabel(into)}` : " for all projects";
}

// The review's lede. With All projects picked an add says it is for all projects; in a project
// the note above the result says where it goes.
export function reviewLede(action, picked) {
  return `${ADDS.includes(action) && !picked ? "Adds for all projects. " : ""}${LEDE}`;
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
  } else if (["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update"].includes(change.action)) {
    what = `${verb} ${["setup_server.update", "gateway.switch"].includes(change.action) ? "in" : "to"} ${clients}`;
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
  // An add says where it goes: into one project, or for all projects.
  const scope = addScope(change.action, previewBody && previewBody.params && previewBody.params.project);
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
  const asked = state.project;
  const result = await postJson("/api/changes/preview", previewBody);
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
    panelState.current = { type: "error" };
    const footer = el("footer");
    footer.append(button("Close", () => closePanel(), "btn"));
    const body = el("div", "body");
    body.append(callout(reason, "error"));
    openPanel([header("Review change", "Could not prepare this change", null, null), body, footer]);
    return;
  }
  showReview(result.data, previewBody, note, back);
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

function showReview(change, previewBody, note, back = null) {
  panelState.current = { type: "review", change, previewBody, note, back };
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
  // From a tool switch, Cancel goes back to its Details; otherwise it closes the panel.
  const cancel = button("Cancel", () => {
    if (!back) return closePanel();
    cancelPreview();
    return back();
  }, "btn");
  apply.type = "button";
  const label = el("span", "label", "Apply");
  apply.append(label);
  apply.addEventListener("click", () => applyChange(change, { apply, cancel, label, body }).catch(brokeAfterAnswer));
  footer.append(cancel, apply);
  openPanel([header("Review change", words.title, reviewLede(change.action, state.project), null), body, footer]);
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

// The server said `verified`: the button turns green while the page reloads, then the panel
// leaves at once and the toast offers Undo. From a tool switch, its Details comes back instead,
// with the switch flipped, and the page behind shows the new state.
async function showApplied(after, apply, label, previewBody, back) {
  for (const spin of apply.querySelectorAll(".spinner")) spin.remove();
  apply.prepend(checkMark());
  apply.classList.add("done");
  label.textContent = "Applied";
  await reloadAll();
  if (back) {
    render();
    await back({ verified: true });
  } else {
    panelState.current = null;
    closePanel({ keepSelection: true, focus: false, force: true });
    showEffect();
    restoreFocus();
  }
  setBusy(false);
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
