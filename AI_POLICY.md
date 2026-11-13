# AI policy

## Contributions made with AI

They are welcome. Say in the pull request that AI helped. You must understand the code you
send and answer questions about it yourself.

## Automated reviewers

Two bots review pull requests: `claude` and `luna`. They look for bugs and check the change
against [PRINCIPLES.md](PRINCIPLES.md).

- They only comment. They never approve, request changes, push or merge.
- They share one comment per pull request, posted by the `kitden-lantern` bot. It starts
  with the title "Agent review" and ends with "👍 useful · 👎 wrong".
- Pull requests from forks get no automatic review for now.

Only the maintainer's 👍 or 👎 on a comment is counted. To reach the maintainer, mention
`@KonstantinStarovoytov` in a comment.

## Automated issues

`kitden-lantern` also opens issues. They carry the label `automated` and one that says where
they come from: `client-change`, `release` or `desk`. An issue without `automated` is from a
person; the bot never edits, labels or closes it. A maintainer marks a bot issue `confirmed`
(real, open until fixed) or `false-alarm`; wait for `confirmed` before you work on it. The
pinned issue "Kitden desk" shows what the automation did and what waits for the maintainer.
A script writes it, not an AI model.
