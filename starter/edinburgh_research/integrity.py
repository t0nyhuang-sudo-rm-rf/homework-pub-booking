"""Ex5 — reference solution for integrity.py.

verify_dataflow's job: for every concrete fact in the flyer, confirm
that some tool call in the session actually produced that value. If
a fact exists in the flyer but not in any tool output, it's fabrication.

Two competing failure modes to balance:
  - Too lenient → misses fabrications (grader plants £9999; must catch it)
  - Too strict → rejects legitimate flyers (fails the "accepts real flyer" test)

This implementation leans slightly strict but uses the scalar-matching
`fact_appears_in_log` helper provided in the starter to tolerate common
variations (leading £, trailing C, case differences).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    output: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


_TOOL_CALL_LOG: list[ToolCallRecord] = []


def record_tool_call(tool_name: str, arguments: dict, output: dict) -> None:
    _TOOL_CALL_LOG.append(
        ToolCallRecord(tool_name=tool_name, arguments=dict(arguments), output=dict(output))
    )


def clear_log() -> None:
    _TOOL_CALL_LOG.clear()


@dataclass
class IntegrityResult:
    ok: bool
    unverified_facts: list[str] = field(default_factory=list)
    verified_facts: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "unverified_facts": self.unverified_facts,
            "verified_facts": self.verified_facts,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_money_facts(text: str) -> list[str]:
    """Find all £<number> occurrences, HTML tags stripped or not."""
    # Strip HTML tags first so e.g. <dd>£540</dd> matches cleanly.
    stripped = re.sub(r"<[^>]+>", " ", text)
    # Allow optional whitespace after the pound sign since tag stripping
    # might leave a space.
    return re.findall(r"£\s*\d+(?:\.\d+)?", stripped)


def extract_temperature_facts(text: str) -> list[str]:
    """Find temperature mentions (number followed by °C or C)."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    return list({m.group(1) for m in re.finditer(r"(\d+)\s*°?\s*[Cc]\b", stripped)})


def extract_condition_facts(text: str) -> list[str]:
    """Find weather condition keywords."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    tl = stripped.lower()
    known = ("sunny", "rainy", "cloudy", "partly_cloudy", "partly cloudy")
    return [c for c in known if c in tl]


def extract_testid_facts(text: str) -> dict[str, str]:
    """For HTML flyers that use data-testid, extract {testid: value} pairs.

    This is the preferred path for HTML — it gives us structured facts
    (e.g. {'total': '£540', 'deposit': '£0'}) instead of loose regex
    matches. The solution flyer ships with data-testid on every fact.
    """
    pattern = re.compile(
        r'<[^>]+data-testid="([^"]+)"[^>]*>([^<]+)</[^>]+>',
        re.IGNORECASE,
    )
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(text)}


def fact_appears_in_log(fact: Any, log: list[ToolCallRecord] | None = None) -> bool:
    records = log if log is not None else _TOOL_CALL_LOG

    # If the in-memory log is empty, try to recover from the workspace persistence
    if not records:
        import json
        import os
        import sys
        from pathlib import Path

        # 1. Try local workspace first
        candidates = [Path("workspace/tool_results.json"), Path("tool_results.json")]

        # 2. Try to find the most recent session's tool_results.json in the platform data dir
        try:
            if sys.platform == "darwin":
                root = Path.home() / "Library" / "Application Support" / "sovereign-agent"
            elif sys.platform == "win32":
                root = Path(os.environ.get("LOCALAPPDATA", "")) / "sovereign-agent"
            else:
                root = (
                    Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
                    / "sovereign-agent"
                )

            if root.exists():
                # Glob for all tool_results.json in any session subfolder
                all_results = list(root.glob("examples/*/sess_*/workspace/tool_results.json"))
                # Sort by modification time, newest first
                all_results.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                candidates.extend(all_results)
        except Exception:
            pass

        for path in candidates:
            if path.exists():
                try:
                    with open(path) as f:
                        data = json.load(f)
                        records = [
                            ToolCallRecord(tool_name=r["tool"], arguments={}, output=r["output"])
                            for r in data
                        ]
                        break
                except Exception:
                    continue

    target = str(fact).lower().strip("£°c ").strip()

    def _scan(obj: Any) -> bool:
        if isinstance(obj, (str, int, float)):
            return str(obj).lower().strip("£°c ").strip() == target
        if isinstance(obj, dict):
            return any(_scan(v) for v in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return any(_scan(v) for v in obj)
        return False

    return any(_scan(r.output) or _scan(r.arguments) for r in records)


# ---------------------------------------------------------------------------
# verify_dataflow — the main check
# ---------------------------------------------------------------------------
def verify_dataflow(flyer_content: str) -> IntegrityResult:
    if not flyer_content or not flyer_content.strip():
        return IntegrityResult(ok=True, summary="no facts to verify (empty flyer)")

    facts_to_check: list[str] = []
    facts_to_check.extend(extract_money_facts(flyer_content))
    facts_to_check.extend(extract_temperature_facts(flyer_content))
    facts_to_check.extend(extract_condition_facts(flyer_content))

    # De-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for f in facts_to_check:
        key = f.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    if not deduped:
        return IntegrityResult(
            ok=True, summary="no extractable facts in flyer (verified vacuously)"
        )

    verified: list[str] = []
    unverified: list[str] = []
    for fact in deduped:
        if fact_appears_in_log(fact):
            verified.append(fact)
        else:
            unverified.append(fact)

    if unverified:
        return IntegrityResult(
            ok=False,
            unverified_facts=unverified,
            verified_facts=verified,
            summary=(
                f"dataflow FAIL: {len(unverified)} unverified fact(s): "
                f"{unverified[:5]}" + ("..." if len(unverified) > 5 else "")
            ),
        )

    return IntegrityResult(
        ok=True,
        verified_facts=verified,
        summary=f"dataflow OK: verified {len(verified)} fact(s) against tool outputs",
    )


__all__ = [
    "IntegrityResult",
    "ToolCallRecord",
    "_TOOL_CALL_LOG",
    "clear_log",
    "extract_condition_facts",
    "extract_money_facts",
    "extract_temperature_facts",
    "extract_testid_facts",
    "fact_appears_in_log",
    "record_tool_call",
    "verify_dataflow",
]
