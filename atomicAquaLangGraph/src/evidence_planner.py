"""
evidence_planner.py — Query understanding + execution plan generation.

Pipeline position:
  User Query → [THIS MODULE] → ExecutionPlan → correlation_orchestrator

This module is PURELY DETERMINISTIC — zero LLM calls.
It answers: "Given this query and these available logs, which tools should run?"

The ExecutionPlan is the contract handed to the orchestrator.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from src.domain_ontology import (
    extract_domains,
    get_tools_for_domains,
    TOOL_REGISTRY,
    DOMAINS,
)


# ═══════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ToolCall:
    """A single tool scheduled for execution."""
    tool_id: str
    available: bool          # True = required logs exist in file
    unavailable_reason: str = ""   # Populated when available=False


@dataclass
class ExecutionPlan:
    """
    Output of the evidence planner.
    Handed directly to the correlation orchestrator for execution.
    """
    query: str
    domains: list[dict]                    # [{domain, score, matched_keywords}]
    tool_calls: list[ToolCall]             # All tools (available + unavailable)
    available_logs: list[str]             # Normalized log names from the file
    has_log_file: bool                    # Whether any log file is loaded
    planning_notes: list[str] = field(default_factory=list)

    @property
    def runnable_tools(self) -> list[str]:
        """Tool IDs that can actually run (have required logs)."""
        return [tc.tool_id for tc in self.tool_calls if tc.available]

    @property
    def skipped_tools(self) -> list[str]:
        """Tool IDs skipped due to missing logs."""
        return [tc.tool_id for tc in self.tool_calls if not tc.available]

    @property
    def top_domains(self) -> list[str]:
        """Domain names ordered by relevance score."""
        return [d["domain"] for d in self.domains]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "domains": self.domains,
            "runnable_tools": self.runnable_tools,
            "skipped_tools": [
                {"tool_id": tc.tool_id, "reason": tc.unavailable_reason}
                for tc in self.tool_calls if not tc.available
            ],
            "available_logs": self.available_logs,
            "has_log_file": self.has_log_file,
            "planning_notes": self.planning_notes,
        }


# ═══════════════════════════════════════════════════════════════════
# PLANNER
# ═══════════════════════════════════════════════════════════════════

# Minimum domain score to include it in planning.
# Score = number of matched keywords. 1 is enough — one keyword is a signal.
_MIN_DOMAIN_SCORE = 1

# Max domains to plan for — avoids over-triggering on short queries.
_MAX_DOMAINS = 4

# Max tools per query — safety cap to prevent runaway parallel execution.
_MAX_TOOLS = 6


def build_execution_plan(
    query: str,
    available_logs: list[str],
) -> ExecutionPlan:
    """
    Core planner function.

    Args:
        query:          Raw user query string
        available_logs: List of log type names present in the uploaded file
                        (normalized, e.g. ["BESTPOS", "RXSTATUS", "TRACKSTAT"])

    Returns:
        ExecutionPlan with all tool decisions made.
    """
    notes: list[str] = []

    # ── Step 1: Normalize available logs ─────────────────────────────
    norm_logs = _normalize_logs(available_logs)
    has_file = len(norm_logs) > 0

    if not has_file:
        notes.append("No log file loaded — only documentation queries are possible.")

    # ── Step 2: Extract domains ───────────────────────────────────────
    all_domains = extract_domains(query)

    # Filter to meaningful scores
    relevant_domains = [d for d in all_domains if d["score"] >= _MIN_DOMAIN_SCORE]

    # Cap to top N domains to avoid exploding tool set
    relevant_domains = relevant_domains[:_MAX_DOMAINS]

    if not relevant_domains:
        # No domain match — still useful for doc-only queries
        notes.append("No telemetry domains matched — query may be documentation-only.")

    # ── Step 3: Map domains → tools ───────────────────────────────────
    domain_names = [d["domain"] for d in relevant_domains]
    candidate_tool_ids = get_tools_for_domains(domain_names)

    # Cap total tools
    if len(candidate_tool_ids) > _MAX_TOOLS:
        notes.append(f"Tool list capped at {_MAX_TOOLS} (from {len(candidate_tool_ids)} candidates).")
        candidate_tool_ids = candidate_tool_ids[:_MAX_TOOLS]

    # ── Step 4: Check log availability for each tool ──────────────────
    tool_calls: list[ToolCall] = []

    for tool_id in candidate_tool_ids:
        spec = TOOL_REGISTRY.get(tool_id)
        if not spec:
            continue

        if not spec.required_logs:
            # Tool works on any file content (e.g. time_analyzer, log_inventory)
            tool_calls.append(ToolCall(tool_id=tool_id, available=has_file))
            if not has_file:
                tool_calls[-1].unavailable_reason = "No log file loaded."
            continue

        # Check each required log
        missing = [
            log for log in spec.required_logs
            if log.upper() not in norm_logs
        ]

        if missing:
            tool_calls.append(ToolCall(
                tool_id=tool_id,
                available=False,
                unavailable_reason=f"Required log(s) not in file: {', '.join(missing)}",
            ))
            notes.append(f"Skipping {tool_id}: missing {', '.join(missing)}")
        else:
            tool_calls.append(ToolCall(tool_id=tool_id, available=True))

    # ── Step 5: Build plan ────────────────────────────────────────────
    plan = ExecutionPlan(
        query=query,
        domains=relevant_domains,
        tool_calls=tool_calls,
        available_logs=list(norm_logs),
        has_log_file=has_file,
        planning_notes=notes,
    )

    _log_plan(plan)
    return plan


def _normalize_logs(raw_logs: list[str]) -> set[str]:
    """
    Normalize log names to uppercase, strip trailing 'A' from ASCII variants
    (e.g. BESTPOSA → BESTPOS).
    """
    normalized = set()
    for log in raw_logs:
        upper = log.upper()
        if upper.endswith("A") and len(upper) > 4:
            normalized.add(upper[:-1])
        normalized.add(upper)
    return normalized


def _log_plan(plan: ExecutionPlan) -> None:
    print(f"\n[EVIDENCE_PLAN] query={plan.query!r}")
    print(f"  domains  : {plan.top_domains}")
    print(f"  runnable : {plan.runnable_tools}")
    print(f"  skipped  : {plan.skipped_tools}")
    print(f"  log file : {plan.has_log_file} ({len(plan.available_logs)} log types)")
    if plan.planning_notes:
        for note in plan.planning_notes:
            print(f"  note     : {note}")
    print()
