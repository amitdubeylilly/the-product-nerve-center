---
name: mcp-tool-implementation-guardrails
description: Enforces implementation guardrails for PM Agent MCP tools to keep outputs grader-safe and deterministic.
---

# MCP Tool Implementation Guardrails

Apply this skill when writing or reviewing tool implementations.

## Implementation Rules
- Keep data loading separate from scoring logic.
- Keep mcp.tool wrappers thin; place logic in tools modules.
- Return structured outputs (objects and arrays), not prose-only strings.
- Add deterministic sort tie-breakers.
- Raise clear ValueError messages for invalid arguments.

## Priority Tool Guidance
For prioritize_backlog:
- Blend value, urgency, confidence, and dependency risk.
- Include score breakdown per ranked item.

For analyze_feedback:
- Aggregate by theme, customer tier, and source.
- Surface urgency and potential revenue/churn signal.

For assess_capacity:
- Use discovered rule for available points from roster attributes.
- Report squad totals and overload or mismatch warnings.

For map_dependencies:
- Include direct and transitive dependencies.
- Distinguish blocks, soft, and external types.
- Flag cycles and external ETA uncertainty.

## Anti-Patterns
- Calling oracle APIs from runtime tool code.
- Assuming sample file sizes or fixed IDs.
- Returning unstable ordering for equivalent scores.
