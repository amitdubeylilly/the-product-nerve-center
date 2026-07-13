---
name: pnc-challenge-context
description: Loads PM Agent challenge context, constraints, and required files for faster onboarding in new chats.
---

# PM Agent Challenge Context Skill

Use this skill when working on anything inside this repository.

## Goal
Quickly establish the challenge constraints and avoid invalid implementations.

## Read Order
1. SKILL.md
2. KNOWLEDGE.md
3. challenge/mcp_starter/README.md
4. data/data_dictionary.md
5. challenge/oracle_connection/README.md

## Required Deliverable
Implement exactly four MCP tools:
- prioritize_backlog
- analyze_feedback
- assess_capacity
- map_dependencies

## Hard Constraints
- Runtime data path must come from PM_AGENT_DATA (with local fallback).
- Submitted runtime code must not call Nimbus Oracle.
- Logic must generalize to unseen datasets; no hardcoded sample values.
- Tool names must exactly match olympics.json.

## Fast Sanity Checks
- server.py starts successfully.
- Four required tool decorators are present.
- Data files are read via the configured DATA_DIR, not absolute local paths.
- Errors are explicit and actionable.
