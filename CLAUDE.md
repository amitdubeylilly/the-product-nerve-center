# Claude Project Context: PM Agent Challenge

## What This Repo Is

This repository is for the PM Agent MCP challenge. The deliverable is an MCP server with exactly four tools:

- prioritize_backlog
- analyze_feedback
- assess_capacity
- map_dependencies

## Canonical Context Files

Read these first in new chats:

- SKILL.md
- KNOWLEDGE.md
- PNC_Challenge_data/mcp_starter/README.md
- data/data_dictionary.md
- PNC_Challenge_data/oracle_connection/README.md

## Non-Negotiable Constraints

- Use PM_AGENT_DATA for runtime dataset path, with local fallback.
- Do not hardcode sample IDs, names, or fixed counts.
- Do not call Nimbus Oracle from submitted runtime tool code.
- Keep exact required tool names as listed in olympics.json.

## Code Locations

- Server entry point: server.py
- Tool modules: tools/
- Local sample data: data/

## Expected Working Style

- Keep MCP wrapper functions thin; business logic belongs in tools modules.
- Return predictable JSON-friendly outputs with clear keys and rationale fields.
- Use deterministic ranking tie-breakers where order matters.
- Validate error handling for malformed input and missing files.

## New-Chat Bootstrap Checklist

1. Confirm required tools are present in server.py.
2. Confirm data loading uses PM_AGENT_DATA.
3. Read SKILL.md and KNOWLEDGE.md for current challenge context.
4. If implementing capacity/dependencies, use discovered rules, not direct oracle calls.
