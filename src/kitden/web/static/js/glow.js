// Two quiet effects under the pointer: a grid of dots on the page column, and a glow on the map
// block or Overview card the pointer is on. Nothing runs by itself: a frame is drawn only while
// the pointer moves or the dots are still easing in or out, and none at rest. Both are off under
// reduced motion. The colour is the page's --glow (R G B numbers, one per theme).
import { reducedMotion } from "./motion.js";

const REACH = 130; // dots show this far from the pointer
const GRID = 22; // the dots' pitch
const EASE = 0.16; // the share of the way to the goal that a frame takes
// Map blocks and Overview cards only. The glow itself is drawn by style.css from --mx and --my.
const SPOTLIGHT = 'div.map .block, #main[data-place="overview"] .ov-card';

// The dots near (x, y): the nearer one is bigger, stronger, and pushed a little away from the pointer.
function drawDots(ctx, { x, y, level, colour }) {
  const first = (point) => Math.max(0, Math.floor((point - REACH) / GRID));
  const last = (point) => Math.ceil((point + REACH) / GRID);
  for (let column = first(x); column <= last(x); column += 1) {
    for (let row = first(y); row <= last(y); row += 1) {
      const dotX = column * GRID + GRID / 2;
      const dotY = row * GRID + GRID / 2;
      const away = Math.hypot(dotX - x, dotY - y);
      if (away > REACH) continue;
      const near = 1 - away / REACH;
      const push = away ? (near * near * 5) / away : 0;
      ctx.beginPath();
      ctx.arc(dotX + (dotX - x) * push, dotY + (dotY - y) * push, 0.8 + near * 1.5, 0, Math.PI * 2);
      ctx.fillStyle = `rgb(${colour} / ${(near * near * 0.55 * level).toFixed(3)})`;
      ctx.fill();
    }
  }
}

// `column` holds the top bar and the canvas (#dots). Called once.
export function startGlow(column) {
  const canvas = column.querySelector("#dots");
  const topbar = column.querySelector(".topbar");
  let ctx = null;
  let scale = 1; // the device pixel ratio the canvas was sized for
  let width = 0;
  let height = 0;
  const dots = { x: 0, y: 0, level: 0, goal: 0, moved: false, running: false, colour: "" };

  const paint = () => {
    if (!ctx) return;
    ctx.clearRect(0, 0, width, height);
    if (dots.level >= 0.01) drawDots(ctx, dots);
  };
  // An empty read (the token is missing for a moment) keeps the last good colour.
  const readColour = () => {
    const colour = getComputedStyle(document.documentElement).getPropertyValue("--glow").trim();
    if (colour) dots.colour = colour;
    paint();
  };
  // The canvas covers the column below the top bar; CSS pins it there (--glow-top, --glow-h).
  const size = () => {
    const top = topbar.offsetHeight;
    scale = devicePixelRatio || 1;
    width = column.clientWidth;
    height = Math.max(0, column.clientHeight - top);
    canvas.style.setProperty("--glow-top", `${top}px`);
    canvas.style.setProperty("--glow-h", `${height}px`);
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    ctx = canvas.getContext("2d");
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    paint();
  };

  const frame = () => {
    if (reducedMotion.matches) {
      dots.level = 0;
      dots.goal = 0;
      dots.moved = false;
    } else dots.level += (dots.goal - dots.level) * EASE;
    paint();
    if (Math.abs(dots.goal - dots.level) > 0.01 || (dots.goal > 0 && dots.moved)) {
      dots.moved = false;
      requestAnimationFrame(frame);
    } else dots.running = false;
  };
  const kick = () => {
    if (dots.running) return;
    // A window moved to another screen changes the pixel ratio without changing the size.
    if ((devicePixelRatio || 1) !== scale) size();
    dots.running = true;
    requestAnimationFrame(frame);
  };

  // The glow of the block or card under the pointer: its --mx and --my are the pointer's place in it.
  const spotlight = (target, clientX, clientY) => {
    const node = target && target.closest && target.closest(SPOTLIGHT);
    if (!node) return;
    const box = node.getBoundingClientRect();
    node.style.setProperty("--mx", `${clientX - box.left}px`);
    node.style.setProperty("--my", `${clientY - box.top}px`);
  };

  column.addEventListener(
    "pointermove",
    (event) => {
      if (reducedMotion.matches) return;
      spotlight(event.target, event.clientX, event.clientY);
      const box = canvas.getBoundingClientRect();
      dots.x = event.clientX - box.left;
      dots.y = event.clientY - box.top;
      dots.goal = 1;
      dots.moved = true;
      kick();
    },
    { passive: true },
  );
  column.addEventListener("pointerleave", () => {
    dots.goal = 0;
    if (dots.level >= 0.01) kick();
  });
  // A setting turned on while the dots show: the next frame clears them.
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) kick();
  });
  // A theme switch (or the system's, while the page follows it) paints the dots in the new colour.
  new MutationObserver(readColour).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", readColour);
  const watch = new ResizeObserver(size);
  watch.observe(column);
  watch.observe(topbar);
  readColour();
  size();
}
