# 2026-03-18 Sparkline Hover Dot Removal Checklist

- [completed] Remove hover highlight dot/halo from the trend sparkline while keeping the data popover.
- [completed] Run a focused verification and record the result.

Verification:
- Confirmed the served asset at `/assets/styles.css` now only reveals `.sparkline-guide` and `.sparkline-popover` on hover, with no hover rule left for `.sparkline-dot` or `.sparkline-halo`.
