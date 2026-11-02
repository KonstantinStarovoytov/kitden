"""Browser sign-ins that wait for Apply (Part 3b of the 2026-11-01 design).

A batch preview hands out one id per server address that signs in through the browser; the page
starts the flow with that id and re-asks the preview with it once it is done. The tokens stay in
memory here until Apply writes them to the Keychain as one item, `<server>/sign-in`.

This module never imports the MCP SDK; `kitden.local_gateway.oauth` runs the flow.
"""

import secrets
from dataclasses import dataclass, field
from typing import Any

KEY = "sign-in"  # the Keychain item's key: `<server>/sign-in`
TIMEOUT = 300  # seconds a flow waits for the person in the browser

CANCELLED = "Sign-in was cancelled."
NOT_FINISHED = "{name} did not finish sign-in."
TIMED_OUT = "Sign-in did not finish in 5 minutes."
NO_BROWSER = "Kitden could not open the browser."
GONE = "Sign in again: that sign-in is no longer here."
# A held server whose stored sign-in no longer works and could not be refreshed.
SIGNED_OUT = "{server} needs sign-in again."


@dataclass
class SignIn:
    """One sign-in: "new", "waiting" (the browser is open), "done" or "failed". `secret` is the
    JSON the Keychain item gets; neither it nor the token shows in the record's repr."""

    id: str
    url: str
    name: str
    state: str = "new"
    reason: str | None = None
    cancelled: bool = False
    access_token: str | None = field(default=None, repr=False)
    secret: str | None = field(default=None, repr=False)
    flow_state: str | None = field(default=None, repr=False)  # the `state` of the authorize URL
    task: Any = field(default=None, repr=False)
    starting: Any = field(default=None, repr=False)  # the start running now, which others join
    code: Any = field(default=None, repr=False)  # a future the callback fills


class SignIns:
    """The sign-ins of one page, by id."""

    def __init__(self) -> None:
        self._all: dict[str, SignIn] = {}

    def offer(self, url: str, name: str) -> str:
        """The id for this address: the one not finished yet, else a new one (a finished one is
        `kept`, and a new Sign in must not throw its tokens away)."""
        for record in self._all.values():
            if record.url == url and record.state in ("new", "waiting"):
                return record.id
        record = SignIn(id=secrets.token_urlsafe(12), url=url, name=name)
        self._all[record.id] = record
        return record.id

    def get(self, id: str) -> SignIn | None:
        return self._all.get(id)

    def by_state(self, state: str) -> SignIn | None:
        return next(
            (
                r
                for r in self._all.values()
                if r.flow_state and secrets.compare_digest(r.flow_state, state)
            ),
            None,
        )

    def kept(self, url: str) -> SignIn | None:
        """A finished sign-in for this address: a row that comes back uses it again."""
        return next((r for r in self._all.values() if r.url == url and r.state == "done"), None)
