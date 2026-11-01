# software-lifecycle (counts only)

This package runs `swlc_mcp.py`, the counts-only server from the
software-lifecycle repo, in Claude Desktop. It offers two tools,
`preflight` and `check_counts`. Each takes the full path to one inventory
`.csv` file on this computer and returns counts from your file only: no
names, versions, publishers, owners or item IDs.

Runs locally with no network by default; not independently assessed.

The package is unsigned, and Claude Desktop may warn when you install it.
It relies on Claude Desktop's own `uv` support to start Python, and has
not been tested in Claude Desktop: **Unverified**. It holds no third-party
packages, only the repo's own standard-library code and bundled data.

Setup, limits and what the server does not protect: `docs/mcp-setup.md`
in the repo. License: MIT (see `LICENSE`). Data sources: `THIRD-PARTY.md`.
