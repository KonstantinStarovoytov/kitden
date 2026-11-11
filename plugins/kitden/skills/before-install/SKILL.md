---
name: before-install
description: Use when the user is about to add or install an MCP server, plugin or skill, or asks whether one is already set up for this client, another client or another project.
---

Before something new is added, look whether this computer already has it. The same server or
skill added twice loads twice.

1. Run `kitden show item NAME` in the project's folder. It only reads and prints JSON: every
   place the name is set, for each client, at the user level and in this project. If `kitden` is not found or the command fails as unknown, follow the kitden `install` skill.
2. Read each definition's `client`, `scope`, `enabled`, `loads` and `why`. Tell the user where
   the item already is and whether it loads here.
3. The same thing can have another name. If nothing is found, run
   `kitden show setup --client CLIENT` for the client the user means and compare each
   `summary`, which holds a server's address or command, with what they want to add.
4. If it is already there for this client and loads, say so and do not add it again. If it is
   there but off, or only for another client or project, say that; the user can turn it on or
   share it on the Kitden page (`kitden open`).
5. If it is nowhere, say so and carry on with what the user asked. Add only servers and plugins
   they trust.
