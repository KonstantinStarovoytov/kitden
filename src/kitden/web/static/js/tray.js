// The preview tray: every change waits here, and all its rows are previewed as one change, so
// Apply all and Undo all write everything or nothing. This module holds the state and talks to
// the server; the dock draws it.
import { getJson, postJson } from "./api.js";
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
// it failed.
export async function changeOutcome(id, verb) {
  const name = verb === "undo" ? "Undo" : "Apply";
  let result;
  try {
    result = await postJson(`/api/changes/${encodeURIComponent(id)}/${verb}`);
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
// "ready", "applying", "applied" (verified; the page takes the result in, then calls
// endApplied) or "failed". A row: { id, key, body, note, icon, picked, title, detail, project,
// part, status }; `status` is "", "busy" or "done". `refused`: { reason } or null. `failure`:
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
// switch is named by what it switches, so on and off share a key.
export function keyFor(body) {
  const { action, targets = [], params = {} } = body;
  if (action === "plugin.enable" || action === "plugin.disable") return `switch:${(targets[0] || {}).item}`;
  if (action === "gateway.rule") return `rule:${params.server}/${params.tool}@${params.project || ""}`;
  if (action === "gateway.strict") return `strict:${params.server}`;
  if (action === "project.align") return `align:${params.project}`;
  return JSON.stringify(sorted({ action, targets, params }));
}

const REMOVES = ["mcp.remove_direct", "plugin.remove", "skill.remove", "gateway.remove"];
const SWITCHES = ["gateway.rule", "gateway.rules", "gateway.strict", "plugin.enable", "plugin.disable", "setup_server.enable"];
const MOVES = ["gateway.move", "gateway.put_back", "gateway.keychain"];
const PLUGS = ["gateway.connect", "gateway.switch", "setup_server.register", "setup_server.update"];
const ADDS = ["mcp.add", "plugin.install", "plugin.skills", "skill.install", "marketplace.add"];

// The icon of a row in the bar.
export function iconFor(body) {
  const { action, params = {} } = body;
  if (params.project || action === "project.align") return "folder";
  if (REMOVES.includes(action)) return "x";
  if (SWITCHES.includes(action)) return "toggle-right";
  if (MOVES.includes(action)) return "arrow-right";
  if (PLUGS.includes(action)) return "plug";
  return ADDS.includes(action) ? "plus" : "file-text";
}

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

// The rows as one change, from the server: { change } or { reason } (a refusal, or no answer).
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
  return { reason: detail || `Could not prepare this change (${result.status}).` };
}

// Ask for a preview of the tray's rows. An answer to an older ask is dropped and its change
// cancelled on the server: { dropped: true }. Else { change } or { reason }.
async function ask() {
  const mine = ++asks;
  tray.phase = "asking";
  tray.refused = null;
  notify();
  const answer = await previewRows(tray.rows);
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

// Ask again for the rows as they are, after a take-out, Try again, or a refused add that
// dropped an ask for the others.
async function repreview(refused = null) {
  const answer = await ask();
  if (answer.dropped) return;
  if (answer.change) accept(answer.change, refused);
  else refuseRows(answer.reason);
}

function empty() {
  Object.assign(tray, { rows: [], change: null, phase: "idle", refused: null, failure: null, done: 0, total: 0, stale: false });
  notify();
}

// Add a change to the tray (a row with the same key is replaced and goes last). True when it
// joined: false when the server refused it (`tray.refused` says why, and the tray is as it
// was), or when it cannot join now: a change is being written, or has just been applied.
export async function addToTray(body, { key = keyFor(body), note = null, icon = iconFor(body) } = {}) {
  if (tray.phase === "applying" || tray.phase === "applied" || busy.change) return false;
  const before = tray.rows;
  const was = tray.phase;
  const row = { id: `r${++rowCount}`, key, body, note, icon, picked: state.project || null, title: "", detail: "", project: null, part: null, status: "" };
  tray.rows = [...before.filter((old) => old.key !== key), row];
  const answer = await ask();
  if (answer.dropped) return tray.rows.includes(row);
  if (answer.change) {
    accept(answer.change);
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

// A row leaves; the rest are previewed again. The last one leaving cancels the change.
export async function takeOut(key) {
  if (tray.phase === "applying" || tray.phase === "applied") return;
  const rows = tray.rows.filter((row) => row.key !== key);
  if (rows.length === tray.rows.length) return;
  if (!rows.length) return cancelTray();
  tray.rows = rows;
  await repreview();
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
  if (tray.phase !== "ready" || busy.change) return;
  const { change } = tray;
  for (const row of tray.rows) row.status = "";
  tray.rows[0].status = "busy";
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
    const { after } = await changeOutcome(change.id, "apply");
    if (after && after.state === "verified") {
      for (const row of tray.rows) row.status = "done";
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

// The page took the applied result in (it read everything again): the tray is empty.
export function endApplied() {
  empty();
}

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
