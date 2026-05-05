"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
from pathlib import Path

from sovereign_agent.errors import ToolError
from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

from starter.edinburgh_research.integrity import record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    # TODO 1a: load venues.json. Raise ToolError(SA_TOOL_DEPENDENCY_MISSING)
    #          if the file is absent.

    try:
        with open(_SAMPLE_DATA / "venues.json") as f:
            venues = json.load(f)
            party_size = int(party_size)
            budget_max_gbp = int(budget_max_gbp)
            filtered_venues = [
                v
                for v in venues
                if v["open_now"]
                and near.lower() in v["area"].lower()
                and v["seats_available_evening"] >= party_size
                and v["hire_fee_gbp"] + v["min_spend_gbp"] <= budget_max_gbp
            ]
            output = {
                "near": near,
                "party_size": party_size,
                "results": filtered_venues,
                "count": len(filtered_venues),
            }

            summary = f"venue_search({near}, party={party_size}): {len(filtered_venues)} result(s)"
            record_tool_call(
                tool_name="venue_search",
                arguments={
                    "near": near,
                    "party_size": party_size,
                    "budget_max_gbp": budget_max_gbp,
                },
                output=output,
            )
            return ToolResult(success=True, output=output, summary=summary)

    except FileNotFoundError as err:
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "venues.json not found") from err


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    try:
        with open(_SAMPLE_DATA / "weather.json") as f:
            weather = json.load(f)
            city_data = weather.get(city.lower())
            if not city_data:
                raise ToolError("SA_TOOL_INVALID_INPUT", f"No weather data for city: {city}")
            date_data = city_data.get(date)
            if not date_data:
                raise ToolError("SA_TOOL_INVALID_INPUT", f"No weather data for {city} on {date}")
            output = {"city": city, "date": date, **date_data}
            summary = (
                f"get_weather({city}, {date}): {output['condition']}, {output['temperature_c']}C"
            )
            record_tool_call(
                tool_name="get_weather", arguments={"city": city, "date": date}, output=output
            )
            return ToolResult(success=True, output=output, summary=summary)
    except FileNotFoundError as err:
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "weather.json not found") from err


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    try:
        with open(_SAMPLE_DATA / "venues.json") as f:
            venues = json.load(f)
            venue_info = [v for v in venues if v["id"] == venue_id]
            if not venue_info:
                raise ToolError("SA_TOOL_INVALID_INPUT", "Venue not found")

        with open(_SAMPLE_DATA / "catering.json") as f:
            catering = json.load(f)

            party_size = int(party_size)
            duration_hours = int(duration_hours)
            base_per_head = catering["base_rates_gbp_per_head"][catering_tier]
            venue_mult = catering["venue_modifiers"][venue_id]
            subtotal = base_per_head * venue_mult * party_size * max(1, duration_hours)
            service = subtotal * catering["service_charge_percent"] / 100
            total = (
                subtotal + service + venue_info[0]["hire_fee_gbp"] + venue_info[0]["min_spend_gbp"]
            )
            if total < 300:
                deposit_required_gbp = 0
            elif 300 <= total <= 1000:
                deposit_required_gbp = total * 0.2
            else:
                deposit_required_gbp = total * 0.3
            output = {
                "venue_id": venue_id,
                "party_size": party_size,
                "duration_hours": duration_hours,
                "catering_tier": catering_tier,
                "subtotal_gbp": int(subtotal),
                "service_gbp": int(service),
                "total_gbp": int(total),
                "deposit_required_gbp": int(deposit_required_gbp),
            }
            summary = f"calculate_cost({venue_id}, {party_size}): total £{total}, deposit £{deposit_required_gbp}"
            record_tool_call(
                tool_name="calculate_cost",
                arguments={
                    "venue_id": venue_id,
                    "party_size": party_size,
                    "duration_hours": duration_hours,
                    "catering_tier": catering_tier,
                },
                output=output,
            )
            return ToolResult(success=True, output=output, summary=summary)
    except FileNotFoundError as err:
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "catering.json not found") from err


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    if not event_details or not all(
        key in event_details
        for key in [
            "venue_name",
            "venue_address",
            "date",
            "time",
            "party_size",
            "condition",
            "temperature_c",
            "total_gbp",
            "deposit_required_gbp",
        ]
    ):
        raise ToolError("SA_TOOL_INVALID_INPUT", "Event details not provided")

    flyer_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Event Flyer - {event_details["venue_name"]}</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ccc; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }}
        .section {{ margin-bottom: 20px; }}
        .section-title {{ font-weight: bold; color: #34495e; text-transform: uppercase; font-size: 0.9em; }}
        .fact {{ margin: 5px 0; }}
        .label {{ font-weight: bold; width: 150px; display: inline-block; }}
    </style>
</head>
<body>
    <h1 data-testid="venue_name">{event_details["venue_name"]}</h1>

    <div class="section">
        <div class="section-title">Event Details</div>
        <div class="fact"><span class="label">Address:</span> <span data-testid="venue_address">{event_details["venue_address"]}</span></div>
        <div class="fact"><span class="label">Date:</span> <span data-testid="date">{event_details["date"]}</span></div>
        <div class="fact"><span class="label">Time:</span> <span data-testid="time">{event_details["time"]}</span></div>
        <div class="fact"><span class="label">Party Size:</span> <span data-testid="party_size">{event_details["party_size"]}</span></div>
    </div>

    <div class="section">
        <div class="section-title">Weather Forecast</div>
        <div class="fact"><span class="label">Condition:</span> <span data-testid="condition">{event_details["condition"]}</span></div>
        <div class="fact"><span class="label">Temperature:</span> <span data-testid="temperature_c">{event_details["temperature_c"]}</span>°C</div>
    </div>

    <div class="section">
        <div class="section-title">Cost Breakdown</div>
        <div class="fact"><span class="label">Total Cost:</span> £<span data-testid="total_gbp">{event_details["total_gbp"]}</span></div>
        <div class="fact"><span class="label">Deposit Required:</span> £<span data-testid="deposit_required_gbp">{event_details["deposit_required_gbp"]}</span></div>
    </div>
</body>
</html>"""

    path = session.workspace_dir / "flyer.html"
    path.write_text(flyer_html, encoding="utf-8")

    summary = f"generate_flyer: wrote {path.name} ({len(flyer_html)} chars)"
    record_tool_call(
        tool_name="generate_flyer",
        arguments={"event_details": event_details},
        output={"path": str(path), "bytes_written": len(flyer_html)},
    )
    return ToolResult(
        success=True, output={"path": str(path), "bytes_written": len(flyer_html)}, summary=summary
    )


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # Helper: persist tool results to workspace so subsequent subgoals
    # can discover them via list_files / read_file.
    _results_path = session.workspace_dir / "tool_results.json"

    def _persist_result(tool_name: str, output: dict) -> None:
        existing = []
        if _results_path.exists():
            try:
                existing = json.loads(_results_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.append({"tool": tool_name, "output": output})
        _results_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    # venue_search — wrapped to persist results
    def _venue_search_with_persist(
        near: str, party_size: int = 6, budget_max_gbp: int = 1000
    ) -> ToolResult:
        result = venue_search(near=near, party_size=party_size, budget_max_gbp=budget_max_gbp)
        if result.success:
            _persist_result("venue_search", result.output)
        return result

    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=_venue_search_with_persist,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {
                        "type": "string",
                        "description": "The area to search (e.g. 'Haymarket'). Found in the 'Context' section of your task.",
                    },
                    "party_size": {"type": "integer", "description": "The number of guests."},
                    "budget_max_gbp": {
                        "type": "integer",
                        "default": 1000,
                        "description": "The maximum budget in British Pounds.",
                    },
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather — wrapped to persist results
    def _get_weather_with_persist(city: str, date: str) -> ToolResult:
        result = get_weather(city=city, date=date)
        if result.success:
            _persist_result("get_weather", result.output)
        return result

    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=_get_weather_with_persist,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost — wrapped to persist results
    def _calculate_cost_with_persist(
        venue_id: str,
        party_size: int = 6,
        duration_hours: int = 3,
        catering_tier: str = "bar_snacks",
    ) -> ToolResult:
        result = calculate_cost(
            venue_id=venue_id,
            party_size=party_size,
            duration_hours=duration_hours,
            catering_tier=catering_tier,
        )
        if result.success:
            _persist_result("calculate_cost", result.output)
        return result

    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=_calculate_cost_with_persist,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(
        venue_name: str,
        venue_address: str,
        date: str,
        time: str,
        party_size: int,
        condition: str,
        temperature_c: int,
        total_gbp: int,
        deposit_required_gbp: int,
    ) -> ToolResult:
        event_details = {
            "venue_name": venue_name,
            "venue_address": venue_address,
            "date": date,
            "time": time,
            "party_size": party_size,
            "condition": condition,
            "temperature_c": temperature_c,
            "total_gbp": total_gbp,
            "deposit_required_gbp": deposit_required_gbp,
        }
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description=(
                "MANDATORY: Call this tool to produce the HTML flyer. Do NOT use write_file instead. "
                "Do NOT skip this tool. This tool writes workspace/flyer.html. Call it BEFORE complete_task."
            ),
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_name": {"type": "string"},
                    "venue_address": {"type": "string", "default": "Edinburgh"},
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "condition": {"type": "string"},
                    "temperature_c": {"type": "integer"},
                    "total_gbp": {"type": "integer"},
                    "deposit_required_gbp": {"type": "integer"},
                },
                "required": [
                    "venue_name",
                    "date",
                    "time",
                    "party_size",
                    "condition",
                    "temperature_c",
                    "total_gbp",
                    "deposit_required_gbp",
                ],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "venue_name": "Haymarket Tap",
                        "venue_address": "Haymarket",
                        "date": "2026-04-25",
                        "time": "19:30",
                        "party_size": 6,
                        "condition": "cloudy",
                        "temperature_c": 12,
                        "total_gbp": 540,
                        "deposit_required_gbp": 0,
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
