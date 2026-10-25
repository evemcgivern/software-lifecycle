# Security

Runs locally with no network by default; built to enterprise security
practices; not independently assessed.

## Reporting a vulnerability

Report vulnerabilities privately with GitHub
private vulnerability reporting: open the repository's **Security** tab and
choose **Report a vulnerability**. Do not open a public issue for a security
problem, and do not include real inventory data in a report.

Support is best effort, with no service level.

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
- Each data release (`data-YYYY.MM.DD.N`) carries a GitHub artifact
  attestation made by the release workflow on main. Check it online before
  use, naming the workflow and the branch that must have made it:

      gh attestation verify data.zip --repo evemcgivern/software-lifecycle --signer-workflow evemcgivern/software-lifecycle/.github/workflows/kev-daily.yml --source-ref refs/heads/main

  Checking `--repo` alone is not enough: it also accepts an attestation
  made by a run on another branch.
- Only main can publish a data release. The publish job runs only for
  `refs/heads/main` and uses the GitHub environment `data-release`. The
  maintainer must create that environment (Settings, Environments) and
  allow only the main branch to deploy to it. If the environment does not
  exist, GitHub creates it with no protection, so the main-branch check in
  the workflow stays the real guard.

- The tool does not and cannot verify signatures offline. Nothing in this
  project claims offline signature checking.
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
