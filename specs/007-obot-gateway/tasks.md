# Tasks: Obot as a gateway in Kitden

Status: Step A **done** on 2026-10-19 (owner's go-ahead the same day); Step B tasks wait for
the research R4 re-check.

## Step A (read-only)

- [x] T001 Research and spec: `docs/research/obot-deploy-2026-10-19.md`, `specs/007-obot-gateway/`.
- [x] T002 [US1] `Gateway.kind` from the address shape; the form shows the key variable for an Obot address and the sign-in fields for MetaMCP (`src/kitden/model.py`, `gateway.js`); tests in `tests/unit/test_gateways.py`.
- [x] T003 [US2] `ObotClient` in `src/kitden/gateway_api.py` with the fake `tests/unit/fake_obot.py`; tests `tests/unit/test_gateway_api.py` (held, missing variable, 401, 403, unexpected shape, no secret in messages).
- [x] T004 [US2] [US4] `GET /api/gateways/{id}/servers` picks the client by kind; the card shows "In the gateway · N" and "Open Obot ↗"; wording tests in `tests/unit/test_page_words.py`.
- [x] T005 [US3] Connect round-trip tests with an Obot address for every client (`env_key` as `${VAR}`, `oauth` with the login note).
- [x] T006 Browser check on a fixture home with the fake Obot, then once against Obot in Docker on the Mac (both themes, 375 px); write the quickstart result.

## Step B (later, conditional)

- [ ] T007 Re-check research R4 against the current Obot release; record the date and verdict.
- [ ] T008 [US5] [US6] Only if T007 passes: `ObotClient.add` and `remove`, the address refusal, `gateway.move` for Obot through the existing engine step, Move all, browser check.

Order: T001 → T002 → T003 → T004 → T005 → T006; T007 → T008. One commit per task.
