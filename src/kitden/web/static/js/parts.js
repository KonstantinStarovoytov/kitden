// Small parts shared by every place: sockets, client marks, flags, loading and error states.
import { $, button, el, icon, joinWords, plural, shortPath } from "./dom.js";
import { animateTo, D, reducedMotion, rollTo } from "./motion.js";

// The shared baseline: the picker's first choice, and the scope of what is set for every project.
export const ALL_PROJECTS = "All projects";
// A picked project that left the list: it stays picked, and the place says this instead.
export const GONE_PROJECT = "This project is no longer on the list.";

// A folder's name, the last part of its path, as the picker and Details say it; "/" stays "/".
export const folderName = (path) => (path ? path.split("/").filter(Boolean).pop() || path : "");

// Actions whose title names its place already, or has none: no place words are added.
export const PLACE_IN_TITLE = ["gateway.rule", "gateway.rules", "gateway.strict", "project.align", "setup_server.register", "setup_server.update", "setup_server.enable", "client.disconnect", "gateway.move_out", "gateway.remove", "gateway.keychain"];

// Where a change's steps go (`target`, from the server), as a title ends: " in website",
// " for all projects", " for all projects except website" (that project's own definition wins
// there), or "" when they go to several places. `folder`: the project's name.
export function targetWords(target, folder = folderName(target && target.project)) {
  if (!target) return "";
  if (target.scope === "project") return ` in ${folder}`;
  if (target.scope === "others") return ` for all projects except ${folder}`;
  return target.scope === "all" ? " for all projects" : "";
}
// The project menu ---------------------------------------------------------------------------

const FIND_PROJECT = "Find a project…";

// The menu's rows: "All projects" first and always there, then each project by its folder name
// (no path), narrowed by `text`. `count`: "3 own rules" when the project has rules of its own.
// A picked project that left the list stays as a row of its own, so the menu never shows All
// projects for it.
export function menuItems(projects, picked, text = "") {
  const find = text.trim().toLowerCase();
  const all = { id: "", name: ALL_PROJECTS, sub: "What applies in every project", count: null, picked: picked === "" };
  const named = projects
    .map((p) => ({
      id: p.id,
      name: folderName(p.path),
      sub: p.exists ? null : "Folder missing",
      count: p.own_rules ? plural(p.own_rules, "own rule", "own rules") : null,
      picked: p.id === picked,
    }))
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
  if (picked && !projects.some((p) => p.id === picked)) {
    named.push({ id: picked, name: "No longer on the list", sub: null, count: null, picked: true });
  }
  return [all, ...named.filter((item) => item.name.toLowerCase().includes(find))];
}

