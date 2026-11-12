// The version and the Update button at the top of the rail's bottom group (spec 2026-11-11,
// "Place and look"). Normally only "Kitden 0.7.2" shows. When a newer version is out and Kitden
// can update itself, a round button glows beside it; a confirm starts the update, the ring fills
// as the server reports each step, and the page reloads on the new version. Every word comes
// from GET /api/update or from the page's own wait for the new page.
import { getJson, postJson } from "./api.js";
import { button, el, icon, reportError } from "./dom.js";
import { animateTo, D, rollTo } from "./motion.js";
import { say } from "./toast.js";

// The steps, as kitden.update.run.STEPS says them. The server reports 0 to 2; the page shows 3
// itself while it waits for the new page.
export const STEPS = ["Downloading…", "Installing…", "Restarting Kitden…", "Reloading the page…"];
const RING = [0.25, 0.55, 0.8, 1];
const FAILED = "Update failed";
const NOT_STARTED = "Kitden did not start again";
const NEW_NOT_STARTED = "The new version did not start";
const SAME = "Already up to date";

const POLL_MS = 500; // while an update runs or the page waits for the new one
const LOOK_MS = 3000; // while the button shows: another tab may start the update
const ASKS = 10; // looks while the server has not heard the latest version yet (the demo never does)
const WAIT_MS = 30000; // no new page in this time: it did not start
const RELOAD_MS = 500; // the last step shows this long before the page reloads
const LAND_MS = 400; // the reloaded page shows the full ring this long, then the button fades
const SLIDE_MS = 200; // the line under the version slides open and shut, so the rail does not jump
const SWAP_MS = 260; // one step's words fade out, the next fade in, each this long
const ROLL = { outMs: 320, inMs: 460 }; // the version's figures roll slowly: it happens once
const FADE_MS = 500;
const FROM_KEY = "kitden-updated-from"; // the old version, kept across the reload (sessionStorage)

const running = (step) => ({ button: "running", tip: STEPS[step], ring: RING[step] });

// What the spot shows for `api` (GET /api/update) and the page's own `phase`: "confirm" (the
// confirm is open), "waiting" (the old page stopped or handed over), "reloading" (the new page
// answered), "gone" (no new page in 30 s), "updated" (the page reloaded on the new version), or
// null. The button shows only when the server says the latest version is newer (`notes_url`).
export function updateView(api, phase) {
  const view = { version: `Kitden ${api.version}`, button: null, tip: "", ring: 0 };
  if (phase === "gone") return { ...view, button: "failed", tip: NOT_STARTED };
  if (phase === "reloading") return { ...view, ...running(3) };
  if (phase === "waiting" || api.state === "done") return { ...view, ...running(2) };
  // After the reload: the page starts from the full ring, then the button fades while the version
  // rolls to the new one. No words show (the version says it); a screen reader hears them.
  if (phase === "landing") return { ...view, button: "running", tip: "", ring: 1, quiet: true };
  if (phase === "updated") return { ...view, tip: `Updated to ${api.version}`, quiet: true };
  if (api.state === "running") return { ...view, ...running(api.step ?? 0) };
  if (api.state === "failed") return { ...view, button: "failed", tip: api.step === 2 ? NEW_NOT_STARTED : FAILED };
  if (api.state === "same") return { ...view, tip: SAME };
  if (!api.notes_url) return view;
  if (!api.can_update) return { ...view, tip: `${api.latest} is out` };
  return { ...view, button: "available", tip: `Update available: ${api.latest}` };
}

// The words of the box behind the red button. "gone": the old page stopped and no new one
// answered. Failed at step 2: the files are new, but the new page could not start, so this old
// page still runs and holds the port. Otherwise the installer failed.
export function failedWords(api, phase) {
  if (phase === "gone") return { title: NOT_STARTED, text: "Run this in a terminal to open it:", command: "kitden open" };
  if (api.step === 2) {
    const text = "Kitden was updated, but the new page could not start. Close this tab: the old page stops within 10 minutes. Then run this in a terminal:";
    return { title: NEW_NOT_STARTED, text, command: "kitden open" };
  }
  return { title: FAILED, text: "The old version keeps running.", command: api.command };
}

