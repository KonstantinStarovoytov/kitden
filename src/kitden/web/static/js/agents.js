// Agents: add the read-only "show my setup" MCP server to a client.
import { button, el } from "./dom.js";
import { entrance } from "./motion.js";
import { review } from "./panel.js";
import { CLIENT_NAMES, mark, skeleton, socket } from "./parts.js";
import { data } from "./store.js";

const CLIENTS = ["claude_code", "codex", "cursor"];
const SETUP_NAME = "kitden";

export function renderAgents(main) {
  main.append(el("h1", null, "Let agents see this setup"));
  main.append(el("p", "lede", "Adds a read-only MCP server to a client. An agent can then answer “what do you load here?” without changing anything."));
  if (!data.map || !data.clients) {
    main.append(skeleton("card", 1));
    return;
  }
  const entry = data.map.rows.find((r) => r.kind === "mcp_server" && r.name === SETUP_NAME);
  const grid = el("div", "conn");
  for (const client of CLIENTS) {
    const cell = el("div", "cell");
    const top = el("div", "chip");
    top.append(mark(client), el("strong", null, CLIENT_NAMES[client]));
    cell.append(top);
    const info = data.clients.find((c) => c.id === client);
    const state = entry && entry.cells[client] ? entry.cells[client].state : "none";
    if (!info || info.status !== "found") cell.append(socket({ state: "missing", word: "Not found" }));
    else if (!["none", "missing"].includes(state)) cell.append(socket({ state: state === "off" ? "off" : "on", word: state === "off" ? "Added, off" : "Added" }));
    else cell.append(el("span", "muted", "Not added"), button("Add…", () => review({ action: "setup_server.register", targets: [{ client }], params: {} })));
    grid.append(cell);
  }
  main.append(grid);
  main.append(el("p", "muted", "Then ask the agent: “show my setup”."));
  entrance("agents", [grid]);
}
