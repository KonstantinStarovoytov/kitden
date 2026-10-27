// Changes: every change made from this page, newest first, as a timeline by day (the mockup's
// Changes, docs/mockup/overview-changes-notes.md §4–§7). A row shows the time, the title, the
// clients, the state and Undo; a press opens the change's Details beside the list. Undo is
// today's Undo (review.js); Redo… only adds a fresh preview to the tray. Paths, backups and
// commands are only under Technical details.
import { detailsCard, keepFrom, showInPreview, technical } from "./details.js";
import { button, el, icon, joinWords, plural } from "./dom.js";
import { loadLibraryFor } from "./library.js";
import { animateTo, D, rise, riseHead, rollTo, STRIKE } from "./motion.js";
import { floatsAt, loadPanel, openPanel, panelState, redoChange, redoStands, undoChange } from "./panel.js";
import { ALL_PROJECTS, backupNote, banner, changeTitle, CLIENT_NAMES, failedWord, kitdenHouse, mark, setHint, skeleton } from "./parts.js";
import { data, goTo, libraryChoice, parseSel, retry } from "./store.js";
import { keyFor } from "./tray.js";

const LEDE = "Every change made from this page. Each one has a backup; Undo puts the previous file back.";
const HINT = "Click a row · Undo · See it on the map";
const GONE = "This item is no longer there.";
const NOTHING_TO_DO = "Nothing to do";
const KITDEN = "Kitden gateway";

// The state a change ended in (views/changes_view.py), in words. Nothing logs a cancel, so there
// is no Cancelled. A failed change says whether it was put back (failedWord).
const WORDS = {
  verified: "Applied",
  undone: "Undone",
  stale: "Not applied: the file changed first",
  undo_blocked: "Can't undo: the file changed after this",
};
// States that need you: an amber lamp and phrase. An undone change is grey.
const AMBER = ["stale", "restored", "undo_blocked"];
// What the history says for each point; any other state says its word.
const HISTORY = { previewed: ["Preview"], verified: ["Applied", "Checked"], stale: ["Stopped: the file changed first"] };

const stateWord = (state, error) => (state === "restored" ? failedWord(error) : WORDS[state] || state);
const lampLook = (state) => (state === "verified" ? "lamp on" : AMBER.includes(state) ? "lamp warn" : "lamp");
const factWord = (entry) => (entry.state === "verified" ? "Applied and checked" : stateWord(entry.state, entry.technical.error));

// The backup in words that are true for the state: the server's `backup` says where the backup
// is, and the state says what Undo can do with it.
export function backupWords({ state, backup }) {
  if (backup === "back") return "Back in place";
  if (backup === "none") return "None, nothing was written";
  if (state === "verified") return "Kept · Undo puts it back";
  if (state === "undo_blocked") return "Kept · Undo can't put it back: the file changed after this";
  return "Kept · not everything was put back";
}

// A date as "2026-10-27" in local time, as the server gives a change's `day`.
const pad = (n) => String(n).padStart(2, "0");
const localDay = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

// "Today", "Yesterday", then a short date in the person's language ("Mon 19 Oct"; another year
// names it). `locale` is for a test; the page uses the browser's.
export function dayWords(day, now = new Date(), locale = undefined) {
  if (!day) return "Earlier";
  if (day === localDay(now)) return "Today";
  const before = new Date(now);
  before.setDate(before.getDate() - 1);
  if (day === localDay(before)) return "Yesterday";
  const [year, month, date] = day.split("-").map(Number);
  const words = { weekday: "short", day: "numeric", month: "short" };
  if (year !== now.getFullYear()) words.year = "numeric";
  return new Date(year, month - 1, date).toLocaleDateString(locale, words);
}

// How many changes were made since Monday of this week.
export function weekCount(entries, now = new Date()) {
  const monday = new Date(now);
  monday.setDate(monday.getDate() - ((monday.getDay() + 6) % 7));
  const since = localDay(monday);
  return entries.filter((e) => e.day && e.day >= since).length;
}