// Where Kitden is installed more than once (uv and Homebrew), each copy updates only itself:
// a quiet line under the version, and the commands that remove a copy behind Details.
const NAMES = { uv: "uv", brew: "Homebrew" };
export function twiceWords(api) {
  const copies = api.installs || [];
  if (copies.length < 2) return null;
  const runs = api.method ? `This page runs the ${NAMES[api.method]} copy. ` : "";
  return {
    line: `Installed twice: ${copies.map((c) => NAMES[c.method]).join(" and ")}`,
    title: "Kitden is installed twice",
    text: `${runs}Each copy updates only itself. Keep one and remove the other:`,
    commands: copies.map((c) => c.remove),
  };
}

// After an update only the figures that change roll: "0.7.5" to "0.7.6" rolls the 5. `same` stays,
// `from` rolls away and `to` rolls in.
export function splitVersions(from, to) {
  let i = 0;
  while (i < from.length && i < to.length && from[i] === to[i]) i += 1;
  while (i > 0 && /\d/.test(to[i - 1]) && /\d/.test(to[i] ?? "")) i -= 1; // never split a number
  return { same: to.slice(0, i), from: from.slice(i), to: to.slice(i) };
}

// How long until the watch reads again: no page came back in 30 s, so now and then.
export const pollMs = (phase) => (phase === "gone" ? LOOK_MS : POLL_MS);

// One read while the page watches an update. `watch.mine` is the version this page runs;
// `watch.last` is the old page's last real answer; `watch.since` is when the old page first said
// it handed over or stopped answering. `answer` is GET /api/update, or null when no page answered.
// A page with another version is the new one: this page reloads. A missed answer means "the
// restart is under way" only after the old page said so (handed over, or the restart step);
// before that the page keeps the last real step, and only 30 s of silence says it did not start.
// Each tab watches on its own clock.
export function watchStep(watch, answer, now) {
  if (answer && answer.version !== watch.mine) return { ...watch, phase: "reloading", reload: true };
  if (answer && answer.state === "running") return { ...watch, last: answer, since: null, phase: null };
  if (answer && answer.state !== "done") return { ...watch, last: answer, phase: null, stop: true };
  const last = answer || watch.last;
  const restarting = Boolean(last) && (last.state === "done" || (last.state === "running" && last.step === 2));
  const since = watch.since ?? now;
  const phase = now - since >= WAIT_MS ? "gone" : restarting ? "waiting" : null;
  return { ...watch, last, since, phase };
}

const SVG_NS = "http://www.w3.org/2000/svg";
const RING_LENGTH = 85; // 2π × 13.5

function ringNode() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "update-ring");
  svg.setAttribute("viewBox", "0 0 30 30");
  svg.setAttribute("aria-hidden", "true");
  for (const name of ["track", "fill"]) {
    const circle = document.createElementNS(SVG_NS, "circle");
    for (const [key, value] of Object.entries({ class: name, cx: "15", cy: "15", r: "13.5" })) circle.setAttribute(key, value);
    svg.append(circle);
  }
  return svg;
}

async function read() {
  try {
    return await getJson("/api/update");
  } catch {
    return null; // the page stopped, or is not up yet
  }
}

function copyRow(command) {
  const row = el("div", "update-command");
  const copy = button("Copy", () => {
    const said = (words) => { copy.textContent = words; say(words); };
    const clipboard = globalThis.navigator && navigator.clipboard;
    if (!clipboard) return said("Could not copy");
    return clipboard.writeText(command).then(() => said("Copied"), () => said("Could not copy"));
  }, "btn ghost small");
  copy.setAttribute("aria-label", `Copy ${command}`);
  row.append(el("code", null, command), copy);
  return row;
}

function tailNode(tail) {
  return el("pre", "update-tail", tail.join("\n"));
}

