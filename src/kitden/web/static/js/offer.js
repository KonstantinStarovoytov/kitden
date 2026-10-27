// The Library's "Add a marketplace…" form (from its add panel), and the note an add for all
// projects carries in a project.
import { busyWhile, button, el, reportError } from "./dom.js";
import { closePanel, openPanel, review, showInPreview } from "./panel.js";
import { clientCheck } from "./parts.js";
import { state } from "./store.js";
import { inTray, keyFor } from "./tray.js";

// Clients whose own command line installs plugins. Cursor keeps its plugins in the account,
// and it loads Claude Code's plugins by itself when "Include Third-Party Plugins" is on.
const INSTALLERS = ["claude_code", "codex"];
const PROJECT_NOTE = "Adds for all projects.";
const PREVIEW = "Preview";

// In a project view an add still goes to the user's settings; the review says so.
export function projectNote(project) {
  return project ? PROJECT_NOTE : null;
}

// Checkboxes for the clients that can take it, checked as `chosen` says; `onChange` hears each.
export function clientChecks(open, chosen, note, onChange) {
  const checks = el("fieldset", "checks");
  checks.append(el("legend", null, "Add to"));
  for (const client of open) {
    checks.append(clientCheck(client, chosen.has(client), note ? note(client) : null, (checked) => {
      if (checked) chosen.add(client); else chosen.delete(client);
      if (onChange) onChange();
    }));
  }
  return checks;
}

// The form: the clients, an optional note about them, then Preview and its message. `bodyOf()`
// is the change the form asks for now, and `onSubmit(body)` adds it to the tray. While that
// change waits there, Preview says "In preview" and takes no press, as the Gateway's forms do; a
// tick or a typed link is another change, so Preview follows that one.
export function addFormBody(checks, chosen, bodyOf, onSubmit, note = null) {
  const form = el("form", "form");
  const message = el("span", "form-message");
  message.setAttribute("aria-live", "polite");
  const submit = el("button", "btn primary");
  const words = el("span", "cut", PREVIEW);
  submit.type = "submit";
  submit.append(words);
  const follow = () => showInPreview(submit, words, PREVIEW, keyFor(bodyOf()));
  follow();
  form.addEventListener("change", follow);
  form.addEventListener("input", follow);
  form.append(...[checks, note, submit, message].filter(Boolean));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!chosen.size) {
      message.className = "form-message error";
      message.textContent = "Choose at least one client.";
      return;
    }
    message.textContent = "";
    const body = bodyOf();
    if (inTray(keyFor(body)) || submit.dataset.working) return;
    busyWhile(submit, onSubmit(body)).catch(reportError);
  });
  return form;
}

// Add a marketplace from a folder here or a GitHub repository. `back`, when the Library's add panel
// opens it: what runs once its row is in the tray (review.js), so the panel comes back.
export function marketplaceForm({ back = null } = {}) {
  const body = el("div", "body");
  const field = el("label", "field grow");
  const input = el("input");
  input.required = true;
  input.placeholder = "owner/repo, a github.com address, or a folder";
  input.autocomplete = "off";
  input.spellcheck = false;
  field.append(el("span", null, "Marketplace link"), input);
  const chosen = new Set(INSTALLERS);
  const ask = () => ({ action: "marketplace.add", targets: [...chosen].map((client) => ({ client })), params: { source: input.value.trim() } });
  const form = addFormBody(clientChecks(INSTALLERS, chosen), chosen, ask, (change) => review(change, { note: projectNote(state.project), back }));
  form.prepend(field);
  body.append(el("p", "muted", "For a GitHub repository, Kitden reads its marketplace file once to name it. Cursor keeps its marketplaces in the Cursor account: add them in Cursor."), form);
  openPanel([panelHead("Add marketplace", "From a link"), body, el("footer")]);
  setTimeout(() => input.focus(), 0);
}

function panelHead(kicker, title) {
  const head = el("header");
  const top = el("div", "top");
  top.append(el("span", "kicker", kicker), button("Close", () => closePanel(), "btn ghost small"));
  const h1 = el("h1", "title-mono", title);
  h1.id = "panel-title";
  head.append(top, h1);
  return head;
}
