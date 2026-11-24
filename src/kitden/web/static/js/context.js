// Context: do the skills fit in what each client sends? (the context screen's prototype,
// design/kitden-context.html). The title, a chip per client with its lamp, a card per context
// window, the verdict, the zoom picture of the skill list, the two sides of skill pills, Details
// with a skill's switch, and "How this is counted". Every sentence and number comes from
// /api/context; the page only places them and names the parts of the picture. A switch only adds
// a `skill.rule` row to the tray, and the limit line on the skill list's bar, dragged or pressed,
// a `skill.limit` row with a place the server offers; the server then answers with the estimate
// after Apply.
import { detailsCard, followTray, keepFrom } from "./details.js";
import { chooseButton, offLine } from "./clients-choice.js";
import { button, el, reportError } from "./dom.js";
import { headActions } from "./map-page.js";
import { animateTo, fold, riseHead } from "./motion.js";
import { closePanel, openPanel, panelState, whenGone } from "./panel.js";
import { banner, CLIENT_NAMES, mark, skeleton } from "./parts.js";
import { current, currentError, data, loadContext, render, retry, setContextDraft, setState, state, takeArrival } from "./store.js";
import { addToTray, CONTEXT_NOTE, inTray, keyFor, onTray, ruleState, takeOut, tray, trayRow } from "./tray.js";

const TITLE = "Do your skills fit?";
const PILL_NUMBERS = "The number beside a skill is the length of its description, in characters.";
// The first words of an estimate stand out; a fact from the last chat has none.
const ESTIMATE = /^(After Apply, estimate:|Estimate:)/;

// The picture's own words; the rest is the server's.
const PICTURE = { window: "Context window", rest: "Rest of the window", list: "Skill list", sent: "Sent", free: "Free" };
const OVER = { claude_code: "Over the limit: not sent", codex: "Over the limit: cut off" };
const STATES = { on: "On", "name-only": "Name only", off: "Off" };
const HOW = "How this is counted";
// The skill list limit (specs skill-list-limit and limit-line-control): the limit line on the bar is
// its control, and Details explain it. The sentences, the places and their numbers are the server's.
const LIMIT = { kind: "Setting", title: "Skill list limit", now: "Now", offer: "Suggested", cost: "Cost", next: "Next chats", today: "Limit now" };
// The pointer snaps to the suggested place within SNAP of it, in % of the bar. The places past the
// furthest one the bar is drawn to (`reach`) share the bar's last part, not to scale: each sends
// the same list, and the readout gives their numbers.
const SNAP = 2;
const PAST_ROOM = 1.3;
// How far a press on the handle moves before it is a drag: less is a press that opens Details.
const DRAG_START = 4;
// The skill list's slice of the window strip, in %: a drawing, not a measure.
const SLICE = 2;

// The window each client shows, by client id; a client starts on its first window. `client`: the
// client drawn last, kept while the page draws again with no client in the address (Details
// closed). `open`: the skill whose Details show ({ client, name }). `hot`: the skill lit by the
// pointer. `marks`: name -> its pill and pieces. `draft`: the tray's skill states the last read
// asked with, as JSON. `bar`: where each piece of the picture was, to move it from there. `how`:
// "How this is counted" is open.
const page = { windows: {}, client: null, open: null, hot: null, marks: new Map(), draft: "{}", bar: { at: "", spots: new Map() }, how: false };

const fmt = (n) => n.toLocaleString("en-US");

// The client shown: the one in the address; else the one drawn last; else the first with an amber
// lamp (a problem to look at); else Claude Code.
function pickClient(cards) {
  const selected = state.selected;
  const name = selected ? (selected.kind === "client" ? selected.name : null) : page.client;
  const wanted = name ? cards.find((c) => c.client === name) : null;
  return wanted || cards.find((c) => c.lamp === "warn") || cards.find((c) => c.client === "claude_code") || cards[0];
}

const lampClass = (lamp) => (lamp === "ok" ? "lamp on" : lamp === "warn" ? "lamp warn" : "lamp");
// A window's lamp. The last chat's window (the first, when the client has a fact) takes the
// client's own lamp, so "cannot tell" is never green. An estimate is amber when its result has a
// misfit, green when it fits, grey with no limit.
function windowLamp(w, index, card) {
  if (index === 0 && card.fact) return card.lamp;
  return w.result.misfit ? "warn" : w.budget ? "ok" : "none";
}

function lampNode(lamp) {
  const node = el("i", lampClass(lamp));
  node.setAttribute("aria-hidden", "true");
  return node;
}