// The option an arrow, Home or End moves to from option `at` of `count` (-1: none yet), or null
// for any other key. It stops at the ends.
export function optionAfter(key, at, count) {
  if (!count) return null;
  if (key === "ArrowDown") return Math.min(at + 1, count - 1);
  if (key === "ArrowUp") return at < 0 ? count - 1 : Math.max(at - 1, 0);
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

// The parts of one option row, in the project menu and in a Details choice: an icon (layers for
// All projects, a folder for a project), the name over its sub line, the count, and a check when
// `check` is set.
export function optionParts(item, check = false) {
  const text = el("span", "where-tx");
  text.append(el("span", "where-label", item.name));
  if (item.sub) text.append(el("span", "where-sub", item.sub));
  const parts = [item.id ? icon("folder", 14) : icon("layers", 14), text];
  if (item.count) parts.push(el("span", "where-count", item.count));
  if (check) parts.push(icon("check", 14, "ic where-check"));
  return parts;
}

// The picker's button: a folder icon, "Project", the picked project's name and a chevron. The page
// draws it, switched off, before the project list is read; projectMenu draws it again after.
export function projectButton(label) {
  const trigger = el("button", "where");
  trigger.id = "where";
  trigger.type = "button";
  const name = el("span", "where-name", label);
  name.id = "where-picked";
  trigger.append(icon("folder", 14), el("span", "where-word", "Project"), name, icon("chevron-down", 13, "ic where-caret"));
  // The label stays "Project"; the picked name is its description, so a screen reader hears both.
  for (const [key, value] of Object.entries({ "aria-label": "Project", "aria-haspopup": "listbox", "aria-expanded": "false", "aria-describedby": name.id })) {
    trigger.setAttribute(key, value);
  }
  return trigger;
}

// The project picker: its button and a menu under it with a find box and the options. Focus stays
// in the find box; the arrows move the active option, which `aria-activedescendant` names.
// `onPick(id)` hears the choice ("" is All projects). `from`: the name the button showed before a
// pick, so the new name rolls in from it.
export function projectMenu(projects, picked, onPick, from = null) {
  const root = el("div", "where-pick");
  root.fading = null; // a promise while the menu fades out, so the page can draw the picker after
  const label = menuItems(projects, picked).find((item) => item.picked).name;
  const trigger = projectButton(label);
  if (from && from !== label && !reducedMotion.matches) {
    const name = trigger.querySelector(".where-name");
    name.classList.add("roll");
    name.replaceChildren(el("span", null, from));
    rollTo(name, label);
  }

  const menu = el("div", "where-menu");
  menu.hidden = true;
  const list = el("div", "where-list");
  list.id = "where-list";
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", "Projects");
  const find = el("input", "where-find");
  find.type = "text";
  find.autocomplete = "off";
  find.spellcheck = false;
  for (const [key, value] of Object.entries({
    placeholder: FIND_PROJECT, "aria-label": FIND_PROJECT, role: "combobox", "aria-autocomplete": "list", "aria-controls": list.id, "aria-expanded": "true",
  })) find.setAttribute(key, value);
  menu.append(find, list);
  root.append(trigger, menu);

  let shown = [];
  let active = -1;
  let isOpen = false;
  const row = (item, at) => {
    const node = el("div", "where-option");
    node.id = `where-option-${at}`;
    node.setAttribute("role", "option");
    node.setAttribute("aria-selected", String(item.picked));
    node.append(...optionParts(item, item.picked));
    node.addEventListener("click", () => pick(item));
    return node;
  };
  function mark(at) {
    active = at;
    [...list.children].forEach((node, i) => node.classList.toggle("active", i === at));
    const node = list.children[at];
    if (node) {
      find.setAttribute("aria-activedescendant", node.id);
      node.scrollIntoView({ block: "nearest" });
    } else {
      find.removeAttribute("aria-activedescendant");
    }
  }
  // Typed text makes the first match active (All projects stays first but is not a match), and
  // Enter has nothing to pick when none matches. With no text, the picked project is active.
  function draw() {
    shown = menuItems(projects, picked, find.value);
    list.replaceChildren(...shown.map(row));
    mark(find.value.trim() ? (shown.length > 1 ? 1 : -1) : shown.findIndex((item) => item.picked));
  }
  // The menu shows first: a hidden list cannot scroll the picked project into view.
  function open() {
    find.value = "";
    isOpen = true;
    menu.hidden = false;
    // A fade-out that is still running ends here.
    for (const move of menu.getAnimations()) move.cancel();
    draw();
    trigger.setAttribute("aria-expanded", "true");
    document.addEventListener("pointerdown", outside);
    animateTo(menu, [{ opacity: 0, transform: "translateY(-8px) scale(.96)" }, { opacity: 1, transform: "none" }], { dur: 180 });
    find.focus();
  }
  function close(back) {
    if (!isOpen) return;
    isOpen = false;
    trigger.setAttribute("aria-expanded", "false");
    document.removeEventListener("pointerdown", outside);
    if (back) trigger.focus();
    fadeOut();
  }
  // The menu hides by time, not by the animation's end: a hidden tab may never finish one, and an
  // open in between cancels it. Only the latest fade hides the menu, and only if it is still closed.
  function fadeOut() {
    if (!D(140)) {
      menu.hidden = true;
      return;
    }
    animateTo(menu, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(-4px) scale(.98)" }], { dur: 140, ease: "ease-in", fill: "forwards" });
    const fade = new Promise((resolve) => {
      setTimeout(() => {
        if (root.fading === fade) {
          root.fading = null;
          if (!isOpen) menu.hidden = true;
        }
        resolve();
      }, D(140));
    });
    root.fading = fade;
  }
  function outside(event) {
    if (!root.contains(event.target)) close(false);
  }
  function pick(item) {
    if (!isOpen) return;
    close(true);
    onPick(item.id);
  }

  trigger.addEventListener("click", () => (isOpen ? close(true) : open()));
  trigger.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown") return;
    event.preventDefault();
    if (!isOpen) open();
  });
  find.addEventListener("input", draw);
  find.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      // Only the menu closes: Escape does not reach the page's own handler for Details.
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (event.key === "Tab") {
      close(false);
    } else if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      if (shown[active]) pick(shown[active]);
    } else {
      const to = optionAfter(event.key, active, shown.length);
      if (to === null) return;
      event.preventDefault();
      mark(to);
    }
  });
  // A press on the list must not take focus from the find box, or the menu would close first.
  list.addEventListener("mousedown", (event) => event.preventDefault());
  return root;
}

