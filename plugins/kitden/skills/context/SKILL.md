---
name: context
description: Use when the user asks whether their skills fit in the context, why the agent does not use or see a skill, which skills lost their description, or how much of the context window the skill list takes.
---

Every chat starts with a list of the user's skills. When the list is over the client's limit,
some skills show only a name, or drop out, and the agent may not use them. Kitden reads what the
client sent in the last chat.

1. In the project's folder run `kitden show context`. It only reads and prints JSON, one card
   for each client. If `kitden` is not found or the command fails as unknown, follow the kitden `install` skill.
2. Use the card of the client the user asks about; by default the one you run in.
3. Give the answer in the card's own words: each window's `say`, then the names in `over`, the
   skills that did not keep their description. A window tagged Estimate is Kitden's estimate,
   not a measurement: say so.
4. If the card has a `message`, or its `lamp` is `none`, Kitden cannot tell for this client.
   Pass the message on and do not guess.
5. When the user asks how Kitden knows, give the card's `how` lines.
6. To make the list fit, the user switches a skill to Name only or Off on the Context page: run
   `kitden open`. Do not edit client settings files; the page previews, backs up and can undo
   every change.
