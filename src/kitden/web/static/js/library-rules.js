// What the Library's changes to a plugin or skill are, as tray bodies: "Turn off for all projects…"
// in Details and the × of a link on the map add the same rows. Nothing here writes; a body only
// goes to the tray (tray.js), and nothing is written before Apply.
import { CLIENT_NAMES } from "./parts.js";
import { tray } from "./tray.js";

// Turn it off for all projects: one row per client that loads its own copy and has a switch (`can.off`,
// library_map.py): a plugin's own switch, or a skill rule. Its first item is then the user's own
// entry; where the project's entry decides, `can.off` leaves the client out.
export function offBodies(item) {
  const clients = (item.can && item.can.off) || [];
  return clients.map((client) => {
    const target = item.items[client][0];
    if (item.kind === "plugin") return { action: "plugin.disable", targets: [{ item: target }], params: {} };
    return { action: "skill.rule", targets: [{ client, item: target }], params: { scope: "all", off: true } };
  });
}


// Whether the tray holds a Claude Code skill rule of `scope` ("all" or "project"). Claude Code may
// not merge skillOverrides across files, so the server never takes one in the user file and one in
// a project's in one tray (changes/batch.py); the page offers neither while the other waits. A
// plugin's rule in one project is enabledPlugins, not skillOverrides: it does not count.
export function skillRuleWaits(scope, answer) {
  const plugins = new Set(answer.groups.flatMap((group) => group.items).filter((item) => item.kind === "plugin").flatMap((item) => (item.items || {}).claude_code || []));
  return tray.rows.some(({ body }) => {
    const target = (body.targets || [])[0] || {};
    return body.action === "skill.rule" && (body.params || {}).scope === scope && target.client === "claude_code" && !plugins.has(target.item);
  });
}

// "Turn off for all projects…" for a skill: one row per client that can, without Claude Code's while
// a one-project skill rule waits in the tray.
export function skillOffBodies(item, answer) {
  const blocked = skillRuleWaits("project", answer);
  return offBodies(item).filter((body) => !(blocked && body.targets[0].client === "claude_code"));
}


// The × of a link from `client` to `item`, as `{ body, tip }`; null where the link has none (it
// stays read only and keeps its Details). A plugin is removed from a client whose own entry Kitden
// can remove (`can.remove`); not from Cursor, which gets plugins through Claude Code (D26). A
// skill is turned off in Claude Code or Codex, as Details' "Turn off for all projects…" does for
// that client, and removed from Cursor's own skills folder.
export function linkRemoval(item, client, answer) {
  const name = item.name;
  const who = CLIENT_NAMES[client];
  const can = item.can || {};
  const target = ((item.items || {})[client] || [])[0];
  if (!target) return null;
  if (item.kind === "plugin" && (can.remove || []).includes(client)) {
    return { body: { action: "plugin.remove", targets: [{ item: target }], params: {} }, tip: `Remove ${name} from ${who}` };
  }
  if (item.kind !== "skill") return null;
  if (client === "cursor") {
    if (!(can.remove || []).includes(client)) return null;
    return { body: { action: "skill.remove", targets: [{ item: target }], params: {} }, tip: `Remove ${name} from ${who}` };
  }
  const body = skillOffBodies(item, answer).find((one) => one.targets[0].client === client);
  return body ? { body, tip: `Turn off ${name} in ${who}` } : null;
}