function chipFor(card, shown) {
  const chip = button("", () => {
    setState({ selected: { kind: "client", name: card.client } });
    // Details of another client's skill go with it.
    if (page.open && page.open.client !== card.client) closePanel({ keepSelection: true, focus: false });
    render();
  }, "ctx-client");
  chip.setAttribute("aria-label", CLIENT_NAMES[card.client] || card.client);
  chip.setAttribute("aria-pressed", String(card === shown));
  chip.classList.toggle("on", card === shown);
  chip.dataset.focus = `client:${card.client}`;
  chip.append(mark(card.client), el("span", null, CLIENT_NAMES[card.client] || card.client), lampNode(card.lamp));
  return chip;
}

function windowCard(w, index, shown, card) {
  const node = button("", () => {
    page.windows[card.client] = index;
    render();
  }, "ctx-win");
  node.setAttribute("aria-pressed", String(index === shown));
  node.classList.toggle("on", index === shown);
  node.dataset.focus = `window:${card.client}:${index}`;
  node.append(lampNode(windowLamp(w, index, card)), el("b", null, w.title), el("em", null, w.tag), el("small", null, w.models), el("span", "ctx-short", w.result.short));
  return node;
}

// A sentence of the verdict, its "Estimate:" start marked.
function sentence(say, className) {
  const node = el("p", className);
  const lead = say.match(ESTIMATE);
  if (lead) node.append(el("span", "ctx-est", lead[0]), say.slice(lead[0].length));
  else node.append(say);
  return node;
}

export function renderContext(main, { again = false } = {}) {
  if (!again) Object.assign(page, { client: null, bar: { at: "", spots: new Map() } });
  page.marks = new Map();
  // The title, with "Choose clients…" at its right, as the Library's head.
  const head = el("div", "page-head");
  head.append(el("h1", null, TITLE), headActions(chooseButton()));
  main.append(head);
  // Nothing here opens Details; the arrival of a link that picked a client is used up.
  takeArrival();
  const model = current("context");
  if (!model) {
    main.append(currentError("context") ? banner("the skill check", retry) : skeleton("card", 2));
    riseHead(head, null, null, { again });
    return;
  }
  const cards = model.clients;
  if (!cards.length) {
    main.append(el("p", "lede", "Kitden found no clients to check."));
    riseHead(head, null, null, { again });
    return;
  }
  const card = pickClient(cards);
  page.client = card.client;
  const lede = el("p", "lede", card.lede);
  const clients = el("div", "ctx-clients");
  clients.setAttribute("role", "group");
  clients.setAttribute("aria-label", "Client");
  clients.append(...cards.map((c) => chipFor(c, card)));
  main.append(lede);
  const off = offLine(data.clients);
  if (off) main.append(off);
  main.append(clients);
  riseHead(head, lede, clients, { again });
  // With the check failed there is no estimate: only the last chat's window, and no After Apply.
  const windows = card.checked ? card.windows : card.windows.slice(0, 1);
  const index = Math.min(page.windows[card.client] || 0, Math.max(0, windows.length - 1));
  if (windows.length) {
    const wins = el("div", "ctx-wins");
    wins.append(...windows.map((w, i) => windowCard(w, i, index, card)));
    main.append(wins);
  }
  const shown = windows[index];
  // The estimate after Apply is for the last chat's window, the first.
  const after = card.checked && index === 0 && shown ? card.after : null;
  // The verdict: the shown window's sentence (after Apply, the estimate), or the client's message
  // when it has no window. The room left (an estimate on the last chat's window) comes under it.
  main.append(sentence(shown ? (after ? after.say : shown.result.say) : card.message || "", "ctx-verdict"));
  // The limit changed after the last chat: said under its verdict, with what Kitden expects now.
  if (index === 0 && !after) for (const line of card.changed || []) main.append(sentence(line, "ctx-room"));
  if (shown && shown.result.room && !after) main.append(sentence(shown.result.room, "ctx-room"));
  // A message beside windows (the estimate could not be checked) is a note under the verdict.
  if (windows.length && card.message) main.append(el("p", "ctx-note", card.message));
  const result = shown ? (after ? after.result : shown.result) : null;
  const estimate = Boolean(after) || index > 0;
  const heat = heatOf(card, result, estimate);
  // The chat's own limit line stays where it is; a new limit shows as a second line (limitControl).
  if (shown) main.append(zoom(card, shown, result, `${card.client}:${index}`, heat, index === 0 ? controlOf(card) : null));
  if (card.skills.length) main.append(sidesFor(card, result, after, estimate, heat));
  if (card.how.length) main.append(howFor(card.how));
  markAll();
  followDraft();
}

