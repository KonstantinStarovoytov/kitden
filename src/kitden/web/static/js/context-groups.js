// Context's groups: the skills of a Claude Code or Codex card by where they come from (the server's
// `card.groups`, named with the Library's words), and what each group takes of the skill list the
// page draws. The numbers come from the same result as the bar and the verdict: the last chat's
// fact, the estimate for the setup now, another window's estimate, or the estimate after Apply. A
// group that is off now says so whatever the page can estimate. Pure: context.js draws, and the
// Library's Details say what a plugin or a skill takes (takesLine).

export const fmt = (n) => n.toLocaleString("en-US");
const CLIENT_WORDS = { claude_code: "Claude Code", codex: "Codex" };
// What a skill on the second side did, or would do: [in the last chat, in an estimate].
const SHORT = { claude_code: ["showed only a name", "would show only a name"], codex: ["cut short", "would be cut short"] };
// More than this many groups start closed.
export const FOLD_ABOVE = 3;

// A skill's side: on the last chat's window, the server's; on an estimate (another window, the setup
// now, or after Apply), from that estimate, also when the last list did not hold it. Claude Code: a
// skill whose description is sent, or one that shows only a name (no room for it, or set to Name
// only). Codex: one with nothing cut off, or one that is cut or left out. A skill on no side (in no
// list, or Kitden cannot tell) stays apart; one the tray turns on (`back`) has a side in the estimate
// after Apply, and none in the others, which know nothing of the tray. `state`: the tray's state for it.
export function sideOf(card, skill, result, estimate, back = false, planned = false, state = undefined) {
  if (back && estimate && !planned) return null;
  if (!estimate) return skill.side;
  // Codex may send a part of a description: such a skill has a piece sent and a piece over.
  if (card.client === "codex" && skill.name in (result.over || {})) return 1;
  if (skill.name in (result.sent || {})) return 0;
  if (skill.name in (result.over || {})) return 1;
  return (planned ? state || skill.state : skill.state) === "name-only" ? 1 : null;
}

// An off skill that the tray sets to On or Name only.
export const turnedOn = (skill, states) => skill.state === "off" && skill.name in states && states[skill.name] !== "off";

const sum = (part, names) => names.reduce((n, name) => n + ((part || {})[name] || 0), 0);
const many = (n, one, more) => `${n} ${n === 1 ? one : more}`;

// Each skill of a group as the page draws it: `look` is "sent", "lo" (only a name, or cut), "apart"
// (in no list), "off" (off now) or "going" (the tray turns it off). `view`: { result, base, fact,
// estimate, planned, states } (see groupsOf).
function membersOf(card, group, view) {
  const { result, estimate, planned, states } = view;
  const names = new Set(group.skills);
  return card.skills.filter((s) => names.has(s.name)).map((skill) => {
    const back = turnedOn(skill, states);
    const going = states[skill.name] === "off" && skill.state !== "off";
    const off = skill.state === "off" && !back;
    const side = going && planned ? null : sideOf(card, skill, result, estimate, back, planned, states[skill.name]);
    const chosen = (planned ? states[skill.name] || skill.state : skill.state) === "name-only";
    const look = off ? "off" : going ? "going" : side === 0 ? "sent" : side === 1 ? "lo" : "apart";
    return { skill, side, back, going, off, chosen, look };
  });
}

// What a group takes in the result drawn: its skills on the list (`n`), the characters (Codex:
// tokens) their entries with a description take there, as the bar's pieces (`size`), how many show
// only a name or are cut there, by the limit and not by choice (`short`), and how many are off now
// or go off after Apply (`off`). `base`: the same without the tray's changes, which orders the
// groups so a switch does not move its group. `was`: what an off group took in the last chat.
// `state`: "on", "off" (all off now), "going" (the tray turns all of it off) or "back" (the tray
// turns some of it on).
export function factsOf(card, group, view) {
  const members = membersOf(card, group, view);
  const listed = members.filter((m) => m.side !== null && !m.off && !m.going);
  const factListed = members.filter((m) => m.skill.side !== null && m.skill.side !== undefined);
  const off = members.filter((m) => m.off || m.going).length;
  const allOff = members.length > 0 && members.every((m) => m.off);
  const going = !allOff && members.some((m) => m.going) && members.every((m) => m.off || m.going);
  const state = allOff ? "off" : going ? "going" : members.some((m) => m.back) ? "back" : "on";
  return {
    group, members, state, off,
    n: listed.length,
    size: sum(view.result.sent, listed.map((m) => m.skill.name)),
    short: listed.filter((m) => m.side === 1 && !m.chosen).length,
    base: sum(view.base.sent, members.filter((m) => !m.off).map((m) => m.skill.name)),
    was: { n: factListed.length, size: sum(view.fact.sent, factListed.map((m) => m.skill.name)) },
  };
}

