# Open Source Sanitization Checklist (2026-03-19)

## Goal

Sanitize tracked files so the repository is safer to publish publicly without leaking local operator details or stale local runtime instructions.

## Checklist

- [x] Confirm tracked files that expose local operator, machine, or absolute path details
- [x] Sanitize public docs that include local usernames, hostnames, or absolute repository paths
- [x] Replace stale public runtime examples that still point to old local ports
- [x] Ignore `test-results/` so generated outputs are not committed later
- [x] Re-scan tracked files for the same sensitive patterns
- [x] Commit this batch

## Pending

- License choice still requires explicit confirmation before adding a public license file