// The scope line under a page head: the shared setup, or a project and how many of its rules
// differ from it. `folder` is the project's folder name, "" with All projects. `count` is the
// project's own rules on this page, null when Kitden could not read them. Kitden counts only
// the rules this page has, so none is "no rules of its own": the rest of the project's setup
// may still differ.
export function scopeText(folder, count) {
  if (!folder) return "Shared setup · project overrides stay separate";
  if (count === null) return `Project ${folder} · rules not known`;
  if (count > 0) return `Project ${folder} · ${plural(count, "rule differs", "rules differ")} from the shared setup`;
  return `Project ${folder} · no rules of its own`;
}

// The icon says the scope too: layers for every project, a folder for one.
export function scopeBar(folder, count) {
  const bar = el("p", folder ? "scope-bar project" : "scope-bar");
  bar.append(folder ? icon("folder", 14) : icon("layers", 14), el("span", null, scopeText(folder, count)));
  return bar;
}

// The line at the bottom of the page (`.hint-line`, found by its id): an info icon and a few
// words. The words change at once; empty words hide the line.
export function setHint(text) {
  const line = document.getElementById("hint");
  line.replaceChildren();
  line.hidden = !text;
  if (text) line.append(icon("info", 13), el("span", null, text));
}

// The twin of views/words.py STATE_WORDS.
export const STATE_WORDS = {
  on: "On", off: "Off", over: "Overridden", unk: "Unknown", review: "Needs review", gw: "Via gateway",
  missing: "Not installed", none: "—", via: "Via Claude Code", done: "Has its skills",
  unread: "Could not read",
};
// The twin of views/words.py ORIGIN_WORDS: the tag of a cell in a project view. "This project":
// the project's own settings decide the cell. "Only this project": only that project has the item.
export const ORIGIN_WORDS = { override: "This project", project: "Only this project" };
// Where a Kitden gateway rule's state comes from, as a tool's or a server's Details says it:
// the rule for all projects, the default, or a strict server's new tool that waits. A project's
// own rule and a parent folder's name the folder (originText).
export const TOOL_ORIGIN_WORDS = { global: ALL_PROJECTS, default: "On by default", strict: "New · waits" };

// The "Comes from" words of a rule (`origin`, and `origin_from` for a parent folder). `folder` is
// the picked project's folder name. Null for an origin Kitden does not name.
export function originText({ origin, origin_from }, folder) {
  if (origin === "project") return `This project · ${folder}`;
  if (origin === "parent") return `From ${origin_from}`;
  return TOOL_ORIGIN_WORDS[origin] || null;
}
// The twin of views/words.py ROUTE_WORDS: how a client gets an item, said in Details and hover
// text. "{}" is the client whose folder it is.
export const ROUTE_WORDS = {
  desktop: "from the Desktop app", kitden: "through the Kitden gateway", plugin: "from a plugin",
  folder: "through {}'s folder",
};
// Why a change reaches Cursor too, in the server's words (views/words.py READS_FOLDER and
// LOADS_PLUGINS): a skill copy in Codex's or Claude Code's folder, or Claude Code's plugin.
export const REACH_NOTES = {
  codex: "Cursor reads Codex's folder",
  claude_code: "Cursor reads Claude Code's folder",
  plugin: "Cursor loads Claude Code's plugins",
};
// The first scan's line: what is still read, and how much of the work is done (0 to 1). Before
// the page has its data it names the clients it reads; then the slow answers still checked.
export function scanLine(view) {
  if (!view || !view.steps || !view.steps.length) return null;
  const open = view.steps.filter((step) => !step.done);
  if (!open.length) return null;
  const share = (view.steps.length - open.length) / view.steps.length;
  const named = open.filter((step) => Boolean(step.later) === Boolean(view.ready)).map((step) => step.name);
  const words = named.length ? named : open.map((step) => step.name);
  return { text: `${view.ready ? "Still checking" : "Reading"} ${joinWords(words)}…`, share };
}

