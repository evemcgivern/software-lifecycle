# Security

Runs locally with no network by default; not independently assessed.

## Reporting a vulnerability

Reporters can use private vulnerability reporting. Open the
repository's **Security** tab and choose **Report a vulnerability**. Do
not open a public issue for a security problem. Do not include real
inventory data in a report.

This project is maintained as time allows. Support is best effort, with no
service level. There is no promised response time. A report is read and
answered when the maintainer can.

## Supported versions

Only the latest release and the latest data release are supported. Older
ones are not patched.

| What | Supported |
|---|---|
| The tool: the latest release | Yes, best effort |
| The data: the latest data release | Yes, best effort |
| Anything older | No |

## Scope

In scope:

- the tool (`swlc/` and `software_lifecycle.py`);
- the optional MCP server (`swlc_mcp.py`), for example a way to make it
  return file content, item IDs or anything beyond its fixed counts, or
  to run something other than its two fixed commands;
- the refresh script (`refresh_data.py`);
- the GitHub workflows;
- the Pages site (`site/`) and its workflow, for example a script, a form or
  a request to another host;
- the data pipeline that builds and publishes data releases;
- the documentation, when it claims more than the code does.

Out of scope:

- findings about your own inventory (the tool reports on those);
- errors in the upstream data. Report a wrong end-of-life date to
  endoflife.date, and a KEV question to CISA;
- how an AI agent behaves when someone runs it with the tool.

## What the tool claims

- It runs locally and makes no network calls by default. A test in the
  repository blocks network access and runs the tool.
- It uses only the Python standard library.
- The Pages site is static pages. It has no forms and no analytics, and
  loads nothing from other hosts. A test in the repository checks this.

## Supply chain

- The tool checks a SHA-256 checksum manifest (`manifest.json`) every time
  it loads its data. This catches a damaged or partly replaced data folder.
  It does not prove who made the files: someone who changes both a data
  file and the manifest is not caught by this check.
- Each data release (`data-YYYY.MM.DD.N`) made while the repository is
  public carries a GitHub artifact attestation made by the release
  workflow on main. Check one online before use, naming the workflow and
  the branch that must have made it:

      gh attestation verify data.zip --repo evemcgivern/software-lifecycle --signer-workflow evemcgivern/software-lifecycle/.github/workflows/kev-daily.yml --source-ref refs/heads/main

  Checking `--repo` alone is not enough: it also accepts an attestation
  made by a run on another branch.
- The tool does not and cannot verify signatures offline. It never checks
  attestations offline.
- Only main can publish a data release. The publish job runs only for
  `refs/heads/main` and uses the GitHub environment `data-release`, which
  allows deployment from main only. The scheduled workflows run when they
  are enabled.
- Data releases are never changed or re-tagged. A fix is a new, higher
  release.
- Only `refresh_data.py`, run by the data workflows, opens network
  connections. KEV data is published automatically only after its checks
  pass. End-of-life data changes arrive as a pull request that a person
  reviews.
- Every GitHub Action is pinned to a commit SHA, and Dependabot proposes
  updates.

## What the MCP server protects

`swlc_mcp.py` returns only fixed labels and numbers, rebuilt from the
tool's output: no cell text, column titles or item IDs. It takes only a
path to a `.csv` file and runs two fixed commands. It does not stop the
counts and the path from going to the chat app's provider, other tools in
the same app from reading files, or the full report (written next to the
CSV) from reaching a synced folder. Someone who can change files on the
computer while a check runs is out of scope. Details are in
[docs/mcp-setup.md](docs/mcp-setup.md).

## What the tool does not claim

- It has not been independently assessed or audited.
- Its end-of-life and KEV data are snapshots and can be out of date.
- A clean result does not prove that software is safe or supported.
- Item IDs do not hide an item from someone who can guess it. An ID is
  an unsalted, truncated SHA-256 of publisher, name and version, so a
  guessed product can be confirmed against the IDs in a report, in
  `--counts-only` output or in an override file. Treat IDs with the same
  care as the inventory.
- A support-records file and the reports made with it hold your record
  references (contract, purchase order or ticket references). Treat them
  as confidential, like item IDs. `--counts-only` prints only the three
  support-record counts. The tool does not check that a record was paid
  for or is current.
