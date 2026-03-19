# Acceptance Automation Checklist (2026-03-19)

## Goal

Promote the temporary scheduler probe and failure readability probe into the acceptance record automation so the generated record no longer leaves those items as manual follow-up by default.

## Checklist

- [x] Confirm template fields that still depend on scheduler / failure probe evidence
- [x] Add local HTTP probe helpers for isolated acceptance validation servers
- [x] Automate scheduler validation and write the result back into section 8 / PRD mapping
- [x] Automate failure readability validation and write the result back into section 9 / final conclusion
- [x] Add focused tests for the new acceptance automation paths
- [x] Run focused verification
- [x] Commit this batch

## Notes

- Keep the main real acceptance flow unchanged; run extra probes in isolated temporary databases and ports
- Reuse existing API endpoints instead of inventing new probe-only code paths
- Do not treat longer-term browser observation as a blocker once the isolated scheduler probe has passed
- Increased the scheduler seed request timeout to 30s after observing real-provider cold starts exceed 10s
