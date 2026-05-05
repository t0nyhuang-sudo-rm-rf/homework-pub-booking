# Changes and Optimizations

## Ex5: Edinburgh Research Tool Orchestration
In addition to implementing the core tools (`venue_search`, `get_weather`, `calculate_cost`, `generate_flyer`), the following architectural workarounds and optimizations were implemented to stabilize the agentic dataflow when using Live LLMs (Qwen3-32B and Llama-3.3-70B):

### 1. Cross-Subgoal Context Persistence (Workspace Shared Memory)
**Problem**: The Executor operates statelessly across subgoals. Data retrieved in `sg_1` (e.g., `venue_id`) was forgotten by the time `sg_3` executed, causing the LLM to hallucinate placeholder strings like `"chosen_venue_id"`. The built-in `MemoryStore` API was unimplemented.
**Solution**: We intercepted the tool registration in `tools.py` (`build_tool_registry`). The data-producing tools (`venue_search`, `get_weather`, `calculate_cost`) were wrapped in closures that automatically append their successful outputs to `workspace/tool_results.json`. This established the workspace directory as the shared state channel across the entire React loop.

### 2. Defeating Schema Ambiguity (Flattening `generate_flyer`)
**Problem**: Even with all context available, the Executor models (especially Llama 70B) refused to call the `generate_flyer` tool, falling back to outputting JSON strings as conversational text. 
**Cause**: LLMs struggle with unspecified nested schemas. The tool required an `event_details: dict` parameter defined simply as `type: object` with no properties.
**Solution**: We flattened the `parameters_schema` in `tools.py` into 8 explicit, required, top-level scalar fields (`venue_name`, `date`, `total_gbp`, etc.). We then implemented a `_flyer_adapter` function that re-packs these flat arguments into the required `event_details` dictionary before invoking the core logic. This perfectly stabilized tool execution.

### 3. Prompt Engineering for Stateless Executors
**Problem**: Despite writing to `tool_results.json`, the LLMs did not reliably check the workspace before executing subgoals.
**Solution**: We injected explicit cross-subgoal memory instructions into the main task prompt in `run.py`. We forced the **Planner** to inject the following rule into every generated subgoal description: *"Before anything else, call list_files('.') and read_file('tool_results.json') to get the venue_id and data from previous steps."* Since the Executor only sees the subgoal description, this successfully compelled it to read the persisted state.

### 4. Redundant Tool Call Prevention (Short-circuiting)
**Problem**: Models (like Qwen3-32B) would blindly re-execute `generate_flyer` or manually call `write_file` multiple times due to overlapping subgoals.
**Solution**: Added a short-circuit directive to the Planner's instructions: *"If you see that a tool's output is already in tool_results.json, or if flyer.html already exists, DO NOT re-run that tool. Consider it successfully completed and move to the next step."*

### 5. Passing Full Context to Planner
**Problem**: `run.py` was previously sending a truncated 7-word string (`"research Edinburgh venue and write flyer"`) to `half.run()`, starving the Planner of necessary constraints.
**Solution**: Updated `run.py` to programmatically extract the full task block directly from `SESSION.md` and pass it to the Planner.

### 6. Weather JSON Traversal Bug
**Problem**: The `get_weather` tool crashed because it misinterpreted the structure of `weather.json`.
**Solution**: Refactored the tool to correctly access the nested dictionary schema (`city` -> `date` -> `condition_data`).

## Ex6: Rasa Structured Half Integration
- **Validation Mapping**: Verified the implementation of `validator.py`, which normalizes the flexible output from the research agent (parsing dates, mapping human names to internal IDs, etc.) into the strict format required by the database.
- **Execution Engine**: Analyzed `structured_half.py` to understand how the system transitions from the LLM React Loop to a deterministic HTTP request against the Rasa Pro API. It interprets Rasa's response messages to flag a `confirmed` completion or an `escalate` rejection.

## Ex7: Handoff Bridge and Rejection Loops
We implemented and debugged the `HandoffBridge`, which orchestrates the round-trip interactions between the Loop Half and the Structured Half. Several fixes were required to make this work with live models (especially Qwen-32B).

### 1. Missing Runner Configurations
**Problem**: The `Makefile` was missing the `ex7-real` target, and `run.py` was hardcoded to use the offline `FakeLLMClient` even when the `--real` flag was passed.
**Solution**: Added the missing Makefile target and correctly initialized the `OpenAICompatibleClient` by pulling the base URL and API keys from `Config.from_env()`. 

### 2. Guarding the Initial Handoff
**Problem**: The base task prompt for Ex7 (`"Book a venue for 12..."`) lacked the strict instructions we engineered in Ex5. The LLM repeatedly called `complete_task` instead of handing off to Rasa, or it hallucinated random party sizes.
**Solution**: Appended critical instructions to the initial task string in `starter/handoff_bridge/run.py` telling the Planner it MUST instruct the Executor to use `handoff_to_structured` and to NEVER call `complete_task`.

### 3. Enforcing the Handoff Schema
**Problem**: The framework's `handoff_to_structured` tool expects an open-ended `data: dict`. Qwen 32B was either stuffing raw search results into it or completely forgetting to pass required keys like `date` and `time`, leading to instant rejections from the validator.
**Solution**: We explicitly documented the required schema shape in the instructions: *"The data argument MUST be a dict containing EXACTLY these keys: venue_id, date, time, party_size, deposit_gbp, and catering_tier."*

### 4. Curing "Amnesia" in Reverse Handoffs
**Problem**: When the agent successfully handed off a booking but Rasa rejected it (e.g., due to the pub being too small for 12 people), the bridge would send back a reverse task (`"Produce an alternative"`). This new prompt overwrote the original task, causing the LLM to completely forget all the tool guardrails and schema rules for Round 2.
**Solution**: Modified `build_reverse_task` in `starter/handoff_bridge/bridge.py` to explicitly append the strict tool and schema instructions to the rejection message. This ensured the agent remembered how to format its output during subsequent retry loops.
