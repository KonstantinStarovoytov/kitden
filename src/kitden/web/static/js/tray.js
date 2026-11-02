// The preview tray: every change waits here, and all its rows are previewed as one change, so
// Apply all and Undo all write everything or nothing. This module holds the state and talks to
// the server; the dock draws it.
import { getJson, postJson } from "./api.js";
import { CLIENT_ORDER } from "./parts.js";
import { busy, setBusy, state } from "./store.js";

// The states a change can end in after each verb. Read back in any other state it has not
// ended, so the page cannot say how it went.
const ENDED = {
  apply: ["verified", "stale", "restored", "cancelled", "undone", "undo_blocked"],
  undo: ["undone", "undo_blocked"],
};
export const LOST = "Could not confirm the result. Check Changes before trying again.";

// The change as the server holds it now, or null when it cannot be read.
export async function readChange(id) {
  try {
    return await getJson(`/api/changes/${encodeURIComponent(id)}`);
  } catch {
    return null;
  }
}

// How the change ended, read back from the server, when the answer cannot say.
async function readOutcome(id, verb) {
  const read = await readChange(id);
  return { after: read && ENDED[verb].includes(read.state) ? read : null, failure: LOST };
}

// How an Apply or an Undo ("apply", "undo") ended: the change as the server holds it, or why
// it failed. `body` goes with the request (Apply all sends the rows' titles).
export async function changeOutcome(id, verb, body) {
  const name = verb === "undo" ? "Undo" : "Apply";
  let result;
  try {
    result = await postJson(`/api/changes/${encodeURIComponent(id)}/${verb}`, body);
    if (!result.data) throw new Error(`The ${name} answer had no body (${result.status}).`);
  } catch (error) {
    // No answer, or one with no body, yet the change may have run: ask the server how it ended.
    console.error(error);
    return readOutcome(id, verb);
  }
  if (result.data.id) return { after: result.data, failure: null };
  // 409 with no change: it had moved on already, for example by an Apply whose answer was lost.
  if (result.status === 409) return readOutcome(id, verb);
  return { after: null, failure: result.data.detail || `${name} failed (${result.status}).` };
}

// The one tray of the page. `phase`: "idle" (no rows), "asking" (a preview is on its way),
// "ready", "waiting" (every row waits for access, so there is no change), "applying",
// "applied" (verified; the page takes the result in, then calls endApplied) or "failed". A
// row: { id, key, body, note, icon, picked, title, detail, project, part, status, waits,
// works }; `status` is "", "busy" or "done". `waits` is null, or what a server needs before
// it can join the change: { server, kind, fields, reason, refused, checking } (a row that
// waits is left out of the change, so Apply writes the others). `works`: its token was
// checked and taken. `refused`: { reason } or null. `failure`:
// { state, error } of an Apply that was not verified, `state` null when its end is not known.
// `stale`: the files changed since the preview.
export const tray = { rows: [], change: null, phase: "idle", refused: null, failure: null, done: 0, total: 0, stale: false };

// The title a row is sent with until its first answer gives it words.
export const PENDING_TITLE = "New change";

const listeners = new Set();
// Every ask for a preview (add, take out, Try again, Cancel all) takes the next number; an answer
// that is not for the latest one is dropped.
let asks = 0;
let rowCount = 0;
// Set once by dock.js: the words of a row, from its part of the change.
let wordsFor = () => ({ title: "", detail: "" });

export function setTrayWords(fn) { wordsFor = fn; }

// `fn(tray)` after every change of state. Returns the way to stop.
export function onTray(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// A drawing that breaks must not stop the tray.
function notify() {
  for (const listener of [...listeners]) {
    try { listener(tray); } catch (error) { console.error(error); }
  }
}

// JSON with the keys of every object in order, so two bodies that differ only in key order match.
function sorted(value) {
  if (Array.isArray(value)) return value.map(sorted);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sorted(value[key])]));
  return value;
}

// What a change is about: a second press of the same switch or rule is the same row. A
// switch is named by what it switches, so on and off share a key. A server moves out of the
// gateway to one client: a pick of another client replaces the row. A marketplace server is
// named by its row in the Add panel.
export function keyFor(body) {
  const { action, targets = [], params = {} } = body;
  if (action === "plugin.enable" || action === "plugin.disable") return `switch:${(targets[0] || {}).item}`;
  if (action === "gateway.rule") return `rule:${params.server}/${params.tool}@${params.project || ""}`;
  if (action === "gateway.strict") return `strict:${params.server}`;
  if (action === "gateway.move_out") return `moveout:${params.server}`;
  if (action === "project.align") return `align:${params.project || ""}`;
  if (action === "gateway.add") return `add:${params.server}`;
  const one = targets[0] || {};
  if (action === "skill.rule") return `skill:${one.client}:${one.item}@${params.project || ""}`;
  return JSON.stringify(sorted({ action, targets: inClientOrder(action, targets), params }));
}

