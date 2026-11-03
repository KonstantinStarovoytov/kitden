// Hover text for every button, switch and link that acts: one or two plain sentences on what it
// does and what changes. It shows 400 ms after the pointer rests on it, and at once when the
// keyboard moves focus there. An element's own words come first (`data-tip`, then its `title`,
// which moves to `data-tip` so the browser's own tooltip does not show too); else `tipFor` finds
// them from the label. Every change still goes through the preview, so the words say so.
import { el } from "./dom.js";

const WAIT_MS = 400;
const GAP = 8; // between the element and the tip
const EDGE = 8; // the tip keeps this far from the window's edge
const PREVIEW = "Nothing changes until you press Apply.";

const where = (place) => (place === "this project" ? "only in the picked project" : `only in ${place}`);

// Label → words, first match wins. `m` is the match, for labels with a name in them.
const RULES = [
  [/^Turn (off|on) in some projects…$/, (m) => `Pick the projects where it is ${m[1]}. The other projects keep the shared rule.`],
  [/^Turn (off|on) for all projects…$/, (m) => `Turns it ${m[1]} in every project that has no rule of its own. ${PREVIEW}`],
  [/^Turn (off|on) (.+ )?in (this project|.+)…$/, (m) => `Turns ${m[2] ? m[2].trim() : "it"} ${m[1]} ${where(m[3])}. Everything else stays as it is.`],
  [/^Turn it on in (.+)…$/, (m) => `Turns it on in ${m[1]}. ${PREVIEW}`],
  [/^Turn strict mode on…$/, () => "In strict mode a tool of this server is off until you turn it on. New tools start off too."],
  [/^Turn strict mode off…$/, () => "Tools without a rule of their own are on again, and new tools start on."],
  [/^Turn off every writing tool…$/, () => "Turns off the tools that can change things. Tools that only read stay on."],
  [/^Use (the shared|.+'s) rule…$/, (m) => `Drops this project's own rule, so it follows ${m[1] === "the shared" ? "the shared setup" : `${m[1].slice(0, -2)}'s rule`} again.`],
  [/^Move out of the gateway…$/, () => "Gives this server back to the clients' own settings. Kitden stops turning its tools on or off."],
  [/^Move (into the gateway|in|into .+)…$/, () => "Moves this server into the Kitden gateway, so you turn its tools on or off in one place for every client."],
  [/^Move all \d+…$/, () => "Moves every server in this list into the gateway in one change."],
  [/^Move secrets to the .+…$/, () => "Moves the secrets in the settings file into a safe store. The file keeps only a reference."],
  [/^Add access…$/, () => "Adds a token, a header or a sign-in that this server needs. The value is kept in a safe store, not in a file."],
  [/^Replace…$/, () => "Puts a new value in place of this one. The old one stays until you press Apply."],
  [/^Remove$/, () => `Takes this out. ${PREVIEW} Undo brings it back.`],
  [/^Sign in again$/, () => "Opens the server's sign-in page in your browser, to get a new token."],
  [/^Sign in$/, () => "Opens the server's sign-in page in your browser."],
  [/^Sign out$/, () => "Forgets this sign-in. The server cannot be reached until you sign in again."],
  [/^\+? ?Add (a server|servers)…?$/, () => "Find an MCP server in a catalog or type its address, and add it to the gateway."],
  [/^Add another gateway…$/, () => "Connects another gateway, such as one your team runs, so Kitden shows its servers too."],
  [/^Use this gateway…$/, () => "Adds this gateway's entry to your clients, so they reach its servers."],
  [/^Connect (.+ )?to the gateway…$/, (m) => `Adds the gateway's entry to ${m[1] ? m[1].trim() : "this client"}, so it reaches every server in the gateway.`],
  [/^Connect…$/, () => "Adds the gateway's entry to this client, so it reaches every server in the gateway."],
  [/^Disconnect (.+ )?from the gateway…$/, (m) => `Takes the gateway's entry out of ${m[1] ? m[1].trim() : "this client"}. The servers stay in the gateway.`],
  [/^Disconnect…$/, () => "Takes the gateway's entry out of this client. The servers stay in the gateway."],
  [/^Put back in (.+)…$/, (m) => `Puts this server back in ${m[1]}'s own settings.`],
  [/^Remove from the Kitden gateway…$/, () => "Takes this server out of the gateway. Clients lose its tools."],
  [/^Remove from (.+)…$/, (m) => `Takes this entry out of ${m[1]}'s settings. A backup is kept, and Undo puts it back.`],
  [/^Remove (direct|old) entry…$/, () => "Takes out the client's own entry for this server. The gateway gives the client the same server."],
  [/^Keep one…$/, () => "Two entries load the same thing. Pick the one to keep; the other is taken out."],
  [/^Add for all projects…$/, () => `Adds it to the user settings, so every project has it. ${PREVIEW}`],
  [/^Add to this project…$/, () => `Adds it to the picked project's own settings only. ${PREVIEW}`],
  [/^Add to (.+)…$/, (m) => `Adds it to ${m[1]}. ${PREVIEW}`],
  [/^Add…$/, () => `Adds it. ${PREVIEW}`],
  [/^Add missing plugins and skills…$/, () => "Lists what one client has and another lacks, so you can add it there too."],
  [/^Add a marketplace…$/, () => "Adds a plugin marketplace by its address, so you can browse and add its plugins."],
  [/^Add source$/, () => "Adds a catalog of MCP servers to search."],
  [/^Add to preview$/, () => "Adds this change to the preview at the bottom. Press Apply there to write it."],
  [/^Update (to Kitden|the Kitden entry|.+'s Kitden entry)…$/, () => "Rewrites the Kitden entry so the client starts this Kitden version."],
  [/^Update…$/, () => "Shows how to update to the newest version."],
  [/^Set up( in .+)?…$/, (m) => `Adds Kitden's entry to ${m[1] ? m[1].slice(4) : "the client"}, so it can read your setup.`],
  [/^Commands…$/, () => "Shows the terminal commands that do the same, if you prefer to run them yourself."],
  [/^Redo…$/, () => "Makes the undone change again, with a new preview."],
  [/^Undo$/, () => "Puts the files back as they were before this change, from its backup."],
  [/^Undo removal$/, () => "Brings back what was just removed."],
  [/^Apply( all| \d+)?$/, () => "Writes every change in the preview, with a backup of each file, then checks it worked."],
  [/^Preview$/, () => "Shows what would change. Nothing is written yet."],
  [/^Take it out$/, () => "Takes this row out of the preview. Nothing was written."],
  [/^Cancel( all)?$/, () => "Drops the preview. Nothing is written."],
  [/^Try again$|^Retry$/, () => "Tries the same step once more."],
  [/^Close$/, () => "Closes this panel. Changes in the preview stay there."],
  [/^Done$/, () => "Closes this. Changes in the preview stay there."],
  [/^Details$/, () => "Opens the details: where it comes from, its paths and settings."],
  [/^More$/, () => "Shows more actions."],
  [/^Refresh tools$/, () => "Asks the server for its tool list again."],
  [/^Rescan$/, () => "Reads every client's settings again."],
  [/^Map$/, () => "Shows clients, the gateway, servers and tools as a map."],
  [/^List$/, () => "Shows the same as a list."],
  [/^Show changes$/, () => "Shows each file this change writes, line by line."],
  [/^Open Overview$/, () => "Goes to the Overview page."],
  [/^See it on the map$/, () => "Shows this on the Gateway map."],
  [/^See what it loads in Library$/, () => "Shows in the Library what this loads in each client."],
  [/^Show all$/, () => "Shows everything, not only what is installed."],
  [/^Show installed$/, () => "Shows only what is installed."],
  [/^Clear search$|^Back to search$/, () => "Clears the search and shows the full list."],
  [/^Save( gateway)?$/, () => "Saves these settings."],
  [/^Edit$/, () => "Changes these settings."],
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
const ACTS = "button, [role=switch], a.btn, [data-tip], [title]";

function wordsOf(node) {
  if (node.title) {
    node.dataset.tip = node.title;
    node.removeAttribute("title");
  }
  if (node.dataset.tip) return node.dataset.tip;
  if (node.disabled) return null;
  return tipFor(node.getAttribute("aria-label") || node.textContent);
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

  const hide = () => {
    clearTimeout(timer);
    if (owner) owner.removeAttribute("aria-describedby");
    owner = null;
    tip.hidden = true;
    tip.classList.remove("in");
  };
  const show = (node) => {
    if (!node.isConnected) return;
    const words = wordsOf(node);
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
    if (node && event.pointerType !== "touch") wait(node, WAIT_MS);
  });
  root.addEventListener("pointerout", (event) => {
    const node = event.target.closest?.(ACTS);
    if (node && !node.contains(event.relatedTarget)) hide();
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
