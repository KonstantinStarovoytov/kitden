// The amber strips at the top of every page: a client that must be restarted so it sees an Apply
// (spec 2026-11-11, "Restart needed after an Apply"). One strip for each client, with the
// client's own note and "Got it". There is no Restart button: the person restarts the client.
// GET /api/restarts says which clients still run from before the Apply. The page asks on load,
// when a change ends and after Rescan, not on a timer. "Got it" hides that client's strip for
// that change in localStorage; without storage it hides it until the page loads again.
import { getJson } from "./api.js";
import { $, button, el, icon } from "./dom.js";
import { animateTo } from "./motion.js";
import { onBusy, busy } from "./store.js";

export const SEEN_KEY = "kitden-restarts-got-it";
const KEEP = 50; // the newest keys kept

// A strip is one client's note for one change: a change that reaches two clients has two.
export const stripKey = (strip) => `${strip.change}:${strip.client}`;

// The keys of the strips that were got, from `storage` (the page's localStorage).
export function seenIds(storage = globalThis.localStorage) {
  try {
    const list = JSON.parse(storage.getItem(SEEN_KEY));
    return new Set(Array.isArray(list) ? list : []);
  } catch {
    return new Set(); // no storage, or a damaged list
  }
}

// Keeps the strip's key as got. Storage that fails is only a strip that comes back on reload.
export function gotIt(key, storage = globalThis.localStorage) {
  const keys = [...seenIds(storage)].filter((id) => id !== key);
  try {
    storage.setItem(SEEN_KEY, JSON.stringify([...keys, key].slice(-KEEP)));
  } catch { /* the strip is hidden for this visit only */ }
}

// The strips to draw: those not got.
export function shownStrips(list, seen) {
  return list.filter((strip) => !seen.has(stripKey(strip)));
}

let box = null;
let list = [];
let asked = 0;
const hiddenNow = new Set(); // got it, and storage may not have kept it

function stripNode(strip) {
  const node = el("div", "restart-strip");
  node.setAttribute("role", "note");
  node.dataset.key = stripKey(strip);
  const mark = icon("triangle-alert", 16);
  mark.setAttribute("aria-hidden", "true");
  const got = button("Got it", () => {
    gotIt(stripKey(strip));
    hiddenNow.add(stripKey(strip));
    const focused = node.contains(document.activeElement);
    draw();
    if (focused) $("#main").focus({ preventScroll: true });
  }, "btn ghost small");
  got.setAttribute("aria-label", `Got it: ${strip.note}`);
  node.append(mark, el("span", "restart-note", strip.note), got);
  return node;
}

// Draws `list` again. A strip that stays is kept as it is; a new one fades in and a gone one
// fades out.
function draw() {
  if (!box) return;
  const seen = seenIds();
  const wanted = shownStrips(list, seen).filter((strip) => !hiddenNow.has(stripKey(strip)));
  const keys = new Set(wanted.map(stripKey));
  for (const node of [...box.children]) {
    if (node.leaving || keys.has(node.dataset.key)) continue;
    node.leaving = true;
    animateTo(node, [{ opacity: 1 }, { opacity: 0 }], { dur: 160, ease: "ease-in", fill: "forwards" }).then(() => node.remove());
  }
  for (const strip of wanted) {
    const there = [...box.children].find((node) => node.dataset.key === stripKey(strip) && !node.leaving);
    if (there) continue;
    const node = stripNode(strip);
    box.append(node);
    animateTo(node, [{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { dur: 220 });
  }
}

// Asks which clients need a restart now. A failed read leaves the strips as they are; the page
// never shows an error for it.
export async function refreshRestarts() {
  if (!box) return;
  const turn = ++asked;
  let found = null;
  try {
    found = await getJson("/api/restarts");
  } catch { /* nothing to say */ }
  if (turn !== asked || !Array.isArray(found)) return;
  list = found;
  draw();
}

export function startRestarts(node) {
  box = node;
  refreshRestarts();
  // A change ends (Apply or Undo): the log has its line by then.
  onBusy(() => { if (!busy.change) refreshRestarts(); });
}
