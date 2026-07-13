# Submission Artifacts Checklist

This checklist tracks what is complete in-repo versus what must be completed in the submission workflow.

## A. Implemented MCP Server

- [x] Required tool names present in olympics.json
- [x] Entry point server.py at repo root
- [x] Runtime reads PM_AGENT_DATA with local fallback
- [x] No runtime oracle/network calls in submitted path
- [x] requirements.txt pinned for runtime reproducibility
- [x] Tests passing with 100% line and branch coverage

## B. Technical Decision Log / Approach Summary

- [x] Approach Summary drafted in APPROACH_SUMMARY.md
- [x] All six required prompts addressed
- [x] Failure modes and tradeoffs documented

## C. Oracle Discovery Evidence

- [ ] Real oracle capacity records captured and stored in workbook table
- [ ] capacity_formula_fitter executed with real records
- [ ] Formula winner and rationale recorded
- [ ] Dependency discovery observations captured from oracle calls

## D. Chat Export Artifact (submission workflow)

- [ ] Claude discovery chat export file prepared (outside repo if required by portal)
- [ ] Export shows baseline, one-variable-at-a-time probing, hypotheses, and outcomes
- [ ] Export includes evidence for PTO and 0% allocation behaviors

## E. Final Submission Readiness

- [x] Working tree clean
- [x] Latest branch pushed to origin/main
- [ ] Pre-submission validator run and archived
- [ ] Final portal submission completed

## Notes

Items in sections C and D require access to historical or active oracle chat outputs.
They cannot be auto-generated solely from the current repository files.
