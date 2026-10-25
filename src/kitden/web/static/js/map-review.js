// The review bar on a map: a preview started on a map shows, applies and ends there (S.8).
import { postJson } from "./api.js";
import { clientName } from "./details.js";
import { $, el, joinWords, reportError, withFocusKey } from "./dom.js";
import { closePanel, isPanelOpen, panelState, toast } from "./panel.js";
import { stepText } from "./parts.js";
import { afterParts, appliedToast, canShowReview, changeOutcome, changeWords, NOTHING, nothingChanged, reloadAll, setMapReview, showReview, stoppedWords } from "./review.js";
import { busy, go, render, setBusy, state } from "./store.js";

// A preview started on the map (a drag, later a marketplace result) shows there: a preview block
// and a review bar on the canvas. `phase`: "idle", "loading" (asked), "ready", "applying" or
// "failed". `body` is the preview request and `change` the server's preview; `done` and `total`
// count Apply's steps; `failure` is how Apply ended: the state and the engine's words of the
// change read back ({ state, error }), both null when none was read.
// `refused` holds the server's words when it would not prepare it. `project` is the project it
// was asked in, and `inDetails` says "Show changes" moved it into Details, where its own review
// shows it.
const IDLE = { body: null, change: null, phase: "idle", done: 0, total: 0, failure: null, refused: null, project: "", inDetails: false };
export const mapPreview = { ...IDLE };
// The newest request on the map: an answer to an older one is dropped.
let asking = 0;
// How the page draws its map again, as the last call gave it.
let redrawMap = () => {};
// The review bar the page shows now (previewBar): one preview on a map at a time, so one bar.
let shownBar = null;

const REFUSED = "Could not prepare this change";