// An add of a plugin or a skill is the same change whatever order its clients were picked in: the
// List's forms, the add panel and a drag give it one key.
const ADD_ORDER = ["plugin.install", "skill.install"];
function inClientOrder(action, targets) {
  if (!ADD_ORDER.includes(action)) return targets;
  const at = (target) => (CLIENT_ORDER.includes(target.client) ? CLIENT_ORDER.indexOf(target.client) : CLIENT_ORDER.length);
  return [...targets].sort((a, b) => at(a) - at(b));
}

const REMOVES = ["mcp.remove_direct", "plugin.remove", "skill.remove", "gateway.remove"];
const SWITCHES = ["gateway.rule", "gateway.rules", "gateway.strict", "plugin.enable", "plugin.disable", "setup_server.enable", "skill.rule"];
const MOVES = ["gateway.move", "gateway.put_back", "gateway.keychain"];
const PLUGS = ["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update", "client.disconnect"];
const ADDS = ["mcp.add", "plugin.install", "plugin.skills", "skill.install", "marketplace.add", "gateway.add"];

// The icon of a row in the bar.
export function iconFor(body) {
  const { action, params = {} } = body;
  if (params.project || action === "project.align") return "folder";
  if (REMOVES.includes(action)) return "x";
  if (action === "gateway.move_out") return "log-out";
  if (SWITCHES.includes(action)) return "toggle-right";
  if (MOVES.includes(action)) return "arrow-right";
  if (PLUGS.includes(action)) return "plug";
  return ADDS.includes(action) ? "plus" : "file-text";
}

// The rows the change covers, and the ones that wait for access.
export function readyRows(t = tray) { return t.rows.filter((row) => !row.waits); }
export function waitingRows(t = tray) { return t.rows.filter((row) => row.waits); }

export function inTray(key) {
  return tray.rows.some((row) => row.key === key);
}

// One row of the combined change as a change of its own kind: only its steps, and the words the
// server worked out for it. A review reads it as it reads a change asked for alone.
export function partOf(change, answerRow) {
  const { kind, steps, target, after, undo_note, left_out, align } = answerRow;
  const part = { ...change, action: kind, steps: steps.map((index) => change.steps[index]), target, after, undo_note, left_out, align };
  delete part.rows;
  return part;
}

// The server forgets a preview nobody will apply. Sent once: the change is marked cancelled.
function cancelOnServer(change) {
  if (!change || change.state !== "previewed") return Promise.resolve();
  change.state = "cancelled";
  return postJson(`/api/changes/${encodeURIComponent(change.id)}/cancel`).catch(() => {});
}

function requestFor(row) {
  const { body } = row;
  return { id: row.id, kind: body.action, title: row.title || PENDING_TITLE, detail: row.detail || "", targets: body.targets || [], params: body.params || {}, picked: row.picked };
}

// The rows as one change, from the server: { change } or { reason } (a refusal, or no answer);
// a row that waits for access adds { row, needs }.
async function previewRows(rows) {
  let result;
  try {
    result = await postJson("/api/batch/preview", { requests: rows.map(requestFor) });
  } catch (error) {
    console.error(error);
    result = { ok: false, status: 0, data: null };
  }
  const data = result.data;
  if (result.ok && data && data.id && Array.isArray(data.rows)) return { change: data };
  const detail = data && typeof data.detail === "string" ? data.detail : "";
  const reason = detail || `Could not prepare this change (${result.status}).`;
  if (data && data.needs && data.row) return { reason, row: data.row, needs: data.needs };
  return { reason };
}

// Ask for a preview of `rows` (the ones that do not wait, by default). An answer to an older
// ask is dropped and its change cancelled on the server: { dropped: true }. Else as
// previewRows answers.
async function ask(rows = readyRows()) {
  const mine = ++asks;
  tray.phase = "asking";
  tray.refused = null;
  notify();
  const answer = await previewRows(rows);
  if (mine === asks) return answer;
  if (answer.change) cancelOnServer(answer.change);
  return { dropped: true };
}

