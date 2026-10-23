// Small parts shared by every place: sockets, client marks, flags, loading and error states.
import { $, button, el, joinWords, plural } from "./dom.js";
import { reducedMotion } from "./motion.js";

// The shared baseline: the picker's first choice, and the scope of what is set for every project.
export const ALL_PROJECTS = "All projects";
// The twin of views/words.py STATE_WORDS.
export const STATE_WORDS = {
  on: "Available", off: "Off", over: "Overridden", unk: "Unknown", gw: "Via gateway",
  missing: "Not installed", none: "—", via: "Via Claude Code", done: "Has its skills",
  unread: "Could not read",
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
// One client's checkbox in an Add form. Its name is the client's name (and the note after it),
// so a screen reader never says "on"; its value is the client id. `onChange` hears the new state.
export function clientCheck(client, checked, note, onChange) {
  const label = el("label");
  const box = el("input");
  box.type = "checkbox";
  box.value = client;
  box.checked = checked;
  box.setAttribute("aria-label", note ? `${CLIENT_NAMES[client]} · ${note}` : CLIENT_NAMES[client]);
  box.addEventListener("change", () => { if (onChange) onChange(box.checked); });
  label.append(box, el("span", null, CLIENT_NAMES[client]));
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
  if (where) node.append(el("span", "where", where));
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
    if (!still) parts.filter((p) => p.matches(".word, .where")).forEach((p) => p.classList.add("swap"));
    node.replaceChildren(...parts);
    if (!still) requestAnimationFrame(() => node.querySelectorAll(".swap").forEach((t) => t.classList.remove("swap")));
  };
  if (still) { swap(); return; }
  node.querySelectorAll(".word, .where").forEach((t) => t.classList.add("swap"));
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
  "setup_server.register": "Added show my setup",
  "setup_server.update": "Updated show my setup to Kitden",
  "gateway.rule": "Changed the rule for",
  "gateway.strict": "Changed strict mode for",
  "gateway.rules": "Changed the rules for",
  "gateway.remove": "Removed",
  "gateway.put_back": "Put back",
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

// The strict switch in words: the review's title and the line after the change.
export function strictText({ server, state }) {
  return { title: `Turn strict mode ${state} for ${server}`, done: `Turned strict mode ${state} for ${server}` };
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

// The badge of a change that did not check out. The engine's error ends with this sentence
// only when everything was put back as it was.
export function failedWord(error) {
  return (error || "").endsWith("The original settings were restored.") ? "Failed, put back" : "Failed";
}

// One line for a change log entry: what, which entries, which clients. Plugins go by their
// short name ("superpowers"); the review named the exact entry before Apply.
// A change whose backup or record keeps a secret says so on the Changes page.
export function backupNote(entry) {
  return entry.holds_secret ? "This change's backup or record holds a secret." : null;
}

export function changeTitle(entry) {
  // A tool rule names its tool, server, project and new state (the server adds them).
  if (entry.action === "gateway.rule" && entry.rule) return ruleText(entry.rule, entry.rule.project).done;
  // The strict switch: its first step is the server's mode; the others are its tools.
  if (entry.action === "gateway.strict" && entry.steps.length) return `${ACTION_WORDS[entry.action]} ${entry.steps[0].name} · Kitden gateway`;
  // The batch switch: its steps are the tools it changed.
  if (entry.action === "gateway.rules") return `${ACTION_WORDS[entry.action]} ${entry.steps.map((s) => s.name).join(", ")} · Kitden gateway`;
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
  if (entry.action === "skill.remove") {
    const { clients: lose, oneCopy } = skillRemoval(steps);
    return `${verb}${oneCopy ? " one copy of" : ""} ${names.join(", ")} · ${lose.map((c) => CLIENT_NAMES[c] || c).join(", ")}`;
  }
  // A plugin's skills can be many; the line counts them, the change lists them.
  if (entry.action === "plugin.skills") return `${verb} ${plural(names.length, "skill", "skills")} · ${clients.join(", ")}`;
  const whole = ["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update", "project.align"].includes(entry.action);
  const what = whole ? "" : ` ${names.join(", ")}`;
  if (kitden) return `${verb}${what} into the Kitden gateway · ${clients.join(", ")}`;
  return `${verb}${what} · ${clients.join(", ")}`;
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