// How the review in Details (review.js) takes turns with the preview on the map, told when the map
// asks its first preview (setMapReview): its review in Details goes back with `mapBack`, a review
// asked elsewhere makes room first, and its verified Apply there ends it.
const TURNS = { back: mapBack, makeRoom, applied: () => Object.assign(mapPreview, IDLE) };

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
// and what Apply says. While Apply runs it counts the steps and Cancel waits. An error makes the
// same "Nothing was changed." call as the review in Details (stoppedWords), without the engine's
// own words: paths and commands stay behind Details and on Changes. It offers "Try again". A
// refusal has no change, so only Cancel stays: trying again would be refused for the same reason.
export function barWords({ phase, change, body, done, total, failure, refused }) {
  if (refused) return { title: REFUSED, outcome: `${refused} ${NOTHING}`, apply: null, cancelWaits: false, retry: false };
  const title = changeWords(change, body).title;
  if (phase === "applying") return { title, outcome: writingLine(change.steps), apply: stepText("Applying", done, total), cancelWaits: true, retry: false };
  if (phase === "failed") {
    const { state: ended = null, error = null } = failure || {};
    return { title, outcome: stoppedWords(ended ? { state: ended, error } : null, null, { detail: false }), apply: "Try again", cancelWaits: false, retry: true };
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

// A review asked elsewhere (review.js) goes first: a preview on the map that is only previewed
// goes, and the map is drawn again. False while the map's change is written: nothing else is
// asked then.
function makeRoom() {
  if (mapPreview.phase === "idle") return true;
  if (mapWriting()) return false;
  dropMapPreview();
  redrawMap();
  return true;
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
// "Preview again" the server refused shows why in the bar. A verified Apply ends in showApplied
// (review.js).
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
  setMapReview(TURNS);
  if (mapWriting() || busy.change) return;
  redrawMap = redraw;
  dropMapPreview();
  // A review in Details goes first, as when other Details take its place: one that is only
  // previewed is cancelled on the server (panel.js). One being written refused this above.
  if (panelState.current && panelState.current.type === "review" && isPanelOpen()) closePanel({ focus: false });
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

// The map's review bar is on the page now (not on the List or another place).
function barShown() {
  return typeof document !== "undefined" && Boolean(document.querySelector(".review-bar"));
}

// Apply in the bar: the button counts the steps as the server reports them, the bar says what is
// written, and Cancel waits. Only `verified` ends it: the page reads everything again, the preview
// goes (its block and link fade out, the server's fade in where it belongs) and the toast offers
// Undo. Any other end stays in the bar with "Try again", focus on it, and the page reads again
// behind it. With the bar no longer on the page (the person went to the List or another place
// meanwhile), a toast with no check says the same words, with a way to Changes when the result is
// not known or not everything was put back, and the preview goes.
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
    const { after } = outcome;
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
    Object.assign(mapPreview, { phase: "failed", failure: { state: after ? after.state : null, error: (after && after.error) || null } });
    setBusy(false);
    if (barShown()) {
      redraw();
      focusBar("apply");
    } else {
      const { title, outcome } = barWords(mapPreview);
      // Changes holds the engine's own words: the way there when the result is not known or not
      // everything was put back.
      const check = !after || (after.state === "restored" && !nothingChanged(after));
      dropMapPreview();
      toast(`${title} · ${outcome}`, check ? () => go("changes") : null, check ? { label: "Open Changes" } : {});
    }
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

// The bar under a page's map ----------------------------------------------------------------

// The review bar under a map, while a preview from the map is open: not while it is prepared, nor
// while its review shows in Details. Its buttons call the page's `redraw` (see redrawPreview).
export function previewBar(redraw) {
  const { phase, change, body, inDetails } = mapPreview;
  shownBar = null;
  if (phase === "idle" || phase === "loading" || inDetails) return null;
  shownBar = reviewBar(change, {
    body,
    onApply: () => (mapPreview.phase === "failed" ? previewOnMap(mapPreview.body, redraw) : applyOnMap(redraw)).catch(reportError),
    onCancel: () => cancelOnMap(redraw).catch(reportError),
    onShow: () => showMapReview(redraw),
  });
  return shownBar;
}

// The page drawn again for a preview on its map: the page's own `redraw` calls this. What only the
// bar shows (Apply's steps, an error after Apply) changes in the bar itself while the map shows the
// same as when it was drawn (`same`), so its status line is read out; anything else draws the page.
// A preview that ended gives focus to the first of `ended` (the ids of the blocks where it may be
// now) on the page, when focus was in the bar, in Details that closed, or nowhere.
export function redrawPreview(redraw, { same, ended = [] }) {
  const old = shownBar;
  if (same && old && old.isConnected) {
    swapBar(old, previewBar(redraw));
    return;
  }
  const active = document.activeElement;
  const closed = !isPanelOpen() && $("#drawer").contains(active);
  const lost = !active || [document.body, $("#main")].includes(active) || closed || Boolean(old && old.contains(active));
  render();
  if (!ended.length || !lost) return;
  const node = ended.map((id) => withFocusKey($("#main"), `block:${id}`)).find(Boolean);
  if (node) node.focus({ preventScroll: true });
}

// Put the new bar's words and buttons into the bar shown. Its status line stays the same node, so
// a screen reader hears the new words; focus stays on the same button.
function swapBar(old, fresh) {
  shownBar = fresh ? old : null;
  if (!fresh) {
    old.remove();
    return;
  }
  const had = old.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
  old.className = fresh.className;
  old.setAttribute("aria-label", fresh.getAttribute("aria-label"));
  const [words, actions] = old.children;
  const [newWords, newActions] = fresh.children;
  words.firstElementChild.replaceWith(newWords.firstElementChild);
  const said = newWords.lastElementChild.textContent;
  if (words.lastElementChild.textContent !== said) words.lastElementChild.textContent = said;
  actions.replaceWith(newActions);
  const again = had ? withFocusKey(old, had) : null;
  if (again) again.focus({ preventScroll: true });
}
