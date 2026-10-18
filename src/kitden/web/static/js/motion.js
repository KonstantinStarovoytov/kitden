// Motion helpers. Animate only where it explains a change; never slow down frequent actions.
import { el } from "./dom.js";

export const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
export const EASE_OUT = "cubic-bezier(0.23, 1, 0.32, 1)";
export const EASE_IN_OUT = "cubic-bezier(0.77, 0, 0.175, 1)";

export function animate(node, keyframes, options) {
  if (reducedMotion.matches || !node || !node.animate) return null;
  return node.animate(keyframes, { easing: EASE_OUT, ...options });
}

let activeTransition = null;
let activeClass = null;

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
    try { change(); } finally { inChange = false; }
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

// Numbers roll: the old value slides out, the new one slides in.
export function rollTo(holder, value) {
  const text = value === null || value === undefined ? "" : String(value);
  const old = holder.lastElementChild;
  if (old && old.textContent === text) return;
  const next = el("span", null, text);
  holder.append(next);
  if (!old) return;
  const up = Number(text) > Number(old.textContent) ? -1 : 1;
  animate(old, [{ transform: "translateY(0)", opacity: 1 }, { transform: `translateY(${-100 * up}%)`, opacity: 0 }], { duration: 300, fill: "forwards" });
  animate(next, [{ transform: `translateY(${100 * up}%)`, opacity: 0 }, { transform: "translateY(0)", opacity: 1 }], { duration: 300 });
  // Remove by time, not by animation end: hidden tabs may never finish an animation.
  setTimeout(() => old.remove(), reducedMotion.matches ? 0 : 320);
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

// The spring from style.css, for animations started from here.
let springEasing = null;
export function spring() {
  if (springEasing === null) {
    const value = getComputedStyle(document.documentElement).getPropertyValue("--spring").trim();
    springEasing = value.startsWith("linear(") ? value : EASE_OUT;
  }
  return springEasing;
}

// One indicator per group (rail, tabs, filters) slides from the last active choice to the new
// one. The choice itself changes at once; only the mark behind it moves.
const inks = new Map();
export function glide(box, active, key, { animated = true } = {}) {
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
    animate(ink, [{ transform: from.transform, width: from.width, height: from.height }, to], { duration: 300, easing: spring() });
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
