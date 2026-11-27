// The words of a state, the same on every tab: the twin of views/words.py (STATE_WORDS,
// SKILL_STATE_WORDS). One word for one state: tests/unit/test_page_words.py fails on a second
// spelling. Pure, so pure modules (context-groups.js) take their words from here too.

// The twin of views/words.py STATE_WORDS.
export const STATE_WORDS = {
  on: "On", off: "Off", unk: "Unknown", review: "Needs review", gw: "Via gateway",
  missing: "Not installed", none: "—", via: "Via Claude Code", done: "Has its skills",
  unread: "Could not read",
};
// The one mark of a change that waits in the tray, on every row, card, block and group: "in preview"
// ("Off · in preview" where the state it waits for is said too, `waitsAs`).
export const WAITING = "in preview";
export const waitsAs = (state) => `${STATE_WORDS[state]} · ${WAITING}`;
// A client's words for the Kitden gateway: Connected, Not connected, or Not installed for a client
// that is not on this computer (`missing`), which has nothing to connect.
export const gatewayWords = (on, missing = false) => (missing ? STATE_WORDS.missing : on ? "Connected" : "Not connected");
// A name with its 's: "Codex's", but "superpowers'" for a name that ends in s (views/words.py
// possessive).
export const possessive = (name) => (String(name).endsWith("s") ? `${name}'` : `${name}'s`);
// The twin of views/words.py SKILL_STATE_WORDS: a skill's own state beyond On and Off.
export const SKILL_STATE_WORDS = { "name-only": "Name only", "user-invocable-only": "Only when you ask", "only-asked": "Only when you ask" };