function clock(time) {
  const date = new Date(time);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// What the page drew last, across draws: the selected change, each change's state (`shown`), the
// rows in page order and each row's parts that move. `drew`: the last draw had the changes.
const page = { selected: null, shown: new Map(), rows: [], parts: new Map(), drew: false };

export function renderChanges(main, { again = false } = {}) {
  const head = el("h1", null, "Changes");
  main.append(head);
  if (!again) page.drew = false;
  const entries = data.changes;
  setHint(entries ? HINT : "");
  if (!entries) {
    page.drew = false;
    main.append(data.errors.changes ? banner("the changes", retry) : skeleton("card", 2));
    riseHead(head, null, null, { again });
    return;
  }
  const lede = el("p", "lede", LEDE);
  const scope = el("p", "scope-bar");
  scope.append(icon("layers", 14), el("span", null, `All projects · ${plural(weekCount(entries), "change", "changes")} this week`));
  main.append(lede, scope);
  riseHead(head, lede, scope, { again });
  if (!entries.length) {
    const box = el("div", "empty");
    box.append(el("strong", null, "No changes yet"), el("p", null, "Changes you make on this page show up here, each with Undo."));
    main.append(box);
    page.shown = new Map();
    return;
  }
  const fresh = !page.drew;
  if (fresh || !entries.some((e) => e.id === page.selected)) page.selected = entries[0].id;
  const before = page.shown;
  const { node, order } = timeline(entries);
  main.append(node);
  if (fresh) rise(order, { step: 40 });
  else for (const entry of entries) moveRow(entry, before.get(entry.id));
  page.shown = new Map(entries.map((e) => [e.id, e.state]));
  page.drew = true;
  // On the way in the first change's Details open beside the list, where they float; a narrow
  // window would cover the page with the drawer, so it only selects the row.
  if (fresh && floatsAt("changes", innerWidth)) openFirst(entries[0]);
}

// The first Details open without taking focus from where it is (the rail link that opened Changes).
function openFirst(entry) {
  const active = document.activeElement;
  showChange(entry);
  if (active && active !== document.body && active.isConnected) active.focus({ preventScroll: true });
}

// The days, newest first: a label, then its rows on a rail. `order` is what rises on the way in.
function timeline(entries) {
  const box = el("div", "tl");
  const order = [];
  const days = new Map();
  for (const entry of entries) {
    const key = entry.day || "";
    if (!days.has(key)) days.set(key, []);
    days.get(key).push(entry);
  }
  page.rows = [];
  page.parts = new Map();
  let count = 0;
  for (const [day, group] of days) {
    const section = el("section", "tl-day");
    const label = el("p", "day", dayWords(day));
    label.id = `changes-day-${(count += 1)}`;
    const rows = el("div", "rows");
    const rail = el("i", "rail-line");
    rail.setAttribute("aria-hidden", "true");
    const list = el("ul", "row-list");
    list.setAttribute("aria-labelledby", label.id);
    order.push(label);
    for (const entry of group) {
      const parts = changeRow(entry);
      page.rows.push(parts.node);
      page.parts.set(entry.id, parts);
      list.append(parts.node);
      order.push(parts.node);
    }
    rows.append(rail, list);
    section.append(label, rows);
    box.append(section);
  }
  return { node: box, order };
}

// A row: its dot on the rail, the time, the title (with the strike an Undo draws), the client
// tiles, the lamp and state word, and Undo on an applied change.
function changeRow(entry) {
  const node = el("li", entry.state === "undone" ? "row undone" : "row");
  node.dataset.change = entry.id;
  node.dataset.focus = `change:${entry.id}`;
  node.setAttribute("tabindex", "0");
  const dot = el("i", "dot");
  dot.setAttribute("aria-hidden", "true");
  const title = el("span", "t");
  const strike = el("i", "strike");
  strike.setAttribute("aria-hidden", "true");
  title.append(el("span", null, changeTitle(entry.title_parts)), strike);
  const state = el("span", AMBER.includes(entry.state) ? "state warn" : "state");
  const lamp = lampNode(entry.state);
  const words = el("span", "sw roll");
  words.append(el("span", null, stateWord(entry.state, entry.technical.error)));
  state.append(lamp, words);
  const act = el("span", "act");
  if (entry.state === "verified") act.append(undoButton(entry));
  node.append(dot, el("span", "time", clock(entry.time)), title, clientTiles(entry.clients, "who"), el("span", "sr-only", clientWords(entry.clients)), state, act, el("span", "sr-only", "Open details"));
  showSelected(node, entry.id === page.selected);
  node.addEventListener("click", (event) => {
    if (event.target && event.target.closest && event.target.closest("button")) return;
    select(entry.id);
  });
  node.addEventListener("keydown", (event) => onKey(event, node, entry.id));
  return { node, strike, lamp, words, act };
}

// Enter and Space open a row; the arrows move to the row above or below.
function onKey(event, node, id) {
  if (event.target !== node) return;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    select(id);
  } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const next = page.rows[page.rows.indexOf(node) + (event.key === "ArrowDown" ? 1 : -1)];
    if (next) next.focus();
  }
}

