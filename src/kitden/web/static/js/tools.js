// Tools of a server in the Kitden gateway: a switch each, for the project picked at the top.
import { getJson, postJson, query } from "./api.js";
import { switchNode } from "./details.js";
import { button, el, withFocusKey } from "./dom.js";
import { ALL_PROJECTS, callout, flag, folderName, skeleton } from "./parts.js";
import { review } from "./review.js";
import { data, state } from "./store.js";

// The project's folder name, as the picker at the top shows it.
export function projectLabel(id) {
  const found = (data.projects || []).find((p) => p.id === id);
  return found ? folderName(found.path) : id;
}

// The rows of a held server's Details, for the project picked at the top (`where`, its folder
// name) or for all projects (null): the whole server first, then each tool it lists. A row
// that differs names what it follows without its own setting: the project around it, or all
// projects. A tool's hint says whether it reads or writes, from the server or by its name.
export function toolRows(answer, where) {
  const place = where || "all projects";
  const row = (key, tool, name, description, entry) => {
    const on = entry.state !== "off";
    const what = tool === null ? answer.server : `${tool} of ${answer.server}`;
    const follows = entry.follows || "all projects";
    const hint = tool === null ? null : entry.hint || null;
    const hintFrom = tool === null ? null : entry.hint_from || null;
    return { key, tool, name, description, on, hint, hintFrom, calls: tool === null ? null : callsText(entry.calls), flag: entry.new ? "New" : null, differs: Boolean(entry.differs), follows, label: `Turn ${on ? "off" : "on"} ${what} in ${place}…` };
  };
  return [
    row("server", null, "Whole server", `Turns every tool of ${answer.server} on or off.`, answer),
    ...answer.tools.map((t) => row(`tool:${t.name}`, t.name, t.name, t.description, t)),
  ];
}

