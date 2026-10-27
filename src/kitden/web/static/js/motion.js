// Motion helpers. Animate only where it explains a change; never slow down frequent actions.
import { el } from "./dom.js";

export const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
export const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
export const EASE_IN_OUT = "cubic-bezier(0.77, 0, 0.175, 1)";

// The motion mockup's curves. CALM is the default for Web Animations. The spring (--spring in
// style.css) is for small parts in CSS only.
export const CALM = "cubic-bezier(.2,.8,.2,1)";
export const DRAW = "cubic-bezier(.3,.7,.2,1)";
export const RETRACT = "cubic-bezier(.4,0,.2,1)";
export const OUT3 = (t) => 1 - (1 - t) ** 3;
export const IN3 = (t) => t ** 3;

// ?slow=2 in the address makes every time twice as long (for looking at a motion; never in the UI).
const slow = (() => {
  if (typeof location === "undefined") return 1;
  const value = Number(new URLSearchParams(location.search).get("slow"));
  return Number.isFinite(value) && value > 0 ? value : 1;
})();

// A time in ms: zero under reduced motion. Read on every call, so a changed setting counts at once.
export function D(ms) {
  return reducedMotion.matches ? 0 : ms * slow;
}

// A time that is already in real ms (a clock reading, scaled by D when it was made), as the ms to
// give `animateTo` as a delay, which scales it once more. Zero under reduced motion.
export function unscaled(ms) {
  const one = D(1);
  return one > 0 ? ms / one : 0;
}

// Animate a node and wait for the end. Under reduced motion it does nothing and is done at once.
// It never throws or keeps a caller waiting: a cancelled animation ends quietly, any other
// failure is reported and ends at once.
export function animateTo(node, keyframes, { dur = 300, delay = 0, ease = CALM, fill = "backwards" } = {}) {
  const duration = D(dur);
  if (!node || !node.animate || !duration) return Promise.resolve();
  try {
    return node.animate(keyframes, { duration, delay: D(delay), easing: ease, fill }).finished.catch((error) => {
      if (!error || error.name !== "AbortError") console.error(error);
    });
  } catch (error) {
    console.error(error);
    return Promise.resolve();
  }
}

// A bar that could not do what was asked shakes once: 7 px left, 6 right, 3 left, and back.
// Nothing under reduced motion.
export function shake(node) {
  const at = (x) => ({ transform: `translateX(${x})` });
  return animateTo(node, [at("0"), at("-7px"), at("6px"), at("-3px"), at("0")], { dur: 380, ease: "ease-out", fill: "none" });
}

// Blocks fade in and lift a little, one step after the other.
export function rise(nodes, { delay = 0, step = 0, y = 6, dur = 260 } = {}) {
  nodes.forEach((node, index) => {
    animateTo(node, [{ opacity: 0, transform: `translateY(${y}px)` }, { opacity: 1, transform: "none" }], { dur, delay: delay + index * step });
  });
}

// The page head rises as a place opens: the title at once, the lede after 120 ms and the scope
// line after 180 ms. Any of them may be null. While the Gateway comes by a view transition they
// wait for the old page to leave (afterOldPage). A draw of the same place (`again`) while the head
// still rises, as when its data comes, draws new nodes: they go on rising from where the old ones
// were, so the head does not jump, and a part that was not there before rises in its turn. A later
// draw leaves the head still.
const HEAD_DELAYS = [0, 120, 180];
const HEAD_MS = 260;
let headRise = { at: -Infinity, wait: 0, shown: [] };
export function riseHead(title, lede, scope, { again = false } = {}) {
  const parts = [title, lede, scope];
  if (!again) headRise = { at: performance.now(), wait: afterOldPage(), shown: parts.map(Boolean) };
  const since = again ? unscaled(performance.now() - headRise.at) : 0;
  if (since >= headRise.wait + HEAD_DELAYS[2] + HEAD_MS) return;
  parts.forEach((node, index) => {
    if (!node) return;
    const delay = headRise.wait + HEAD_DELAYS[index] - since;
    rise([node], { delay: headRise.shown[index] ? delay : Math.max(0, delay) });
    headRise.shown[index] = true;
  });
}

export function animate(node, keyframes, options) {
  if (reducedMotion.matches || !node || !node.animate) return null;
  return node.animate(keyframes, { easing: EASE_OUT, ...options });
}

let activeTransition = null;
let activeClass = null;
let changeClass = null; // the class of the place change whose change is running now

// How long the new Gateway waits for the old page to leave (120 ms, style.css), while it comes by a
// view transition: its head and map start then, as in the mockup, and do not show through the
// fading page. Zero anywhere else, and under reduced motion (no transition runs).
export function afterOldPage() {
  return changeClass === "map-entrance" ? 120 : 0;
}

// Snapshots sit above all normal stacking contexts; drop them before opening a drawer.
export function finishTransition() {
  activeTransition?.skipTransition();
  if (activeClass) document.documentElement.classList.remove(activeClass);
  activeTransition = null;
  activeClass = null;
}