// The first scan's later steps that change what a Library tab shows, with the line that tab
// shows above its table while the step runs. The top bar says "Still checking …"; this line
// says what it means here, in other words. Only Codex's plugin list changes a tab (the
// marketplaces step only reads ahead).
const SOURCE_LINES = {
  "Codex plugins": { kind: "plugin", text: "Codex plugins are still being read, so Codex's column may change." },
};
export function sourceLines(progress, kind) {
  const steps = (progress && progress.steps) || [];
  return steps
    .filter((step) => step.later && !step.done && SOURCE_LINES[step.name] && SOURCE_LINES[step.name].kind === kind)
    .map((step) => SOURCE_LINES[step.name].text);
}

// With no client found: each client Kitden looks for and the folder it checks, in client order.
const LOOKS_FOR = ["claude_code", "codex", "cursor"];
export function lookFor(clients) {
  return LOOKS_FOR.map((id) => (clients || []).find((c) => c.id === id)).filter(Boolean)
    .map((c) => ({ name: c.display_name, where: shortPath((c.config_roots || [])[0]) }));
}

// A client's version, or what is known of it: while the versions are still read in the
// background, a found client says "Checking the version…", never a false "version unknown".
// A client that is not installed keeps its own word.
function versionsOpen(progress) {
  const step = ((progress && progress.steps) || []).find((s) => s.name === "client versions");
  return Boolean(step && !step.done);
}
export function versionWords(version, progress, found) {
  if (version) return version;
  return found && versionsOpen(progress) ? "Checking the version…" : "version unknown";
}
// The versions step shows open for the first time, so a card drawn before it knew should say so.
export function versionsOpened(before, after) {
  return !versionsOpen(before) && versionsOpen(after);
}

// "gateway" is a registered gateway's own step; "kitden" is the Kitden gateway's settings file.
export const CLIENT_MARKS = {
  claude_code: "CC", codex: "CX", cursor: "CU", claude_desktop_code_tab: "CD", gateway: "GW", kitden: "GW",
};
// Icon file names under /static/brand/clients. Codex and Cursor also ship a "-dark" version.
export const CLIENT_ICONS = {
  claude_code: "claude", claude_desktop_code_tab: "claude", codex: "codex", cursor: "cursor",
};
export const DARK_ICONS = new Set(["codex", "cursor"]);
export const CLIENT_ORDER = ["claude_code", "claude_desktop_code_tab", "codex", "cursor"];
export const CLIENT_NAMES = {
  claude_code: "Claude Code", codex: "Codex", cursor: "Cursor",
  claude_desktop_code_tab: "Claude Desktop (Code tab)", gateway: "Gateway", kitden: "Kitden gateway",
};
// A checkbox: the real input, which keeps the keys and the screen reader, and the box drawn after
// it (.chk, with a check that springs in). CSS ticks the box from the input; both go in a label.
export function checkBox() {
  const input = el("input");
  input.type = "checkbox";
  const box = el("span", "chk");
  box.append(icon("check", 12));
  return [input, box];
}

// One client's checkbox in an Add form. Its name is the client's name (and the note after it),
// so a screen reader never says "on"; its value is the client id. `onChange` hears the new state.
export function clientCheck(client, checked, note, onChange) {
  const label = el("label");
  const [box, tick] = checkBox();
  box.value = client;
  box.checked = checked;
  box.setAttribute("aria-label", note ? `${CLIENT_NAMES[client]} · ${note}` : CLIENT_NAMES[client]);
  box.addEventListener("change", () => { if (onChange) onChange(box.checked); });
  label.append(box, tick, el("span", null, CLIENT_NAMES[client]));
  if (note) label.append(el("span", "muted", ` · ${note}`));
  return label;
}

// Which gateway an address belongs to, told from its path (the server does the same).
export function kindOf(url) {
  try {
    const path = new URL(url).pathname;
    if (path.startsWith("/metamcp/")) return "metamcp";
    if (path.startsWith("/mcp-connect/")) return "obot";
  } catch { /* not an address yet */ }
  return "other";
}