// The zoom picture -----------------------------------------------------------------------------

// The context window as a thin strip whose small slice opens into the skill list's bar: a piece
// per skill as wide as what was sent, the names' characters as one piece, then past the limit
// line, hatched, what was not sent (Codex: cut off). The scale is the limit (or what was sent,
// when it is larger) plus what did not fit. A sent piece takes its skill's heat.
function zoom(card, w, r, at, heat, control = null) {
  const sent = r.sent || {};
  const over = r.over || {};
  const total = (part) => Object.values(part).reduce((sum, n) => sum + n, 0);
  const limit = w.budget || r.used;
  const top = Math.max(limit, r.used);
  // With the limit control, the bar also has room for the place that fits everything and for the
  // new limit, so the line can be dragged there; a place further right is past the bar's end.
  const reach = control ? control.reach : 0;
  const scale = Math.max(top + total(over), reach * (control && control.beyond ? PAST_ROOM : 1.04)) || 1;
  const pct = (n) => (n / scale) * 100;
  const spots = new Map();
  const place = (node, key, from, size) => {
    const spot = { left: `${pct(from)}%`, width: `${pct(size)}%` };
    Object.assign(node.style, spot);
    spots.set(key, { node, spot });
  };

  const box = el("div", "ctx-zoom");
  const strip = el("div", "ctx-window");
  const slice = el("i", "ctx-slice");
  slice.style.width = `${SLICE}%`;
  strip.append(slice, el("p", null, PICTURE.rest));
  const label = (text) => { const node = el("div", "ctx-zl"); node.append(el("span", null, text)); return node; };
  box.append(label(PICTURE.window), strip, link(pct(limit)), label(PICTURE.list));

  const hold = el("div", "ctx-hold");
  const bar = el("div", "ctx-bar");
  let used = 0;
  let past = top;
  for (const skill of card.skills) {
    for (const [kind, part] of [["sent", sent], ["over", over]]) {
      const size = part[skill.name];
      if (!size) continue;
      const piece = el("div", `ctx-seg ${kind}`);
      piece.dataset.skill = skill.name;
      place(piece, `${kind}:${skill.name}`, kind === "sent" ? used : past, size);
      if (kind === "sent") used += size;
      else past += size;
      if (kind === "sent" && heat.has(skill.name)) piece.style.setProperty("--heat", heat.get(skill.name));
      lights(piece, skill.name);
      piece.addEventListener("click", () => openSkill(card.client, skill.name));
      bar.append(piece);
    }
  }
  const names = r.used - total(sent);
  if (names > 0) {
    const piece = el("div", "ctx-seg names");
    place(piece, "names", used, names);
    bar.append(piece);
  }
  bar.setAttribute("aria-hidden", "true");
  hold.append(bar);
  if (w.budget) {
    const line = el("i", "ctx-limit");
    line.style.left = `${pct(limit)}%`;
    const flag = el("span", "ctx-flag", `Limit: ${fmt(w.budget)} ${card.unit}`);
    if (pct(limit) > 70) flag.style.right = "0";
    else flag.style.left = `calc(${pct(limit)}% + 8px)`;
    const chip = (word, middle) => {
      const node = el("span", "ctx-chip", word);
      node.style.left = `${middle}%`;
      return node;
    };
    const chips = [chip(PICTURE.sent, pct(Math.min(r.used, limit)) / 2)];
    if (total(over)) {
      // Past the limit line, clear of the handle: with the control, right after the hatched part
      // (the bar has room there); else in the middle of what is past the line.
      const node = chip(OVER[card.client] || OVER.claude_code, (pct(top) + 100) / 2);
      if (control && pct(top + total(over)) < 70) {
        node.style.left = `calc(${pct(top + total(over))}% + 8px)`;
        node.classList.add("after");
      }
      chips.push(node);
    }
    // Room left gets its word when there is room for the word.
    else if (limit - r.used > limit * 0.08) chips.push(chip(PICTURE.free, (pct(r.used) + 100) / 2));
    hold.append(line, ...chips, flag);
    if (control) limitControl(card, control, hold, pct, flag, limit);
  } else if (control) {
    // No limit line for the chat (its limit is not known): the control stands at today's limit.
    limitControl(card, control, hold, pct, null, null);
  }
  box.append(hold);
  moveFrom(at, spots);
  return box;
}

// The slice of the window strip widening into the skill list's bar up to its limit line.
function link(limitAt) {
  const SVG = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("class", "ctx-link");
  svg.setAttribute("viewBox", "0 0 100 44");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("aria-hidden", "true");
  const shape = document.createElementNS(SVG, "polygon");
  shape.setAttribute("points", `0,0 ${SLICE},0 ${limitAt},44 0,44`);
  svg.append(shape);
  return svg;
}

