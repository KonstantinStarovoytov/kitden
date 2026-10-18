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
    return null;
  }
  if (extraClass) document.documentElement.classList.add(extraClass);
  const t = document.startViewTransition(change);
  activeTransition = t;
  activeClass = extraClass;
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
