// Agents: add the Kitden "show my setup" MCP server to a client, update an old entry, or show
// that the kitden plugin already provides it (feature 003).
import { button, el } from "./dom.js";
import { entrance } from "./motion.js";
import { review } from "./panel.js";
import { banner, CLIENT_NAMES, mark, skeleton, socket } from "./parts.js";
import { data, retry } from "./store.js";

// The old entry was made by the working version, called agentsetup (feature 002).
function update(item) {
  return review({ action: "setup_server.update", targets: [{ item }], params: {} });
}

function cell(entry) {
  const box = el("div", "cell");
  const top = el("div", "who");
  top.append(mark(entry.client), el("strong", null, CLIENT_NAMES[entry.client]));
  box.append(top);
  if (entry.state === "not_installed") {
    box.append(socket({ state: "missing" }));
  } else if (entry.state === "added") {
    box.append(entry.enabled === false ? socket({ state: "off", word: "Added, off" }) : socket({ state: "on", word: "Added" }));
    if (entry.item) box.append(el("span", "muted", "An old entry is still there."), button("Remove old entry…", () => update(entry.item)));
  } else if (entry.state === "plugin") {
    box.append(entry.enabled === false ? socket({ state: "off", word: "Plugin, off" }) : socket({ state: "on", word: "Plugin" }));
    box.append(el("span", "muted", "Provided by the kitden plugin."));
    if (entry.item) box.append(el("span", "muted", "An old entry is still there."), button("Remove old entry…", () => update(entry.item)));
  } else if (entry.state === "old") {
    box.append(socket({ state: "unk", word: "Old entry" }));
    const note = entry.command_exists ? "Made by the working version, agentsetup." : "Made by the working version; its command is missing.";
    box.append(el("span", "muted", note), button("Update to Kitden…", () => update(entry.item)));
  } else {
    box.append(el("span", "muted", "Not added"), button("Add…", () => review({ action: "setup_server.register", targets: [{ client: entry.client }], params: {} })));
  }
  return box;
}

export function renderAgents(main) {
  main.append(el("h1", null, "Let agents read this setup"));
  main.append(el("p", "lede", "Adds the Kitden MCP server to a client. An agent can then answer “what do you load here?”. Its own tools only read. Servers moved into the gateway add their tools, which do what those servers do."));
  if (!data.setupServer) {
    if (data.errors.setupServer) main.append(banner("the clients", retry));
    else main.append(skeleton("card", 1));
    return;
  }
  const grid = el("div", "conn");
  for (const entry of data.setupServer) grid.append(cell(entry));
  main.append(grid);
  main.append(el("p", "muted", "Then ask the agent: “show my setup”."));
  entrance("agents", [grid]);
}
