// The one form that asks for what a server needs before it can join the preview (Part 3a of the
// 2026-11-01 design): one field per value the server declares, labelled with its own words. A
// plain token is the token alone; Kitden adds "Bearer ". The header or variable name shows only
// under Details. The catalog details, the map and the dock all use it.
import { busyWhile, button, el, icon, secretsWord } from "./dom.js";
import { closePanel, header, openPanel } from "./panel.js";
import { animateTo, D, glide, shake } from "./motion.js";
import { addToTray, giveAccess, inTray, keyFor, tray } from "./tray.js";
import { postJson } from "./api.js";

// "Token works" shows a moment before the panel goes.
const WORKS_MS = 600;
const closeSoon = (form) => setTimeout(() => { if (form.node.isConnected) closePanel(); }, D(WORKS_MS));

// The lines under a form's fields: why it was refused (`refused(reason)`: amber words that stay,
// read out), or that it works (`worked(words)`: the green lamp, and a check drawn in 320 ms).
function statusLines() {
  const why = el("p", "access-why");
  why.setAttribute("role", "alert");
  why.hidden = true;
  const done = el("p", "access-works");
  done.hidden = true;
  const refused = (reason) => {
    done.hidden = true;
    why.replaceChildren(icon("triangle-alert", 14), reason);
    why.hidden = false;
    animateTo(why, [{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }], { dur: 200 });
  };
  const worked = (words) => {
    why.hidden = true;
    const mark = icon("check", 14, "ic access-check");
    done.replaceChildren(el("span", "lamp on"), mark, words);
    done.hidden = false;
    const line = mark.querySelector?.("path");
    if (line) animateTo(line, [{ strokeDashoffset: 24 }, { strokeDashoffset: 0 }], { dur: 320 });
  };
  return { why, done, refused, worked };
}

// A panel with a form (its `node`) in its body. With `back`, a Back button before the kicker goes
// back to where the form was opened from (a server's Details).
function openForm(kicker, title, lede, node, back = null) {
  const body = el("div", "body");
  body.append(node);
  const head = header(kicker, title, lede);
  if (back) {
    const backButton = button(null, back, "btn ghost small step-back");
    backButton.setAttribute("aria-label", "Back");
    backButton.append(icon("arrow-left", 14));
    head.querySelector(".top").prepend(backButton);
  }
  openPanel([head, body]);
}

// The form for `waits` ({ server, kind, fields, reason }): `onCheck(values)` runs on Add token
// (Preview when every value is optional; `values` is then null when none is typed).
// Returns { node, values, focus, checking, works, refuse }.
export function accessForm(waits, onCheck) {
  const form = el("form", "form access-form");
  const inputs = [];
  const required = waits.fields.filter((f) => !f.optional);
  const optional = waits.fields.filter((f) => f.optional);
  const more = el("details", "access-more");
  more.append(el("summary", null, "More values"));
  const fieldNode = (field) => {
    const label = el("label", "field");
    const input = el("input");
    input.type = "password";
    input.autocomplete = "off";
    input.placeholder = field.prefix ? "Paste token" : "Enter value";
    label.append(el("span", null, field.label), input);
    if (field.later) label.append(el("small", "muted", "Checked when the gateway starts it"));
    inputs.push({ field, input });
    return label;
  };
  const rows = el("div", "access-fields");
  rows.append(...required.map(fieldNode));
  if (optional.length) {
    more.append(...optional.map(fieldNode));
    rows.append(more);
  }
  const names = el("details", "access-names");
  names.append(el("summary", null, "Details"));
  for (const { name, field } of waits.fields) names.append(el("p", "muted", field === "env" ? `Set as ${name}` : `Sent as the ${name} header`));
  const { why, done, refused, worked } = statusLines();
  // With only optional values (a remote that may take a token), the form previews without one.
  const label = required.length ? "Add token" : "Preview";
  const submit = el("button", "btn primary", label);
  submit.type = "submit";
  form.append(rows, why, done, el("p", "muted", `Saved in your ${secretsWord()} on Apply.`), names, submit);

  // The values typed, as the change's params ({ headers?, env? }), or null while a required one
  // is empty. A pasted "Bearer …" keeps one prefix.
  const values = () => {
    if (inputs.some(({ field, input }) => !field.optional && !String(input.value || "").trim())) return null;
    const out = {};
    for (const { field, input } of inputs) {
      let value = String(input.value || "").trim();
      if (!value) continue;
      if (field.prefix) value = field.prefix + value.replace(/^bearer\s+/i, "");
      (out[field.field] ||= {})[field.name] = value;
    }
    return Object.keys(out).length ? out : null;
  };
  const focus = () => inputs[0]?.input.focus();
  // Checking…: the words change at once, and the busy ring comes after 150 ms (busyWhile).
  const checking = (work) => {
    submit.textContent = "Checking…";
    const back = () => { submit.textContent = label; };
    return busyWhile(submit, Promise.resolve(work).finally(back));
  };
  // Token works. Values only a running server can check (a local server's) are not called
  // checked: Apply's verify checks them.
  const unchecked = waits.fields.length > 0 && waits.fields.every((f) => f.later);
  const works = () => {
    if (!unchecked) {
      worked("Token works");
      return;
    }
    why.hidden = true;
    done.replaceChildren("Saved on Apply. Checked when the gateway starts it");
    done.hidden = false;
  };
  // Refused: the reason, focus back in the field, and one shake of the fields.
  const refuse = (reason) => {
    refused(reason);
    focus();
    shake(rows);
  };
  form.addEventListener("input", () => { why.hidden = true; });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const given = values();
    if (!given && required.length) {
      focus();
      return;
    }
    checking(Promise.resolve().then(() => onCheck(given))).catch(() => {});
  });
  return { node: form, values, focus, checking, works, refuse };
}

