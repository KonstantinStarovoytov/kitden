// Changes: every change made from this page, newest first, with Undo.
import { button, el, shortPath, shortPaths } from "./dom.js";
import { entrance } from "./motion.js";
import { closePanel, openChange, undoChange } from "./panel.js";
import { backupNote, banner, changeTitle, failedWord, mark, notesSection, opens, skeleton } from "./parts.js";
import { data, retry } from "./store.js";

// The state in words. Rows that no longer change anything are plain grey text, not badges.
const STATE_BADGES = {
  verified: ["Applied", "badge win"],
  undone: ["Undone", "faint"],
  stale: ["Not applied: the file changed before Apply", "badge warn"],
  restored: ["Failed", "badge warn"],
  undo_blocked: ["Can't undo: the file changed after this", "badge warn"],
  cancelled: ["Cancelled", "faint"],
  previewed: ["Preview only", "badge"],
};
const OVER = ["undone", "cancelled"];

const SCOPE_WORDS = { user: "all projects", project: "this project", local: "this Mac" };

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
    if (data.errors.changes) main.append(banner("the changes", retry));
    else main.append(skeleton("card", 2));
    return;
  }
  // One entry per change, newest first (views/changes_view.py).
  const latest = data.changes;
  if (!latest.length) {
    const box = el("div", "empty");
    box.append(el("strong", null, "No changes yet"), el("p", null, "Changes you make on this page show up here, each with Undo."));
    main.append(box);
    return;
  }
  const card = el("div", "card timeline");
  const list = el("ul", "feed");
  for (const entry of latest) list.append(changeRow(entry));
  card.append(list);
  main.append(card);
  entrance("changes", [card]);
}

function changeRow(entry) {
  const li = el("li", OVER.includes(entry.state) ? "over" : null);
  let [word, look] = STATE_BADGES[entry.state] || [entry.state, "badge"];
  if (entry.state === "restored") word = failedWord(entry.technical.error);
  const actions = el("span", "row-actions");
  if (entry.state === "verified") actions.append(button("Undo", () => undoChange(entry)));
  li.append(el("span", "muted", when(entry.time)), el("span", null, changeTitle(entry.title_parts)), el("span", look, word), actions, opens());
  // The whole row opens the panel with the files it touched; the Undo button keeps to itself.
  li.tabIndex = 0;
  li.addEventListener("click", (event) => { if (!event.target.closest("button")) show(entry); });
  li.addEventListener("keydown", (event) => {
    if (event.target === li && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      show(entry);
    }
  });
  return li;
}

// Files and paths live here, not on the page.
function show(entry) {
  const body = el("div", "body");
  const steps = el("div", "stack");
  for (const step of entry.title_parts.steps) {
    const row = el("div", "layer");
    row.append(mark(step.client), el("div", "name", `${step.name} · ${SCOPE_WORDS[step.scope] || step.scope}`));
    steps.append(row);
  }
  body.append(steps);
  for (const path of entry.technical.paths) {
    const line = el("p", "why mono", shortPath(path));
    line.title = path;
    body.append(line);
  }
  const notes = notesSection("To take effect", entry.takes_effect.map((t) => ({ restart_note: t.note })));
  if (notes) body.append(notes);
  body.append(el("p", "muted", entry.history.map((e) => `${when(e.time)} ${(STATE_BADGES[e.state] || [e.state])[0]}`).join(" → ")));
  if (entry.technical.error) body.append(el("p", "muted", shortPaths(entry.technical.error)));
  const secret = backupNote(entry);
  if (secret) body.append(el("p", "muted", secret));
  // Undo from the panel closes it; the page then shows the undone row.
  const undo = () => { closePanel({ focus: false }); return undoChange(entry); };
  openChange(changeTitle(entry.title_parts), body, entry.state === "verified" ? undo : null);
}
