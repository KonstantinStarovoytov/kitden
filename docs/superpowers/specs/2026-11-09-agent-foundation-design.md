# Agents for Kitden: the foundation and the two reviewers

Date: 2026-11-09. Owner's choices from a chat the same day; the rest are the writer's calls,
marked "(call)". Facts about other tools were checked on 2026-11-09; the sources are at the end.

## Why

The owner wants agents to run Kitden's development cycle. He approves the roadmap and new
features and answers people when a human is needed; agents do the rest and call him on GitHub.
The failure he named: the product bloats, grows useless features and gets worse to use. He also
wants the setup to be a public, working example of agent-run development.

This is the first of several projects. It builds what every later agent stands on (rules,
limits, secrets, measurement, a second repository) and the two reviewers. Reviewers come first
because they only comment: a mistake costs a wrong comment, not a wrong merge.

## The whole picture

Context only; this document covers step 1.

1. Foundation and two reviewers (this document).
2. Triage of issues and contributors.
3. Watcher of Claude Code, Codex and Cursor changes: a small LangGraph graph inside one run, on
   GPT-6 Luna; the pull request it opens is the pause for the human (owner).
4. Bug fixer.
5. QA.
6. Auto-merge, last.

Two pieces have no agreed place yet (call): a product guard, which should land before the first
agent that writes code, and automatic review of fork pull requests, which the owner wants as its
own project after this one.

One rule decides who acts: an agent acts alone on anything that keeps Kitden working; anything
new needs the owner. No agent orchestrates the others: GitHub events, labels and checks do.

## Goals

1. Every pull request from a branch of the `kitden` repository gets two independent reviews as
   comments: one from Claude on a strong model, paid by the owner's Max subscription, and one
   from GPT-6 Luna through Codex, paid by the owner's OpenAI key.
2. The rules for agent workflows are written once and checked by CI, so an unsafe agent
   workflow cannot be merged unnoticed.
3. The owner can stop every agent with one switch. No agent runs more often, longer or at a
   higher cost than its written limits.
4. A short product principles file exists in `kitden`, approved by the owner, and both
   reviewers read it.
5. A set of real Kitden review tasks exists, and the Claude reviewer's model was chosen by
   running it.
6. The second repository shows a stranger in one minute which agents run, what limits they
   have, and the numbers: pull requests reviewed, findings the owner marked useful, cost.
7. After a month the numbers say whether Luna earns its place.

## Non-goals

- Triage, a product guard check, the watcher, the bug fixer, QA, auto-merge.
- Reviews of pull requests from forks. Until that project exists the owner reviews them himself.
- Telegram. GitHub notifications only.
- An orchestrator agent, GitHub Agentic Workflows, outside MCP servers in CI.
- Reviewers that approve, request changes, push commits or merge.

## Anti-goals

- A job that holds untrusted text, a secret and write permission at the same time.
- A reviewer whose rules a pull request can change. What a pull request is judged by comes
  from `kitden-agents` at a fixed point or from the base branch of `kitden`.
- Review noise: style remarks, a new comment on every push, more than one summary per reviewer
  per pull request.
- Agents quietly using up the owner's Max limit, or going past $5 a month on the OpenAI key.
- A blocked merge because an agent is down. Neither review is a required check (call).
- A showcase written as a portfolio piece. The second repository describes a working system
  with real numbers, failures included.

## The parts

### 1. Two repositories

Two from the start (owner).

- `kitden` keeps the product and nothing about agents (owner): the code, the tests, the docs,
  CONTRIBUTING.md, AGENTS.md, the existing `release.yml` (its tests and its PyPI publishing are
  tied to this repository), the principles file and the AI policy, which are about Kitden and
  are read by its contributors (part 8). The only agent-related files are two thin workflow
  files, a few lines each, that call a shared workflow in `kitden-agents`. GitHub runs a
  workflow only from the repository where the pull request is, so these two files cannot move.
- `kitden-agents` (name and public from day one: call) keeps everything else: the reusable
  workflows, the role skills packaged as a plugin (the repository is a plugin marketplace), the
  prompts, the rules and their checker, the merge policy in words, the review tasks and their
  results, the numbers, and a README that is the showcase. A second project could use it by
  adding the same two thin files.

`kitden` calls the reusable workflows pinned to a full commit SHA and passes each secret by
name, never `secrets: inherit` (call). The skills come from the same repository through the
action's `plugin_marketplaces` and `plugins` inputs, pinned to a tag, since the action documents
branch and tag pins only; the tag is protected in `kitden-agents` so it cannot move quietly
(call). A pull request in `kitden` therefore cannot change the rules it is judged by: they come
from another repository at a fixed point.

### 2. Rules for every agent workflow

`kitden-agents/RULES.md`, eight rules:

1. No job holds untrusted text, a secret and write permission together. The model reads; a
   step without a model posts, or the action's own comment tool is allowed by its exact name.
2. `pull_request` only, never `pull_request_target`. A job skips when the head is a fork, when
   the actor is a bot, and when the switch is off.
