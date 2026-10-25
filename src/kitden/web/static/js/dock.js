// The preview tray's bar, in the dock at the bottom left of the page: one change, or a list of them,
// with Cancel and Apply. tray.js holds the state and talks to the server; this module draws it. The
// toast (toast.js) stands in the same dock: the bar and the toast take turns.
import { clientName } from "./details.js";
import { $, button, el, icon, joinWords, reportError, withFocusKey } from "./dom.js";
import { animateTo, D, DRAW, rollTo, shake } from "./motion.js";
import { closePanel, isPanelOpen, panelState } from "./panel.js";
import { stepText } from "./parts.js";
import { afterParts, changeWords, detailsAgain, nothingChanged, reloadAll, showEffect, showRowReview, undoChange } from "./review.js";
import { go, state } from "./store.js";
import { hideToast, makeRoom, onToastGone, say, toast } from "./toast.js";
import { applyTray, cancelTray, endApplied, onTray, setTrayWords, takeOut, tray, tryAgain } from "./tray.js";

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

// A row's words, from its own part of the preview: the title of the change, then what it will do
// (or the note the caller gave it).
export function rowWords(part, body, note) {
  return { title: changeWords(part, body).title, detail: outcomeLine(part) || note || "" };
}

// A reason from the engine may name a file by its full path ("/Users/me/.cursor/mcp.json", or one
// under "~/"). The bar and its spoken words name the file only ("mcp.json"); the full words stay on
// Changes.
export function baseNames(text) {
  return String(text).replace(/(^|[\s"'(`])(~?\/[^\s"'`)]+)/g, (whole, lead, path) => lead + (path.split("/").filter(Boolean).at(-1) || path));
}

const STALE = "Settings changed since this preview.";
const CHECK_CHANGES = "Check Changes before trying again.";
const IN_PREVIEW = " changes in preview";

// How a tray that did not go through ends: the head and line, and what Apply's place holds.
// "Nothing was changed" only when that is true (nothingChanged, review.js); the engine's own words
// name paths and commands, so they stay behind Details and on Changes.
function endWords({ failure, refused }, reason) {
  if (refused) return { head: "Could not prepare the preview", line: reason, apply: "Try again", retry: true };
  const { state: ended = null, error = null } = failure || {};
  if (nothingChanged({ state: ended, error })) {
    return { head: "Nothing was changed", line: ended === "stale" ? STALE : "The change did not check out. Kitden put the files back.", apply: "Try again", retry: true };
  }
  return { head: ended === "restored" ? "Not everything was put back" : "Could not confirm the result", line: CHECK_CHANGES, apply: null, changes: true };
}

// The bar's words for a tray whose rows all have words (`t.rows`; drawTray leaves out a row still
// being asked). `retry`: Apply's place holds Try again or Preview again. `changes`: the bar also
// offers Open Changes. `applyWaits`: Apply takes no press yet (a preview is on its way, or the
// change is being written or was applied). With no rows and a refusal the bar only says why.
export function barWords(t, { onMap = false } = {}) {
  const count = t.rows.length;
  const base = { applyWaits: false, retry: false, changes: false };
  const reason = t.refused ? baseNames(t.refused.reason) : "";
  if (!count) return { head: "Could not prepare this change", line: reason, cancel: "Close", apply: null, ...base };
  const many = count > 1;
  const words = {
    head: many ? `${count}${IN_PREVIEW}` : t.rows[0].title,
    line: many ? `Nothing is written until you Apply.${onMap ? " Click one on the map to take it out." : ""}` : t.rows[0].detail,
    cancel: many ? "Cancel all" : "Cancel",
    apply: many ? "Apply all" : "Apply",
    ...base,
  };
  if (t.phase === "asking") words.applyWaits = true;
  else if (t.phase === "ready" && t.stale) Object.assign(words, { line: STALE, apply: "Preview again", retry: true });
  else if (t.phase === "applying") Object.assign(words, { line: writingLine(t.change.steps), apply: stepText("Applying", t.done, t.total), applyWaits: true });
  else if (t.phase === "applied") Object.assign(words, { apply: many ? "All applied" : "Applied", applyWaits: true });
  else if (t.phase === "failed") Object.assign(words, endWords(t, reason));
  // A refused add: the tray stands as it was, and the reason takes the line.
  if (t.refused && t.phase !== "failed") words.line = reason;
  return words;
}

// The toast after a verified Apply: `done` is { change, rows }, kept before the tray emptied. One
// change says its own words and offers Undo; many say how many and offer Undo all, which undoes
// the one combined change.
export function appliedToast({ change, rows }) {
  if (!rows.length) return;
  const many = rows.length > 1;
  const text = many ? `Applied ${rows.length} changes` : changeWords(rows[0].part, rows[0].body).done;
  toast(text, () => undoChange(change), { ok: true, label: many ? "Undo all" : "Undo" });
}

// The bar on the page ---------------------------------------------------------------------------

let host = null;
// The bar on the page now, and what it shows: { sig, kind, words, status, head, num, cancel, apply,
// label, icon, iconKind, meter, ratio, changes, show, list, rows } (`rows`: key -> its parts).
let bar = null;
let shown = null;
// The bar on its way out, so a new one can take its place at once.
let leaving = null;
// The timer while rows slide out, and the size the bar had before they went.
let sliding = null;
let carried = null;
// The bar's size animation, while it runs.
let growing = null;
// The refusal or failure the bar last answered with a shake, so each is answered once.
let reacted = null;

const later = (fn, ms) => (ms > 0 ? setTimeout(fn, ms) : fn());
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const set = (node, text) => { if (node.textContent !== text) node.textContent = text; };

// A button that runs `run` and reports an error. `key` is its data-focus, so a redraw can give it
// focus back.
function wire(node, key, run) {
  node.type = "button";
  node.dataset.focus = key;
  node.addEventListener("click", () => Promise.resolve(run(node)).catch(reportError));
  return node;
}

function textButton(label, className, key, run) {
  return wire(button(label, null, className), key, run);
}

function iconButton(name, label, className, key, run) {
  const node = wire(el("button", className), key, run);
  node.setAttribute("aria-label", label);
  node.title = label;
  node.append(icon(name, 13));
  return node;
}

// The kinds of bar: "one" change, "many" (a list), or a "refusal" that has no rows to show. The
// head of a list counts ("3 changes in preview") except while it tells how an Apply or a preview ended.
const counting = (view) => view.kind === "many" && view.t.phase !== "failed";
// What the bar is built of; when it changes the bar is built again, else its parts are updated.
const sigOf = (view) => [view.kind, counting(view), view.words.apply !== null, view.words.changes].join("|");

// The arrow, the spinner or the check: the icon in Apply's place.
const APPLY_ICONS = { "arrow-right": ["arrow-right", "ic"], again: ["rotate-cw", "ic"], spin: ["rotate-cw", "ic spin"], check: ["check", "ic"] };

function applyButton() {
  const node = textButton("", "btn primary apply", "tray:apply", onApply);
  const label = el("span", "lbl");
  const meter = el("i", "meter");
  meter.setAttribute("aria-hidden", "true");
  const mark = icon("arrow-right", 14);
  node.append(label, mark, meter);
  return { node, label, mark, meter };
}

// The parts of a bar of this kind, empty. `status` is the line from the bar before, if there is
// one: the same node keeps its place, so a screen reader hears the new words. `startCount` is the
// number the head shows first (the old count, so it can roll to the new one).
function build(view, status, startCount) {
  const { kind, words } = view;
  const item = { sig: sigOf(view), kind, words, rows: new Map(), ratio: 0, iconKind: "arrow-right" };
  item.status = status || el("small");
  item.status.setAttribute("role", "status");
  item.head = el("b");
  if (counting(view)) {
    item.num = el("span", "num roll");
    item.num.append(el("span", null, String(startCount)));
    item.head.append(item.num, IN_PREVIEW);
  }
  const acts = el("div", "acts");
  item.cancel = textButton(words.cancel, "btn", "tray:cancel", () => cancelTray());
  acts.append(item.cancel);
  if (words.changes) {
    item.changes = textButton("Open Changes", "btn primary", "tray:changes", () => go("changes"));
    acts.append(item.changes);
  }
  if (words.apply !== null) {
    const made = applyButton();
    Object.assign(item, { apply: made.node, label: made.label, mark: made.mark, meter: made.meter });
    acts.append(made.node);
  }
  const top = el("div", kind === "many" ? "tray-head" : "tx");
  top.append(item.head, item.status);
  if (kind === "one") {
    // The row is looked for when pressed: the only one that has its words.
    item.show = textButton("Show changes", "btn ghost small", "tray:show", () => showRowReview(tray.rows.find((row) => row.part)));
    top.append(item.show);
  }
  if (kind === "many") {
    item.list = el("ul", "tray-list");
    bar.replaceChildren(top, item.list, acts);
  } else {
    bar.replaceChildren(top, acts);
  }
  return item;
}

// One row of the list: its icon, words, "Show changes", status and ×.
function makeRow(row) {
  const li = el("li");
  li.dataset.key = row.key;
  const lead = el("span", "ti");
  lead.append(icon(row.icon, 13));
  const title = el("b");
  const detail = el("small");
  const words = el("span", "tt");
  words.append(title, detail);
  const show = iconButton("file-text", "", "ib", `tray:show:${row.key}`, () => {
    const found = tray.rows.find((candidate) => candidate.key === row.key);
    if (found && found.part) showRowReview(found);
  });
  const mark = el("span", "ts");
  const out = iconButton("x", "Take it out of the preview", "x", `tray:x:${row.key}`, () => takeOut(row.key));
  li.append(lead, words, show, mark, out);
  return { li, title, detail, show, mark, out, status: "" };
}

// A row spins while its step is written, and shows a green check once the whole change checked out.
function setRowStatus(item, status) {
  if (item.status === status) return;
  item.status = status;
  item.mark.replaceChildren(...(status === "busy" ? [icon("rotate-cw", 12, "ic spin")] : status === "done" ? [icon("check", 12, "ic ok")] : []));
}

function patchRows(view, known, animate) {
  const working = view.t.phase === "applying" || view.t.phase === "applied";
  for (const row of view.rows) {
    let item = shown.rows.get(row.key);
    if (!item) {
      item = makeRow(row);
      shown.rows.set(row.key, item);
      shown.list.append(item.li);
      if (animate && !known.has(row.key)) {
        animateTo(item.li, [{ opacity: 0, transform: "translateY(10px) scale(.98)" }, { opacity: 1, transform: "none" }], { dur: 200, delay: 80 });
      }
    }
    set(item.title, row.title);
    set(item.detail, row.detail);
    const label = `Show changes: ${row.title}`;
    if (item.show.getAttribute("aria-label") !== label) {
      item.show.setAttribute("aria-label", label);
      item.show.title = label;
    }
    item.out.disabled = working;
    setRowStatus(item, row.status);
  }
}

// The icon in Apply's place; a check draws itself in.
function setApplyIcon(kind) {
  if (shown.iconKind === kind) return;
  const [name, look] = APPLY_ICONS[kind];
  const next = icon(name, 14, look);
  shown.mark.replaceWith(next);
  Object.assign(shown, { mark: next, iconKind: kind });
  if (kind === "check" && next.firstElementChild) {
    animateTo(next.firstElementChild, [{ strokeDashoffset: 24 }, { strokeDashoffset: 0 }], { dur: 300, ease: DRAW });
  }
}

// The meter along Apply's bottom edge shows the share of steps done. It lands on that share at
// once (the style), and glides there when it grows.
function setMeter(ratio) {
  const from = shown.ratio;
  if (ratio === from) return;
  shown.ratio = ratio;
  shown.meter.style.transform = ratio ? `scaleX(${ratio})` : "";
  if (ratio > from) animateTo(shown.meter, [{ transform: `scaleX(${from})` }, { transform: `scaleX(${ratio})` }], { dur: 480, ease: "ease-out" });
}

function patchApply(view) {
  const { t, words } = view;
  const applied = t.phase === "applied";
  const { apply } = shown;
  apply.classList.toggle("primary", !applied);
  apply.classList.toggle("ok", applied);
  set(shown.label, words.apply);
  if (words.applyWaits) apply.setAttribute("aria-disabled", "true");
  else apply.removeAttribute("aria-disabled");
  setApplyIcon(applied ? "check" : t.phase === "applying" ? "spin" : words.retry ? "again" : "arrow-right");
  setMeter(applied ? 1 : t.phase === "applying" && t.total > 0 ? t.done / t.total : 0);
}

// Put the words and states of `view` into the parts of the bar. `known`: the rows that were drawn
// before (they do not enter again).
function patch(view, { known = new Set(), animate = true } = {}) {
  const { t, kind, words } = view;
  shown.words = words;
  bar.classList.toggle("many", kind === "many");
  bar.classList.toggle("err", t.phase === "failed" || kind === "refusal");
  bar.setAttribute("aria-label", words.head);
  set(shown.status, words.line);
  shown.status.classList.toggle("bad", Boolean(t.refused));
  if (shown.num) rollTo(shown.num, view.rows.length);
  else set(shown.head, words.head);
  set(shown.cancel, words.cancel);
  // Cancel, and every ×, wait while the change is written: it cannot stop halfway.
  shown.cancel.disabled = t.phase === "applying" || t.phase === "applied";
  if (shown.apply) patchApply(view);
  if (kind === "many") patchRows(view, known, animate);
}

// The bar is built of other parts now: draw it again inside the same bar, with the rows that were
// there staying quiet. Focus stays on the same button when it is still there.
function rebuild(view) {
  const known = new Set(shown.rows.keys());
  const old = shown;
  const had = bar.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
  shown = build(view, old.status, old.num ? known.size : view.rows.length);
  patch(view, { known });
  if (had) (withFocusKey(bar, had) || shown.apply || shown.cancel).focus({ preventScroll: true });
}

function enterBar(view) {
  if (leaving) leaving.remove();
  leaving = null;
  hideToast({ now: true });
  bar = el("section", "bar tray");
  bar.setAttribute("role", "region");
  host.append(bar);
  shown = build(view, null, view.rows.length);
  patch(view, { animate: false });
  // The page's room sizes itself to whatever the dock shows, the bar or a toast (makeRoom, toast.js).
  makeRoom();
  animateTo(bar, [{ opacity: 0, transform: "translateY(18px) scale(.97)" }, { opacity: 1, transform: "none" }], { dur: 220 });
  react(view, true);
}

// The page forgets the bar it drew: it left, or a toast took its place.
function forgetBar() {
  bar = null;
  shown = null;
  growing = null;
  reacted = null;
}

// The last row out, Cancel all, or an Apply taken in: the bar goes down 10 px and fades; then it is
// removed, by time and not by the animation's end.
function leaveBar() {
  if (!bar) return;
  const old = bar;
  // Focus inside the bar goes to the page, so a keyboard user is never left on nothing.
  if (old.contains(document.activeElement)) $("#main").focus({ preventScroll: true });
  forgetBar();
  animateTo(old, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(10px)" }], { dur: 160, ease: "ease-in", fill: "forwards" });
  if (D(160) > 0) leaving = old;
  later(() => {
    old.remove();
    if (leaving === old) leaving = null;
    makeRoom();
  }, D(160));
}

// Rows taken out slide off to the right, 180 ms; the bar is drawn again once they have gone. Focus
// on one of them goes to Apply (or Cancel) first: a button that is turned off while it has focus
// loses it at once.
function slideOut(keys) {
  const items = keys.map((key) => shown.rows.get(key));
  if (items.some((item) => item.li.contains(document.activeElement))) (shown.apply || shown.cancel).focus({ preventScroll: true });
  for (const item of items) {
    item.out.disabled = true;
    item.show.disabled = true;
    animateTo(item.li, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateX(18px)" }], { dur: 180, ease: "ease-in", fill: "forwards" });
  }
  carried = bar.getBoundingClientRect();
  const finish = () => {
    sliding = null;
    dropRows(keys);
    drawTray();
  };
  if (D(180) > 0) sliding = setTimeout(finish, D(180));
  else finish();
}

function dropRows(keys) {
  for (const key of keys) {
    const item = shown.rows.get(key);
    if (!item) continue;
    item.li.remove();
    shown.rows.delete(key);
  }
}

// The bar grows or shrinks from the size it had (`before`, as it showed, maybe mid-animation) to
// its new one, and the page's room follows its new size. A size animation still running is
// cancelled first: while it runs the browser reports its height, not the bar's own.
function resize(before) {
  if (growing) growing.cancel();
  growing = null;
  const now = bar.getBoundingClientRect();
  makeRoom();
  if (Math.abs(before.height - now.height) < 1 && Math.abs(before.width - now.width) < 1) return;
  const running = bar.getAnimations ? bar.getAnimations().length : 0;
  animateTo(bar, [{ height: `${before.height}px`, width: `${before.width}px` }, { height: `${now.height}px`, width: `${now.width}px` }], { dur: 200 });
  if (bar.getAnimations && bar.getAnimations().length > running) growing = bar.getAnimations().at(-1);
}

// A refusal or a failure is answered once: the bar shakes, and after a failure focus goes to Try
// again (or Open Changes when there is no Try again). A first refused add (no bar before) comes in
// with the bar's entrance and does not shake: one motion per change. A refusal on a bar that is
// already shown shakes it.
function react(view, fresh) {
  const { t } = view;
  const end = t.refused || (t.phase === "failed" ? t.failure : null);
  if (end && end !== reacted && !fresh) {
    shake(bar);
    if (t.phase === "failed") (shown.apply || shown.changes || shown.cancel).focus({ preventScroll: true });
  }
  reacted = end;
}

// A row's review in Details goes with its row. True when focus was in Details: it is handed on.
function closeRowReview(t) {
  const open = panelState.current;
  if (!open || open.type !== "row-review" || !isPanelOpen() || t.rows.some((row) => row.key === open.row.key)) return false;
  const inside = $("#drawer").contains(document.activeElement);
  closePanel({ focus: false });
  return inside;
}

// "Click one on the map to take it out." only while the Gateway shows its map, not its List.
const onTheMap = () => state.view === "gateway" && Boolean($("#main .map"));

// Draw the tray: the rows with words (one still being asked is not drawn), as one change, a list, or
// only the reason a first add was refused. No rows and no refusal: no bar. Called after every change
// of the tray, so it only updates what changed. `toastStays`: only a bar on the page is updated, and
// a toast keeps the dock (the bar comes back, as it is then, when the toast has gone): for a redraw
// of the page (app.js) and for a mark the tray gets by itself. A row's review that had focus closes
// with its row; focus goes to Apply (or Cancel), or to the page when the bar goes, as when a row's
// × had it.
export function drawTray(t = tray, { toastStays = false } = {}) {
  if (toastStays && !(bar && bar.isConnected)) return;
  const handOn = closeRowReview(t);
  drawBar(t);
  if (handOn) ((shown && (shown.apply || shown.cancel)) || $("#main")).focus({ preventScroll: true });
}

function drawBar(t) {
  const rows = t.rows.filter((row) => row.part);
  const kind = rows.length > 1 ? "many" : rows.length ? "one" : t.refused ? "refusal" : null;
  if (!kind) {
    clearTimeout(sliding);
    sliding = null;
    carried = null;
    leaveBar();
    return;
  }
  // Rows are sliding out: the bar is drawn once they have gone.
  if (sliding) return;
  // A toast took the dock's place while the tray still had rows: the bar is drawn again, and it
  // takes the place of the toast.
  if (bar && !bar.isConnected) forgetBar();
  const view = { t, rows, kind, words: barWords({ ...t, rows }, { onMap: onTheMap() }) };
  if (!bar) {
    enterBar(view);
    return;
  }
  const gone = shown.kind === "many" ? [...shown.rows.keys()].filter((key) => !rows.some((row) => row.key === key)) : [];
  if (gone.length) {
    slideOut(gone);
    return;
  }
  const before = carried || bar.getBoundingClientRect();
  carried = null;
  if (sigOf(view) !== shown.sig) rebuild(view);
  else patch(view);
  resize(before);
  react(view, false);
}

// Apply writes the tray; Try again and Preview again ask for a fresh preview. A press does nothing
// while Apply waits.
async function onApply() {
  const { apply, words } = shown;
  if (apply.getAttribute("aria-disabled") === "true") return;
  if (words.retry) {
    await tryAgain();
    return;
  }
  await applyTray();
  if (tray.phase === "applied") await land();
}

// Apply is verified: the Applied look rests 200 ms, the page reads everything again and shows the
// effect, open Details are drawn again with it, the tray empties (the bar leaves, and a row's
// review with it), and the toast takes its place after 60 ms a change.
async function land() {
  await wait(D(200));
  try {
    await reloadAll();
    showEffect();
    await detailsAgain(tray.rows.map((row) => row.key));
  } catch (error) {
    reportError(error);
  }
  const kept = { change: tray.change, rows: [...tray.rows] };
  endApplied();
  later(() => appliedToast(kept), D(kept.rows.length * 60));
}

// What a screen reader was last told of the tray: its rows with words (key -> title), its phase,
// and the refusal.
let told = { rows: new Map(), phase: "idle", refused: null };

// How the tray changed, in words for a screen reader, or "": each row that joined ("…: in the
// preview.", and the count from two on), the rows taken out, and why an add was refused when the
// bar came in with the reason (`had`: a bar was on the page, and its line, a status, says it).
// A tray that empties after Apply says nothing: the toast says it.
function trayNews(t, had) {
  const rows = t.rows.filter((row) => row.part);
  const keys = new Set(t.rows.map((row) => row.key));
  const gone = [...told.rows].filter(([key]) => !keys.has(key)).map(([, title]) => title);
  const joined = t.phase === "ready" ? rows.filter((row) => !told.rows.has(row.key)) : [];
  const news = [];
  if (gone.length && told.phase !== "applied") news.push(gone.length > 1 ? `${gone.length} changes taken out of the preview.` : `${gone[0]}: taken out of the preview.`);
  for (const row of joined) news.push(`${row.title}: in the preview.`);
  if (joined.length && rows.length > 1) news.push(`${rows.length}${IN_PREVIEW}.`);
  if (t.refused && t.refused !== told.refused && !had) {
    news.push(`${t.phase === "failed" ? "Could not prepare the preview" : "Could not prepare this change"}. ${baseNames(t.refused.reason)}`);
  }
  told = { rows: new Map(rows.map((row) => [row.key, row.title])), phase: t.phase, refused: t.refused };
  return news.join(" ");
}

// The rows and phase of the tray as last drawn. A change of either (an add, a take-out, Cancel or
// Apply, and their answers) takes the dock from a toast; a mark the tray gets by itself (a stale
// preview, a step's count) waits until the toast has gone.
let drawn = "";

// Every change of the tray: the bar is drawn, then a screen reader hears what changed, through the
// page's quiet live region (toast.js). The bar comes first: one that takes the dock from a toast
// empties the region.
function trayChanged(t) {
  const had = Boolean(bar && bar.isConnected);
  const now = JSON.stringify([t.phase, t.rows.map((row) => row.key)]);
  drawTray(t, { toastStays: now === drawn });
  drawn = now;
  const news = trayNews(t, had);
  if (news) say(news);
}

export function initDock() {
  host = $("#dock");
  setTrayWords(rowWords);
  onTray(trayChanged);
  // A toast that goes by itself leaves the dock empty: a tray that still has rows draws its bar.
  onToastGone(drawTray);
  // A narrower window can wrap the bar's words, so its height changes; makeRoom (toast.js) sizes
  // the page's room for whatever the dock shows.
  if (typeof addEventListener === "function") addEventListener("resize", makeRoom);
}