// Run a DOM change as a View Transition where the browser has one; otherwise just run it.
// Hidden tabs skip it: the browser would hold the change until the tab is visible.
export function transition(change, extraClass) {
  finishTransition();
  if (!document.startViewTransition || reducedMotion.matches || document.hidden) {
    change();
    flying = null;
    return null;
  }
  if (extraClass) document.documentElement.classList.add(extraClass);
  let landed = null;
  const t = document.startViewTransition(() => {
    inChange = true;
    changeClass = extraClass || null;
    try { change(); } finally { inChange = false; changeClass = null; }
    flying = null;
    landed = landing;
    landing = null;
  });
  activeTransition = t;
  activeClass = extraClass;
  t.finished.catch(() => {}).finally(() => { if (landed) landed.style.viewTransitionName = ""; });
  t.ready.catch(() => {});
  t.finished.catch(() => {}).finally(() => {
    if (activeTransition !== t) return;
    if (extraClass) document.documentElement.classList.remove(extraClass);
    activeTransition = null;
    activeClass = null;
  });
  return t;
}

// Numbers roll: the old value leaves, then the new one comes in from the other side.
// A bigger number goes up, a smaller one down; text always goes down.
export function rollTo(holder, value) {
  const text = value === null || value === undefined ? "" : String(value);
  const old = holder.lastElementChild;
  if (old && old.textContent === text) return;
  const next = el("span", null, text);
  holder.append(next);
  if (!old) return;
  // The old value moves 70 % of its height away; the new one starts the same distance on the other side.
  const out = Number(text) > Number(old.textContent) ? -70 : 70;
  animateTo(old, [{ transform: "translateY(0)", opacity: 1 }, { transform: `translateY(${out}%)`, opacity: 0 }], { dur: 140, ease: "ease-in", fill: "forwards" });
  animateTo(next, [{ transform: `translateY(${-out}%)`, opacity: 0 }, { transform: "translateY(0)", opacity: 1 }], { dur: 200, delay: 140 });
  // Remove by time, not by animation end: hidden tabs may never finish an animation.
  setTimeout(() => old.remove(), D(140));
}

// A number counts up from 0 to `value` in `dur` ms (OUT3), `delay` ms late. Under reduced motion,
// in a hidden tab or at 0 it shows the number at once.
export function countUp(node, value, { dur = 700, delay = 0 } = {}) {
  const total = D(dur);
  node.textContent = String(value);
  if (!total || !value || document.hidden) return;
  const start = performance.now() + D(delay);
  node.textContent = "0";
  const step = (now) => {
    const t = Math.min(1, Math.max(0, (now - start) / total));
    node.textContent = String(Math.round(value * OUT3(t)));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// First visit to a place: its blocks rise in 45 ms apart. Later visits are instant.
const seen = new Set();
export function entrance(place, nodes) {
  if (seen.has(place)) return;
  seen.add(place);
  nodes.filter(Boolean).forEach((node, index) => {
    node.classList.add("rise");
    node.style.animationDelay = `${index * 45}ms`;
  });
}

// One indicator per group (rail, tabs, filters) slides from the last active choice to the new
// one. The choice itself changes at once; only the mark behind it moves.
const inks = new Map();
export function glide(box, active, key, { animated = true, duration = 300 } = {}) {
  if (!box) return;
  let ink = box.querySelector(":scope > .ink");
  if (!ink) {
    ink = el("span", "ink");
    ink.setAttribute("aria-hidden", "true");
    box.prepend(ink);
  }
  if (!active) {
    ink.style.opacity = "0";
    inks.delete(key);
    return;
  }
  const to = {
    transform: `translate(${active.offsetLeft}px, ${active.offsetTop}px)`,
    width: `${active.offsetWidth}px`,
    height: `${active.offsetHeight}px`,
  };
  Object.assign(ink.style, to, { opacity: "1" });
  const from = inks.get(key);
  if (animated && from && from.box === box && from.transform !== to.transform) {
    animateTo(ink, [{ transform: from.transform, width: from.width, height: from.height }, to], { dur: duration, fill: "none" });
  }
  inks.set(key, { ...to, box });
}

// After a resize, every indicator sits on its choice again, without moving.
if (typeof addEventListener === "function") {
  addEventListener("resize", () => {
    for (const [key, { box }] of inks) {
      if (!box.isConnected) { inks.delete(key); continue; }
      glide(box, box.querySelector('[aria-current="page"], [aria-selected="true"], [aria-pressed="true"]'), key, { animated: false });
    }
  });
}

// A <details> that opens and closes smoothly: its content sits in a row that grows from 0.
// The summary keeps its keyboard behaviour; the closed state is set by time, not by an event.
export function fold(details) {
  const summary = details.querySelector(":scope > summary");
  const inner = el("div", "fold-in");
  inner.append(...[...details.childNodes].filter((n) => n !== summary));
  const box = el("div", "fold");
  box.append(inner);
  details.append(box);
  box.classList.toggle("open", details.open);
  let closing = null;
  summary.addEventListener("click", (event) => {
    event.preventDefault();
    if (details.open && !closing) {
      box.classList.remove("open");
      closing = setTimeout(() => { details.open = false; closing = null; }, reducedMotion.matches ? 0 : 300);
    } else {
      clearTimeout(closing);
      closing = null;
      details.open = true;
      requestAnimationFrame(() => box.classList.add("open"));
    }
  });
  return details;
}

// Shared element: a tile that is on the next page too flies there instead of fading.
// fly() names it before the place changes; land() names its twin while the new place draws.
let flying = null;
let landing = null;
let inChange = false;
export function fly(node, name) {
  if (!node) return;
  node.style.viewTransitionName = name;
  flying = name;
}
// Only a twin drawn inside a transition keeps the name; the transition clears it when done.
export function land(node, name) {
  if (!node || flying !== name || !inChange) return;
  node.style.viewTransitionName = name;
  landing = node;
}
