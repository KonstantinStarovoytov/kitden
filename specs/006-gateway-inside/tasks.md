# Tasks: Manage the gateway from inside Kitden

- [x] T001 Research note, spec, plan, tasks, quickstart (`docs/research/gateway-api-2026-10-19.md`, `specs/006-gateway-inside/`).
- [ ] T002 [US4] Gateway sign-in fields: `Gateway.login_email`, `login_password_env_var` in `src/kitden/model.py`, `src/kitden/gateways.py`, `src/kitden/views/gateway_view.py`, the API and the form in `gateway.js`; tests in `tests/unit/test_gateways.py`, `test_api_changes.py`.
- [ ] T003 [US1] MetaMCP client `src/kitden/gateway_api.py` with the fake server `tests/unit/fake_metamcp.py`; tests `tests/unit/test_gateway_api.py` (sign-in, held, add, remove, errors, no secrets in messages).
- [ ] T004 [US2] Engine gateway steps: `GatewayEdit` in `model.py`, preview/apply/verify/undo/record in `src/kitden/changes/engine.py`; tests in `tests/unit/test_engine.py`.
- [ ] T005 [US2] [US3] Action `gateway.move` in `src/kitden/changes/actions.py`, `GET /api/gateways/{id}/servers` and the preview branch in `src/kitden/web/app.py`, `after_words`; tests in `tests/unit/test_api_changes.py`.
- [ ] T006 [US1] [US2] [US3] Gateway page: held rows, "Move into the gateway…", "Move all N…", review and Changes words (`gateway.js`, `panel.js`, `parts.js`, `changes.js`); wording tests in `tests/unit/test_page_words.py`.
- [ ] T007 Browser check on a fixture home with the fake MetaMCP (both themes, 375 px, Apply and Undo); tick the quickstart.

Order: T001 → T002 → T003 → T004 → T005 → T006 → T007. One commit per task.
