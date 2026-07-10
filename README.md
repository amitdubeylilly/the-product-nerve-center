# the-product-nerve-center

Challenge workspace for the PM Agent MCP Olympics problem set.

## Quick Links

- [challenge-brief.md](challenge-brief.md): full challenge statement and scoring rubric.
- [CLAUDE.md](CLAUDE.md): auto-loaded project context for new Claude chats.
- [SKILL.md](SKILL.md): implementation playbook for the 4 required tools.
- [KNOWLEDGE.md](KNOWLEDGE.md): consolidated challenge context, data contract, and discovery notes.
- [.claude/skills/pnc-challenge-context/SKILL.md](.claude/skills/pnc-challenge-context/SKILL.md): reusable challenge bootstrap skill.
- [.claude/skills/mcp-tool-implementation-guardrails/SKILL.md](.claude/skills/mcp-tool-implementation-guardrails/SKILL.md): implementation guardrails skill.
- [PNC_Challenge_data/mcp_starter/README.md](PNC_Challenge_data/mcp_starter/README.md): starter setup and runtime contract.
- [PNC_Challenge_data/data/data_dictionary.md](PNC_Challenge_data/data/data_dictionary.md): source schema reference.
- [PNC_Challenge_data/oracle_connection/README.md](PNC_Challenge_data/oracle_connection/README.md): Nimbus Oracle discovery guide.

## Repository Structure

- `PNC_Challenge_data/data`: local sample JSON files for development.
- `PNC_Challenge_data/mcp_starter`: MCP starter server scaffold.
- `PNC_Challenge_data/oracle_connection`: discovery instructions for reverse engineering capacity and dependency rules.

## Current Focus

Implement the four required MCP tools in the starter server:

- `prioritize_backlog`
- `analyze_feedback`
- `assess_capacity`
- `map_dependencies`

Important: submitted tool logic must be data-driven from mounted `PM_AGENT_DATA` and must not call the oracle at runtime.
