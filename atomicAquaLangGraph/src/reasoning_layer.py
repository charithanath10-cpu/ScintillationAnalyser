"""
reasoning_layer.py — LLM Reasoning + Explanation Layer (Phase 2, Step 5).

Pipeline position:
  Correlation JSON → [THIS MODULE] → Final Response (markdown string)

The LLM ONLY does:
  - Correlate evidence from multiple tools
  - Explain likely root causes
  - Summarize diagnostics in plain English
  - Generate human-readable response

The LLM NEVER does:
  - Parse raw telemetry
  - Compute metrics
  - Perform statistical analysis
  - Identify low-level anomalies (those come in the Correlation JSON already)

This is the ONLY place an LLM call happens in the new pipeline.
"""

from __future__ import annotations

import json
import time

from src.response_formatter import format_final_response, format_fallback_response
from src.doc_answering import answer_without_file


# ═══════════════════════════════════════════════════════════════════
# REASONING PROMPT
# The LLM receives pre-computed evidence — it explains, not discovers.
# ═══════════════════════════════════════════════════════════════════

_REASONING_PROMPT = """You are a senior GNSS systems engineer analyzing NovAtel OEM7 receiver telemetry.

You have been given a structured telemetry evidence JSON that was computed deterministically from raw log data.
Your job is ONLY to:
1. Explain the named diagnoses that were found
2. Correlate the evidence across multiple sources to explain root causes
3. Summarize the findings clearly for the user's question
4. If multiple diagnoses are present, explain how they relate to each other

STRICT RULES:
- Base your answer ENTIRELY on the evidence JSON provided. Do not invent or assume data.
- The "diagnostics" section contains NAMED CONCLUSIONS already identified — explain them, don't re-derive them.
- The "events" section contains DETECTED FACTS — reference them when explaining.
- The "metrics" section contains PRE-COMPUTED values — use them directly, never re-calculate.
- If evidence is marked "unavailable", explicitly state what was missing and how it limits the analysis.
- Write in clear, professional language suitable for a GNSS engineer.
- Lead with the most critical diagnosis (severity: critical > high > medium > low).
- For each diagnosis, explain: what happened, why it happened, and what to do about it.
- Keep the response focused — if there is a primary diagnosis, lead with it.

USER QUESTION:
{question}

TELEMETRY EVIDENCE JSON:
{evidence_json}

MISSING EVIDENCE (logs not present in file):
{missing_evidence}

Now provide your analysis based on the diagnoses and evidence above:"""


_NO_EVIDENCE_PROMPT = """You are a NovAtel OEM7 GNSS expert assistant.

The user asked: "{question}"

A log file IS loaded, but none of the required log types for this question were found in the file.

Available logs in file: {available_logs}
Required logs that were missing: {missing_logs}

Explain what the question requires and suggest what log types the user would need.
Also suggest what questions CAN be answered from the available logs."""


