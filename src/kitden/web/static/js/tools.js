// Tools of a server in the Kitden gateway: a switch each, for the project picked at the top.
import { postJson } from "./api.js";
import { previewButton, switchNode } from "./details.js";
import { button, el, icon, plural } from "./dom.js";
import { ALL_PROJECTS, flag, folderName } from "./parts.js";
import { review } from "./review.js";
import { data } from "./store.js";
import { keyFor } from "./tray.js";

// The project's folder name, as the picker at the top shows it.
export function projectLabel(id) {
  const found = (data.projects || []).find((p) => p.id === id);
  return found ? folderName(found.path) : id;
}

// What a tool says it does, as its row says it: from the server's hint, or "may write" by its
// name; nothing when neither says.
const DOES = { reads: "Reads only", writes: "May write", "may write": "May write" };
// The whole server's quiet line: how many of its tools are on where the list is for.
const wholeWords = (on, all) => (on ? `${on} of ${all} tools on` : "Every tool is off");

// The rows of a held server's switches, for the project picked at the top (`where`, its folder
// name) or for all projects (null): the whole server first ("3 of 4 tools on"), then each tool it
// lists ("Read file · Reads only"). A row that differs names what it follows without its own
// setting: the project around it, or all projects. A tool's hint says whether it reads or writes,
// from the server or by its name.
export function toolRows(answer, where) {
  const place = where || "all projects";
  const tools = answer.tools || [];
  const row = (key, tool, name, sub, entry) => {
    const on = entry.state !== "off";
    const what = tool === null ? answer.server : `${tool} of ${answer.server}`;
    const follows = entry.follows || "all projects";
    const hint = tool === null ? null : entry.hint || null;
    const hintFrom = tool === null ? null : entry.hint_from || null;
    return { key, tool, name, sub, description: entry.description || null, on, hint, hintFrom, calls: tool === null ? null : callsText(entry.calls), flag: entry.new ? "New" : null, differs: Boolean(entry.differs), follows, label: `Turn ${on ? "off" : "on"} ${what} in ${place}…` };
  };
  const on = tools.filter((t) => (t.effective ?? t.state) === "on").length;
  return [
    row("server", null, "Whole server", tools.length ? wholeWords(on, tools.length) : null, answer),
    ...tools.map((t) => row(`tool:${t.name}`, t.name, t.name, [t.title, DOES[t.hint]].filter(Boolean).join(" · ") || null, t)),
  ];
}

// The head over a server's switches: "Tools · All projects" or "Tools · atlas".
export const toolsHead = (where) => `Tools · ${where || ALL_PROJECTS}`;
export const NO_TOOLS = "Kitden does not know its tools yet. Refresh tools asks the server.";

// Over the switches of a server that is off: its tools keep their own switches, but none is
// offered. With All projects it is off by the shared rule, never "in all projects": the known
// projects whose own rule turns it on are counted (as the map block says "On in 2 projects").
// Null while it is on.
export function offNote(answer, where) {
  if (answer.state !== "off") return null;
  if (where) return el("p", "muted", `${answer.server} is off in ${where}, so none of its tools are offered there.`);
  const others = answer.shared ? (answer.projects || []).filter((p) => p.server && p.server !== answer.shared).length : 0;
  const otherwise = others ? ` ${plural(others, "project decides", "projects decide")} otherwise.` : "";
  return el("p", "muted", `${answer.server} is off by the shared rule, so none of its tools are offered.${otherwise}`);
}