// The bar drawn again for the same window (a tray change, a new read): each piece moves from where
// it was, in 240 ms. A new piece fades in.
function moveFrom(at, spots) {
  const before = page.bar.at === at ? page.bar.spots : null;
  page.bar = { at, spots: new Map([...spots].map(([key, { spot }]) => [key, spot])) };
  if (!before) return;
  for (const [key, { node, spot }] of spots) {
    const was = before.get(key);
    if (!was) animateTo(node, [{ opacity: 0 }, { opacity: 1 }], { dur: 240 });
    else if (was.left !== spot.left || was.width !== spot.width) animateTo(node, [was, spot], { dur: 240 });
  }
}

// The two sides --------------------------------------------------------------------------------

// A skill's side: on the last chat's window, the server's; on an estimate (another window, or
// after Apply), from that estimate (Claude Code: a skill whose description is sent; Codex: one
// with nothing cut off). A skill on no side (not in the last list, or Kitden cannot tell) stays
// apart.
function sideOf(card, skill, result, estimate) {
  if (skill.side === null || skill.side === undefined || !estimate) return skill.side;
  if (card.client === "codex") return skill.name in (result.over || {}) ? 1 : 0;
  return skill.name in (result.sent || {}) ? 0 : 1;
}

// How warm each skill on the first side is, grey to orange: its size against the largest there,
// "0.00" to "1.00". The sizes to weigh at a glance; the other side stays grey.
function heatOf(card, result, estimate) {
  const states = draftFrom(current("context"))[card.client] || {};
  const first = card.skills.filter((s) => states[s.name] !== "off" && sideOf(card, s, result, estimate) === 0);
  const top = Math.max(0, ...first.map((s) => s.size));
  return new Map(first.map((s) => [s.name, (top ? s.size / top : 0).toFixed(2)]));
}

function sidesFor(card, result, after, estimate, heat) {
  const states = draftFrom(current("context"))[card.client] || {};
  const box = el("div", "ctx-sides");
  const clouds = card.sides.map((name, i) => {
    const side = el("section", i ? "ctx-side lo" : "ctx-side");
    if (card.client === "cursor") side.classList.add("calm");
    const head = el("h3");
    head.append(el("i"), el("span", null, name));
    const cloud = el("div", "ctx-cloud");
    side.append(head, cloud);
    box.append(side);
    return cloud;
  });
  const apart = el("div", "ctx-cloud ctx-apart");
  const off = el("div", "ctx-cloud");
  for (const skill of card.skills) {
    // A skill the tray turns off leaves the list.
    if (states[skill.name] === "off") continue;
    const side = sideOf(card, skill, result, estimate);
    // Not in the last list because it is off: it waits under Turned off, so it can come back.
    (clouds[side] || (skill.state === "off" ? off : apart)).append(pillFor(card, skill, states, after, heat, result));
  }
  const wrap = el("div");
  // What the number on a pill is: the same for every client (the Codex limit is in tokens, a pill's
  // number is always the description's characters).
  if (card.skills.some((s) => s.size)) wrap.append(el("p", "ctx-pillnote", PILL_NUMBERS));
  wrap.append(box);
  if (apart.children.length) wrap.append(apart);
  if (off.children.length) {
    const shelf = el("section", "ctx-off ctx-apart");
    shelf.setAttribute("aria-label", "Turned off");
    shelf.append(el("p", "ctx-off-head", "Turned off"), off);
    wrap.append(shelf);
  }
  return wrap;
}

// A skill's pill: its name and size, warmed by its heat on the first side; a cut one says how much
// of its description was sent. A dashed line while the tray changes it; after Apply, a skill that
// gets its description is filled, one that loses it is lit amber.
function pillFor(card, skill, states, after, heat, result) {
  const node = button("", () => openSkill(card.client, skill.name), "ctx-pill");
  node.dataset.skill = skill.name;
  if (heat.has(skill.name)) node.style.setProperty("--heat", heat.get(skill.name));
  node.dataset.focus = `skill:${card.client}:${skill.name}`;
  // A plugin's skill shows its plugin before its name, quieter ("venture:" and "review"); the hover
  // words and the name a screen reader hears carry both.
  if (skill.plugin) {
    node.append(el("span", "ctx-plug", `${skill.plugin}:`));
    node.setAttribute("title", skill.name);
  }
  node.append(el("span", null, skill.shown));
  // Built into Claude Code: no file, so no Library item. Said on the pill.
  if (skill.built_in) {
    node.classList.add("builtin");
    node.setAttribute("title", skill.source || "Built into Claude Code");
    node.append(el("i", "ctx-tag", "built-in"));
  }
  const kept = result && result.kept ? result.kept[skill.name] : undefined;
  if (skill.size && kept !== undefined) {
    const part = `${fmt(kept)} of ${fmt(skill.size)}`;
    const size = el("u", null, part);
    size.setAttribute("title", `${part} characters sent`);
    node.append(size);
  } else if (skill.size) node.append(el("u", null, fmt(skill.size)));
  const changed = skill.name in states && states[skill.name] !== skill.state;
  node.classList.toggle("chg", changed);
  node.classList.toggle("back", Boolean(after && after.gets.includes(skill.name)));
  node.classList.toggle("lost", Boolean(after && after.loses.includes(skill.name)));
  lights(node, skill.name);
  return node;
}