// The rail's foot sits at the bottom, so a line that shows or goes moves the version: it grows from
// nothing (height, and the 4 px gap above it) and shrinks back instead of jumping.
function slide(node, open) {
  if (open === (!node.hidden && !node.dataset.closing)) return;
  node.getAnimations().forEach((a) => a.cancel());
  const shut = { height: "0px", marginTop: "-4px", opacity: 0 };
  if (open) {
    delete node.dataset.closing;
    node.hidden = false;
    animateTo(node, [shut, { height: `${node.scrollHeight}px`, marginTop: "0px", opacity: 1 }], { dur: SLIDE_MS, fill: "none" });
    return;
  }
  node.dataset.closing = "1";
  animateTo(node, [{ height: `${node.offsetHeight}px`, marginTop: "0px", opacity: 1 }, shut], { dur: SLIDE_MS, fill: "forwards" });
  setTimeout(() => {
    if (!node.dataset.closing) return;
    delete node.dataset.closing;
    node.hidden = true;
    node.getAnimations().forEach((a) => a.cancel());
  }, D(SLIDE_MS));
}

export function startUpdate(spot) {
  // The version: "Kitden 0.7." stays, and the figures that change roll (splitVersions).
  const version = el("span", "update-version");
  const versionHead = el("span");
  const versionTail = el("span", "roll");
  version.append(versionHead, versionTail);
  const press = el("button", "update-btn");
  press.type = "button";
  press.hidden = true;
  const ring = ringNode();
  const fill = ring.lastElementChild;
  press.append(ring);
  const row = el("div", "update-row");
  row.append(version, press);
  const words = el("span");
  const more = el("button", "update-more", "Details");
  more.type = "button";
  more.hidden = true;
  // The step or note under the version. It is said through the page's live region (say), so a
  // line that shows and goes is never a live region a screen reader misses.
  const line = el("p", "update-say");
  line.append(words, more);
  const twiceText = el("span");
  const twiceMore = el("button", "update-more", "Details");
  twiceMore.type = "button";
  const twice = el("p", "update-say");
  twice.append(twiceText, twiceMore);
  twice.hidden = true;
  const pop = el("div", "update-pop");
  pop.setAttribute("role", "dialog");
  pop.hidden = true;
  spot.append(row, line, twice, pop);

  let api = null;
  let mine = null; // the version this page runs
  let phase = null;
  let watch = null;
  let timer = 0;
  let shown = null; // the button's look as drawn
  let popFor = null; // the control that opened the box, for focus back
  let asks = 0; // reads while the latest version is not known yet
  let heard = ""; // the last words said that do not show
  let shownVersion = null; // the version number as drawn
  let wordsFor = ""; // the words the line shows, or is fading to

  // A step's words change: the old ones fade out and the new ones fade in. Words that come or go
  // with the line itself just change, as the line slides.
  function swapWords(tip) {
    if (tip === wordsFor) return;
    const was = wordsFor;
    wordsFor = tip;
    if (!was || !tip || line.hidden) {
      words.getAnimations().forEach((a) => a.cancel());
      words.textContent = tip;
      return;
    }
    animateTo(words, [{ opacity: 1 }, { opacity: 0 }], { dur: SWAP_MS, ease: "ease-in-out", fill: "forwards" }).then(() => {
      if (wordsFor !== tip) return;
      words.textContent = tip;
      words.getAnimations().forEach((a) => a.cancel());
      animateTo(words, [{ opacity: 0 }, { opacity: 1 }], { dur: SWAP_MS, ease: "ease-in-out" });
    });
  }

  function draw() {
    const view = updateView(api, phase);
    const number = view.version.replace(/^Kitden /, "");
    if (number !== shownVersion) {
      if (shownVersion === null) {
        versionHead.textContent = view.version;
      } else {
        const parts = splitVersions(shownVersion, number);
        versionHead.textContent = `Kitden ${parts.same}`;
        versionTail.replaceChildren(el("span", null, parts.from));
        rollTo(versionTail, parts.to, { up: true, ...ROLL });
      }
      shownVersion = number;
    }
    if (view.quiet) {
      if (view.tip && view.tip !== heard) say(view.tip);
      heard = view.tip;
    }
    const tip = view.button === "available" || view.quiet ? "" : view.tip;
    if (tip && tip !== wordsFor) say(tip);
    swapWords(tip);
    more.hidden = view.button !== null || !(api.state === "same" || (api.notes_url && !api.can_update));
    slide(line, Boolean(tip) || !more.hidden);
    const two = twiceWords(api);
    twice.hidden = !two;
    twiceText.textContent = two ? two.line : "";
    drawButton(view);
    spot.hidden = false;
  }

  function drawButton(view) {
    fill.style.strokeDashoffset = String(RING_LENGTH * (1 - view.ring));
    if (view.button === shown) {
      if (view.button === "available") press.title = view.tip;
      return;
    }
    shown = view.button;
    if (!view.button) {
      // The button fades, then goes by time.
      if (press.hidden) return;
      press.classList.add("leaving");
      setTimeout(() => { if (!shown) press.hidden = true; }, D(FADE_MS));
      return;
    }
    press.hidden = false;
    press.className = `update-btn ${view.button}`;
    press.querySelector(".ic")?.remove();
    const mark = { available: "download", failed: "x" }[view.button];
    if (mark) press.append(icon(mark, 14));
    press.removeAttribute("title");
    press.removeAttribute("aria-disabled");
    if (view.button === "available") {
      press.title = view.tip;
      press.setAttribute("aria-label", `Update Kitden to ${api.latest}`);
    } else if (view.button === "running") {
      press.setAttribute("aria-label", "Updating Kitden");
      press.setAttribute("aria-disabled", "true");
    } else if (view.button === "failed") {
      press.setAttribute("aria-label", `${view.tip}. Show why`);
    }
  }

  // While an update runs: every 500 ms, and every 3 s once no page came back. While the button
  // shows: now and then, as another tab may start it. Until the server knows the latest version
  // (it asks in the background): a few times.
  function schedule() {
    clearTimeout(timer);
    if (watch) timer = setTimeout(poll, pollMs(phase));
    else if (shown === "available" || (api.latest === null && asks++ < ASKS)) timer = setTimeout(poll, LOOK_MS);
  }

  async function poll() {
    const answer = await read();
    if (!watch && answer && (answer.version !== mine || ["running", "done"].includes(answer.state))) watch = { mine, since: null };
    if (watch) {
      watch = watchStep(watch, answer, Date.now());
      phase = watch.phase;
      if (answer && !watch.reload) api = answer;
      if (watch.reload) {
        draw();
        try { sessionStorage.setItem(FROM_KEY, mine); } catch { /* the new version just shows */ }
        setTimeout(() => location.reload(), RELOAD_MS);
        return;
      }
      if (watch.stop) watch = null;
    } else if (answer) {
      api = answer;
    }
    draw();
    schedule();
  }

  // The confirm, why it failed, or the details of a quiet note: a small box beside the spot.
  function openPop(parts, from) {
    closePop(false);
    popFor = from;
    const head = el("h3", null, parts.title);
    head.id = "update-pop-title";
    pop.setAttribute("aria-labelledby", head.id);
    pop.replaceChildren(head, ...parts.body);
    pop.hidden = false;
    animateTo(pop, [{ opacity: 0, transform: "translateY(6px) scale(.96)" }, { opacity: 1, transform: "none" }], { dur: 180 });
    document.addEventListener("pointerdown", outside);
    pop.querySelector("button, a")?.focus();
  }

  function closePop(back = true) {
    if (pop.hidden) return;
    document.removeEventListener("pointerdown", outside);
    if (back && popFor?.isConnected && !popFor.hidden) popFor.focus();
    popFor = null;
    if (!D(140)) {
      pop.hidden = true;
      return;
    }
    animateTo(pop, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(4px) scale(.98)" }], { dur: 140, ease: "ease-in", fill: "forwards" });
    setTimeout(() => {
      if (popFor) return; // opened again meanwhile
      pop.hidden = true;
      for (const move of pop.getAnimations()) move.cancel();
    }, D(140));
  }

  function outside(event) {
    if (!spot.contains(event.target)) closePop(false);
  }

  // Update and Try again: the server starts the installer, or says why not.
  async function runUpdate(refused) {
    const reply = await postJson("/api/update");
    const now = reply.ok ? reply.data : await read();
    if (now && now.state === "running") {
      api = now;
      phase = null;
      watch = { mine, since: null, last: now };
      closePop(false);
      draw();
      press.focus();
      schedule();
      return;
    }
    refused.textContent = (reply.data && reply.data.detail) || "Kitden could not start the update.";
    refused.hidden = false;
  }

  function refusedNode() {
    const node = el("p", "update-refused");
    node.setAttribute("role", "alert");
    node.hidden = true;
    return node;
  }

  function whatsNew() {
    const link = el("a", "btn ghost small", "What's new");
    link.href = api.notes_url;
    link.target = "_blank";
    link.rel = "noopener";
    return link;
  }

  function confirmParts() {
    const refused = refusedNode();
    const acts = el("div", "update-acts");
    acts.append(button("Update", () => runUpdate(refused), "btn primary small"), whatsNew());
    return {
      title: `Update to Kitden ${api.latest}?`,
      body: [el("p", null, "Kitden restarts and this page reloads. Your agents keep working."), refused, acts],
    };
  }

  function detailsNode(parts) {
    const box = el("details", "update-details");
    box.append(el("summary", null, "Details"), ...parts);
    return box;
  }

  function failedParts() {
    const what = failedWords(api, phase);
    if (phase === "gone" || api.step === 2) {
      const body = [el("p", null, what.text), copyRow(what.command)];
      if (api.tail?.length && phase !== "gone") body.push(detailsNode([tailNode(api.tail)]));
      return { title: what.title, body };
    }
    const refused = refusedNode();
    const acts = el("div", "update-acts");
    acts.append(button("Try again", () => runUpdate(refused), "btn primary small"));
    const why = api.tail?.length ? [tailNode(api.tail)] : [];
    return {
      title: what.title,
      body: [el("p", null, what.text), refused, acts, detailsNode([...why, el("p", null, "Or run it yourself:"), copyRow(what.command)])],
    };
  }

  function moreParts() {
    if (api.state === "same") {
      const body = [el("p", null, "The installer did not change Kitden.")];
      if (api.tail?.length) body.push(tailNode(api.tail));
      return { title: SAME, body };
    }
    const acts = el("div", "update-acts");
    acts.append(whatsNew());
    return {
      title: `Kitden ${api.latest} is out`,
      body: [el("p", null, "Kitden cannot update itself here. Run this in a terminal:"), copyRow(api.command), acts],
    };
  }

  press.addEventListener("click", () => {
    if (shown === "available") {
      if (!pop.hidden) return closePop();
      openPop(confirmParts(), press);
    } else if (shown === "failed") {
      if (!pop.hidden) return closePop();
      openPop(failedParts(), press);
    }
  });
  twiceMore.addEventListener("click", () => {
    const two = twiceWords(api);
    if (!two) return;
    if (!pop.hidden) return closePop();
    openPop({ title: two.title, body: [el("p", null, two.text), ...two.commands.map(copyRow)] }, twiceMore);
  });
  more.addEventListener("click", () => {
    if (more.hidden) return;
    if (pop.hidden) openPop(moreParts(), more);
    else closePop();
  });
  pop.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    closePop();
  });

  // After a reload on the new version: the full ring under the old version, then the button fades
  // while the version rolls to the new one.
  function landed(from) {
    phase = "landing";
    api = { ...api, version: from };
    draw();
    api = { ...api, version: mine };
    // A moment later, so the full ring shows first. A timer, not a frame: a hidden tab draws none.
    setTimeout(() => {
      phase = "updated";
      draw();
      setTimeout(() => {
        phase = null;
        draw();
        schedule();
      }, D(FADE_MS));
    }, LAND_MS);
  }

  read().then((answer) => {
    if (!answer) return;
    api = answer;
    mine = answer.version;
    let from = null;
    try {
      from = sessionStorage.getItem(FROM_KEY);
      sessionStorage.removeItem(FROM_KEY);
    } catch { /* no storage: the new version just shows */ }
    if (["running", "done"].includes(answer.state)) watch = { mine, since: null, last: answer };
    if (from && from !== mine && !watch) return landed(from);
    draw();
    schedule();
  }).catch(reportError);
}