const KIND_NAMES = { metamcp: "MetaMCP", obot: "Obot" };

// The Kitden gateway has its own name; a registered one goes by its kind or its address.
export function gatewayName(gateway) {
  if (gateway.name) return gateway.name;
  const kind = gateway.kind || kindOf(gateway.url);
  if (KIND_NAMES[kind]) return KIND_NAMES[kind];
  try { return new URL(gateway.url).host || "Gateway"; } catch { return "Gateway"; }
}

// A move's steps that take an entry out of a client. The gateway's own steps and the kitden
// entry a move adds to a client are not servers.
const leavesClient = (s) => s.client !== "gateway" && s.client !== "kitden" && s.name !== "kitden";

// The servers a move takes, each once.
export function movedNames(steps) {
  return [...new Set(steps.filter(leavesClient).map((s) => s.name))];
}

// A move into a registered gateway has that gateway's own step; one into the Kitden gateway has
// none, also when the Kitden gateway holds the server already and only the entries go.
export function kitdenMove(change) {
  return change.action === "gateway.move" && !change.steps.some((s) => s.client === "gateway");
}

// A direct server, when no gateway here can take it: the Gateway page and Details say the same.
export const GATEWAY_NOTE = "Add the server in the gateway first, then remove its direct entry here.";

// The clients the Kitden gateway can reach.
const KITDEN_CLIENTS = ["claude_code", "codex", "cursor"];

// The Kitden gateway reaches a client through the client's `kitden` entry, when that entry is
// on (`linked`); an entry that is there but off is `off`. A client without the entry is offered
// to set it up; an old entry is updated. `entries` is the answer of /api/setup-server; without
// it (`known` false) the card says nothing about who connects. The Gateway card, Overview and
// the Affects line of a move use it.
export function kitdenClients(entries) {
  const linked = [];
  const off = [];
  const setup = [];
  for (const entry of entries || []) {
    if (!KITDEN_CLIENTS.includes(entry.client)) continue;
    if (entry.state === "added" || entry.state === "plugin") (entry.enabled === false ? off : linked).push(entry.client);
    const label = `Set up in ${CLIENT_NAMES[entry.client]}…`;
    if (entry.state === "missing") {
      setup.push({ client: entry.client, label, body: { action: "setup_server.register", targets: [{ client: entry.client }], params: {} } });
    } else if (entry.state === "old") {
      setup.push({ client: entry.client, label, body: { action: "setup_server.update", targets: [{ item: entry.item }], params: {} } });
    }
  }
  return { linked, setup, off, known: Boolean(entries) };
}

// `label` is what a screen reader hears for a dash: why nothing can be done, when known.
export function socket({ state, where, word, label, stale = false }) {
  // `stale`: kept from the last good read, drawn with a dashed dot.
  const node = el("span", stale ? `socket s-${state} stale` : `socket s-${state}`);
  if (state === "none") {
    node.append(el("span", "word faint", "—"));
    node.setAttribute("aria-label", label || "Not set up");
    return node;
  }
  const dot = el("span", "dot");
  dot.setAttribute("aria-hidden", "true");
  node.append(dot, el("span", "word", word || STATE_WORDS[state] || state));
  if (where) node.append(el("span", "tag", where));
  return node;
}

// Morph a socket to a new state: the words fade out, the new socket fades in, one ping.
// The socket is rebuilt, so "not set up" (no dot) and the other states swap cleanly.
// `next` takes what socket() takes, so a word or a dash's reason stays. With reduced motion the
// new words show at once.
export function morphSocket(node, next) {
  const still = reducedMotion.matches;
  const swap = () => {
    const fresh = socket(next);
    node.className = still ? fresh.className : `${fresh.className} pulse`;
    if (fresh.hasAttribute("aria-label")) node.setAttribute("aria-label", fresh.getAttribute("aria-label"));
    else node.removeAttribute("aria-label");
    // Keep the old dot when both have one, so its fill drains or fills instead of jumping.
    const oldDot = node.querySelector(".dot");
    const newDot = fresh.querySelector(".dot");
    if (oldDot && newDot) newDot.replaceWith(oldDot);
    const parts = [...fresh.childNodes];
    if (!still) parts.filter((p) => p.matches(".word, .tag")).forEach((p) => p.classList.add("swap"));
    node.replaceChildren(...parts);
    if (!still) requestAnimationFrame(() => node.querySelectorAll(".swap").forEach((t) => t.classList.remove("swap")));
  };
  if (still) { swap(); return; }
  node.querySelectorAll(".word, .tag").forEach((t) => t.classList.add("swap"));
  setTimeout(swap, 160);
}