// Browser sign-in (Part 3b): Sign in opens the server's own page in the browser, and the form
// waits for it ("Waiting for browser…", with a Cancel). `onSigned(id)` then adds the sign-in to
// the change and answers true (joined), false (refused) or null. A server Kitden cannot sign in
// to gets its reason and the token field, which runs `onToken(values)` (none when `onToken` is
// null: the reason alone). Returns { node, start, signed, refuse }.
export function signInForm(waits, onSigned, onToken = null) {
  const node = el("div", "form access-form sign-in-form");
  const row = el("div", "access-fields sign-in-row");
  const go = el("button", "btn primary", "Sign in");
  go.type = "button";
  const cancel = el("button", "btn", "Cancel");
  cancel.type = "button";
  cancel.hidden = true;
  row.append(go, cancel);
  const { why, done, refused, worked } = statusLines();
  const token = el("div", "sign-in-token");
  node.append(row, why, done, el("p", "muted", `Saved in your ${secretsWord()} on Apply.`), token);

  const refuse = (reason) => {
    refused(reason);
    go.textContent = "Try again";
    shake(row);
  };
  const signed = () => worked("Signed in");
  const run = async () => {
    why.hidden = true;
    // Cancel shows at once: finding the server's sign-in page may take a while too.
    cancel.hidden = false;
    const started = await postJson("/api/sign-in/start", { id: waits.sign_in });
    if (!started.ok) {
      cancel.hidden = true;
      const reason = started.data?.detail || "Kitden could not open the sign-in page.";
      refuse(reason);
      if (started.data?.cannot && onToken && !token.children.length) token.append(accessForm({ ...waits, kind: "token" }, onToken).node);
      return;
    }
    const answer = await postJson("/api/sign-in/wait", { id: waits.sign_in });
    cancel.hidden = true;
    const ended = answer.data || {};
    if (ended.state !== "done") {
      refuse(ended.detail || `${waits.server} did not finish sign-in.`);
      return;
    }
    if (await onSigned(waits.sign_in)) signed();
  };
  // Waiting for browser…: the words change at once, and the busy ring comes after 150 ms.
  const start = () => {
    go.textContent = "Waiting for browser…";
    go.disabled = true;
    const back = () => {
      go.disabled = false;
      if (go.textContent === "Waiting for browser…") go.textContent = "Sign in";
    };
    return busyWhile(go, run().finally(back)).catch(() => {});
  };
  go.addEventListener("click", () => { if (!go.disabled) start(); });
  cancel.addEventListener("click", () => { postJson("/api/sign-in/cancel", { id: waits.sign_in }); });
  return { node, start, signed, refuse };
}

// The panel for a row that waits (tray.js): its form, checked by asking the preview again. A
// token that works closes the panel after a moment; a refused one keeps it, with the reason. A
// server that signs in through the browser gets the Sign in form (`start`: begin at once).
export function openAccess(row, { start = false } = {}) {
  const { waits } = row;
  const kicker = waits.kind === "sign-in" ? "Needs sign-in" : "Needs token";
  const check = async (values) => {
    const joined = await giveAccess(row.key, values);
    if (joined) {
      // The sign-in form shows Signed in itself when its check answers true.
      if (form.works) form.works();
      closeSoon(form);
    } else if (joined === false && row.waits) form.refuse(row.waits.reason);
    return joined;
  };
  const form = waits.kind === "sign-in" && waits.sign_in
    ? signInForm(waits, (id) => check({ sign_in: id }), check)
    : accessForm(waits, check);
  openForm(kicker, waits.server, waits.refused ? null : waits.reason, form.node);
  if (waits.refused) form.refuse(waits.reason);
  if (form.focus) form.focus();
  if (start && form.start) form.start();
  return form;
}