function lampNode(state) {
  const node = el("span", lampLook(state));
  node.setAttribute("aria-hidden", "true");
  return node;
}

// The clients a change reached, as 20 px tiles; a change of Kitden's own settings only shows the
// Kitden gateway's mark.
function clientTiles(clients, className) {
  const box = el("span", className);
  box.append(...(clients.length ? clients.map((c) => mark(c)) : [kitdenMark()]));
  return box;
}

function kitdenMark() {
  const node = el("span", "client-mark kitden-mark");
  node.title = KITDEN;
  node.setAttribute("aria-hidden", "true");
  node.append(kitdenHouse());
  return node;
}

// The tiles are hidden from a screen reader, so a row says their names: "Claude Code and Codex",
// or the Kitden gateway.
const clientWords = (clients) => (clients.length ? joinWords(clients.map((c) => CLIENT_NAMES[c] || c)) : KITDEN);

function undoButton(entry) {
  const node = button(null, () => undoFromRow(entry, node));
  node.append(icon("undo-2", 13), el("span", null, "Undo"));
  node.dataset.focus = `undo:${entry.id}`;
  return node;
}

// Undo from a row. The page draws again from the files; focus that was on the button, which is
// gone then, goes to its row.
async function undoFromRow(entry, node) {
  const had = document.activeElement === node;
  await undoChange(entry);
  const parts = page.parts.get(entry.id);
  const active = document.activeElement;
  if (had && parts && (!active || active === document.body || !active.isConnected)) parts.node.focus({ preventScroll: true });
}

function showSelected(node, on) {
  node.classList.toggle("selected", on);
  if (on) node.setAttribute("aria-current", "true");
  else node.removeAttribute("aria-current");
}

function select(id) {
  const entry = (data.changes || []).find((e) => e.id === id);
  if (!entry) return;
  page.selected = id;
  for (const row of page.rows) showSelected(row, row.dataset.change === id);
  showChange(entry);
}

// Motion ------------------------------------------------------------------------------------

// A row drawn again moves what changed since the last draw: a new one comes in at the top, an
// applied one that was undone draws its Undo. Under reduced motion every row is there at once.
function moveRow(entry, was) {
  const parts = page.parts.get(entry.id);
  if (!D(1) || !parts) return;
  if (was === undefined) animateTo(parts.node, [{ opacity: 0, transform: "translateY(-8px) scale(0.98)" }, { opacity: 1, transform: "none" }], { dur: 220 });
  else if (was === "verified" && entry.state === "undone") undoMotion(parts);
}

// The Undo on its row (mockup §6): the strike draws in from the left, the lamp goes grey, the
// word rolls from Applied, and the Undo button goes out and is then removed.
function undoMotion({ strike, lamp, words, act }) {
  animateTo(strike, [{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { dur: 200, ease: STRIKE });
  fadeLamp(lamp, lampLook("verified"));
  words.replaceChildren(el("span", null, WORDS.verified));
  rollTo(words, WORDS.undone);
  const going = el("span", "btn small going");
  going.setAttribute("aria-hidden", "true");
  going.append(icon("undo-2", 13), el("span", null, "Undo"));
  act.append(going);
  animateTo(going, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "scale(0.8)" }], { dur: 180, fill: "forwards" });
  setTimeout(() => going.remove(), D(180));
}

// A lamp fades from the colour of `from` to its own in 400 ms. Both colours are read with its CSS
// transition off, which would give the old one for both.
function fadeLamp(lamp, from) {
  const look = lamp.className;
  lamp.style.transition = "none";
  lamp.className = from;
  const was = getComputedStyle(lamp).backgroundColor;
  lamp.className = look;
  const now = getComputedStyle(lamp).backgroundColor;
  lamp.style.transition = "";
  animateTo(lamp, [{ backgroundColor: was }, { backgroundColor: now }], { dur: 400, ease: "ease" });
}

// Details ------------------------------------------------------------------------------------

// A change's Details beside the list: a skeleton first where they float, then the card.
function showChange(entry) {
  loadPanel("Change");
  drawChange(entry.id);
}

// The card from the change as the page has it now; drawn again after Apply all or an Undo.
function drawChange(id) {
  const entry = (data.changes || []).find((e) => e.id === id);
  if (!entry) return;
  panelState.current = { type: "change", id };
  const content = changeCard(entry);
  openPanel(content);
  keepFrom(() => drawChange(id), content);
}