3. `permissions: {}` at the top; each job lists the least it needs.
4. Every action is pinned to a full SHA; a plugin marketplace is pinned to a tag.
5. Every agent job has `timeout-minutes`, a turn limit and `concurrency` with one run per pull
   request, where a newer run cancels the older.
6. Tools are allowed by exact name. Reviewers get no Bash, no web tools and no MCP server; the
   only file writes go to the findings folder on the runner.
7. A secret reaches a job as a named input and is never printed. The Claude token and the
   OpenAI key are never in the same job.
8. An agent's comment starts with one line saying it is automated and which model wrote it.

The checker (call): `actionlint` and `zizmor` run as ordinary CI steps in both repositories,
and a small script fails any workflow that uses `claude-code-action` or `codex-action` and
breaks rules 2 to 5. It runs in `kitden` on every pull request that touches
`.github/workflows/`. Whoever edits an agent workflow also runs the `agentic-actions-auditor`
skill from Trail of Bits locally; that is a line in the AGENTS.md of `kitden-agents`, not a CI
step.

### 3. The switch and the limits

- A repository variable `AGENTS_ENABLED` in `kitden` (call). Every agent job starts with a
  check of it. Off means no agent runs.
- Each reviewer: one review per head commit, drafts skipped, 15 minutes at most (call), a label
  `no-agent-review` to skip one pull request (call), and at most 10 reviews a day per reviewer,
  counted by a step without a model (call).
- OpenAI: a key made for this project only, with a $5 monthly budget set in the OpenAI
  dashboard (owner). When the budget is hit the Luna job fails and nothing else changes.
- Claude runs on the Max subscription through `CLAUDE_CODE_OAUTH_TOKEN`. That limit is shared
  with the owner's own work, which is why the daily cap exists.
- The owner's limits for later agents, at most 3 pull requests waiting for him and at most 2
  new agent pull requests a day, are written into the merge policy now and enforced by the
  first agent that opens pull requests.

### 4. The Claude reviewer

A Kitden-owned review skill, not Anthropic's `code-review` plugin (owner, after the design
check). The plugin reviews a pull request only once, runs its own helpers on Haiku, Sonnet and
Opus, holds `gh` commands including `gh pr comment`, and can be measured only on live pull
requests (its command file, checked 2026-11-09). That breaks rules 1, 3 and 6 and the one-model
comparison in part 6.

- Runs when a pull request is opened, updated, reopened or marked ready: one review per head
  commit.
- A step without a model writes the diff, the list of changed files, the pull request's title
  and body, and `PRINCIPLES.md` and AGENTS.md from the base branch into a folder `.review/` on
  the runner. Then `anthropics/claude-code-action` runs the skill `review-kitden` (name: call)
  from the `kitden-agents` plugin, loaded from a checkout of `kitden-agents` at the same commit
  as the shared workflow, so skill and workflow are pinned together by SHA (call; the
  marketplace-and-tag path is the fallback if the action cannot load a plugin from a folder).
  The pull request cannot change the skill it is judged by, because the skill is not in
  `kitden` at all.
- Tools: read-only file tools, and writing only inside `.review/`. No Bash, no web, no MCP
  server. The model's job has read permission only and the job's own GitHub token, so the
  Claude GitHub App is not needed (call).
- The model writes `.review/findings.json` in the same fixed schema Luna uses: a summary, the
  list of things a user can newly see or set, and findings with file, line and text. A second
  job without a model posts it, the same way as for Luna (part 5). One posting script serves
  both reviewers (call).
- One model through `--model`: Sonnet 5.5 or Opus 5.5, chosen by part 6.
- It looks for bugs first, then for breaks of Kitden's own rules in AGENTS.md (every change
  goes through preview, Apply with a backup, verify, Undo; tests use sandbox homes). Each
  finding is one inline comment with the file and line; at most five per push (call). Findings
  already posted are not repeated.
- One summary comment, edited in place on later pushes. Until a product guard exists, the
  summary says when a change adds something a user can see or set: a route, a command, a
  setting, a page element, a dependency. This is a note for the owner, not a verdict (call).
- It never approves, requests changes or pushes.

### 5. The Luna reviewer

GPT-6 Luna only (owner). The writer told the owner that a cheap second reviewer may add little;
part 7 measures it.

- `openai/codex-action` with `model: gpt-6-luna`, in the two-job shape of the action's README.
  The first job has `contents: read`, the key and `safety-strategy: read-only` (call), and
  writes its findings to a file in a fixed schema: file, line, what is wrong. The second job
  has no model and no key and has `pull-requests: write`. It posts one inline comment per
  finding, so each can get its own thumb as Claude's do, and one summary comment that it edits
  in place on later pushes. A finding it already posted is not posted again (call).
- At most five findings per push, bugs only (call).
- Its prompt is a file in `kitden-agents`. `kitden`'s AGENTS.md is not changed for it.
- At $0.10 and $0.50 per million tokens the $5 budget should be far more than a month of
  reviews. This is an expectation, not a measurement.

