// Changes: every change made from this page, newest first, with Undo.
import { button, el, shortPath, shortPaths } from "./dom.js";
import { entrance } from "./motion.js";
import { undoChange } from "./panel.js";
import { banner, CLIENT_NAMES, changeTitle, latestChanges, skeleton } from "./parts.js";
import { data, loadChanges, render } from "./store.js";

const STATE_BADGES = {
  verified: ["Applied", "badge win"],
  undone: ["Undone", "badge"],
  stale: ["Stopped: file changed", "badge warn"],
  restored: ["Failed, put back", "badge warn"],
  undo_blocked: ["Undo stopped", "badge warn"],
  cancelled: ["Cancelled", "badge"],
  previewed: ["Preview only", "badge"],
};

const SCOPE_WORDS = { user: "everywhere", project: "project", local: "this Mac" };

const open = new Set();

function when(time) {
  const date = new Date(time);
  if (Number.isNaN(date.getTime())) return "";
  const clock = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  if (date.toDateString() === new Date().toDateString()) return `Today ${clock}`;
  return `${date.toLocaleDateString([], { month: "short", day: "numeric" })} ${clock}`;
}

export function renderChanges(main) {
  main.append(el("h1", null, "Changes"));
  main.append(el("p", "lede", "Every change made from this page. Each one has a backup; Undo puts the previous file back."));
  if (!data.changes) {
    if (data.errors.changes) main.append(banner("the changes", async () => { await loadChanges(); render(); }));
    else main.append(skeleton("card", 2));
    return;
  }
  const latest = latestChanges(data.changes);
  if (!latest.length) {
    const box = el("div", "empty");
    box.append(el("strong", null, "No changes yet"), el("p", null, "Changes you make on this page show up here, each with Undo."));
    main.append(box);
    return;
  }
  const card = el("div", "card timeline");
  const list = el("ul", "feed");
  for (const entry of latest) list.append(...changeRow(entry));
  card.append(list);
  main.append(card);
  entrance("changes", [card]);
}

function changeRow(entry) {
  const li = el("li");
  const [word, look] = STATE_BADGES[entry.state] || [entry.state, "badge"];
  const actions = el("span", "row-actions");
  const details = button(open.has(entry.id) ? "Hide" : "Details", () => {
    if (open.has(entry.id)) open.delete(entry.id); else open.add(entry.id);
    render();
  }, "btn ghost small");
  details.setAttribute("aria-expanded", String(open.has(entry.id)));
  actions.append(details);
  if (entry.state === "verified") actions.append(button("Undo", () => undoChange(entry)));
  li.append(el("span", "muted", when(entry.time)), el("span", null, changeTitle(entry)), el("span", look, word), actions);
  if (!open.has(entry.id)) return [li];

  const more = el("li", "change-detail");
  const steps = el("ul");
  for (const step of entry.steps) {
    const line = el("li");
    const path = el("span", "mono muted", shortPath(step.path));
    path.title = step.path || "";
    const scope = SCOPE_WORDS[step.scope] || step.scope;
    line.append(el("span", null, `${CLIENT_NAMES[step.client] || step.client} · ${scope} · ${step.name} `), path);
    steps.append(line);
  }
  more.append(steps);
  const history = data.changes.filter((e) => e.id === entry.id).reverse();
  more.append(el("p", "muted", history.map((e) => `${when(e.time)} ${(STATE_BADGES[e.state] || [e.state])[0]}`).join(" → ")));
  if (entry.error) more.append(el("p", "muted", shortPaths(entry.error)));
  return [li, more];
}
