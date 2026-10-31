# Maintaining

Notes for the maintainer. See also "Maintaining" in the
[README](../README.md).

## Going public again

The repository is currently private. When it goes public again:

- Turn private vulnerability reporting on again (it was on while the
  repository was public on 2026-10-25). SECURITY.md and the issue-template
  link send reporters there, and no email address is given.
- Re-enable the daily KEV and weekly end-of-life workflows.
- Check that "Allow GitHub Actions to create and approve pull requests" is
  on in the Actions settings. The weekly end-of-life job opens its pull
  request with the job token.
- Re-run the dry runs.
