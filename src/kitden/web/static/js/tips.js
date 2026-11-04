// Hover text for every button, switch and link that acts: one or two plain sentences on what it
// does and what changes. It shows 400 ms after the pointer rests on it, and at once when the
// keyboard moves focus there. An element's own words come first (`data-tip`, then its `title`,
// which moves to `data-tip` so the browser's own tooltip does not show too); else `tipFor` finds
// them from the label. Every change still goes through the preview, so the words say so.
import { el } from "./dom.js";

const WAIT_MS = 400;
const GAP = 8; // between the element and the tip
const EDGE = 8; // the tip keeps this far from the window's edge

// Label → words, first match wins. Only what the label leaves out: what else it touches, what
// stays, where the value goes. A label that says it all ("Close", "Details", "Map") has none.
// `m` is the match, for labels with a name in them.
const RULES = [
  [/^Turn (off|on) in some projects…$/, (m) => `You pick the projects. Every other project keeps the shared rule, and new projects follow it too.`],
  [/^Turn (off|on) for all projects…$/, () => "Sets the shared rule. A project with a rule of its own keeps it."],
  [/^Turn (off|on) (.+ )?in (this project|.+)…$/, (m) => `A rule for ${m[3] === "this project" ? "this project" : m[3]} only. The shared rule and other projects stay as they are.`],
  [/^Turn it on in (.+)…$/, (m) => `Only ${m[1]} changes. Other clients keep what they have.`],
  [/^Turn strict mode on…$/, () => "Tools without a rule of their own go off, and tools the server adds later start off too."],
  [/^Turn strict mode off…$/, () => "Tools without a rule of their own come back on, and tools the server adds later start on."],
  [/^Turn off every writing tool…$/, () => "Tools that can change things go off. Tools that only read stay on. The hints come from the server or the tool's name, so check the list."],
  [/^Use (the shared|.+'s) rule…$/, () => "Drops this project's own rule, so it follows the shared setup again."],
  [/^Move out of the gateway…$/, () => "Each client gets its own entry for this server back, and Kitden stops turning its tools on or off."],
  [/^Move (into the gateway|in|into .+)…$/, () => "Each client's own entry for this server is replaced by the gateway. Then you turn its tools on or off once, for every client."],
  [/^Move all \d+…$/, () => "Moves every server outside the gateway that can move into it, in one change. Servers set up differently in two clients stay out until you keep one."],
  [/^Move secrets to the .+…$/, () => "The settings file keeps only a reference; the values go to a safe store on this computer."],
  [/^Add access…$/, () => "A token, a header or a browser sign-in this server needs. The value goes to a safe store on this computer, never to a file."],
  [/^Replace…$/, () => "The old value keeps working until you apply the new one."],
  [/^Sign out$/, () => "Kitden forgets this sign-in. The server's tools stop working until you sign in again."],
  [/^\+? ?Add (a server|servers)…?$/, () => "From a catalog or by its address. It joins the gateway, so every connected client gets it."],
  [/^Add another gateway…$/, () => "A gateway someone else runs, such as your team's. Kitden shows its servers next to yours."],
  [/^Use this gateway…$/, () => "Adds this gateway's entry to your clients. Your other servers stay as they are."],
  [/^Connect (.+ )?to the gateway…$|^Connect…$/, () => "Adds one entry to this client. Through it, the client reaches every server in the gateway."],
  [/^Disconnect (.+ )?from the gateway…$|^Disconnect…$/, () => "Takes the gateway's entry out of this client. The servers stay in the gateway for the other clients."],
  [/^Put back in (.+)…$/, (m) => `${m[1]} gets its own entry for this server again. The gateway keeps it too.`],
  [/^Remove from the Kitden gateway…$/, () => "Every client loses this server's tools. Its secrets stay in the safe store, so Undo brings it back."],
  [/^Remove from (.+)…$/, (m) => `Only ${m[1]}'s entry goes. A backup is kept, and Undo puts it back.`],
  [/^Remove (direct|old) entry…$/, () => "The client loads this server through the gateway already, so its own entry is a second copy."],
  [/^Keep one…$/, () => "Two entries load the same thing. You pick the one to keep; the other is taken out."],
  [/^Add for all projects…$/, () => "Goes to the user settings, so every project has it."],
  [/^Add to this project…$/, () => "Goes to this project's own settings. Other projects do not get it."],
  [/^Add missing plugins and skills…$/, () => "What one client has and another lacks, so every client has the same."],
  [/^Add a marketplace…$/, () => "A marketplace is a list of plugins at an address, such as a GitHub repository."],
  [/^Update (to Kitden|the Kitden entry|.+'s Kitden entry)…$/, () => "The client's entry still starts an older Kitden. This points it at the one you run now."],
  [/^Set up( in .+)?…$/, () => "Adds Kitden's own entry, so the agent can read this setup and use the gateway."],
  [/^Commands…$/, () => "The same change as terminal commands, if you would rather run it yourself."],
  [/^Redo…$/, () => "Makes the undone change again. It is checked against the files as they are now."],
  [/^Undo$/, () => "Puts back the files this change wrote, from their backups. A file changed since is not touched."],
  [/^Apply( all| \d+)?$/, () => "Each file is backed up before it is written and read back after. If anything fails, everything is put back."],
  [/^Rescan$/, () => "Reads every client's settings again, for changes made outside Kitden."],
];

// The words for a label, or null.
export function tipFor(label) {
  const text = String(label || "").replace(/\s+/g, " ").trim();
  for (const [pattern, say] of RULES) {
    const m = text.match(pattern);
    if (m) return say(m);
  }
  return null;
}

// The element a tip belongs to, from where the pointer or focus is.
const ACTS = "button, [role=switch], a.btn, [data-tip], [title], [data-held]";

// Whether a part of `node` (or `node` itself) shows its words cut off with "…".
function cutOff(node) {
  const parts = [node, ...(node.querySelectorAll?.("*") || [])];
  return parts.some((part) => part.scrollWidth > part.clientWidth + 1 && getComputedStyle?.(part).textOverflow === "ellipsis");
}

// The words for `node`, or null. Words already on screen (a title that repeats a button's label
// or a block's name: "Kitden gateway") show only while they are cut off with "…"; else the
// label's own hover words, if it has any.
export function wordsOf(node, title = node.title) {
  const shown = String(node.textContent || "").replace(/\s+/g, " ").trim();
  const label = String(node.getAttribute?.("aria-label") || shown).trim();
  const own = (title || node.dataset.tip || "").trim();
  // An icon's name written beside it ("Kitden gateway" next to its tile) is on screen too.
  const beside = String(node.parentElement?.textContent || "").replace(/\s+/g, " ");
  if (own && !shown.includes(own) && !beside.includes(own)) return own;
  const extra = node.disabled ? null : tipFor(label);
  if (extra) return extra;
  return own && cutOff(node) ? own : null;
}

// One tip on the page at a time.
export function startTips(root = document) {
  const tip = el("div", "tip");
  tip.id = "tip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.append(tip);
  let owner = null;
  let timer = 0;
  // The title of the element under the pointer or focus, held aside so the browser's own tooltip
  // never shows; it is put back when the element is left (unless the page set a new one).
  let holder = null;
  let held = "";
  const hold = (node) => {
    if (holder === node) return;
    release();
    holder = node;
    held = node.title;
    node.removeAttribute("title");
    node.dataset.held = "";
  };
  const release = () => {
    if (holder) delete holder.dataset.held;
    if (holder && held && !holder.title) holder.title = held;
    holder = null;
    held = "";
  };
  const wordsHere = (node) => wordsOf(node, node.title || (node === holder ? held : ""));

  const hide = () => {
    clearTimeout(timer);
    if (owner) owner.removeAttribute("aria-describedby");
    owner = null;
    tip.hidden = true;
    tip.classList.remove("in");
  };
  const show = (node) => {
    if (!node.isConnected) return;
    const words = wordsHere(node);
    if (!words) return;
    owner = node;
    node.setAttribute("aria-describedby", tip.id);
    tip.textContent = words;
    tip.hidden = false;
    // Under the element, or over it when there is no room; never past the window's edge.
    const box = node.getBoundingClientRect();
    const size = tip.getBoundingClientRect();
    const below = box.bottom + GAP + size.height <= innerHeight - EDGE;
    const top = below ? box.bottom + GAP : Math.max(EDGE, box.top - GAP - size.height);
    const left = Math.min(Math.max(EDGE, box.left + box.width / 2 - size.width / 2), innerWidth - EDGE - size.width);
    tip.style.top = `${Math.round(top)}px`;
    tip.style.left = `${Math.round(left)}px`;
    tip.classList.toggle("above", !below);
    // Measured above with opacity 0, so the fade runs from there.
    tip.classList.add("in");
  };
  const wait = (node, ms) => {
    clearTimeout(timer);
    if (owner && owner !== node) hide();
    if (owner === node) return;
    timer = setTimeout(() => show(node), ms);
  };

  root.addEventListener("pointerover", (event) => {
    const node = event.target.closest?.(ACTS);
    if (!node || event.pointerType === "touch") return;
    hold(node);
    wait(node, WAIT_MS);
  });
  root.addEventListener("pointerout", (event) => {
    const node = event.target.closest?.(ACTS);
    if (node && !node.contains(event.relatedTarget)) {
      hide();
      release();
    }
  });
  // Keyboard focus shows it at once; focus from a press does not.
  root.addEventListener("focusin", (event) => {
    const node = event.target.closest?.(ACTS);
    if (node && node.matches(":focus-visible")) wait(node, 0);
  });
  root.addEventListener("focusout", hide);
  root.addEventListener("pointerdown", hide);
  root.addEventListener("keydown", (event) => { if (event.key === "Escape") hide(); });
  addEventListener("scroll", hide, true);
  return { hide };
}