# ═══════════════════════════════════════════════════════════════════
# REASONING ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def synthesize_response(
    correlation_json: dict,
    question: str,
    session_id: str = "",
) -> str:
    """
    Takes the Correlation JSON from the orchestrator and produces
    a final human-readable response using one LLM call.

    Args:
        correlation_json:  Output from correlation_orchestrator.execute_plan()
        question:          Original user query
        session_id:        For status tracking

    Returns:
        Final markdown-formatted response string
    """
    from src.main import get_llm, set_status
    from langchain_core.messages import HumanMessage

    t0 = time.time()

    has_file    = correlation_json.get("execution_meta", {}).get("has_log_file", False)
    tools_run   = correlation_json.get("execution_meta", {}).get("tools_run", [])
    unavailable = correlation_json.get("unavailable_evidence", [])
    events      = correlation_json.get("events", [])
    evidence    = correlation_json.get("evidence", {})

    # ── Case 1: No log file loaded ────────────────────────────────────
    if not has_file:
        return answer_without_file(question, session_id)

    # ── Case 2: File loaded but no evidence collected ─────────────────
    available_tools_ran = [t for t in tools_run if evidence.get(t, {}).get("status") == "ok"]
    if not available_tools_ran:
        missing_logs = list({u["tool_id"] for u in unavailable})
        available_logs = correlation_json.get("available_logs", [])

        if session_id:
            set_status(session_id, "Checking available log types...")

        prompt = _NO_EVIDENCE_PROMPT.format(
            question=question,
            available_logs=", ".join(available_logs) if available_logs else "none",
            missing_logs=", ".join(missing_logs) if missing_logs else "none",
        )
        try:
            resp = get_llm().invoke([HumanMessage(content=prompt)])
            return resp.content.strip()
        except Exception as e:
            logs_str = ", ".join(available_logs) if available_logs else "none"
            return (
                f"The required log types for this question were not found in the file.\n\n"
                f"**Available logs:** {logs_str}\n\n"
                f"Try asking about the logs that are present in your file."
            )

    # ── Case 3: Evidence collected — LLM reasoning ────────────────────
    if session_id:
        set_status(session_id, "Correlating evidence across log sources...")

    # Build a focused evidence subset — only include tools that ran successfully
    # and strip oversized arrays to keep the prompt manageable
    focused_evidence = _build_focused_evidence(correlation_json)

    # Format missing evidence block
    missing_str = _format_missing_evidence(unavailable) if unavailable else "None — all required evidence was available."

    # Build evidence JSON string (compact, no indentation to save tokens)
    evidence_str = json.dumps(focused_evidence, indent=2, default=str)

    # Truncate if very large (safety cap)
    if len(evidence_str) > 8000:
        evidence_str = evidence_str[:8000] + "\n... [truncated for length]"

    prompt = _REASONING_PROMPT.format(
        question=question,
        evidence_json=evidence_str,
        missing_evidence=missing_str,
    )

    if session_id:
        set_status(session_id, "Generating correlated analysis...")

    try:
        resp = get_llm().invoke([HumanMessage(content=prompt)])
        llm_explanation = resp.content.strip()
        elapsed = time.time() - t0
        print(f"[REASONING] completed in {elapsed:.2f}s tools_used={available_tools_ran}")

        # Phase 5: Format the final structured response
        answer = format_final_response(
            llm_explanation=llm_explanation,
            correlation_json=correlation_json,
            elapsed_seconds=elapsed,
        )
        return answer
    except Exception as e:
        print(f"[REASONING] LLM error: {e}")
        # Phase 5: Deterministic fallback response
        return format_fallback_response(correlation_json)


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _build_focused_evidence(correlation_json: dict) -> dict:
    """
    Build a focused, size-controlled evidence dict for the LLM prompt.
    Diagnostics and events are always included in full.
    Raw record arrays are stripped from tool evidence.
    """
    evidence    = correlation_json.get("evidence", {})
    events      = correlation_json.get("events", [])
    metrics     = correlation_json.get("metrics", {})
    diagnostics = correlation_json.get("diagnostics", [])

    focused = {
        "query":            correlation_json.get("query", ""),
        "domains_analyzed": correlation_json.get("domains", []),
        # Phase 4: Diagnostics come FIRST — LLM should read these before raw evidence
        "diagnostics":      diagnostics,
        # Phase 3: Semantic events as supporting evidence
        "events":           events,
        # Flat metrics for quick reference
        "metrics":          metrics,
        # Per-tool summaries (arrays stripped)
        "tool_evidence":    {},
    }

    # Per-tool: include summary fields, drop raw record arrays
    _ARRAY_KEYS_TO_DROP = {
        "jamming_events", "spoofing_events", "interference_events",
        "records", "gaps", "high_age_events", "satellite_drop_events",
    }

    for tool_id, result in evidence.items():
        if result.get("status") != "ok":
            focused["tool_evidence"][tool_id] = {
                "status": result.get("status"),
                "reason": result.get("reason", result.get("error", "")),
            }
            continue

        slim = {k: v for k, v in result.items() if k not in _ARRAY_KEYS_TO_DROP}
        for key in _ARRAY_KEYS_TO_DROP:
            if key in result and isinstance(result[key], list) and result[key]:
                slim[f"{key}_sample"] = result[key][:3]
                slim[f"{key}_total"]  = len(result[key])

        focused["tool_evidence"][tool_id] = slim

    return focused


def _format_missing_evidence(unavailable: list[dict]) -> str:
    if not unavailable:
        return "None"
    lines = []
    for item in unavailable:
        lines.append(f"- {item['tool_id']}: {item['reason']}")
    return "\n".join(lines)