// The latest answer: its change replaces the old one (which the server then forgets) and each
// row takes its words from its own part. `refused` is the notice to keep, if any.
function accept(change, refused = null) {
  cancelOnServer(tray.change);
  const answers = new Map(change.rows.map((row) => [row.id, row]));
  for (const row of tray.rows) {
    const found = answers.get(row.id);
    if (!found) continue;
    row.part = partOf(change, found);
    const { title, detail } = wordsFor(row.part, row.body, row.note);
    Object.assign(row, { title, detail, project: found.project || null, status: "" });
  }
  Object.assign(tray, { change, phase: "ready", refused, failure: null, done: 0, total: 0, stale: false });
  notify();
}

// A preview of the rows that were already there was refused: they stay, with no change. Cancel
// all or Try again follows.
function refuseRows(reason) {
  cancelOnServer(tray.change);
  Object.assign(tray, { change: null, phase: "failed", refused: { reason }, failure: null, done: 0, total: 0, stale: false });
  notify();
}

// A tray whose rows all wait has no change: "waiting", or "idle" with no rows.
function noChange() {
  cancelOnServer(tray.change);
  asks += 1;
  Object.assign(tray, { change: null, phase: tray.rows.length ? "waiting" : "idle", refused: null, failure: null, done: 0, total: 0, stale: false });
  notify();
}

// A row starts to wait for what `needs` says; its words are the server's name and the reason.
function startWaiting(row, needs) {
  Object.assign(row, { waits: { ...needs, checking: false }, works: false, title: needs.server, detail: needs.reason, part: null, status: "" });
}

// Ask again for the rows as they are, after a take-out, Try again, or a refused add that
// dropped an ask for the others.
async function repreview(refused = null) {
  if (!readyRows().length) return noChange();
  const answer = await ask();
  if (answer.dropped) return;
  if (answer.change) accept(answer.change, refused);
  else refuseRows(answer.reason);
}

function empty() {
  Object.assign(tray, { rows: [], change: null, phase: "idle", refused: null, failure: null, done: 0, total: 0, stale: false });
  notify();
}

// Add a change to the tray (a row with the same key is replaced and goes last; until its answer it
// keeps the old row's words, so the bar does not go and come back). True when it joined: false
// when the server refused it (`tray.refused` says why, and the tray is as it was), or when it
// cannot join now: a change is being written, or has just been applied. `picked` is the project
// it is asked in: the one picked now, or the old row's when a row's own review asks again.
export async function addToTray(body, { key = keyFor(body), note = null, icon = iconFor(body), picked = state.project || null } = {}) {
  if (tray.phase === "applying" || tray.phase === "applied" || busy.change) return false;
  const before = tray.rows;
  const was = tray.phase;
  const old = before.find((row) => row.key === key) || { title: "", detail: "", project: null, part: null };
  const row = { id: `r${++rowCount}`, key, body, note, icon, picked, title: old.title, detail: old.detail, project: old.project, part: old.part, status: "", waits: null, works: false };
  tray.rows = [...before.filter((other) => other.key !== key), row];
  const answer = await ask();
  if (answer.dropped) return tray.rows.includes(row);
  if (answer.change) {
    accept(answer.change);
    return true;
  }
  if (answer.needs && answer.row === row.id) {
    // It joins as waiting. The change still covers the other rows, unless this one replaced a
    // row it covered or an ask for them was dropped: then they are asked for again.
    startWaiting(row, answer.needs);
    const replaced = before.some((other) => other.key === key && !other.waits);
    if (was === "asking" || replaced) await repreview();
    else if (!tray.change) noChange();
    else {
      tray.phase = was;
      notify();
    }
    return true;
  }
  tray.rows = before;
  if (was === "asking") {
    // The ask for these rows was dropped by this one: ask for them again.
    await repreview({ reason: answer.reason });
  } else {
    Object.assign(tray, { phase: was, refused: { reason: answer.reason } });
    notify();
  }
  return false;
}

// A row leaves (`keys`: its key, or the keys of several); the rest are previewed again, in one
// ask. The last one leaving cancels the change.
export async function takeOut(keys) {
  if (tray.phase === "applying" || tray.phase === "applied") return;
  const gone = [].concat(keys);
  const rows = tray.rows.filter((row) => !gone.includes(row.key));
  if (rows.length === tray.rows.length) return;
  if (!rows.length) return cancelTray();
  // Rows that wait are in no change: taking only those out asks nothing.
  const changed = tray.rows.some((row) => gone.includes(row.key) && !row.waits);
  tray.rows = rows;
  if (changed) return repreview();
  notify();
}