// One skill lit at a time: its pill and its pieces, by the pointer or the keyboard; the one whose
// Details show is marked too.
function lights(node, name) {
  page.marks.set(name, [...(page.marks.get(name) || []), node]);
  const on = () => light(name);
  const off = () => light(null);
  node.addEventListener("mouseenter", on);
  node.addEventListener("mouseleave", off);
  node.addEventListener("focus", on);
  node.addEventListener("blur", off);
}

function light(name) {
  page.hot = name;
  markAll();
}

function markAll() {
  const open = page.open && page.open.client === page.client ? page.open.name : null;
  for (const [name, nodes] of page.marks) {
    for (const node of nodes) {
      node.classList.toggle("hot", name === page.hot);
      node.classList.toggle("sel", name === open);
    }
  }
}

// Details and the switch -----------------------------------------------------------------------

// A skill's Details: its size, its source, its switch and the server's sentence on it. Drawn from
// the page's latest read, so they follow an Apply.
function openSkill(client, name) {
  const model = current("context");
  const card = model && model.clients.find((c) => c.client === client);
  const skill = card && card.skills.find((s) => s.name === name);
  if (!skill) return;
  // No size when Kitden could not read the description: 0 would be a claim.
  const facts = [];
  if (skill.size) facts.push({ label: "Size", value: `${fmt(skill.size)} characters` });
  if (skill.source) facts.push({ label: "Source", value: skill.source });
  const list = skill.switch.length ? switchFor(card, skill) : null;
  const content = detailsCard({ kind: "Skill", title: skill.shown, facts, list, why: skill.note, text: describe(skill) });
  openPanel(content);
  panelState.current = { type: "context-skill", client, name };
  keepFrom(() => openSkill(client, name), content);
  page.open = { client, name };
  whenGone(content[0], () => {
    page.open = null;
    markAll();
  });
  markAll();
}

// The skill's description from its file, the part the agent did not get in grey (`seen`: how
// many characters it got; null when it got all of it). None when Kitden could not read it.
function describe(skill) {
  if (!skill.description) return null;
  // By code point, as the server counts: an emoji is one character, not two.
  const chars = Array.from(skill.description);
  const box = el("section", "ctx-desc");
  box.setAttribute("aria-label", "Description");
  const shown = el("p", "ctx-desc-text");
  const cut = skill.seen != null && skill.seen < chars.length;
  shown.append(el("span", "", (cut ? chars.slice(0, skill.seen) : chars).join("")));
  if (cut) shown.append(el("span", "ctx-cut", chars.slice(skill.seen).join("")));
  box.append(el("p", "ctx-desc-head", "Description"), shown);
  if (cut) box.append(el("p", "ctx-desc-note", "Grey: the part the agent did not get."));
  return box;
}

// The row a state of this skill adds: for all projects, or for a project's own skill in its
// project (Claude Code takes it only there).
function ruleBody(card, skill, value) {
  const params = skill.project ? { scope: "project", project: skill.project, state: value } : { scope: "all", state: value };
  // A built-in skill has no item: the target is its name.
  const which = skill.built_in ? { built_in: skill.name } : { item: skill.item };
  return { action: "skill.rule", targets: [{ client: card.client, ...which }], params };
}