export function mark(clientId) {
  const node = el("span", "mono-mark", CLIENT_MARKS[clientId] || "?");
  node.title = CLIENT_NAMES[clientId] || clientId;
  const icon = CLIENT_ICONS[clientId];
  if (icon) {
    // One rounded tile for every client; the vendor icon keeps its own colors.
    // Where the vendor offers a dark version, both are in the tile and CSS shows one.
    node.className = "client-mark";
    node.dataset.icon = icon;
    const image = (suffix, kind) => {
      const img = el("img", kind);
      img.src = `/static/brand/clients/${icon}${suffix}.png`;
      img.alt = "";
      img.width = 24;
      img.height = 24;
      img.addEventListener("error", () => {
        node.className = "mono-mark";
        node.textContent = CLIENT_MARKS[clientId] || "?";
      }, { once: true });
      return img;
    };
    node.replaceChildren(image("", "icon-light"));
    if (DARK_ICONS.has(icon)) {
      node.classList.add("has-dark");
      node.append(image("-dark", "icon-dark"));
    }
  }
  node.setAttribute("aria-hidden", "true");
  return node;
}

// "Applying 2 of 5" while a change with several steps runs; one step just says the verb.
export function stepText(verb, done, total) {
  return total > 1 ? `${verb} ${done} of ${total}` : `${verb}…`;
}

export function flag({ text, level }) {
  return el("span", level === "warning" ? "flag" : "flag info", text);
}

// In `kitden demo`, a quiet flag after the wordmark; its hover text says what the sample is.
export function demoTag(about) {
  if (!about?.demo) return null;
  const tag = el("span", "flag info", "Demo");
  tag.setAttribute("title", "A sample setup in a temporary folder. Your own settings are not read or changed.");
  return tag;
}

// The end of a row that opens Details: a chevron for the eye, words for a screen reader.
export function opens() {
  const node = el("span", "opens");
  const chevron = el("span", null, "›");
  chevron.setAttribute("aria-hidden", "true");
  node.append(chevron, el("span", "sr-only", "Open details"));
  return node;
}

export function skeleton(kind = "card", count = 3) {
  const box = el("div");
  box.setAttribute("aria-busy", "true");
  box.setAttribute("aria-label", "Loading");
  for (let i = 0; i < count; i += 1) box.append(el("div", `skeleton ${kind}`));
  return box;
}

const CONTROLS = "button:not([disabled]), a[href], select, input, textarea, summary, [tabindex]:not([tabindex='-1'])";

// The page is drawn again after a Retry, so this button is gone. Focus goes to the new Retry
// when the read failed again, otherwise to the first control on the page.
export function banner(what, onRetry) {
  const node = el("div", "banner");
  node.setAttribute("role", "alert");
  node.append(el("span", null, `Could not load ${what}.`), button("Retry", async () => {
    await onRetry();
    const main = $("#main");
    if (!main || main.contains(document.activeElement)) return;
    (main.querySelector(".banner button") || main.querySelector(CONTROLS) || main).focus();
  }));
  return node;
}

// A quiet note in the page, or an error that stays until the next action.
export function callout(text, level = "warn") {
  const box = el("div", level === "error" ? "callout error" : "callout");
  box.setAttribute("role", level === "error" ? "alert" : "note");
  const icon = el("span", null, "⚠");
  icon.setAttribute("aria-hidden", "true");
  box.append(icon, el("span", null, text));
  return box;
}