// A held server whose sign-in ended (Part 3b): Sign in again in its own panel. Once signed in,
// a row joins the tray that writes the new sign-in to its Keychain item on Apply.
export async function signInAgain(name, { back = null } = {}) {
  const reason = `${name} needs sign-in again.`;
  const form = await heldSignIn(name, reason);
  openForm("Needs sign-in", name, reason, form.node, back);
  form.start();
  return form;
}

// The Sign in form for a held server: a sign-in id from the page, and once signed in a row in the
// tray that writes it to the server's Keychain item on Apply.
async function heldSignIn(name, reason) {
  const offered = await postJson("/api/sign-in/offer", { server: name });
  if (!offered.ok) throw new Error(offered.data?.detail || "Kitden could not start sign-in.");
  const waits = { server: name, kind: "sign-in", sign_in: offered.data.id, fields: [], reason };
  const signed = async (id) => {
    const body = { action: "gateway.sign_in", targets: [], params: { server: name, sign_in: id } };
    await addToTray(body);
    if (inTray(keyFor(body))) return true;
    if (tray.refused) form.refuse(tray.refused.reason);
    return false;
  };
  const form = signInForm(waits, signed);
  return form;
}

// Replace… in a held server's Access block: the access form for that one value, in its own
// panel. Its check is the preview of the change, as when the server was added: a value that
// works joins the tray (preview, Apply, Undo); a refused one keeps the panel, with the reason.
export function replaceAccess(server, row, { back = null } = {}) {
  const local = row.field === "env";
  const field = { field: row.field, name: row.name, label: row.name, prefix: row.name === "Authorization" ? "Bearer " : "", later: local };
  const waits = { server, kind: "token", fields: [field], reason: "" };
  const form = accessForm(waits, async (values) => {
    const value = values && values[row.field] && values[row.field][row.name];
    const body = { action: "gateway.access", targets: [], params: { server, field: row.field, name: row.name, value } };
    await addToTray(body);
    if (inTray(keyFor(body))) {
      form.works();
      closeSoon(form);
    } else if (tray.refused) form.refuse(tray.refused.reason);
  });
  openForm("Replace", server, `A new ${row.name}. The old one stays until Apply.`, form.node, back);
  form.focus();
  return form;
}

// The tray row for new access to a held server, or null while a value (or a header's or
// variable's name) is missing. A token is sent as "Authorization: Bearer <token>"; a pasted
// "Bearer …" keeps one prefix.
export function newAccess(server, way, name, value) {
  const given = String(value || "").trim();
  const called = String(name || "").trim();
  if (!given) return null;
  const params = (field, key, text) => ({ action: "gateway.access", targets: [], params: { server, field, name: key, value: text, added: true } });
  if (way === "token") return params("headers", "Authorization", `Bearer ${given.replace(/^bearer\s+/i, "")}`);
  if (!called) return null;
  return params(way === "variable" ? "env" : "headers", called, given);
}

// The ways to give a server access: a remote server takes a token, a header of its own or a
// browser sign-in (only one that offers it); a local one a variable. `hint` says where the value
// comes from; `say`, how it is sent, waits under Details.
const WAYS = {
  token: { label: "Token", fields: [], hint: "The server's docs or your account page there give it.", say: "Sent as the Authorization header, with \"Bearer\" in front." },
  header: { label: "Header", fields: ["Header name", "X-API-Key"], hint: "The server's docs name the header and say where to get its value.", say: "Sent as this header on every request." },
  "sign-in": { label: "Sign in", fields: null, hint: "Opens the server's own sign-in page in your browser.", say: "The sign-in is kept in your Keychain and refreshed by the gateway." },
  variable: { label: "Variable", fields: ["Variable name", "API_KEY"], hint: "The server's docs name the variable and say where to get its value.", say: "Set as this variable when the gateway starts the server." },
};

// What a remote server answered when asked with no value (/api/gateway/access-kind), in words;
// none when it wants a value or did not answer.
const KIND_SAYS = {
  open: (name) => `${name} answers without a token or header now. Add one only if its docs ask for it.`,
  "sign-in-later": (name) => `${name} has a sign-in Kitden cannot use yet. It may take an API key; see its docs.`,
};

