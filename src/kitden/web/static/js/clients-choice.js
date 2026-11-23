// Choose clients: which clients Kitden reads. Details lists each client with a switch. A switch
// acts at once: nothing of the client is written, so there is no preview and no Apply. The server
// saves the choice and reads again; the page reads everything again and draws.
import { postJson } from "./api.js";
import { detailsCard, keepFrom, switchNode } from "./details.js";
import { button, el, joinWords, reportError } from "./dom.js";
import { openPanel, panelState, toast } from "./panel.js";
import { CLIENT_NAMES, kitdenClients, mark, versionWords, WRITABLE } from "./parts.js";
import { detailsAgain, reloadAll, showEffect } from "./review.js";
import { data } from "./store.js";

export const CHOICE_KIND = "Clients";
export const CHOICE_TITLE = "Which clients Kitden reads";
export const CHOICE_NOTE = "Kitden stops reading a client that is off. Nothing in the client's own settings changes.";
export const LAST_ON = "Keep at least one client on.";

const STATUS_WORDS = { not_found: "Not found on this computer", unreadable: "Could not be read", off: "Off" };

// One row per client in client order: its words (the version, "Not found on this computer" or
// "Off"), whether its switch is on, whether it is the last one on (then the switch cannot turn
// off), and a quiet line when it uses the Kitden gateway. `progress`: the first scan's.
export function choiceRows(clients, setup, progress = null) {
  const { linked } = kitdenClients(setup);
  const known = (id) => (clients || []).find((c) => c.id === id);
  const on = WRITABLE.filter((id) => known(id) && known(id).status !== "off");
  return WRITABLE.filter(known).map((id) => {
    const client = known(id);
    const isOn = client.status !== "off";
    const words = STATUS_WORDS[client.status] || versionWords(client.version, progress, true);
    const gateway = isOn && linked.includes(id) ? `${CLIENT_NAMES[id]} uses the Kitden gateway. Turning it off here does not disconnect it.` : null;
    return { id, name: CLIENT_NAMES[id], words, on: isOn, last: isOn && on.length === 1, gateway };
  });
}

// The Details card: the rows, then one sentence. `press(id, on)` turns a client on or off.
export function choiceCard(clients, setup, press, progress = null) {
  const list = el("div", "sw-list client-rows");
  for (const row of choiceRows(clients, setup, progress)) {
    const label = `Kitden reads ${row.name}`;
    const node = switchNode(row.on, () => press(row.id, !row.on), null, label);
    node.dataset.focus = `client:${row.id}`;
    if (row.last) {
      node.disabled = true;
      node.title = LAST_ON;
    }
    const state = el("small", null, row.words);
    const words = el("div", "sw-tx");
    words.append(el("b", null, row.name), state);
    if (row.gateway) words.append(el("small", "note", row.gateway));
    const item = el("div", "sw-row");
    item.append(mark(row.id), words, node);
    list.append(item);
  }
  return { kind: CHOICE_KIND, title: CHOICE_TITLE, list, text: el("p", "muted", CHOICE_NOTE) };
}

// The sentence for the clients that are off ("Codex and Cursor are turned off in Kitden."), in
// client order, or null when none is off.
export function offWords(clients) {
  const list = Array.isArray(clients) ? clients : [];
  const off = WRITABLE.filter((id) => list.some((c) => c.id === id && c.status === "off"));
  if (!off.length) return null;
  return `${joinWords(off.map((id) => CLIENT_NAMES[id]))} ${off.length === 1 ? "is" : "are"} turned off in Kitden.`;
}

// A quiet line for a page that shows less because a client is off. Null when none is off. The
// button that opens the panel is in the page's head (chooseButton).
export function offLine(clients = data.clients) {
  const words = offWords(clients);
  return words ? el("p", "muted scope-note", words) : null;
}

// The page head's button that opens the panel, the same on every page that lists clients. It has a
// focus key, so a page drawn again while the panel is open still gives focus back to it.
export function chooseButton() {
  const choose = button("Choose clients…", showChoice, "btn");
  choose.dataset.focus = "choose:clients";
  return choose;
}

// Open the panel. A press draws it again from what the page read.
export function showChoice() {
  const nodes = detailsCard(choiceCard(data.clients, data.setupServer, turn, data.progress));
  panelState.current = { type: "clients" };
  keepFrom(showChoice, nodes);
  openPanel(nodes);
}

let turning = false;

// Turn a client on or off, read everything again and say so. Undo turns it back on.
export async function turn(client, on) {
  if (turning) return;
  turning = true;
  const name = CLIENT_NAMES[client];
  try {
    const result = await postJson("/api/clients/choice", { client, on });
    if (!result.ok) {
      toast((result.data && result.data.detail) || "Could not change this. Try again.");
      return;
    }
    await reloadAll();
    showEffect();
    await detailsAgain().catch(reportError);
    if (on) toast(`Kitden reads ${name} again.`, null, { ok: true });
    else toast(`Kitden no longer reads ${name}.`, () => turn(client, true), { ok: true });
  } catch (error) {
    reportError(error);
  } finally {
    turning = false;
  }
}