// A server's switches as the mockup lists them (`rows` from toolRows): the whole server first,
// then each tool. A press adds the row's rule for `project` (null: all projects) to the tray, and
// a second press on a pending switch takes it out (switchNode). `back(key)` is the way
// back to its Details after a refusal; `flip` names the switch that has just flipped.
//
// Several tools can be picked and turned off or on in one row of the preview: Cmd (Mac) or Ctrl
// and a press picks one more, Shift a run, and a drag over the rows picks the rows it covers. A
// bar at the top then says how many, with Turn off, Turn on and Clear; Space turns them all off
// (or on, when all are off), and Escape lets them go.
export function switchList(rows, { server, project, back = () => null, flip = null }) {
  const list = el("div", "sw-list");
  const tools = rows.filter((row) => row.tool !== null);
  const keys = tools.map((row) => row.tool);
  const nodes = new Map();
  let picked = new Set();
  let anchor = null;
  const bar = el("div", "sw-picked");
  const flipPicked = (state) => {
    const body = pickedBody(server, project, keys.filter((key) => picked.has(key)), state);
    pick(new Set(), null);
    return review(body, { back: back(null) });
  };
  const action = (label, tip, run) => {
    const node = button(label, run);
    node.dataset.tip = tip;
    return node;
  };
  const pick = (next, from) => {
    picked = next;
    anchor = from;
    for (const [key, node] of nodes) {
      node.classList.toggle("picked", picked.has(key));
      node.setAttribute("aria-selected", String(picked.has(key)));
    }
    // The bar is in the list only while tools are picked.
    if (!picked.size) return bar.remove();
    if (!bar.isConnected) list.prepend(bar);
    const count = plural(picked.size, "tool", "tools");
    bar.replaceChildren(
      el("span", null, `${picked.size} selected`),
      action("Turn off", `Turns the ${count} off. ${PREVIEW}`, () => flipPicked("off")),
      action("Turn on", `Turns the ${count} on. ${PREVIEW}`, () => flipPicked("on")),
      action("Clear", "Lets the picked tools go. Nothing changes.", () => pick(new Set(), null)),
    );
  };
  for (const row of rows) {
    const rule = (value) => ({ action: "gateway.rule", targets: [], params: { server, tool: row.tool, state: value, project } });
    const node = switchRow(row, rule, back, flip);
    if (row.tool !== null) {
      nodes.set(row.tool, node);
      node.addEventListener("click", (event) => {
        if (event.target.closest?.("button, a, input") || dragged) return;
        const next = pickTools(picked, keys, row.tool, { add: event.metaKey || event.ctrlKey, range: event.shiftKey, anchor });
        pick(next.picked, next.anchor);
      });
    }
    list.append(node);
  }
  list.addEventListener("keydown", (event) => {
    if (!picked.size) return;
    if (event.key === "Escape") {
      event.stopPropagation();
      pick(new Set(), null);
    } else if (event.key === " " && !event.target.closest?.("input")) {
      event.preventDefault();
      const anyOn = tools.some((row) => picked.has(row.tool) && row.on);
      flipPicked(anyOn ? "off" : "on").catch?.(() => {});
    }
  });
  // A drag over the rows (not from a switch or a button) picks the rows it covers; with Cmd or
  // Ctrl, on top of what is picked.
  let dragged = false;
  list.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || event.target.closest?.("button, a, input, summary")) return;
    const start = { x: event.clientX, y: event.clientY };
    const base = event.metaKey || event.ctrlKey ? new Set(picked) : new Set();
    let box = null;
    dragged = false;
    const move = (moved) => {
      const [x0, x1] = [Math.min(start.x, moved.clientX), Math.max(start.x, moved.clientX)];
      const [y0, y1] = [Math.min(start.y, moved.clientY), Math.max(start.y, moved.clientY)];
      if (!box && Math.hypot(x1 - x0, y1 - y0) < 5) return;
      if (!box) {
        dragged = true;
        box = el("div", "sw-marquee");
        list.append(box);
        list.classList.add("picking");
      }
      const frame = list.getBoundingClientRect();
      Object.assign(box.style, { left: `${x0 - frame.left}px`, top: `${y0 - frame.top + list.scrollTop}px`, width: `${x1 - x0}px`, height: `${y1 - y0}px` });
      const hits = new Set(base);
      for (const [key, node] of nodes) {
        const r = node.getBoundingClientRect();
        if (r.bottom >= y0 && r.top <= y1 && r.right >= x0 && r.left <= x1) hits.add(key);
      }
      pick(hits, anchor);
    };
    const end = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", end);
      box?.remove();
      list.classList.remove("picking");
      // The click that ends a drag picks nothing more.
      setTimeout(() => { dragged = false; }, 0);
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", end);
  });
  return list;
}

const PREVIEW = "Nothing changes until you press Apply.";