// Add access… in a held server's Access block: one form, a choice of way first (a remote server
// only). The server is asked first what it takes: Sign in shows only for one that offers it, and
// one that needs nothing says so. Preview adds a row to the tray; a remote server is asked with
// the value first, and a server that answers without it says the first call checks it. Sign in
// runs in the same form, so another way is one click away when it does not finish.
export function addAccess(server, { remote = true, back = null, need = null } = {}) {
  const ways = remote ? ["token", "header"] : ["variable"];
  // A value the server's catalog entry requires (`need`): its way, its name filled in, and the
  // catalog's words for where to get it.
  const needWay = !need ? null : need.field === "env" ? "variable" : need.prefix || need.name.toLowerCase() === "authorization" ? "token" : "header";
  let way = ways.includes(needWay) ? needWay : ways[0];
  const form = el("form", "form access-form");
  const pick = el("div", "seg sm");
  const kindSay = el("p", "muted");
  kindSay.hidden = true;
  const fields = el("div", "access-fields");
  const hint = el("p", "muted");
  // How the value is sent: technical, so under Details.
  const say = el("p", "muted");
  const how = el("details", "access-names");
  how.append(el("summary", null, "Details"), say);
  const saved = el("p", "muted", `Saved in your ${secretsWord()} on Apply.`);
  const submit = el("button", "btn primary", "Preview");
  submit.type = "submit";
  const { why, done, refused, worked } = statusLines();
  let name = null;
  let value = null;
  let drawn = 0;
  const draw = () => {
    const ask = WAYS[way];
    const turn = ++drawn;
    const needed = way === needWay;
    say.textContent = ask.say;
    hint.textContent = needed && need.label && need.label !== need.name ? need.label : ask.hint;
    name = value = null;
    fields.replaceChildren();
    submit.hidden = ask.fields === null;
    why.hidden = done.hidden = true;
    // The Sign in form says where it is saved itself, and its hint goes above its button.
    saved.hidden = hint.hidden = ask.fields === null;
    if (ask.fields === null) {
      heldSignIn(server, ask.hint).then((signIn) => {
        if (turn === drawn) fields.replaceChildren(el("p", "muted", ask.hint), signIn.node);
      }).catch((error) => {
        if (turn === drawn) refused(error.message);
      });
      return;
    }
    const input = (label, type, placeholder) => {
      const line = el("label", "field");
      const box = el("input");
      Object.assign(box, { type, placeholder, autocomplete: "off", spellcheck: false });
      line.append(el("span", null, label), box);
      fields.append(line);
      return box;
    };
    if (ask.fields.length) name = input(ask.fields[0], "text", ask.fields[1]);
    if (name && needed) name.value = need.name;
    value = input(way === "token" ? "Token" : "Value", "password", way === "token" ? "Paste token" : "Enter value");
  };
  const choices = [];
  const choose = (id) => {
    const choice = button(WAYS[id].label, () => {
      way = id;
      for (const other of choices) other.setAttribute("aria-pressed", String(other === choice));
      glide(pick, choice, "access-way", { duration: 280 });
      draw();
      (name?.value ? value : name || value)?.focus();
    }, "");
    choice.setAttribute("aria-pressed", String(id === way));
    choices.push(choice);
    pick.append(choice);
    return choice;
  };
  ways.forEach(choose);
  if (ways.length > 1) form.append(pick);
  form.append(kindSay, fields, hint, why, done, saved, how, submit);
  draw();
  form.addEventListener("input", () => { why.hidden = true; });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const body = newAccess(server, way, name?.value, value?.value);
    if (!body) {
      (name && !name.value.trim() ? name : value)?.focus();
      return;
    }
    submit.textContent = "Checking…";
    const check = addToTray(body).then(() => {
      if (!inTray(keyFor(body))) {
        if (tray.refused) refused(tray.refused.reason);
        shake(fields);
        return;
      }
      const note = (tray.change?.steps || []).find((step) => step.name === server && step.check_note)?.check_note;
      if (way === "variable" || note) {
        why.hidden = true;
        done.replaceChildren(note || "Saved on Apply. Checked when the gateway starts it");
        done.hidden = false;
        return;
      }
      worked("Works");
      closeSoon({ node: form });
    }).finally(() => { submit.textContent = "Preview"; });
    busyWhile(submit, check).catch(() => {});
  });
  openForm("Add access", server, remote ? "What the server asks for. Nothing changes until Apply." : "A variable with a secret. Nothing changes until Apply.", form, back);
  if (ways.length > 1) glide(pick, choices[ways.indexOf(way)], "access-way", { animated: false });
  (name?.value ? value : name || value)?.focus();
  // What the server takes, asked with no value: Sign in joins the choice only when it offers it.
  if (remote) {
    postJson("/api/gateway/access-kind", { server }).then((answer) => {
      const kind = answer.ok ? answer.data?.kind : null;
      if (!form.isConnected) return;
      if (kind === "sign-in") choose("sign-in");
      // A key its catalog entry requires outweighs a server that answers without it.
      const words = need ? null : KIND_SAYS[kind];
      if (words) {
        kindSay.textContent = words(server);
        kindSay.hidden = false;
      }
    }).catch(() => {});
  }
}
