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
import { FOLD_ABOVE, groupLine, groupsOf, sideOf, turnedOn } from "./context-groups.js";
import { button, el, icon, reportError } from "./dom.js";
import { headActions } from "./map-page.js";
import { animateTo, fold, riseHead } from "./motion.js";
import { closePanel, openPanel, panelState, whenGone } from "./panel.js";
import { banner, CLIENT_NAMES, mark, skeleton } from "./parts.js";
import { current, currentError, data, go, goTo, loadContext, render, retry, setContextDraft, setState, state, takeArrival } from "./store.js";
import { addToTray, CONTEXT_NOTE, inTray, keyFor, onTray, ruleState, takeOut, tray, trayRow } from "./tray.js";

const TITLE = "Do your skills fit?";
const PILL_NUMBERS = "The number beside a skill is the length of its description, in characters.";
// The first words of an estimate stand out; a fact from the last chat has none.
const ESTIMATE = /^(After Apply, estimate:|Estimate:)/;

// The picture's own words; the rest is the server's.
const PICTURE = { window: "Context window", rest: "Rest of the window", list: "Skill list", now: "Skill list now, estimate", sent: "Sent", free: "Free" };
const OVER = { claude_code: "Over the limit: not sent", codex: "Over the limit: cut off" };
const STATES = { on: "On", "name-only": "Name only", off: "Off" };
const HOW = "How this is counted";
// The skill list limit (specs skill-list-limit and limit-line-control): the limit line on the bar is
// its control, and Details explain it. The sentences, the places and their numbers are the server's.
const LIMIT = { kind: "Setting", title: "Skill list limit", now: "Now", offer: "Suggested", cost: "Cost", next: "Next chats", today: "Limit now" };
// The pointer snaps to the suggested place within SNAP of it, in % of the bar. The places past the
// furthest one the bar is drawn to (`reach`) share the bar's last part, not to scale: each sends
// the same list, and the readout gives their numbers. Each of them has at least PAST_GAP % of the
// bar (about 15 px at 800 px, a little more than the handle is wide), so the twelve places of the
// list stay apart; the bar is drawn wider than `reach` by `roomFor` to make that room.
const SNAP = 2;
const PAST_ROOM = 1.3;
const PAST_MOST = 1.5;
const PAST_GAP = 3;
const PAST_END = 98;
// How far a press on the handle moves before it is a drag: less is a press that opens Details.
const DRAG_START = 4;
// The skill list's slice of the window strip, in %: a drawing, not a measure.
const SLICE = 2;

