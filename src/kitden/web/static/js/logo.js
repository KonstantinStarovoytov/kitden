// The logo's one gesture, as if the stove is lit: the door of the house glows, and a soft stream
// of smoke leaves the top of the d, rises a little and drifts right over "en", where it thins out.
// Once, when the page opens. Nothing under reduced motion. The numbers come from
// design/logo-motion.md; the mockup is design/kitden-cloud-smoke.html.
import { el } from "./dom.js";
import { D } from "./motion.js";

const SVG_NS = "http://www.w3.org/2000/svg";

// Twelve puffs on one path, 110 ms apart: this close they melt into one ribbon.
const PUFFS = 12;
const GAP = 110;
const LEAD = 500; // the first puff waits for the door to light
const FLIGHT = 2600;
const WIDTHS = [0.3, 0.32, 0.34, 0.36, 0.38]; // in em of the wordmark, cycling
// The path as a share of the full move (right .9 em, up .4 em): it rises first, then the air
// carries it right. A puff is born at 70 % of its size and grows to 140 %; it is faint (.31 at
// most) and a little blurred (.24 to .4 px).
const PATH = [[0, -0.12], [0.15, 0.4], [0.6, 0.78], [1, 0.92]];
const AT = [0, 0.2, 0.6, 1];
const FADE = [0, 0.31, 0.22, 0];
const RIGHT = 0.9;
const UP = 0.4;
// The door's light grows over 1200 ms, slowly at first, like a fire catching; it is held while
// any smoke is in the air and goes out over the last 700 ms, which end 200 ms after the last puff.
const LIGHT_IN = 1200;
const GROW = "cubic-bezier(.45, 0, .25, 1)";
const LIGHT_OUT = 700;
const AFTER = 200;
export const TOTAL = LEAD + (PUFFS - 1) * GAP + FLIGHT + AFTER;
const START = 400; // after the page opens
const HOVER_WAIT = 200; // after the pointer comes to the logo

// One soft puff: a rounded body with two round bumps on top, in a 28 × 20 box, drawn with DOM
// calls like the icons.
function puff(width) {
  const node = el("i", "puff");
  node.style.setProperty("--w", `${width}em`);
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 -5 28 20");
  const shapes = [
    ["rect", { x: 0, y: 0, width: 22, height: 14.4, rx: 7 }],
    ["ellipse", { cx: 8, cy: 1.8, rx: 7.5, ry: 6.75 }],
    ["ellipse", { cx: 19.5, cy: 4, rx: 8.5, ry: 6.3 }],
  ];
  for (const [tag, attrs] of shapes) {
    const part = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attrs)) part.setAttribute(key, String(value));
    svg.append(part);
  }
  node.append(svg);
  return node;
}

// The frames of one puff, on one linear clock, so the path reads as a drift and not a bounce.
export function puffFrames() {
  return PATH.map(([x, y], k) => {
    const t = AT[k];
    return {
      offset: t,
      opacity: FADE[k],
      transform: `translate(${(RIGHT * x).toFixed(3)}em, ${(-UP * y).toFixed(3)}em) scale(${(0.7 + 0.7 * t).toFixed(3)})`,
      filter: `blur(${(0.24 + 0.16 * t).toFixed(3)}px)`,
    };
  });
}

// The frames of the door's light at `strength`: each step has its own curve, so the hold holds.
export function lightFrames(strength) {
  return [
    { opacity: 0, easing: GROW },
    { opacity: strength, offset: LIGHT_IN / TOTAL, easing: "linear" },
    { opacity: strength, offset: (TOTAL - LIGHT_OUT) / TOTAL, easing: "ease-in-out" },
    { opacity: 0 },
  ];
}

// Builds the smoke in the d and the light in the door of `brand` (the rail's logo, a link to the
// Overview), and plays the gesture 400 ms after the page opens, and again when the pointer or
// keyboard focus comes to the logo. Never twice at once: a gesture that plays runs to its end
// (set by time, not by an event). Returns `play`.
export function startLogo(brand) {
  const mark = brand.querySelector(".brand-mark");
  const label = brand.querySelector(".label");
  if (!mark || !label) return () => {};
  const step = el("span", "step");
  const door = el("span", "door");
  mark.append(step, door);
  const puffs = [];
  for (let i = 0; i < PUFFS; i += 1) puffs.push(puff(WIDTHS[i % WIDTHS.length]));
  const smoke = el("span", "smoke");
  smoke.append(...puffs);
  const d = el("span", "d", "d");
  d.append(smoke);
  label.replaceChildren("Kit", d, "en");
  let playing = false;
  const play = () => {
    if (playing || !D(1) || !door.animate) return; // still going, reduced motion, or no Web Animations
    playing = true;
    setTimeout(() => { playing = false; }, D(TOTAL));
    puffs.forEach((node, i) => node.animate(puffFrames(), { duration: D(FLIGHT), delay: D(LEAD + i * GAP), easing: "linear" }));
    door.animate(lightFrames(0.92), { duration: D(TOTAL) });
    step.animate(lightFrames(0.42), { duration: D(TOTAL) });
  };
  // The pointer (or focus) must stay a moment: one that only passes starts nothing.
  let wait = 0;
  const soon = () => { clearTimeout(wait); wait = setTimeout(play, D(HOVER_WAIT)); };
  const never = () => clearTimeout(wait);
  brand.addEventListener("pointerenter", soon);
  brand.addEventListener("focus", soon);
  brand.addEventListener("pointerleave", never);
  brand.addEventListener("blur", never);
  setTimeout(play, D(START));
  return play;
}
