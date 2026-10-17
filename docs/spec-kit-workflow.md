# Spec Kit workflow

## Installed setup

Initialized on 2026-10-16 using the already installed **Specify CLI 1.0.10**.
Templates and scripts came from the installed package; no global upgrade was performed.
The local Git repository uses `main`; no remote has been set up.

```sh
specify init --here --integration codex --integration-options='--skills' --script sh --non-interactive
```

The first attempt could not write the protected `.agents` directory. Initialization then
succeeded with filesystem approval and `--force` to complete the partial setup.

| Location | Content |
| --- | --- |
| `.agents/skills/speckit-*/SKILL.md` | Codex skill instructions |
| `.specify/memory/constitution.md` | Project principles |
| `.specify/templates/` | Official templates; kept unchanged |
| `.specify/scripts/bash/` | Official helper scripts |
| `.specify/workflows/` | Installed SDD workflow |
| `.specify/init-options.json` | Initialization settings and tool version |

## Sequence

```mermaid
flowchart LR
    R[Research] --> C[Constitution]
    C --> S[Specify]
    S --> Q[Clarify]
    Q --> P[Plan]
    P --> K[Checklist]
    K --> T[Tasks]
    T --> A[Analyze]
    A --> I[Implement]
    I --> V[Converge]
    V -->|Remaining work| I
```

Research is complete. The constitution was amended to version 2.0.0 on 2026-10-17 after the
product changed from an MCP gateway to a local tool for AI coding client setups, and to 2.1.0 the
same day for "gateway first" (MCP tools are managed in an existing gateway).
The approved project brief is input to the specification step, not a substitute for it.

## Commands in the agent chat

| Skill | Expected result |
| --- | --- |
| `$speckit-constitution` | Change project principles when needed |
| `$speckit-specify` | Describe user needs and measurable acceptance scenarios |
| `$speckit-clarify` | Resolve consequential uncertainties |
| `$speckit-plan` | Select technology and record the implementation design |
| `$speckit-checklist` | Check requirement quality |
| `$speckit-tasks` | Create ordered implementation tasks |
| `$speckit-analyze` | Find conflicts or gaps across artifacts |
| `$speckit-implement` | Implement the agreed feature |
| `$speckit-converge` | Check the result and identify remaining work |

These are agent skills, not shell commands. Installed skills may require a new chat or reload
to appear in a skill picker; their files are present and can be read directly.

For the first specification, use the approved [project brief](project-brief.md): a local page
that shows what Claude Code, Codex and Cursor actually load, where each item comes from, and what
loads twice, with safe on/off changes. Keep the technology stack and the choice between an own
tool and a contribution to Cross-Code Organizer open until the technical plan.

Reference: [Spec Kit process documentation](https://github.github.com/spec-kit/reference/agentic-sdd.html).