// The kind and title with the day and time under it, the facts, every tray row's title when there
// were several, the backup's secret note, the actions, and the paths under Technical details.
export function changeCard(entry) {
  const status = el("p", "gone-note");
  status.setAttribute("role", "status");
  const tech = techRowsOf(entry.technical);
  return detailsCard({
    kind: "Change",
    title: changeTitle(entry.title_parts),
    id: `${dayWords(entry.day)} ${clock(entry.time)}`,
    facts: changeFacts(entry),
    list: rowTitles(entry.rows),
    why: backupNote(entry),
    actions: changeActions(entry, status),
    after: entry.map ? status : null,
    technical: tech.length ? technical(tech) : null,
  });
}

function changeFacts(entry) {
  return [
    { label: "Project", value: factMark(icon(entry.project ? "folder" : "layers", 13), entry.project || ALL_PROJECTS) },
    { label: "State", value: factMark(lampNode(entry.state), factWord(entry)) },
    { label: "Backup", value: backupWords(entry) },
    takesEffect(entry),
    { label: "Clients", value: clientsValue(entry.clients) },
    { label: "History", value: historyNode(entry) },
  ];
}

function factMark(lead, words) {
  const node = el("span", "fact-mark");
  node.append(lead, el("span", null, words));
  return node;
}

// Each client's restart and log-in notes, in amber, or "Nothing to do".
function takesEffect(entry) {
  const lines = entry.takes_effect.flatMap((t) => [t.note, t.login && `Log in: ${t.login}`]).filter(Boolean);
  if (!lines.length) return { label: "Takes effect", value: NOTHING_TO_DO };
  const value = el("span", "fact-lines");
  value.append(...lines.map((line) => el("span", null, line)));
  return { label: "Takes effect", value, warn: true };
}

function clientsValue(clients) {
  const node = clientTiles(clients, "fact-tiles");
  node.append(el("span", null, clients.length ? plural(clients.length, "client", "clients") : KITDEN));
  return node;
}

// Each point of the change in order, joined by arrows: "14:02 Preview → 14:02 Applied → …".
function historyNode(entry) {
  const box = el("span", "p-hist");
  const steps = entry.history.flatMap(({ time, state }) => (HISTORY[state] || [stateWord(state, entry.technical.error)]).map((word) => `${clock(time)} ${word}`));
  steps.forEach((step, index) => {
    if (index) box.append(icon("arrow-right", 11));
    box.append(el("span", null, step));
  });
  return box;
}

function rowTitles(rows) {
  if (!rows || rows.length < 2) return null;
  const list = el("ul", "p-rows");
  list.append(...rows.map((row) => el("li", null, row.title)));
  return list;
}

// Undo on an applied change, See it on the map when the change touched one item, and Redo… on an
// undone change that kept its request, while no later applied change made the same one.
function changeActions(entry, status) {
  const actions = [];
  if (entry.state === "verified") actions.push({ label: "Undo", run: () => undoChange(entry) });
  if (entry.map) actions.push({ label: "See it on the map", run: () => seeOnMap(entry.map, status) });
  if (entry.state === "undone" && redoStands(entry)) actions.push({ label: "Redo…", node: redoButton(entry) });
  return actions;
}

// Redo… adds a fresh preview of the same request to the tray; it says "In preview" while it waits.
function redoButton(entry) {
  const label = "Redo…";
  const words = el("span", "cut", label);
  const node = button(null, () => (node.getAttribute("aria-disabled") === "true" ? null : redoChange(entry)), "btn");
  node.title = label;
  node.append(words);
  node.dataset.focus = `action:${label}`;
  showInPreview(node, words, label, keyFor(entry.redo[0]));
  return node;
}

// The Gateway's map or the Library with the item the change touched selected; it opens its
// Details there. An item that is no longer there is said in Details.
async function seeOnMap({ view, sel, gone }, status) {
  const selected = parseSel(sel);
  if (gone || !selected) {
    status.textContent = GONE;
    return;
  }
  if (view === "library") {
    await loadLibraryFor(libraryChoice(selected));
    await goTo("library", selected);
  } else {
    await goTo("gateway", selected, { mode: "map" });
  }
}

// What Technical details show: the files written, the backups, the commands and the engine's
// error, which names files.
function techRowsOf({ paths, backups, commands, error }) {
  return [
    ...paths.map((path) => ({ title: "File", path })),
    ...backups.map((path) => ({ title: "Backup", path })),
    ...commands.map((summary) => ({ title: "Command", summary })),
    ...(error ? [{ title: "Error", summary: error }] : []),
  ];
}
