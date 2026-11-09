// Context: do the skills fit in what each client sends? (the context screen's prototype,
// design/kitden-context.html). The title, a chip per client with its lamp, a card per context window
// and the verdict. Every sentence and number comes from /api/context; the page only places them.
import { button, el } from "./dom.js";
import { riseHead } from "./motion.js";
import { banner, CLIENT_NAMES, mark, skeleton } from "./parts.js";
import { current, currentError, render, retry, setState, state, takeArrival } from "./store.js";

const TITLE = "Do your skills fit?";
// The first words of an estimate stand out; a fact from the last chat has none.
const ESTIMATE = /^(After Apply, estimate:|Estimate:)/;

// The window each client shows, by client id; a client starts on its first window.
const page = { windows: {} };

// The client shown: the one in the address; else the first with an amber lamp (a problem to
// look at); else Claude Code.
function pickClient(cards) {
  const wanted = state.selected && state.selected.kind === "client" ? cards.find((c) => c.client === state.selected.name) : null;
  return wanted || cards.find((c) => c.lamp === "warn") || cards.find((c) => c.client === "claude_code") || cards[0];
}

const lampClass = (lamp) => (lamp === "ok" ? "lamp on" : lamp === "warn" ? "lamp warn" : "lamp");
// A window's lamp: amber when its result has a misfit, green when it fits, grey with no limit.
const windowLamp = (w) => (w.result.misfit ? "warn" : w.budget ? "ok" : "none");

function lampNode(lamp) {
  const node = el("i", lampClass(lamp));
  node.setAttribute("aria-hidden", "true");
  return node;
}

function chipFor(card, shown) {
  const chip = button("", () => {
    setState({ selected: { kind: "client", name: card.client } });
    render();
  }, "ctx-client");
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
  node.append(lampNode(windowLamp(w)), el("b", null, w.title), el("em", null, w.tag), el("small", null, w.models), el("span", "ctx-short", w.result.short));
  return node;
}

// The verdict: the shown window's sentence, or the client's message when it has no window.
function verdictNode(card, w) {
  const node = el("p", "ctx-verdict");
  const say = w ? w.result.say : card.message || "";
  const lead = say.match(ESTIMATE);
  if (lead) node.append(el("span", "ctx-est", lead[0]), say.slice(lead[0].length));
  else node.append(say);
  return node;
}

export function renderContext(main, { again = false } = {}) {
  const head = el("h1", null, TITLE);
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
  const lede = el("p", "lede", card.lede);
  const clients = el("div", "ctx-clients");
  clients.setAttribute("role", "group");
  clients.setAttribute("aria-label", "Client");
  clients.append(...cards.map((c) => chipFor(c, card)));
  main.append(lede, clients);
  riseHead(head, lede, clients, { again });
  const index = Math.min(page.windows[card.client] || 0, Math.max(0, card.windows.length - 1));
  if (card.windows.length) {
    const wins = el("div", "ctx-wins");
    wins.append(...card.windows.map((w, i) => windowCard(w, i, index, card)));
    main.append(wins);
  }
  main.append(verdictNode(card, card.windows[index]));
  // A message beside windows (the estimate could not be checked) is a note under the verdict.
  if (card.windows.length && card.message) main.append(el("p", "ctx-note", card.message));
}
