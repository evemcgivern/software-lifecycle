# Maintaining

Notes for the maintainer. See also "Maintaining" in the
[README](../README.md).

## Go-public day checklist

Reference for the owner. Each step needs repository admin rights. Private
vulnerability reporting, secret scanning and push protection can only be
set once the repository is public.

1. Make the repository public.
2. Turn private vulnerability reporting on. SECURITY.md and the
   issue-template link send reporters there, and no email address is
   given.
3. Turn on secret scanning and push protection.
4. Set fork pull request approval to require approval for all outside
   contributors.
5. Confirm that "Allow GitHub Actions to create and approve pull
   requests" is still on in the Actions settings. The weekly end-of-life
   job opens its pull request with the job token.
6. Re-enable the daily KEV and weekly end-of-life workflows.
7. After the switch, run the daily KEV workflow by hand on main with
   `dry_run=true`, then with `dry_run=false`. Do this after the switch
   because attestations on a private repository need a paid plan.
8. Check the new data release with `gh attestation verify` (the command
   is in the README).
9. Run the weekly end-of-life workflow by hand and merge its pull request
   as an admin, because CI does not run on pull requests opened by the
   job token.