// The skill's states, the pressed one as the tray will leave it. A press adds the row (one row per
// skill, whatever its state); a press on the state it has now takes the row out.
function switchFor(card, skill) {
  const box = el("div", "seg ctx-switch");
  box.setAttribute("role", "group");
  box.setAttribute("aria-label", "State");
  const key = keyFor(ruleBody(card, skill, "off"));
  // Codex writes only `enabled = false`: a Codex skill that is off comes back by Undo in Changes,
  // so its switch shows Off and no On.
  const values = card.client === "codex" && skill.state === "off" ? skill.switch.filter((v) => v !== "on") : skill.switch;
  const parts = values.map((value) => {
    const node = button(STATES[value] || value, () => choose(card, skill, value), "");
    node.dataset.state = value;
    node.dataset.focus = `state:${value}`;
    return node;
  });
  box.append(...parts);
  followTray(box, key, () => {
    const row = trayRow(key);
    const now = row ? ruleState(row.body.params) : skill.state;
    for (const node of parts) {
      const on = node.dataset.state === now;
      node.setAttribute("aria-pressed", String(on));
      node.classList.toggle("pending", on && Boolean(row));
    }
  });
  return box;
}

function choose(card, skill, value) {
  const body = ruleBody(card, skill, value);
  if (value !== skill.state) return addToTray(body, { note: CONTEXT_NOTE });
  const key = keyFor(body);
  return inTray(key) ? takeOut(key) : null;
}

// The skill list limit ---------------------------------------------------------------------------

// The row a place adds: a value the server offered (a share, or "default", which takes the key out).
// `param` names it as the server's `limit.param` does.
export function limitBody(client, value, param = "fraction") {
  return { action: "skill.limit", targets: [{ client }], params: { [param]: value } };
}

// The value a row asks for, or undefined.
const rowValue = (row, param) => (row ? (row.body.params || {})[param] : undefined);

// One row per client, whatever its value: a press adds it (or puts this value in place of the
// other); a second press of the same value takes it out.
export function pickLimit(body, param = "fraction") {
  const key = keyFor(body);
  const row = trayRow(key);
  if (row && rowValue(row, param) === body.params[param]) return takeOut(key);
  return addToTray(body, { note: CONTEXT_NOTE });
}

function limitButton(client, choice, primary, param) {
  const body = limitBody(client, choice[param], param);
  const key = keyFor(body);
  const node = button(choice.label, () => pickLimit(body, param), primary ? "btn primary" : "btn");
  node.dataset.focus = `limit:${choice[param]}`;
  followTray(node, key, () => {
    const on = rowValue(trayRow(key), param) === choice[param];
    node.setAttribute("aria-pressed", String(on));
    node.classList.toggle("pending", on);
  });
  return node;
}

// What the limit control of a card works with, or null when the server offers nothing to change
// (the line then is only a picture). `steps`: the places, left to right; `at`: the place the new
// limit has now (the tray's row, else today's); `reach`: the limit the bar must have room for.
export function controlOf(card) {
  const limit = card.limit;
  if (!limit || !(limit.offer || limit.back)) return null;
  const param = limit.param || "fraction";
  const steps = limit.steps || [];
  const here = Math.max(0, steps.findIndex((s) => s.now));
  const row = trayRow(keyFor(limitBody(card.client, null, param)));
  const asked = steps.findIndex((s) => s.value === rowValue(row, param));
  const at = asked >= 0 ? asked : here;
  const offered = limit.offer ? steps.findIndex((s) => s.value === limit.offer[param]) : -1;
  const reach = Math.max(steps[at] ? steps[at].limit : 0, offered >= 0 ? steps[offered].limit : 0);
  const beyond = steps.filter((s) => s.limit > reach).length;
  return { client: card.client, param, steps, here, at, offered, reach, beyond, waits: Boolean(row) };
}

// The place a pointer leads to. `x`: the pointer in % of the bar. Within SNAP of the suggested place,
// the suggested place, unless today's place (or the default) is nearer: those can always be had.
export function stepAt(control, x, pct) {
  const spots = placesOf(control, pct);
  let best = 0;
  for (let i = 1; i < spots.length; i += 1) if (Math.abs(spots[i] - x) < Math.abs(spots[best] - x)) best = i;
  const fixed = control.steps[best] && (control.steps[best].now || control.steps[best].value === "default");
  if (!fixed && control.offered >= 0 && Math.abs(spots[control.offered] - x) <= SNAP) return control.offered;
  return best;
}

// Where each place is, in % of the bar: to scale up to `reach`, then spread evenly up to 98%.
function placesOf(control, pct) {
  const from = pct(control.reach);
  const room = Math.max(0, 98 - from);
  let past = 0;
  return control.steps.map((s) => (s.limit <= control.reach ? pct(s.limit) : from + (room * ++past) / control.beyond));
}