// A token (or other values, `{ headers?, env? }`) for a row that waits: the change is asked
// again with that row in it, which is the check. True when it joined. Refused, the row waits
// as before with the reason, and the change and the phase stay as they were.
export async function giveAccess(key, values) {
  const row = tray.rows.find((each) => each.key === key);
  if (!row || !row.waits || row.waits.checking || tray.phase === "applying" || tray.phase === "applied" || busy.change) return false;
  const { body } = row;
  const was = tray.phase;
  row.body = { ...body, params: { ...(body.params || {}), ...values } };
  row.waits = { ...row.waits, checking: true };
  const answer = await ask(tray.rows.filter((each) => !each.waits || each === row));
  if (answer.dropped) {
    if (row.waits) Object.assign(row, { body, waits: { ...row.waits, checking: false } });
    return false;
  }
  if (answer.change) {
    Object.assign(row, { waits: null, works: true });
    accept(answer.change);
    return true;
  }
  row.body = body;
  if (answer.needs && answer.row === row.id) startWaiting(row, answer.needs);
  else Object.assign(row, { waits: { ...row.waits, reason: answer.reason, refused: true, checking: false }, detail: answer.reason });
  if (was === "asking") await repreview();
  else {
    tray.phase = was;
    notify();
  }
  return false;
}

// Cancel all (also Close, after a refusal): the rows go and the server forgets the preview. A
// late answer for an ask still out is dropped. Nothing is cancelled while a change is written.
export async function cancelTray() {
  if (tray.phase === "applying") return;
  asks += 1;
  const { change } = tray;
  empty();
  await cancelOnServer(change);
}

// A fresh preview of the same rows, after a failed Apply or a refused preview, or when the
// files changed since the preview. The person presses Apply again.
export async function tryAgain() {
  if (!tray.rows.length || (tray.phase !== "ready" && tray.phase !== "failed")) return;
  cancelOnServer(tray.change);
  await repreview();
}

// Apply all: the first row spins at once, and each finished step names the row it belongs to.
// Only `verified` ends it well; the page then takes the result in and calls endApplied.
export async function applyTray() {
  if (tray.phase !== "ready" || busy.change || !readyRows().length) return;
  const { change } = tray;
  const ready = readyRows();
  for (const row of tray.rows) row.status = "";
  ready[0].status = "busy";
  Object.assign(tray, { phase: "applying", refused: null, failure: null, done: 0, total: 0 });
  setBusy(true);
  notify();
  const onProgress = (event) => {
    const { id, done, total, row } = event.detail || {};
    if (id !== change.id) return;
    const found = tray.rows.find((candidate) => candidate.id === row);
    if (found) found.status = "busy";
    Object.assign(tray, { done, total });
    notify();
  };
  document.addEventListener("kitden:progress", onProgress);
  try {
    // The titles shown now, which came after the preview was asked: Changes keeps these.
    const titles = ready.map((row) => row.title || PENDING_TITLE);
    const { after } = await changeOutcome(change.id, "apply", { titles });
    if (after && after.state === "verified") {
      for (const row of ready) row.status = "done";
      Object.assign(tray, { change: after, phase: "applied" });
    } else {
      // Kept as the server has it, so Try again knows whether it must cancel the preview.
      if (after) change.state = after.state;
      for (const row of tray.rows) row.status = "";
      Object.assign(tray, { phase: "failed", failure: { state: after ? after.state : null, error: (after && after.error) || null } });
    }
    notify();
  } finally {
    document.removeEventListener("kitden:progress", onProgress);
    setBusy(false);
  }
}

// The page took the applied result in (it read everything again): the tray keeps only the
// rows that wait for access, for a later Apply.
export function endApplied() {
  const left = waitingRows();
  if (!left.length) return empty();
  Object.assign(tray, { rows: left, change: null, phase: "waiting", refused: null, failure: null, done: 0, total: 0, stale: false });
  notify();
}

// The change an Undo has just put back (its id), until the Gateway map draws what Kitden read
// after it: the map then plays that change's rows back (gateway.js). undoChange (review.js) sets it.
export const undone = { id: null };

// After a rescan, whether the files changed since the preview. Only a ready tray is asked, and
// never while a change is written; an answer that comes after the tray moved on is dropped.
export async function checkTrayStale() {
  const { change } = tray;
  if (tray.phase !== "ready" || !change || busy.change) return;
  const read = await readChange(change.id);
  if (!read || !read.stale || tray.stale || tray.change !== change || tray.phase !== "ready" || busy.change) return;
  tray.stale = true;
  notify();
}