// The window each client shows, by client id; a client starts on its first window. `client`: the
// client drawn last, kept while the page draws again with no client in the address (Details
// closed). `open`: the skill whose Details show ({ client, name }). `hot`: the skill lit by the
// pointer. `marks`: name -> its pill and pieces. `draft`: the tray's skill states the last read
// asked with, as JSON. `bar`: where each piece of the picture was, to move it from there. `how`:
// "How this is counted" is open. `line`: where the limit line's parts stood last, to move them from
// there as the bar's pieces move.
// `groups`: per client, the keys of the groups opened (a group opens to its pills); `arrive`: the
// group a link from the Library opens, glows and focuses once ({ client, key }).
const page = { windows: {}, client: null, open: null, hot: null, marks: new Map(), draft: "{}", bar: { at: "", spots: new Map() }, line: { at: "", lefts: new Map() }, how: false, groups: {}, arrive: null, heads: new Map() };

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
  // A new visit starts with the groups as they start (groupsFor); a link's group opens.
  if (!again) Object.assign(page, { client: null, bar: { at: "", spots: new Map() }, line: { at: "", lefts: new Map() }, groups: {} });
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
  // With the check failed there is no estimate of another window: only the last chat's.
  const windows = card.checked ? card.windows : card.windows.slice(0, 1);
  const index = Math.min(page.windows[card.client] || 0, Math.max(0, windows.length - 1));
  if (windows.length) {
    const wins = el("div", "ctx-wins");
    wins.append(...windows.map((w, i) => windowCard(w, i, index, card)));
    main.append(wins);
  }
  const shown = windows[index];
  // The estimate after Apply is for the last chat's window, the first. With the check failed the
  // server may still count what all descriptions need (`limit.counted`).
  const counted = Boolean(card.limit && card.limit.counted && card.limit.counted.length);
  const after = (card.checked || counted) && index === 0 && shown ? card.after : null;
  // The verdict: the shown window's sentence (after Apply, the estimate), or the client's message
  // when it has no window. The room left (an estimate on the last chat's window) comes under it.
  main.append(sentence(shown ? (after ? after.say : shown.result.say) : card.message || "", "ctx-verdict"));
  // The limit or the skills changed after the last chat: said under its verdict, with what Kitden
  // expects now. The picture and the sides show that estimate; the verdict and the card stay the
  // chat's fact.
  if (index === 0 && !after) for (const line of card.changed || []) main.append(sentence(line, "ctx-room"));
  const now = index === 0 && !after && shown ? card.now || null : null;
  const room = shown && !after ? (now || shown.result).room : null;
  if (room) main.append(sentence(room, "ctx-room"));
  // A message beside windows (the estimate could not be checked) is a note under the verdict.
  if (windows.length && card.message) main.append(el("p", "ctx-note", card.message));
  // A count that does not fit everything cannot say which skills do: no result of its own, so the
  // picture and the sides stay the last chat's.
  const planned = after ? after.result : null;
  const result = shown ? planned || now || shown.result : null;
  const estimate = Boolean(planned || now) || index > 0;
  const heat = heatOf(card, result, estimate, Boolean(planned));
  // The chat's own limit line stays where it is; a new limit shows as a second line (limitControl).
  const look = { name: now ? PICTURE.now : PICTURE.list, room: planned ? after.budget : now ? now.budget : null, fact: !estimate };
  if (shown) main.append(zoom(card, shown, result, `${card.client}:${index}`, heat, index === 0 ? controlOf(card) : null, look));
  // Claude Code and Codex: the skills by where they come from. Cursor (and a card with no list to
  // read): the two sides.
  const grouped = shown && (card.groups || []).length;
  if (grouped) {
    const states = draftFrom(current("context"))[card.client] || {};
    const view = { result, base: now || shown.result, fact: card.windows[0].result, estimate, planned: Boolean(planned), states };
    main.append(groupsFor(card, view, after, heat));
  } else if (card.skills.length) main.append(sidesFor(card, result, after, estimate, heat));
  if (card.how.length) main.append(howFor(card.how));
  markAll();
  followDraft();
}

// The zoom picture -----------------------------------------------------------------------------

