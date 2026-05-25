# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In my Ex7 handoff bridge run (session `sess_c53a2a05ce7a`), the planner's second subgoal was assigned to the structured half. The specific subgoal `sg_2` (found in `logs/tickets/tk_f2a3bbdb/raw_output.json`) has `"assigned_half": "structured"`. 

The signal that caused this decision was the prompt task's critical instruction: *"You MUST use handoff_to_structured to submit the booking."* (This task preview is recorded at line 11 of `logs/trace.jsonl`). 

Sovereign-agent's `DefaultPlanner` is guided by its system prompt (defined in `sovereign_agent/planner/__init__.py`), which dictates: *"use 'structured' only for subgoals that need strict rule-following (e.g. a confirmation dialog...)"*. Because the subgoal description explicitly required calling the external `handoff_to_structured` tool (which serves as the IPC boundary to Rasa's validation and confirmation flows), the LLM correctly mapped the subgoal to the structured half.

### Citation

- `logs/sovereign-agent/examples/ex7-handoff-bridge/sess_c53a2a05ce7a/logs/tickets/tk_f2a3bbdb/raw_output.json`
- `logs/sovereign-agent/examples/ex7-handoff-bridge/sess_c53a2a05ce7a/logs/trace.jsonl:11`

---

## Q2 — Dataflow integrity catch

### Your answer

During Ex5 development, my dataflow integrity check successfully caught a subtle LLM fabrication that manual review would likely miss. In session `sess_34cb72249cf8`, the generated HTML flyer (`workspace/flyer.html` line 33) claimed that the total event cost was "£540" and deposit required was "£0". 

However, cross-referencing this flyer with the actual tool outputs in `workspace/tool_results.json` reveals that the `calculate_cost` tool returned `"total_gbp": 556` and `"deposit_required_gbp": 111` for a party of 6 at the Haymarket Tap. The LLM executor had fabricated these lower figures—likely pulling placeholders from its context window or prompt examples—instead of passing the correct outputs from the previous tool. 

The integrity check caught this by verifying every numeric cost and weather fact in `flyer.html` against the `_TOOL_CALL_LOG` entries. Since "540" was never returned by `calculate_cost` or any other tool, the dataflow validator returned `ok=False` and surfaced `'£ 540'` as an unverified fact.

### Citation

- `logs/sovereign-agent/examples/ex5-edinburgh-research/sess_34cb72249cf8/workspace/flyer.html:33`
- `logs/sovereign-agent/examples/ex5-edinburgh-research/sess_34cb72249cf8/workspace/tool_results.json`

---

## Q3 — First Production Failure Expected, and which primitive would surface it?

### Your answer

Assuming we ship this agent with this current architecture to a real pub-booking business, the first production failure I expect is the agent failing to complete bookings because the task prompt lacks essential user context (e.g., customer name, contact details, payment info) or the pub requires a different booking method (e.g., online forms instead of voice calls).

The sovereign-agent primitive that would surface this failure is the Ticket State Machine. When the agent attempts to validate the booking details or initiate the handoff/voice subgoal, the structured validator (or the API client) will raise a validation exception due to these missing parameters or unsupported interfaces. The ticket state machine catches this, transitions the active ticket status in `state.json` to `failed`, and logs the error context. By wrapping these execution steps in state-tracked tickets, the framework guarantees that any failure due to insufficient real-world booking context is immediately captured and visible in the run artifacts, rather than the agent hallucinating info or silently hanging.