// The limit line as a control: a handle on the line where the new limit is (on the chat's own line
// until there is a new one), the flag beside it that opens Details, and while it moves a second line,
// "next chats", with the server's words for that place. Pointer and keys move it place by place; a
// release or Enter adds the row (or takes it out at today's limit); Esc puts it back. Nothing is read
// from the server meanwhile and the page is not drawn again: only these parts change.
function limitControl(card, control, hold, pct, flag, chatLimit) {
  const { steps } = control;
  const spot = (i) => (steps[i] ? Math.min(placesOf(control, pct)[i], 100) : 100);
  const grip = el("span", "ctx-grip");
  grip.setAttribute("role", "slider");
  grip.setAttribute("tabindex", "0");
  grip.setAttribute("aria-label", LIMIT.title);
  grip.dataset.tip = "";
  grip.dataset.focus = `limit:${card.client}`;
  if (steps.length) {
    grip.setAttribute("aria-valuemin", String(steps[0].limit));
    grip.setAttribute("aria-valuemax", String(steps.at(-1).limit));
  }
  const next = el("i", "ctx-next");
  const tag = el("span", "ctx-next-tag");
  const readout = el("span", "ctx-readout");
  readout.setAttribute("aria-hidden", "true");
  const mark = el("i", "ctx-mark");
  if (control.offered >= 0) mark.style.left = `${spot(control.offered)}%`;
  // Without a line of the chat's own, the flag says today's limit and goes where it is.
  if (!flag) {
    const today = steps[control.here];
    flag = el("span", "ctx-flag", today ? `${LIMIT.today}: ${fmt(today.limit)} ${card.unit}` : LIMIT.title);
    flag.style.left = `calc(${spot(control.here)}% + 8px)`;
    if (spot(control.here) > 70) Object.assign(flag.style, { left: "", right: "0" });
    hold.append(flag);
  }
  flag.classList.add("act");
  flag.addEventListener("click", () => openLimit(card.client));
  hold.classList.add("ctl");
  hold.append(next, tag, mark, readout, grip);

  // `shown`: the place drawn now; `moving`: a drag or keys moved it since the last commit.
  let shown = control.at;
  let moving = false;
  const differs = (i) => steps[i] && (chatLimit === null || steps[i].limit !== chatLimit);
  const draw = (i, live) => {
    const started = performance.now();
    shown = i;
    const left = `${spot(i)}%`;
    grip.style.left = left;
    const line = differs(i);
    next.hidden = !line;
    next.style.left = left;
    tag.hidden = !line || live;
    if (line) tag.textContent = `${LIMIT.next}: ${fmt(steps[i].limit)} ${card.unit}`;
    tag.style.left = left;
    tag.classList.toggle("end", spot(i) > 60);
    readout.hidden = !live || !steps[i];
    if (steps[i]) {
      readout.textContent = steps[i].say;
      readout.style.left = left;
      readout.classList.toggle("end", spot(i) > 60);
      grip.setAttribute("aria-valuenow", String(steps[i].limit));
      grip.setAttribute("aria-valuetext", steps[i].say);
    }
    mark.hidden = !live || control.offered < 0;
    next.classList.toggle("pending", control.waits && !live);
    if (live) performance.measure("kitden:limit-step", { start: started, end: performance.now() });
  };
  draw(control.at, false);

  // A release or Enter on place `i`: today's place takes the row out (or leaves it out), another
  // place adds its row unless that row waits already.
  const commit = (i) => {
    moving = false;
    const step = steps[i];
    draw(i, false);
    const key = keyFor(limitBody(card.client, null, control.param));
    if (!step || step.now) return trayRow(key) ? takeOut(key) : null;
    if (rowValue(trayRow(key), control.param) === step.value) return null;
    return addToTray(limitBody(card.client, step.value, control.param), { note: CONTEXT_NOTE });
  };
  const cancel = () => {
    moving = false;
    draw(control.at, false);
  };

  let press = null;
  grip.addEventListener("pointerdown", (event) => {
    if (event.button !== undefined && event.button !== 0) return;
    event.preventDefault();
    grip.focus();
    try { grip.setPointerCapture(event.pointerId); } catch { /* a pointer that is gone */ }
    press = { x: event.clientX, dragging: false };
  });
  grip.addEventListener("pointermove", (event) => {
    if (!press || !steps.length) return;
    if (!press.dragging && Math.abs(event.clientX - press.x) < DRAG_START) return;
    if (!press.dragging) {
      document.documentElement.classList.add("grabbing");
      // The tag takes the place under the handle where its hover words were: they stay off until
      // the pointer has left the handle and come back (tips.js).
      grip.dispatchEvent?.(new Event("quiettip", { bubbles: true }));
    }
    press.dragging = true;
    moving = true;
    const box = hold.getBoundingClientRect();
    const x = ((event.clientX - box.left) / (box.right - box.left)) * 100;
    const i = stepAt(control, x, pct);
    if (i !== shown || readout.hidden) draw(i, true);
  });
  const release = (event) => {
    if (!press) return;
    const was = press;
    press = null;
    document.documentElement.classList.remove("grabbing");
    if (event.type !== "pointerup") return cancel();
    if (!was.dragging) return openLimit(card.client);
    if (moving) commit(shown);
  };
  grip.addEventListener("pointerup", release);
  grip.addEventListener("pointercancel", release);
  grip.addEventListener("keydown", (event) => {
    const move = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[event.key];
    if (move && steps.length) {
      event.preventDefault();
      // The readout takes the place under the handle where its hover words were: they stay off, as
      // for a drag.
      if (!moving) grip.dispatchEvent?.(new Event("quiettip", { bubbles: true }));
      const i = Math.min(steps.length - 1, Math.max(0, shown + move));
      moving = moving || i !== control.at;
      draw(i, true);
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (moving && shown !== control.at) commit(shown);
      else if (!moving) openLimit(card.client);
      else cancel();
    } else if (event.key === "Escape" && (moving || press)) {
      event.preventDefault();
      event.stopPropagation();
      press = null;
      document.documentElement.classList.remove("grabbing");
      cancel();
    }
  });
  grip.addEventListener("blur", () => { if (moving && !press) cancel(); });
}

