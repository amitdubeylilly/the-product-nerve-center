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

- [x] Real oracle capacity records captured and stored in workbook table (8 engineers)
- [x] Capacity formula verified against oracle records — direct recomputation reproduces all 8 available_points plus squad/team totals exactly (ORACLE_VERIFICATION_WORKBOOK.md §4)
- [x] Formula winner and rationale recorded (multiplicative PTO, carry-over after proration)
- [x] Dependency discovery observations captured from oracle calls (12 edges: 8 blocks, 2 soft, 2 external)

## D. Chat Export Artifact (submission workflow)

- [ ] Claude discovery chat export file prepared (outside repo if required by portal)
- [ ] Export shows baseline, one-variable-at-a-time probing, hypotheses, and outcomes
- [ ] Export includes evidence for PTO and 0% allocation behaviors

## E. Final Submission Readiness

- [ ] File-based revert + doc updates committed (working tree clean)
- [ ] Latest branch pushed to origin/main
- [ ] Pre-submission validator run and archived
- [ ] Final portal submission completed

## Notes

Section C is complete: discovery evidence is recorded in ORACLE_VERIFICATION_WORKBOOK.md.
Section D (chat export) requires exporting the Phase 1 discovery / Phase 2 planning
conversation from Claude and attaching it per the submission portal — it is a scored
Investigation Rigor artifact and cannot be generated from repo files alone.