// The tools picked after a press on `key` (`keys`: every tool, in order): with `add` (Cmd or
// Ctrl) one more, or one less when it was picked; with `range` (Shift) every tool from `anchor`
// (the last one picked, else the first) to `key`, on top of what is picked; else none.
export function pickTools(picked, keys, key, { add = false, range = false, anchor = null } = {}) {
  if (range) {
    const from = keys.indexOf(anchor ?? keys[0]);
    const to = keys.indexOf(key);
    const run = keys.slice(Math.min(from, to), Math.max(from, to) + 1);
    return { picked: new Set([...picked, ...run]), anchor: anchor ?? keys[0] };
  }
  if (add) {
    const next = new Set(picked);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return { picked: next, anchor: key };
  }
  return { picked: new Set(), anchor: null };
}

// One row of the preview that turns the picked tools off or on.
export function pickedBody(server, project, tools, state) {
  return { action: "gateway.rules", targets: [], params: { server, tools, state, project } };
}

// One row: the name (a tool's in mono, with its "New" flag), its quiet line, its description in two
// lines at most (so it reads without a pointer; the whole of it in hover text), and under a project
// with its own rule "Differs from all projects · Use all projects"; then its switch. Its calls
// wait in hover text.
function switchRow(row, rule, back, flip) {
  const node = el("div", row.tool === null ? "sw-row whole" : "sw-row");
  const text = el("div", "sw-tx");
  const name = el("span", "sw-name");
  name.append(el(row.tool === null ? "b" : "code", null, row.name));
  if (row.flag) name.append(flag({ text: row.flag, level: "info" }));
  text.append(name);
  if (row.calls) text.title = row.calls;
  if (row.sub) {
    const sub = el("small", null, row.sub);
    if (row.hintFrom) sub.title = HINT_FROM[row.hintFrom];
    text.append(sub);
  }
  if (row.description) {
    const about = el("small", "about", row.description);
    about.title = row.description;
    text.append(about);
  }
  if (row.differs) text.append(differsLine(row, rule(null), back));
  const toggle = switchNode(row.on, () => review(rule(row.on ? "off" : "on"), { back: back(row.key) }), keyFor(rule(null)), row.label);
  toggle.dataset.focus = row.key;
  // Drawn in its new state after Apply all; the thumb slides there once (the resting style is the truth).
  if (flip === row.key) toggle.classList.add("flipped");
  node.append(text, toggle);
  return node;
}

// A rule of the picked project's own, and the way back to what it follows. The link adds the
// same row as the switch, so both show it waits.
function differsLine(row, body, back) {
  const line = el("small", "differs");
  const use = previewButton(`Use ${row.follows}`, body, { look: "lnk", back: back(`follow:${row.key}`) });
  use.dataset.focus = `follow:${row.key}`;
  line.append(icon("folder", 11), `Differs from ${row.follows} · `, use);
  return line;
}

// How often the gateway forwarded a call to a tool and when last: "12 calls · last today 14:02",
// as a tool's Details and the tool row's hover text say it. The file keeps UTC minutes; the time
// shown is the browser's.
export function callsText(calls, now = new Date()) {
  if (!calls || !calls.count) return null;
  const last = new Date(calls.last);
  const pad = (n) => String(n).padStart(2, "0");
  const time = `${pad(last.getHours())}:${pad(last.getMinutes())}`;
  const today = last.toDateString() === now.toDateString();
  const day = today ? "today" : `${last.getDate()} ${last.toLocaleString("en-GB", { month: "short" })}`;
  return `${plural(calls.count, "call", "calls")} · last ${day} ${time}`;
}

// The tools the batch switch turns off: those that are on and write, or may write by their name.
export function writingToolsOn(tools) {
  return tools.filter((t) => t.state === "on" && (t.hint === "writes" || t.hint === "may write")).map((t) => t.name);
}

const HINT_FROM = { server: "from the server", name: "by its name" };

// Asks every held server for its tools again. The server says when it is done; without the
// event stream, stop waiting after a minute. Ends when the refresh does, with why it could not
// start (null when it ran), so a server's Details on the Gateway can read its tools again.
export async function refreshTools() {
  const ended = new Promise((resolve) => {
    document.addEventListener("kitden:tools", () => resolve(), { once: true });
    setTimeout(resolve, 60000);
  });
  const result = await postJson("/api/gateway/tools/refresh");
  if (!result.ok) return (result.data && result.data.detail) || `Could not refresh the tools (${result.status}).`;
  await ended;
  return null;
}
