// Same-origin JSON calls. Writes carry the header the server requires (research R6).

export function query(params) {
  const parts = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export async function getJson(url) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

// Why a change could not be prepared when the page gave no words: no answer at all (status 0:
// the page stopped) or a failed one. Plain words, no status code.
export function notPrepared(status) {
  return status === 0 ? "Kitden is not running. Start it with kitden open, then try again." : "Could not prepare this change. Try again.";
}

export async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-Tool-Request": "1", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  return { ok: response.ok, status: response.status, data };
}
