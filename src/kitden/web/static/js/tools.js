// Tools of a server in the Kitden gateway: a switch each, for the project picked at the top.
import { getJson, postJson, query } from "./api.js";
import { previewButton, switchNode } from "./details.js";
import { button, el, icon, plural, withFocusKey } from "./dom.js";
import { ALL_PROJECTS, callout, flag, folderName, skeleton } from "./parts.js";
import { review } from "./review.js";
import { data, state } from "./store.js";
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
// a second press on a pending switch takes it out (switchNode). `back(key)` is the Library's way
// back to its Details after a refusal; `flip` names the switch that has just flipped.
export function switchList(rows, { server, project, back = () => null, flip = null }) {
  const list = el("div", "sw-list");
  for (const row of rows) {
    const rule = (value) => ({ action: "gateway.rule", targets: [], params: { server, tool: row.tool, state: value, project } });
    list.append(switchRow(row, rule, back, flip));
  }
  return list;
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

// The tool list in the open panel: a refresh reads it again, an Undo draws its Details again.
export let tools = null;

export function reloadTools() {
  if (tools && tools.section.isConnected) tools.load();
}

// Asks every held server for its tools again. The server says when it is done; without the
// event stream, stop waiting after a minute. The list reads the answer when the event comes.
// Ends when the refresh does, with why it could not start (null when it ran), so a server's
// Details on the Gateway can read its tools again.
export async function refreshTools() {
  // True when the minute ran out: the list is read again here, since no event will do it.
  const ended = new Promise((resolve) => {
    document.addEventListener("kitden:tools", () => resolve(false), { once: true });
    setTimeout(() => resolve(true), 60000);
  });
  const result = await postJson("/api/gateway/tools/refresh");
  if (!result.ok) {
    const error = (result.data && result.data.detail) || `Could not refresh the tools (${result.status}).`;
    if (tools) tools.load({ error });
    return error;
  }
  if (await ended) reloadTools();
  return null;
}

// A held server's tools, a switch each, for the project picked at the top. A switch adds its change
// to the tray and rests pending there; after Apply all, `again(next)` draws this Details again
// with the switch in its new state. `next` says which control gets focus (`focus`), why a change
// was refused (`error`) and which switch has just flipped (`flip`). An error stays as a callout
// until the next action.
export function toolsSection(server, again, next = {}) {
  const section = el("section", "tools");
  const where = state.project ? projectLabel(state.project) : null;
  const head = el("div", "tools-head");
  const refresh = button("Refresh tools", () => refreshTools(), "btn small ghost");
  refresh.dataset.focus = "tools:refresh";
  head.append(el("h2", "sw-head", toolsHead(where)), refresh);
  const list = el("div", "tool-list");
  list.append(skeleton("line", 3));
  section.append(head);
  if (!state.project) section.append(el("p", "muted", "These switches also apply in folders Kitden does not know."));
  section.append(list);

  // After a press its change waits in the tray (`queued`), and the control's look follows the tray
  // by itself (details.js syncTray). A refusal draws this Details again with the reason above the
  // list, focus on the control pressed.
  const backTo = (pressed) => ({ queued = false, error = null } = {}) => (queued || !section.isConnected ? null : again({ focus: pressed, error }));

  // Strict mode is set for all projects: with a project picked the switch only shows it.
  const strictRow = (answer, flip) => {
    const row = el("div", "sw-row whole");
    const text = el("div", "sw-tx");
    text.append(el("b", null, "Strict"), el("small", null, "Only tools that are on are offered; a new tool waits."));
    const body = { action: "gateway.strict", targets: [], params: { server, state: answer.strict ? "off" : "on" } };
    const toggle = switchNode(Boolean(answer.strict), () => review(body, { back: backTo("strict") }), keyFor(body), "Strict: only tools that are on");
    toggle.dataset.focus = "strict";
    if (flip === "strict") toggle.classList.add("flipped");
    if (state.project) {
      toggle.disabled = true;
      toggle.title = "Set for all projects";
    }
    row.append(text, toggle);
    const box = el("div", "sw-list");
    box.append(row);
    return box;
  };

  const draw = (answer, { error = null, flip = null }) => {
    const nodes = [];
    if (error) nodes.push(callout(error, "error"));
    if (answer.problem) nodes.push(callout(answer.problem));
    const off = offNote(answer, where);
    if (off) nodes.push(off);
    nodes.push(strictRow(answer, flip));
    const writing = writingToolsOn(answer.tools);
    if (writing.length) {
      const body = { action: "gateway.rules", targets: [], params: { server, tools: writing, state: "off", project: state.project || null } };
      const all = previewButton("Turn off every writing tool…", body, { look: "btn small", back: backTo("writing") });
      all.dataset.focus = "writing";
      const line = el("div");
      line.append(all);
      nodes.push(line);
    }
    nodes.push(switchList(toolRows(answer, where), { server, project: state.project || null, back: backTo, flip }));
    if (!answer.tools.length) nodes.push(el("p", "muted", NO_TOOLS));
    return nodes;
  };

  const load = async (options = {}) => {
    let answer = null;
    try {
      answer = await getJson(`/api/gateway/tools${query({ server, project: state.project })}`);
    } catch {
      answer = null;
    }
    if (!section.isConnected) return;
    // A redraw keeps keyboard focus on the same control. A control asked for that is gone (the
    // writing tools button once they are off) gives way to Refresh tools.
    const kept = list.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    list.replaceChildren(...(answer ? draw(answer, options) : [callout("Could not load the tools.", "error")]));
    const target = withFocusKey(section, options.focus || kept) || (options.focus ? withFocusKey(section, "tools:refresh") : null);
    if (target) target.focus();
  };
  // `flipped`: the switch the last verified change flipped; an Undo puts focus back on it.
  tools = { section, load, again, flipped: next.flip || null };
  load(next);
  return section;
}
