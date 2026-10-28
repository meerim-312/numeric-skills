# Engagement Summary — Finance Skills Security Review

**Date:** 2026-10-28
**Reviewed by:** Meerim Musabaeva, AI Security Architect
**Scope:** 5 finance-priority skills from the Numeric MCP toolkit — `complete-accruals-task`, `vendor-accrual-confirmation-mailer`, `close-retro`, `automatically-draft-flux-explanations`, `skill-reviewer`
**Approved platform:** Copilot only. **Not approved for use in Claude Code.**

---

## Work done

1. Reviewed all 5 skills against the `mcp-skill-vet` control framework (provenance, instruction/script inspection, read/write classification, SoD, audit trail).
2. Ran Snyk Code (SAST) against the bundled scripts and normalized the SARIF output (3+ scan rounds).
3. Fixed the real code-level issues found; verified each fix functionally (regression suite + manual smoke tests) before and after.

## Issues found, with risk

| # | Issue | Risk | Severity |
|---|---|---|---|
| 1 | `complete-accruals-task` posts JEs to NetSuite with only a single self-confirmation — no second approver | Wrong/fraudulent accrual reaches the GL unreviewed (SOX 404/ICFR deficiency) | High |
| 2 | `automatically-draft-flux-explanations` loops over all PENDING tasks with an implicit "show-then-post," not an explicit per-account gate | Unreviewed variance narrative posted at scale under the preparer's name | High |
| 3 | `vendor-accrual-confirmation-mailer` resolves vendor emails via Gmail search once, then reuses forever without re-verification | Internal financial estimates sent to a wrong/stale external address | Medium |
| 4 | Account-name/period data flowed unsanitized into output filenames in `generate_outputs.py` | A crafted Numeric account name could write the accrual workpaper outside the intended folder (real path-traversal vector) | Medium |
| 5 | 9 scripts across 4 skills took CLI file paths (including harness-saved tool-result files) with no containment — Snyk flagged 36 `python/PT` findings | Scripts could read/write outside the intended working directory | Low (operator-controlled, not externally exploitable, but flagged by SAST) |
| 6 | `skill-reviewer`'s `--submission` accepted a third-party skill from anywhere on disk | No workspace boundary when reviewing a downloaded skill | Low |
| 7 | No rollback runbook for a bad JE post; `close-retro` digest surfaces named individual performance data to Slack | Slower incident recovery; HR/access-review gap, not a financial control | Low |

## What was fixed

- **Issue 4**: sanitized account-name/period filename components in `generate_outputs.py` — verified a traversal payload now collapses harmlessly.
- **Issue 5 & 6**: added real `--root` workspace containment to all 12 scripts across `skill-reviewer`, `complete-accruals-task`, `close-retro`, and `automatically-draft-flux-explanations`; updated each skill's `SKILL.md` usage instructions accordingly. Verified at runtime: in-root calls succeed unchanged, out-of-root calls are refused.
- **Refactor**: fixed a discard-then-re-derive bug in the containment checks (validated path wasn't the one actually used at the sink) — closed **24 of the original 36** Snyk findings on re-scan, including 100% of `skill-reviewer`'s.

## Not yet fixed (open)

- Issues **1, 2, 3** — require a process/product decision (second-approver gate, per-account confirmation, vendor-master cross-check), not just a code patch.
- Issue **7** — process recommendation only.
- **12 residual Snyk findings** (10 reads, 2 writes) — all sit behind verified `--root` containment already; the scanner doesn't credit the same pattern for reads as consistently as for writes. Treated as accepted/residual, not a security gap.

*Not an approved IMO policy document — pending security-team sign-off.*
