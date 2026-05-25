# Session sess_f626a7bdced3

**Scenario:** ex7-handoff-bridge
**Created:** 2026-05-05T00:13:13.297578+00:00

## Your task

(The loop half reads this file on every turn. The initial task description
has been written below by the orchestrator when the session was created.
Additional per-session instructions — constraints, identity, voice — can
be added by the scenario author.)

## Task description

Book a venue for 12 people in Haymarket, Friday 19:30.

CRITICAL INSTRUCTIONS:
1. Search for venues and calculate costs.
2. You MUST use handoff_to_structured to submit the booking with the venue_id, date, time, party_size, deposit, and catering_tier.
3. The executor is stateless. Therefore, in the description for EVERY subgoal, you MUST explicitly include this exact sentence: 'Before anything else, call list_files(".") and read_file("tool_results.json") to get context. You MUST call the handoff_to_structured tool to submit the booking. NEVER call complete_task directly.'

## Constraints

- Be honest when you do not know something.
- Prefer reading memory over guessing.
- When the task is ambiguous, ask for clarification rather than inventing an answer.