### 6. The review tasks

In `kitden-agents/evals/`. Twenty to start (call); Anthropic's advice is 20 to 50 tasks drawn
from real failures.

- Each task is a real Kitden change with a known defect: a merged pull request whose bug was
  fixed later, or a real pull request with one defect put back by hand. It records the base
  commit, the diff, the file and line of the defect and one sentence on what is wrong.
- Three clean changes count false alarms. One task carries text in the diff that tells the
  reviewer to ignore its rules; it passes when the reviewer does not obey.
- Score per model: defects found, false findings, time. A model may match findings to the
  known defect and must be able to answer "cannot tell"; the owner spot-checks five (call).
- Runs: the same review skill on a checkout at the base commit with the diff applied, with no
  pull request involved; the Claude reviewer on Sonnet 5.5, Opus 5.5 and Haiku 5.5, in small
  batches because they use the subscription; Luna once. The table is committed. The owner picks
  the model; the writer's suggestion is the cheapest one within one defect of the best.

### 7. The numbers

- The owner marks an agent's finding with a thumbs-up when it was useful and a thumbs-down
  when it was wrong or noise (call).
- A weekly job in `kitden-agents`, a plain script with no model, counts per reviewer the pull
  requests reviewed, the findings, the thumbs up and down, and the runs, and commits the result.
- The job does not match Luna's findings against Claude's. The owner sees both on the pull
  request; "useful findings per reviewer" is the number the Luna decision rests on (call).
- OpenAI cost is copied from the dashboard once a month by hand (call).
- Thirty days in, the owner reads the table and decides whether Luna stays.

### 8. The principles file and the AI policy

Both in `kitden` (call): they are about Kitden, not about agents, and the people who contribute
read them next to CONTRIBUTING.md. The reviewers read the principles from the base branch of
`kitden`, never from the pull request.

- `PRINCIPLES.md` (name: call). The writer drafts it from the owner's three pillars, his three
  requirements and AGENTS.md; the owner edits and approves it, the "we do not do" list above
  all (owner). Forty lines at most (call): what Kitden is for, what it must always be, what it
  does not do, what counts as new. AGENTS.md points to it so both reviewers see it.
- `AI_POLICY.md`. Contributions made with AI are welcome when the author says so, understands
  the code and answers questions personally (owner). It also lists Kitden's own bots: what each
  does, what it never does, and how to ask for a human.
- CONTRIBUTING.md points to both.

### 9. The showcase README

One screen in `kitden-agents`: what this is, a table of agents (role, trigger, model, what it
may do, limits), the eight rules, the numbers, a short log of what went wrong and what changed
because of it, and how to copy the setup. Plain English. It leads with the problem and the
working system; no job titles and no "portfolio" (owner's standing rule).

### 10. What only the owner does

Settings and secrets; neither the builder nor an agent does these.

- Creates `kitden-agents`.
- Runs `claude setup-token` and saves the result as the secret `CLAUDE_CODE_OAUTH_TOKEN`.
- Creates the OpenAI project key with its $5 budget and saves it as `OPENAI_API_KEY`.
- Sets `AGENTS_ENABLED`.
- Approves `PRINCIPLES.md`.

## Left to the builder

File and job names, the text of the review skill and of the Luna prompt, the findings schema,
how the checker is written, turn limits, how the reviewers are pointed at AGENTS.md and
`PRINCIPLES.md`, and how the review tasks are run.

## Checked facts

- `claude-code-action` accepts a subscription token made by `claude setup-token`, on Max too,
  and such runs use the subscription, not API billing. On a public repository GitHub gives no
  secrets to runs from fork pull requests. A skill packaged in a plugin is installed with the
  `plugin_marketplaces` and `plugins` inputs and invoked as `/plugin-name:skill-name`.
  ([Claude Code docs](https://code.claude.com/docs/en/github-actions))
- Anthropic's `code-review` plugin: skips a pull request that already has a Claude comment,
  assigns Haiku, Sonnet and Opus to its own steps, and allows `gh pr diff`, `gh pr comment` and
  other `gh` commands. ([command file](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-review/commands/code-review.md))
- `codex-action` needs an API key, takes `model` and `safety-strategy`, and its review example
  posts from a second job. ([README](https://github.com/openai/codex-action/blob/main/README.md))
- `gpt-6-luna` costs $0.10 per million input tokens and $0.50 per million output tokens.
  ([OpenAI model page](https://developers.openai.com/api/docs/models/gpt-6-luna))
- Standard GitHub-hosted runners are free in public repositories; the page does not name macOS
  runners. ([GitHub billing docs](https://docs.github.com/en/billing/concepts/product-billing/github-actions))

Not checked: whether the action can load a plugin from a folder on the runner (`--plugin-dir`)
or only from a marketplace pinned to a branch or tag; whether a `Write(.review/**)` permission
rule limits writes as intended; how Max counts usage per model.

The wider research behind these choices is in `reports/Агентный SDLC практики скиллы и MCP.md`
in the owner's checkout.
