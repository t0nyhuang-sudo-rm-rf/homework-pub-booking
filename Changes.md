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
