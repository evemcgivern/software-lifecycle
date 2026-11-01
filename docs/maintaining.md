# Maintaining

Notes for the maintainer. See also "Maintaining" in the
[README](../README.md).

## Go-public day checklist

Reference for the owner. Each step needs repository admin rights.

1. Make the repository public.
2. Turn private vulnerability reporting on. SECURITY.md and the
   issue-template link send reporters there, and no email address is
   given.
3. Check that "Allow GitHub Actions to create and approve pull requests"
   is on in the Actions settings. The weekly end-of-life job opens its
   pull request with the job token.
4. Re-enable the daily KEV and weekly end-of-life workflows.
5. After the switch, run the daily KEV workflow by hand on main with
   `dry_run=true`, then with `dry_run=false`. Do this after the switch
   because attestations on a private repository need a paid plan.
6. Check the new data release with `gh attestation verify` (the command
   is in the README).
7. Run the weekly end-of-life workflow by hand and merge its pull request
   as an admin, because CI does not run on pull requests opened by the
   job token.

