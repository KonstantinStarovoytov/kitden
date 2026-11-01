// The one form that asks for what a server needs before it can join the preview (Part 3a of the
// 2026-11-01 design): one field per value the server declares, labelled with its own words. A
// plain token is the token alone; Kitden adds "Bearer ". The header or variable name shows only
// under Details. The catalog details, the map and the dock all use it.
import { busyWhile, el, icon } from "./dom.js";
import { closePanel, header, openPanel } from "./panel.js";
import { animateTo, D, shake } from "./motion.js";
import { giveAccess } from "./tray.js";

// "Token works" shows a moment before the panel goes.
const WORKS_MS = 600;

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
  const why = el("p", "access-why");
  why.setAttribute("role", "alert");
  why.hidden = true;
  const done = el("p", "access-works");
  done.hidden = true;
  // With only optional values (a remote that may take a token), the form previews without one.
  const label = required.length ? "Add token" : "Preview";
  const submit = el("button", "btn primary", label);
  submit.type = "submit";
  form.append(rows, why, done, el("p", "muted", "Saved in macOS Keychain on Apply."), names, submit);

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
  // Token works: the green lamp, and a check drawn in 320 ms.
  const works = () => {
    why.hidden = true;
    const mark = icon("check", 14, "ic access-check");
    done.replaceChildren(el("span", "lamp on"), mark, "Token works");
    done.hidden = false;
    const line = mark.querySelector?.("path");
    if (line) animateTo(line, [{ strokeDashoffset: 24 }, { strokeDashoffset: 0 }], { dur: 320 });
  };
  // Refused: amber words that stay, focus back in the field, and one shake of the fields.
  const refuse = (reason) => {
    done.hidden = true;
    why.replaceChildren(icon("triangle-alert", 14), reason);
    why.hidden = false;
    animateTo(why, [{ opacity: 0, transform: "translateY(4px)" }, { opacity: 1, transform: "none" }], { dur: 200 });
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

// The panel for a row that waits (tray.js): its form, checked by asking the preview again. A
// token that works closes the panel after a moment; a refused one keeps it, with the reason.
export function openAccess(row) {
  const { waits } = row;
  const kicker = waits.kind === "sign-in" ? "Needs sign-in" : "Needs token";
  const form = accessForm(waits, async (values) => {
    const joined = await giveAccess(row.key, values);
    if (joined) {
      form.works();
      setTimeout(() => { if (form.node.isConnected) closePanel(); }, D(WORKS_MS));
    } else if (row.waits) form.refuse(row.waits.reason);
  });
  const body = el("div", "body");
  body.append(form.node);
  openPanel([header(kicker, waits.server, waits.refused ? null : waits.reason), body]);
  if (waits.refused) form.refuse(waits.reason);
  form.focus();
  return form;
}
