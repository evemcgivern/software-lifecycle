# Security

Runs locally with no network by default; built to enterprise security practices; not independently assessed.

> This repository is currently private. This policy and process apply when
> it is public.

## Reporting a vulnerability

When the repository is public, private vulnerability reporting is
turned on. Open the repository's **Security** tab and choose **Report a
vulnerability**. Do not open a public issue for a security problem. Do not
include real inventory data in a report.

While the repository is private, GitHub does not offer it. Contact the repository owner on GitHub instead.

This project is maintained as time allows. Support is best effort, with no
service level. There is no promised response time. A report is read and
answered when the maintainer can.

## Supported versions

Only the latest release and the latest data release are supported. Older
ones are not patched. No tool release exists yet, so the tool's supported
version is `main` until the first release.

| What | Supported |
|---|---|
| The tool: the latest release, or `main` until the first tool release | Yes, best effort |
| The data: the latest data release | Yes, best effort |
| Anything older | No |

## Scope

In scope:

- the tool (`swlc/` and `software_lifecycle.py`);
- the refresh script (`refresh_data.py`);
- the GitHub workflows;
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
- It is built to enterprise security practices.
- It uses only the Python standard library.

## Supply chain

- The tool checks a SHA-256 checksum manifest (`manifest.json`) every time
  it loads its data. This catches a damaged or partly replaced data folder.
  It does not prove who made the files: someone who changes both a data
  file and the manifest is not caught by this check.
- When the repository is public, each data release (`data-YYYY.MM.DD.N`)
  carries a GitHub artifact attestation made by the release workflow on
  main. Release attestations on a private repository need GitHub
  Enterprise Cloud. Check one online before use, naming the workflow and
  the branch that must have made it:

      gh attestation verify data.zip --repo evemcgivern/software-lifecycle --signer-workflow evemcgivern/software-lifecycle/.github/workflows/kev-daily.yml --source-ref refs/heads/main

  Checking `--repo` alone is not enough: it also accepts an attestation
  made by a run on another branch.
- The tool does not and cannot verify signatures offline. It never checks
  attestations offline.
- Only main can publish a data release. The publish job runs only for
  `refs/heads/main` and uses the GitHub environment `data-release`, which
  allows deployment from main only. The scheduled workflows run when they
  are enabled; they are disabled while the repository is private.
- Data releases are never changed or re-tagged. A fix is a new, higher
  release.
- Only `refresh_data.py`, run by the data workflows, opens network
  connections. KEV data is published automatically only after its checks
  pass. End-of-life data changes arrive as a pull request that a person
  reviews.
- Every GitHub Action is pinned to a commit SHA, and Dependabot proposes
  updates.

## What the tool does not claim

- It has not been independently assessed or audited.
- Its end-of-life and KEV data are snapshots and can be out of date.
- A clean result does not prove that software is safe or supported.