// Details of the skill list limit: the limit now, the share that fits every description and its
// cost, Set and Back; or why there is no share to offer. Drawn from the latest read, so they
// follow an Apply.
function openLimit(client) {
  const model = current("context");
  const card = model && model.clients.find((c) => c.client === client);
  const limit = card && card.limit;
  if (!limit) return;
  const facts = [];
  if (limit.now) facts.push({ label: LIMIT.now, value: limit.now });
  if (limit.offer) facts.push({ label: LIMIT.offer, value: limit.offer.say }, { label: LIMIT.cost, value: limit.offer.cost });
  const param = limit.param || "fraction";
  const choices = [limit.offer, limit.back].filter(Boolean);
  const actions = choices.map((choice) => ({ node: limitButton(client, choice, choice === limit.offer, param) }));
  // With nothing to raise, only the limit now and Back.
  const content = detailsCard({ kind: LIMIT.kind, title: LIMIT.title, facts, why: limit.offer ? limit.note : null, actions });
  openPanel(content);
  panelState.current = { type: "context-limit", client };
  keepFrom(() => openLimit(client), content);
}

// "How this is counted": folded, with the server's lines; it stays open across a redraw.
function howFor(lines) {
  const box = el("details", "ctx-how");
  const summary = el("summary", null, HOW);
  summary.addEventListener("click", () => { page.how = !box.open; });
  const list = el("ul");
  list.append(...lines.map((line) => el("li", null, line)));
  box.append(summary, list);
  box.open = page.how;
  return fold(box);
}

// The estimate after Apply ---------------------------------------------------------------------

// The tray's skill rules for the clients of `model`: client -> skill name -> state; and its
// skill list limits under `limits`: client -> Claude Code's share or Codex's tokens (or "default").
function draftFrom(model) {
  const draft = {};
  for (const { body } of tray.rows) {
    if (body.action === "skill.limit") {
      const params = body.params || {};
      const value = "tokens" in params ? params.tokens : params.fraction;
      for (const target of body.targets || []) (draft.limits ||= {})[target.client] = value;
      continue;
    }
    if (body.action !== "skill.rule") continue;
    for (const target of body.targets || []) {
      const card = model && model.clients.find((c) => c.client === target.client);
      const skill = card && card.skills.find((s) => (target.built_in ? s.built_in && s.name === target.built_in : s.item && s.item === target.item));
      if (skill) (draft[target.client] ||= {})[skill.name] = ruleState(body.params);
    }
  }
  return draft;
}

// Each read of the page sends the tray's skill states, so the server answers with the estimate
// after Apply.
setContextDraft(() => {
  const model = current("context");
  if (!model) return null;
  const draft = draftFrom(model);
  page.draft = JSON.stringify(draft);
  return draft;
});

// The tray changed (or the page drew a read made with other rows): while Context shows, it reads
// again with the rows as they are now, and draws the answer.
function followDraft() {
  const model = current("context");
  if (!model) return;
  const draft = JSON.stringify(draftFrom(model));
  if (draft === page.draft) return;
  page.draft = draft;
  if (state.view !== "context") return;
  loadContext().then(() => { if (state.view === "context") render(); }).catch(reportError);
}
onTray(followDraft);