// The groups of a card, largest first by what they take without the tray's changes, those off now
// last (by what they took in the last chat); the server's order breaks ties.
export function groupsOf(card, view) {
  const all = (card.groups || []).map((group) => factsOf(card, group, view));
  const key = (f) => (f.state === "off" ? [1, -f.was.size] : [0, -f.base]);
  return all.map((f, i) => [key(f), i, f]).sort(([a, i], [b, j]) => a[0] - b[0] || a[1] - b[1] || i - j).map(([, , f]) => f);
}

// The header's line after the name: "12 skills · 6,450 characters · 3 showed only a name · 1 off";
// "Off · was 9 skills, 3,435 characters in your last chat"; "Off after Apply · frees about 2,291
// characters"; "On after Apply · …". In an estimate, "would show only a name".
export function groupLine(card, facts, estimate) {
  const unit = card.unit || "characters";
  if (facts.state === "off") {
    const { n, size } = facts.was;
    const was = n ? `was ${many(n, "skill", "skills")}, ${fmt(size)} ${unit} in your last chat` : many(facts.members.length, "skill", "skills");
    return ["Off", was];
  }
  if (facts.state === "going") return ["Off after Apply", ...(facts.base ? [`frees about ${fmt(facts.base)} ${unit}`] : [])];
  const parts = facts.state === "back" ? ["On after Apply"] : [];
  parts.push(many(facts.n, "skill", "skills"));
  if (facts.size) parts.push(`${fmt(facts.size)} ${unit}`);
  if (facts.short) parts.push(`${facts.short} ${SHORT[card.client][estimate ? 1 : 0]}`);
  if (facts.off) parts.push(`${facts.off} off`);
  return parts;
}

// The Library's line for a plugin or a skill on a card: what it takes of that client's skill list
// now (the estimate for the setup now, else the last chat), with the group it is in; null when the
// card does not hold it. `match`: { plugin } (a plugin's id, "superpowers@market"), { plugin, skill }
// (a skill inside that plugin, by its own name) or { items } (a skill's item ids).
export function takesLine(card, match) {
  const groups = card.groups || [];
  const fact = (card.windows && card.windows[0] && card.windows[0].result) || { sent: {} };
  const base = card.now || fact;
  const client = CLIENT_WORDS[card.client] || card.client;
  const unit = card.unit || "characters";
  if (match.plugin && match.skill) {
    const group = groups.find((g) => g.lookup === match.plugin);
    const skill = group && card.skills.find((s) => s.group === group.key && s.shown === match.skill);
    return skill ? skillLine(card, skill, base, client, unit) : null;
  }
  if (match.plugin) {
    const group = groups.find((g) => g.lookup === match.plugin);
    if (!group) return null;
    const facts = factsOf(card, group, { result: base, base, fact, estimate: Boolean(card.now), planned: false, states: {} });
    if (facts.state === "off") return { group: group.key, client: card.client, say: `Off now. Took ${fmt(facts.was.size)} ${unit} of ${client}'s skill list in your last chat.` };
    return { group: group.key, client: card.client, say: `Takes ${fmt(facts.size)} ${unit} of ${client}'s skill list.` };
  }
  const ids = new Set(match.items || []);
  const skill = card.skills.find((s) => s.item && ids.has(s.item));
  return skill ? skillLine(card, skill, base, client, unit) : null;
}

// One skill's line: what it takes now, only its name, or off.
function skillLine(card, skill, base, client, unit) {
  if (skill.state === "off") return { group: skill.group, client: card.client, say: `Off now: not in ${client}'s next skill list.` };
  const size = (base.sent || {})[skill.name];
  const say = size ? `Takes ${fmt(size)} ${unit} of ${client}'s skill list.` : `Shows only its name in ${client}'s skill list.`;
  return { group: skill.group, client: card.client, say };
}