// The context window as a thin strip whose small slice opens into the skill list's bar: a piece
// per skill as wide as what was sent, the names' characters as one piece, then past the limit
// line, hatched, what was not sent (Codex: cut off). The scale is the limit (or what was sent,
// when it is larger) plus what did not fit. A sent piece takes its skill's heat.
// `name`: what the bar shows; `room`: the limit an estimate on the chat's window goes by; `fact`: the
// bar is the last chat's, so a skill off now has a piece there, drawn faded.
function zoom(card, w, r, at, heat, control = null, { name = PICTURE.list, room = null, fact = false } = {}) {
  const sent = r.sent || {};
  const over = r.over || {};
  const total = (part) => Object.values(part).reduce((sum, n) => sum + n, 0);
  const limit = w.budget || r.used;
  // What did not fit starts past the limit, or past the one the estimate goes by, lower or higher.
  const top = Math.max(room || limit, r.used);
  // With the limit control, the bar also has room for the place that fits everything and for the
  // new limit, so the line can be dragged there; a place further right is past the bar's end.
  const reach = control ? control.reach : 0;
  const scale = Math.max(top + total(over), limit, reach * roomFor(control ? control.beyond : 0)) || 1;
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
  box.append(label(PICTURE.window), strip, link(pct(limit)), label(name));

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
      if (fact && skill.state === "off") piece.classList.add("gone");
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
    if (control) limitControl(card, control, { hold, pct, flag, chatLimit: limit, chatLine: line, at });
  } else if (control) {
    // No limit line for the chat (its limit is not known): the control stands at today's limit.
    limitControl(card, control, { hold, pct, flag: null, chatLimit: null, chatLine: null, at });
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

// A skill's side: sideOf (context-groups.js).

// How warm each skill on the first side is, grey to orange: its size against the largest there,
// "0.00" to "1.00". The sizes to weigh at a glance; the other side stays grey.
function heatOf(card, result, estimate, planned) {
  const states = draftFrom(current("context"))[card.client] || {};
  const first = card.skills.filter((s) => states[s.name] !== "off" && sideOf(card, s, result, estimate, turnedOn(s, states), planned, states[s.name]) === 0);
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
  const off = [];
  const going = [];
  for (const skill of card.skills) {
    // A skill the tray turns off leaves the list: it waits under Off after Apply, with the rest of
    // its plugin when its plugin's switch turns it off.
    if (states[skill.name] === "off") {
      if (skill.state !== "off") going.push(skill);
      continue;
    }
    const back = turnedOn(skill, states);
    const side = sideOf(card, skill, result, estimate, back, Boolean(after && after.result), states[skill.name]);
    // Off now: it waits under Turned off, so it can come back, also where the page shows the last
    // chat's list, which still held it. The verdict and the bar keep that chat's fact.
    const out = skill.state === "off" && !back;
    if (out) off.push(skill);
    else (clouds[side] || apart).append(pillFor(card, skill, states, after, heat, result));
  }
  const wrap = el("div");
  // What the number on a pill is: the same for every client (the Codex limit is in tokens, a pill's
  // number is always the description's characters).
  if (card.skills.some((s) => s.size)) wrap.append(el("p", "ctx-pillnote", PILL_NUMBERS));
  wrap.append(box);
  if (apart.children.length) wrap.append(apart);
  if (going.length) wrap.append(shelfFor(card, OFF_SHELVES.going, going, states, after, heat, result));
  if (off.length) wrap.append(shelfFor(card, OFF_SHELVES.off, off, states, after, heat, result));
  return wrap;
}

// The shelves under the two sides: what the tray turns off, and what is off now.
const OFF_SHELVES = { going: { head: "Off after Apply", look: "ctx-off ctx-going" }, off: { head: "Turned off", look: "ctx-off" } };

// A shelf of skills that go off, or are off: those of one plugin together, on a line that names the
// plugin, how many skills go with it and its one switch (the way back, or the row that waits); the
// others as pills.
function shelfFor(card, { head, look }, skills, states, after, heat, result) {
  const shelf = el("section", `${look} ctx-apart`);
  shelf.setAttribute("aria-label", head);
  shelf.append(el("p", "ctx-off-head", head));
  const plugins = new Map();
  const alone = el("div", "ctx-cloud");
  for (const skill of skills) {
    const offer = skill.plugin_switch;
    if (offer) plugins.set(offer.item, [...(plugins.get(offer.item) || []), skill]);
    else alone.append(pillFor(card, skill, states, after, heat, result));
  }
  for (const members of plugins.values()) {
    const offer = members[0].plugin_switch;
    const row = el("div", "ctx-offplug");
    const name = members[0].plugin || pluginName(offer);
    row.setAttribute("role", "group");
    row.setAttribute("aria-label", name);
    const line = el("p", "ctx-offline");
    line.append(el("b", null, name), ` · ${members.length} ${members.length === 1 ? "skill" : "skills"}`);
    const cloud = el("div", "ctx-cloud");
    cloud.append(...members.map((skill) => pillFor(card, skill, states, after, heat, result)));
    row.append(line, pluginButton(offer), cloud);
    shelf.append(row);
  }
  if (alone.children.length) shelf.append(alone);
  return shelf;
}

// The plugin's switch as one small button: the same row as its skills' Details, saying what goes
// with it. `words`: its text, when shorter than its name ("Turn off" on a group's header).
function pluginButton(offer, { words = offer.label, className = "btn small", focus = "offplug" } = {}) {
  const body = { action: offer.action, targets: [{ item: offer.item }], params: {} };
  const key = keyFor(body);
  const node = button(words, () => (trayRow(key) ? takeOut(key) : addToTray(body, { note: CONTEXT_NOTE, goes: offer.goes || null })), className);
  if (words !== offer.label) node.setAttribute("aria-label", offer.label);
  node.dataset.focus = `${focus}:${offer.item}`;
  followTray(node, key, () => {
    const waits = Boolean(trayRow(key));
    node.setAttribute("aria-pressed", String(waits));
    node.classList.toggle("pending", waits);
  });
  return node;
}

// The groups -----------------------------------------------------------------------------------

// The words of a group's parts, and of a pill's state inside it.
const GROUP = { library: "Details in the Library", show: "Show the skills of", hide: "Hide the skills of", off: "Off", going: "Off after Apply" };

// The skills by where they come from: a group per source, largest first (groupsOf), each with its
// header (the name, what it takes, its switch) and its pills. More than a few start closed; the
// ones a person opened stay open across a redraw.
function groupsFor(card, view, after, heat) {
  const wrap = el("div", "ctx-grouped");
  if (card.skills.some((s) => s.size)) wrap.append(el("p", "ctx-pillnote", PILL_NUMBERS));
  const all = groupsOf(card, view);
  if (!(card.client in page.groups)) page.groups[card.client] = new Set(all.length <= FOLD_ABOVE ? all.map((f) => f.group.key) : []);
  const opened = page.groups[card.client];
  // A link's group: opened and lit for the draws of its first moments (the page reads again as it
  // arrives), focused once.
  const link = page.arrive && page.arrive.client === card.client && performance.now() < page.arrive.until ? page.arrive : null;
  const arrive = link ? link.key : null;
  if (arrive) opened.add(arrive);
  const focus = Boolean(link && !link.focused);
  if (link) link.focused = true;
  const list = el("div", "ctx-groups");
  page.heads = new Map();
  all.forEach((facts, i) => list.append(groupNode(card, facts, view, after, heat, opened, `ctx-g-${card.client}-${i}`, facts.group.key === arrive, focus)));
  wrap.append(list);
  return wrap;
}

function groupNode(card, facts, view, after, heat, opened, id, arrived, focus) {
  const { group } = facts;
  const open = opened.has(group.key);
  const box = el("section", `ctx-group ${facts.state}`);
  box.dataset.group = group.key;
  box.setAttribute("aria-label", group.name);
  // The header: the toggle, the name (the Library's Details of a plugin), the marketplace, what the
  // group takes, and the group's switch. A press anywhere else on it opens or closes the group too.
  const head = el("div", "ctx-ghead");
  const line = groupLine(card, facts, view.estimate);
  const toggle = button("", () => setOpen(!opened.has(group.key)), "ctx-gtoggle");
  toggle.dataset.focus = `group:${card.client}:${group.key}`;
  page.heads.set(group.key, toggle);
  toggle.setAttribute("aria-controls", id);
  toggle.append(icon("chevron-right", 14));
  const name = group.lookup ? button(group.name, () => openInLibrary(group), "ctx-gname act") : el("span", "ctx-gname", group.name);
  if (group.lookup) {
    name.setAttribute("title", GROUP.library);
    name.setAttribute("aria-label", `${group.name}: ${GROUP.library}`);
    name.dataset.focus = `library:${card.client}:${group.key}`;
  }
  const meta = el("span", "ctx-gmeta");
  line.forEach((part, i) => {
    const tag = i === 0 && (facts.state === "off" || facts.state === "going" || facts.state === "back");
    const short = Boolean(facts.short) && /only a name|cut short/.test(part);
    meta.append(el("span", tag ? "ctx-gstate" : short ? "ctx-gshort" : null, part));
  });
  head.append(toggle, name);
  if (group.from) head.append(el("span", "ctx-gfrom", group.from));
  head.append(meta);
  if (group.switch) head.append(groupSwitch(group.switch));
  head.addEventListener("click", (event) => { if (!event.target || !event.target.closest || !event.target.closest("button")) setOpen(!opened.has(group.key)); });
  // The pills: sent first, then only a name or cut, then in no list, then off.
  const body = el("div", "fold ctx-gbody");
  body.id = id;
  const inner = el("div", "fold-in");
  if (group.why) inner.append(el("p", "ctx-gwhy", group.why));
  const cloud = el("div", "ctx-cloud");
  const order = { sent: 0, lo: 1, apart: 2, going: 3, off: 4 };
  const members = [...facts.members].sort((a, b) => order[a.look] - order[b.look]);
  // A pill says Off, or Off after Apply, where its header does not say it for the whole group.
  const whole = facts.state === "off" || facts.state === "going";
  cloud.append(...members.map((m) => pillFor(card, m.skill, view.states, after, heat, view.result, m.look, whole)));
  inner.append(cloud);
  body.append(inner);
  box.append(head, body);
  // Lights the group's pieces on the bar while the pointer or the focus is on its header.
  for (const node of [toggle, head]) {
    node.addEventListener("mouseenter", () => light(group.skills));
    node.addEventListener("mouseleave", () => light(null));
  }
  toggle.addEventListener("focus", () => light(group.skills));
  toggle.addEventListener("blur", () => light(null));
  const show = (now) => {
    toggle.setAttribute("aria-expanded", String(now));
    toggle.setAttribute("aria-label", `${now ? GROUP.hide : GROUP.show} ${group.name}: ${line.join(", ")}`);
    box.classList.toggle("open", now);
    body.classList.toggle("open", now);
    inner.inert = !now;
  };
  function setOpen(now) {
    if (now) opened.add(group.key);
    else opened.delete(group.key);
    show(now);
  }
  show(open);
  if (arrived) box.classList.add("arrive");
  if (arrived && focus) {
    requestAnimationFrame(() => {
      if (box.scrollIntoView) box.scrollIntoView({ block: "nearest" });
      // The header drawn last: the page may have been drawn again meanwhile.
      (page.heads.get(facts.group.key) || toggle).focus();
    });
  }
  return box;
}

// The group's switch on its header: the plugin's own, the same row as its Details and the Library
// add (one row, `switch:<item>`); a second press takes it out.
function groupSwitch(offer) {
  const words = offer.action === "plugin.disable" ? "Turn off" : "Turn on";
  return pluginButton(offer, { words, className: "btn small ctx-gswitch", focus: "gswitch" });
}

// The Library with the group's plugin selected: it opens the same Details as there. Back returns.
function openInLibrary(group) {
  closePanel({ keepSelection: true, focus: false });
  goTo("library", { kind: "plugin", name: group.lookup });
}

// Context on a client's group, opened, lit and focused: the Library's link to it.
// The time it stays lit, as the Library's own arrival glows.
const ARRIVE_MS = 1200;
export function openContextGroup(client, key) {
  page.arrive = { client, key, until: performance.now() + ARRIVE_MS, focused: false };
  go("context", { selected: { kind: "client", name: client } });
}

// A skill's pill: its name and size, warmed by its heat on the first side; a cut one says how much
// of its description was sent. A dashed line while the tray changes it; after Apply, a skill that
// gets its description is filled, one that loses it is lit amber.
function pillFor(card, skill, states, after, heat, result, look = null, whole = false) {
  const node = button("", () => openSkill(card.client, skill.name), "ctx-pill");
  // In a group (`look`): only a name (or cut), in no list, off now, or going off after Apply.
  if (look && look !== "sent") node.classList.add(look);
  node.dataset.skill = skill.name;
  if (heat.has(skill.name)) node.style.setProperty("--heat", heat.get(skill.name));
  node.dataset.focus = `skill:${card.client}:${skill.name}`;
  // A plugin's skill shows its plugin before its name, quieter ("venture:" and "review"), unless
  // its group says it; the hover words and the name a screen reader hears carry both.
  if (skill.plugin) {
    if (!look) node.append(el("span", "ctx-plug", `${skill.plugin}:`));
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
  if ((look === "off" || look === "going") && !whole) node.append(el("i", "ctx-tag", look === "off" ? GROUP.off : GROUP.going));
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

// `name`: one skill's name, a group's names, or null.
function light(name) {
  page.hot = name;
  markAll();
}

function markAll() {
  const open = page.open && page.open.client === page.client ? page.open.name : null;
  for (const [name, nodes] of page.marks) {
    for (const node of nodes) {
      node.classList.toggle("hot", Array.isArray(page.hot) ? page.hot.includes(name) : name === page.hot);
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
  // A plugin's skill names its plugin first: its switch is the plugin's, not the skill's.
  const plugin = !skill.switch.length && skill.plugin_switch ? skill.plugin || pluginName(skill.plugin_switch) : null;
  if (plugin) facts.push({ label: "Plugin", value: plugin });
  if (skill.size) facts.push({ label: "Size", value: `${fmt(skill.size)} characters` });
  if (skill.source) facts.push({ label: "Source", value: skill.source });
  const list = skill.switch.length ? switchFor(card, skill) : skill.plugin_switch ? pluginSwitch(skill.plugin_switch, plugin) : null;
  const content = detailsCard({ kind: "Skill", title: skill.shown, facts, list, why: plugin ? null : skill.note, text: describe(skill) });
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

// The plugin's name from its switch's label ("Turn off plug").
const pluginName = (offer) => offer.label.replace(/^Turn (off|on) /, "");

// A plugin skill's plugin: whose switch it is, the server's sentence on what goes with it, and one
// button that adds the Library's own row for the plugin (a second press takes it out). The row says
// what goes with it too. `plugin`: the plugin's name, for the line that says the switch is its.
function pluginSwitch(offer, plugin = null) {
  const box = el("div", "ctx-plugin");
  const body = { action: offer.action, targets: [{ item: offer.item }], params: {} };
  const key = keyFor(body);
  const node = button(offer.label, () => (trayRow(key) ? takeOut(key) : addToTray(body, { note: CONTEXT_NOTE, goes: offer.goes || null })), "btn");
  node.dataset.focus = `plugin:${offer.item}`;
  followTray(node, key, () => {
    const waits = Boolean(trayRow(key));
    node.setAttribute("aria-pressed", String(waits));
    node.classList.toggle("pending", waits);
  });
  if (plugin) box.append(el("p", "why", `The switch is ${plugin}'s: it turns the whole plugin ${offer.action === "plugin.disable" ? "off" : "on"}, not one skill.`));
  if (offer.say) box.append(el("p", "why", offer.say));
  box.append(node);
  return box;
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

// What the limit control of a card works with, or null when the server offers nothing to change and
// gives no places (the line then is only a picture; while changes wait it can have places with
// nothing to suggest). `steps`: the places, left to right; `at`: the place the new
// limit has now (the tray's row, else today's); `reach`: the limit the bar must have room for, never
// less than today's limit and the chat's own, so every place up to them is to scale.
export function controlOf(card) {
  const limit = card.limit;
  if (!limit || !(limit.offer || limit.back || (limit.steps || []).length)) return null;
  const param = limit.param || "fraction";
  const steps = limit.steps || [];
  const here = Math.max(0, steps.findIndex((s) => s.now));
  const row = trayRow(keyFor(limitBody(card.client, null, param)));
  const asked = steps.findIndex((s) => s.value === rowValue(row, param));
  const at = asked >= 0 ? asked : here;
  const offered = limit.offer ? steps.findIndex((s) => s.value === limit.offer[param]) : -1;
  const chat = (card.windows && card.windows[0] && card.windows[0].budget) || 0;
  const limits = [at, offered, here].map((i) => (steps[i] ? steps[i].limit : 0));
  const reach = Math.max(chat, ...limits);
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

// How much wider than `reach` the bar is drawn, with `beyond` places past it: 4% more for a picture
// of the place itself, else PAST_ROOM, or more to give each place past it PAST_GAP % of the bar
// (up to PAST_MOST: Codex's twenty places keep most of the bar to scale).
export function roomFor(beyond) {
  if (!beyond) return 1.04;
  return Math.min(PAST_MOST, Math.max(PAST_ROOM, 100 / (PAST_END - PAST_GAP * beyond)));
}

// Where each place is, in % of the bar: to scale up to `reach`, then spread evenly up to 98%.
export function placesOf(control, pct) {
  const from = pct(control.reach);
  const room = Math.max(0, PAST_END - from);
  let past = 0;
  return control.steps.map((s) => (s.limit <= control.reach ? pct(s.limit) : from + (room * ++past) / control.beyond));
}

// The limit line as a control: a handle on the line where the new limit is (on the chat's own line
// until there is a new one), the flag beside it that opens Details, and while it moves a second line,
// "next chats", with the server's words for that place. Pointer and keys move it place by place; a
// release or Enter adds the row (or takes it out at today's limit); Esc puts it back. Nothing is read
// from the server meanwhile and the page is not drawn again: only these parts change. While it
// moves, the handle, the line, its tag and the readout glide to each place (style.css); when the bar
// is drawn again for the same window, they and the chat's line move from where they stood, in 240 ms
// as the bar's pieces do. `chatLine`: the chat's own limit line; `at`: the window drawn.
function limitControl(card, control, { hold, pct, flag, chatLimit, chatLine, at }) {
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
  // Where each part stands, for the next time the bar is drawn; a hidden part, or the flag at the
  // bar's right end, stands nowhere and just shows then. `carried`: a carry from the last draw runs.
  const parts = { grip, next, tag, readout, ...(chatLine ? { line: chatLine } : {}), ...(flag && !flag.style.right ? { flag } : {}) };
  const before = page.line.at === at ? page.line.lefts : new Map();
  const lefts = new Map();
  page.line = { at, lefts };
  const note = () => {
    for (const [key, node] of Object.entries(parts)) {
      if (node.hidden) lefts.delete(key);
      else lefts.set(key, node.style.left);
    }
  };
  let carried = false;
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
    if (live && carried) {
      // A move cuts the carry short, so the handle follows the pointer at once. A CSS transition
      // (the glide) has a transitionProperty; the carry does not.
      carried = false;
      for (const node of Object.values(parts)) for (const move of node.getAnimations?.() || []) if (!move.transitionProperty) move.cancel();
    }
    note();
    if (live) performance.measure("kitden:limit-step", { start: started, end: performance.now() });
  };
  draw(control.at, false);
  for (const [key, node] of Object.entries(parts)) {
    const was = before.get(key);
    const now = node.style.left;
    if (node.hidden || was === undefined || was === now) continue;
    animateTo(node, [{ left: was }, { left: now }], { dur: 240 });
    carried = true;
  }

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
  // The server's quiet lines: the numbers are a count, not a replay of the chat's list, or skills
  // the chat did not list are counted too.
  let text = null;
  if (limit.counted && limit.counted.length) {
    text = el("section", "ctx-desc");
    text.append(...limit.counted.map((line) => el("p", "ctx-desc-note ctx-counted", line)));
  }
  // With nothing to raise, only the limit now and Back.
  const content = detailsCard({ kind: LIMIT.kind, title: LIMIT.title, facts, why: limit.offer ? limit.note : null, text, actions });
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
// A plugin's own switch, from Context or the Library (one row, `switch:<item>`), sets each skill
// that follows that plugin.
function draftFrom(model) {
  const draft = {};
  for (const { body } of tray.rows) {
    if (body.action === "plugin.disable" || body.action === "plugin.enable") {
      const item = (body.targets || [])[0]?.item;
      const value = body.action === "plugin.disable" ? "off" : "on";
      for (const card of (model && model.clients) || []) {
        for (const skill of card.skills) if (skill.plugin_switch && skill.plugin_switch.item === item) (draft[card.client] ||= {})[skill.name] = value;
      }
      continue;
    }
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