// Above a page whose latest read failed: the page still shows the read from that time.
export function staleNote(time) {
  const clock = new Date(time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const node = el("div", "callout stale");
  node.setAttribute("role", "note");
  const icon = el("span", null, "⚠");
  icon.setAttribute("aria-hidden", "true");
  node.append(icon, el("span", null, `Could not refresh. Showing what Kitden read at ${clock}.`));
  return node;
}

const ACTION_WORDS = {
  "gateway.connect": "Added gateway",
  "gateway.move": "Moved into the gateway",
  "gateway.switch": "Switched the gateway",
  "plugin.install": "Added",
  "marketplace.add": "Added marketplace",
  "skill.install": "Added skill",
  "plugin.skills": "Added",
  "mcp.remove_direct": "Removed",
  "plugin.enable": "Turned on",
  "plugin.disable": "Turned off",
  "plugin.remove": "Removed",
  "skill.remove": "Removed",
  "setup_server.register": "Connected to Kitden",
  "client.disconnect": "Disconnected from Kitden",
  "setup_server.update": "Updated show my setup to Kitden",
  "setup_server.enable": "Turned on the kitden entry",
  "gateway.rule": "Changed the rule for",
  "gateway.strict": "Changed strict mode for",
  "gateway.rules": "Changed the rules for",
  "gateway.remove": "Removed",
  "gateway.put_back": "Put back",
  "gateway.move_out": "Moved out of the gateway",
  "mcp.add": "Added",
  "project.align": "Added missing items",
};

// A Kitden gateway rule in words: "slow of echo in website", as the review's after line says
// it. `where` is the project's folder name, or null for all projects; `state` null removes the
// project's own rule. The review's title and the line after a change (the toast, the Changes page).
export function ruleText({ server, tool, state }, where) {
  const what = tool ? `${tool} of ${server}` : server;
  const place = where || "all projects";
  if (state === "on" || state === "off") return { title: `Turn ${state} ${what} in ${place}`, done: `Turned ${state} ${what} in ${place}` };
  // A removed rule: what the project then follows is in the review, not known when a line is read.
  return { title: `Remove the own setting for ${what} in ${place}`, done: `${what} in ${place}: own setting removed` };
}

// The batch switch in words: "Turn off 3 tools of github in website".
export function rulesText({ server, tools, state }, where) {
  const count = `${tools.length} ${tools.length === 1 ? "tool" : "tools"}`;
  const what = `${state} ${count} of ${server} in ${where || "all projects"}`;
  return { title: `Turn ${what}`, done: `Turned ${what}` };
}

// The strict switch in words: the review's title and the line after the change. It has no
// project rule, so it says it is for all projects, also in a project view.
export function strictText({ server, state }) {
  return { title: `Turn strict mode ${state} for ${server} in all projects`, done: `Turned strict mode ${state} for ${server} in all projects` };
}

// The clients a skill removal takes the skill from: those that read the folder and load no
// other copy. When every one of them keeps another copy, the words say "one copy" instead.
export function skillRemoval(steps) {
  const reached = [...new Set(steps.flatMap((s) => s.reaches || [s.client]))];
  const keeps = new Set(steps.flatMap((s) => s.keeps || []));
  const lose = reached.filter((c) => !keeps.has(c));
  const clients = (lose.length ? lose : reached).sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  return { clients, oneCopy: !lose.length };
}

// How many tools a server in the Kitden gateway adds, when Kitden knows: "12 tools".
export function toolsWord(server) {
  return server.tools ? plural(server.tools, "tool", "tools") : null;
}

// The tool count as a quiet node: small text in a row, a line in Details. Null when unknown.
export function toolsNode(server, inRow = false) {
  const word = toolsWord(server);
  return word ? el(inRow ? "small" : "div", inRow ? "meta" : "why", word) : null;
}

// The engine's error of a change that did not check out ends with this sentence only when
// everything was put back as it was.
export function allPutBack(error) {
  return (error || "").endsWith("The original settings were restored.");
}

// The badge of a change that did not check out.
export function failedWord(error) {
  return allPutBack(error) ? "Failed, put back" : "Failed";
}

// One line for a change log entry: what, which entries, which clients. Plugins go by their
// short name ("superpowers"); the review named the exact entry before Apply.
// A change whose backup or record keeps a secret says so on the Changes page.
export function backupNote(entry) {
  return entry.holds_secret ? "This change's backup or record holds a secret." : null;
}

// A server moved out of the gateway: the server, then the client that got its entry (the other
// steps are the gateway's own settings).
function moveOutTitle(entry) {
  const into = entry.steps.filter((s) => s.client !== "kitden").map((s) => CLIENT_NAMES[s.client] || s.client);
  return `${ACTION_WORDS[entry.action]} · ${entry.steps[0].name} · ${into.join(", ")}`;
}

export function changeTitle(entry) {
  // A tool rule names its tool, server, project and new state (the server adds them).
  if (entry.action === "gateway.rule" && entry.rule) return ruleText(entry.rule, entry.rule.project).done;
  // The strict switch: its first step is the server's mode; the others are its tools.
  if (entry.action === "gateway.strict" && entry.steps.length) return `${ACTION_WORDS[entry.action]} ${entry.steps[0].name} in all projects · Kitden gateway`;
  // The batch switch: its steps are the tools it changed.
  if (entry.action === "gateway.rules") return `${ACTION_WORDS[entry.action]} ${entry.steps.map((s) => s.name).join(", ")} · Kitden gateway`;
  if (entry.action === "gateway.move_out" && entry.steps.length) return moveOutTitle(entry);
  if (entry.action === "gateway.remove" && entry.steps.length) return `${ACTION_WORDS[entry.action]} ${entry.steps[0].name} from the Kitden gateway`;
  if (entry.action === "gateway.keychain" && entry.steps.length) return `Moved the secrets of ${entry.steps[0].name} to the Keychain`;
  const kitden = kitdenMove(entry);
  const verb = kitden ? "Moved" : ACTION_WORDS[entry.action] || entry.action;
  const plugin = ["plugin.enable", "plugin.disable", "plugin.install", "plugin.remove"].includes(entry.action);
  // The gateway's own step is not a client: the line names the clients the entry left. An
  // install's marketplace steps only make the plugin reachable: the line names the plugin.
  const steps = entry.action === "gateway.move"
    ? entry.steps.filter(leavesClient)
    : entry.steps.filter((s) => s.client !== "gateway" && (entry.action !== "plugin.install" || s.name.includes("@")));
  const names = [...new Set(steps.map((s) => (plugin ? s.name.split("@")[0] : s.name)))];
  // A copied skill folder reaches every client that reads that folder.
  const reached = [...new Set(steps.flatMap((s) => s.reaches || [s.client]))];
  reached.sort((a, b) => CLIENT_ORDER.indexOf(a) - CLIENT_ORDER.indexOf(b));
  const clients = reached.map((c) => CLIENT_NAMES[c] || c);
  // Where it went, as the review's title said it; a line from before Kitden kept it says none.
  const place = PLACE_IN_TITLE.includes(entry.action) ? "" : targetWords(entry.target);
  if (entry.action === "skill.remove") {
    const { clients: lose, oneCopy } = skillRemoval(steps);
    return `${verb}${oneCopy ? " one copy of" : ""} ${names.join(", ")}${place} · ${lose.map((c) => CLIENT_NAMES[c] || c).join(", ")}`;
  }
  // A plugin's skills can be many; the line counts them, the change lists them.
  if (entry.action === "plugin.skills") return `${verb} ${plural(names.length, "skill", "skills")}${place} · ${clients.join(", ")}`;
  const whole = ["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update", "setup_server.enable", "client.disconnect", "project.align"].includes(entry.action);
  const what = whole ? "" : ` ${names.join(", ")}`;
  if (kitden) return `${verb}${what} into the Kitden gateway${place} · ${clients.join(", ")}`;
  return `${verb}${what}${place} · ${clients.join(", ")}`;
}

// How many lines a diff adds and removes: the summary says so before the diff is opened.
export function diffCounts(text) {
  let added = 0;
  let removed = 0;
  for (const line of String(text || "").split("\n")) {
    if (line.startsWith("+++") || line.startsWith("---")) continue;
    if (line.startsWith("+")) added += 1;
    else if (line.startsWith("-")) removed += 1;
  }
  return { added, removed };
}

// The restart and log-in notes of a change's steps, each once, under a heading. Null when none.
export function notesSection(heading, steps) {
  const notes = [...new Set(steps.flatMap((s) => [s.restart_note, s.login_note && `Log in: ${s.login_note}`]).filter(Boolean))];
  if (!notes.length) return null;
  const section = el("section");
  const list = el("ul", "checklist");
  for (const note of notes) list.append(el("li", null, note));
  section.append(el("h2", null, heading), list);
  return section;
}

// The latest log line per change, newest first.
export function latestChanges(entries) {
  const seen = new Map();
  for (const entry of entries) if (!seen.has(entry.id)) seen.set(entry.id, entry);
  return [...seen.values()];
}

export { plural };
