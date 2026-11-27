// A skill's switch: the one control Context's Details and the Library's Details draw for it, so
// the two look and read the same. On, Name only and Off as the client takes them (`states`: the
// server's answer, `can.rule` in /api/library-map and `skill.switch` in /api/context, both from
// actions.py SKILL_SWITCHES), the pressed one as the tray will leave it, under a quiet line that
// names the client and where it holds ("Claude Code · all projects"). A press adds one `skill.rule`
// row (one row per skill, whatever its state); a press on the state it has now takes the row out.
// Nothing is written before Apply.
import { button, el } from "./dom.js";
import { CLIENT_NAMES } from "./parts.js";
import { followTray } from "./details.js";
import { addToTray, inTray, keyFor, ruleState, takeOut, trayRow } from "./tray.js";

export const SKILL_STATES = { on: "On", "name-only": "Name only", off: "Off" };
export const ALL_PROJECTS_SCOPE = "all projects";
// Codex writes only `enabled` for a skill (docs/clients.md, checked 2026-11-26).
export const CODEX_NO_NAME_ONLY = "Codex has no Name only setting.";

// The row a state of this skill adds: for all projects, or in `project` (a project's own skill:
// Claude Code takes its rule only there). `target`: `{ item }`, or `{ built_in }` for a skill
// built into Claude Code, which has no item.
export function skillRuleBody(client, target, value, project = null) {
  const params = project ? { scope: "project", project, state: value } : { scope: "all", state: value };
  return { action: "skill.rule", targets: [{ client, ...target }], params };
}

// The switch. `scope`: the words after the client ("all projects", "in atlas"); `note`: the tray
// row's note.
export function skillSwitch({ client, target, states, now, project = null, scope = ALL_PROJECTS_SCOPE, note = null }) {
  const box = el("div", "skill-switch");
  const label = `${CLIENT_NAMES[client] || client} · ${scope}`;
  box.append(el("p", "sw-scope", label));
  const seg = el("div", "seg ctx-switch");
  seg.setAttribute("role", "group");
  seg.setAttribute("aria-label", `State in ${label}`);
  const key = keyFor(skillRuleBody(client, target, "off", project));
  const parts = states.map((value) => {
    const node = button(SKILL_STATES[value] || value, () => choose(value), "");
    node.dataset.state = value;
    node.dataset.focus = `state:${client}:${value}`;
    return node;
  });
  seg.append(...parts);
  box.append(seg);
  if (client === "codex") box.append(el("p", "sw-scope", CODEX_NO_NAME_ONLY));
  function choose(value) {
    const body = skillRuleBody(client, target, value, project);
    if (value !== now) return addToTray(body, { note });
    return inTray(key) ? takeOut(key) : null;
  }
  followTray(seg, key, () => {
    const row = trayRow(key);
    const shown = row ? ruleState(row.body.params) : now;
    for (const node of parts) {
      const on = node.dataset.state === shown;
      node.setAttribute("aria-pressed", String(on));
      node.classList.toggle("pending", on && Boolean(row));
    }
  });
  return box;
}