// What the tool row says when hovered: how often the gateway forwarded a call and when last. The
// file keeps UTC minutes; the time shown is the browser's.
export function callsText(calls, now = new Date()) {
  if (!calls || !calls.count) return null;
  const last = new Date(calls.last);
  const pad = (n) => String(n).padStart(2, "0");
  const time = `${pad(last.getHours())}:${pad(last.getMinutes())}`;
  const today = last.toDateString() === now.toDateString();
  const day = today ? "today" : `${last.getDate()} ${last.toLocaleString("en-GB", { month: "short" })}`;
  const times = calls.count === 1 ? "once" : `${calls.count} times`;
  return `Called ${times}, last ${day} ${time}`;
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
async function refreshTools() {
  // True when the minute ran out: the list is read again here, since no event will do it.
  const ended = new Promise((resolve) => {
    document.addEventListener("kitden:tools", () => resolve(false), { once: true });
    setTimeout(() => resolve(true), 60000);
  });
  const result = await postJson("/api/gateway/tools/refresh");
  if (!result.ok) {
    if (tools) tools.load({ error: (result.data && result.data.detail) || `Could not refresh the tools (${result.status}).` });
    return;
  }
  if (await ended) reloadTools();
}

// A held server's tools, a switch each, for the project picked at the top. A switch opens the
// review; when the change is verified, `again(next)` draws this Details again with the switch
// flipped. `next` says which control gets focus (`focus`), why a review stopped (`error`) and
// which switch has just flipped (`flip`). An error stays as a callout until the next action.
export function toolsSection(server, again, next = {}) {
  const section = el("section", "tools");
  const where = state.project ? projectLabel(state.project) : null;
  const head = el("div", "tools-head");
  const refresh = button("Refresh tools", () => refreshTools(), "btn small ghost");
  refresh.dataset.focus = "tools:refresh";
  head.append(el("h2", null, `Tools · ${where || ALL_PROJECTS}`), refresh);
  const list = el("div", "tool-list");
  list.append(skeleton("line", 3));
  section.append(head);
  if (!state.project) section.append(el("p", "muted", "These switches also apply in folders Kitden does not know."));
  section.append(list);

  const change = (row, value, pressed) => {
    const back = ({ error = null, verified = false } = {}) => again({ focus: verified ? row.key : pressed, error, flip: verified ? row.key : null });
    const params = { server, tool: row.tool, state: value, project: state.project || null };
    return review({ action: "gateway.rule", targets: [], params }, { back });
  };

  // Strict mode is set for all projects: with a project picked the switch only shows it.
  const strictRow = (answer, flip) => {
    const row = el("div", "layer tool whole");
    const middle = el("div");
    middle.append(el("div", "name", "Strict"), el("div", "why", "Only tools you turned on are offered; a new tool waits."));
    const back = ({ error = null, verified = false } = {}) => again({ focus: "strict", error, flip: verified ? "strict" : null });
    const params = { server, state: answer.strict ? "off" : "on" };
    const toggle = switchNode(Boolean(answer.strict), () => review({ action: "gateway.strict", targets: [], params }, { back }));
    toggle.setAttribute("aria-label", "Strict: only tools you turned on");
    toggle.dataset.focus = "strict";
    if (flip === "strict") toggle.classList.add("flipped");
    if (state.project) {
      toggle.disabled = true;
      toggle.title = "Set for all projects";
    }
    row.append(middle, toggle);
    const stack = el("div", "stack");
    stack.append(row);
    return stack;
  };

  const draw = (answer, { error = null, flip = null }) => {
    const nodes = [];
    if (error) nodes.push(callout(error, "error"));
    if (answer.problem) nodes.push(callout(answer.problem));
    if (answer.state === "off") nodes.push(el("p", "muted", `${server} is off in ${where || "all projects"}, so none of its tools are offered there.`));
    nodes.push(strictRow(answer, flip));
    const writing = writingToolsOn(answer.tools);
    if (writing.length) {
      // Verified, the button is gone (no writing tool is on), so focus goes to Refresh tools.
      const back = ({ error = null, verified = false } = {}) => again({ focus: verified ? "tools:refresh" : "writing", error });
      const params = { server, tools: writing, state: "off", project: state.project || null };
      const all = button("Turn off every writing tool…", () => review({ action: "gateway.rules", targets: [], params }, { back }), "btn small");
      all.dataset.focus = "writing";
      const line = el("div");
      line.append(all);
      nodes.push(line);
    }
    const stack = el("div", "stack");
    for (const row of toolRows(answer, where)) {
      const node = el("div", row.tool === null ? "layer tool whole" : "layer tool");
      if (row.calls) node.title = row.calls;
      const middle = el("div");
      const title = el("div", row.tool === null ? "name" : "name mono", row.name);
      if (row.hintFrom) {
        const hint = el("span", "muted hint", row.hint);
        hint.title = HINT_FROM[row.hintFrom];
        title.append(" ", hint);
      }
      if (row.flag) title.append(" ", flag({ text: row.flag, level: "info" }));
      middle.append(title);
      if (row.description) {
        const about = el("div", "why", row.description);
        about.title = row.description;
        middle.append(about);
      }
      if (row.differs) {
        const line = el("div", "differs");
        const follow = button(`Use ${row.follows}`, () => change(row, null, `follow:${row.key}`), "btn small");
        follow.dataset.focus = `follow:${row.key}`;
        line.append(flag({ text: `Differs from ${row.follows}`, level: "info" }), follow);
        middle.append(line);
      }
      const toggle = switchNode(row.on, () => change(row, row.on ? "off" : "on", row.key));
      toggle.setAttribute("aria-label", row.label);
      toggle.dataset.focus = row.key;
      // Drawn in its new state; the thumb slides there once (the resting style is the truth).
      if (flip === row.key) toggle.classList.add("flipped");
      node.append(middle, toggle);
      stack.append(node);
    }
    nodes.push(stack);
    if (!answer.tools.length) nodes.push(el("p", "muted", "Kitden does not know its tools yet. Refresh tools asks the server."));
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
    // A redraw keeps keyboard focus on the same control.
    const kept = list.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    list.replaceChildren(...(answer ? draw(answer, options) : [callout("Could not load the tools.", "error")]));
    const target = withFocusKey(section, options.focus || kept);
    if (target) target.focus();
  };
  // `flipped`: the switch the last verified change flipped; an Undo puts focus back on it.
  tools = { section, load, again, flipped: next.flip || null };
  load(next);
  return section;
}
