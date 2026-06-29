"""
response_formatter.py — Phase 5: Structured Response Formatter

Pipeline position:
  LLM Explanation + Correlation JSON → [THIS MODULE] → Final Markdown Response

This module takes the raw LLM explanation text and the full Correlation JSON
and assembles a final, structured markdown response that includes:

  1. Severity header  — visual severity indicator at the top
  2. LLM explanation  — the main body (written by LLM)
  3. Diagnostic cards — one card per diagnosis (deterministic, not LLM)
  4. Key metrics bar  — the most relevant numbers in a compact table
  5. Evidence footer  — which tools ran, what was missing, elapsed time

ARCHITECTURE PRINCIPLE:
  The LLM writes the narrative explanation.
  The formatter adds the deterministic structure around it.
  The user gets both: readable prose + auditable evidence.

  The structured cards are always deterministic — they never change
  based on how the LLM phrases things. This prevents hallucination
  from affecting the factual summary.
"""

from __future__ import annotations

from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# SEVERITY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

_SEVERITY_ICONS = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
    "info":     "ℹ️",
    "nominal":  "✅",
}

_SEVERITY_LABELS = {
    "critical": "CRITICAL",
    "high":     "HIGH",
    "medium":   "MEDIUM",
    "low":      "LOW",
    "info":     "INFO",
    "nominal":  "NOMINAL",
}

_CONFIDENCE_BAR = {
    (0.95, 1.01): "████████████ 100%",
    (0.90, 0.95): "███████████░ ~92%",
    (0.85, 0.90): "██████████░░ ~87%",
    (0.80, 0.85): "█████████░░░ ~82%",
    (0.70, 0.80): "████████░░░░ ~75%",
    (0.60, 0.70): "██████░░░░░░ ~65%",
    (0.00, 0.60): "████░░░░░░░░ <60%",
}


def _conf_bar(confidence: float) -> str:
    for (lo, hi), bar in _CONFIDENCE_BAR.items():
        if lo <= confidence < hi:
            return bar
    return "████████████ 100%"


# ═══════════════════════════════════════════════════════════════════
# RESPONSE FORMATTER
# ═══════════════════════════════════════════════════════════════════

def format_final_response(
    llm_explanation: str,
    correlation_json: dict,
    elapsed_seconds: float = 0.0,
) -> str:
    """
    Assemble the final markdown response.

    Args:
        llm_explanation:  The raw text from the LLM reasoning call
        correlation_json: The full Correlation JSON from the orchestrator
        elapsed_seconds:  Total pipeline elapsed time for the footer

    Returns:
        Final markdown string ready for display
    """
    diagnostics = correlation_json.get("diagnostics", [])
    events      = correlation_json.get("events", [])
    metrics     = correlation_json.get("metrics", {})
    unavailable = correlation_json.get("unavailable_evidence", [])
    tools_run   = correlation_json.get("execution_meta", {}).get("tools_run", [])
    has_file    = correlation_json.get("execution_meta", {}).get("has_log_file", False)

    # If no log file, return explanation as-is (doc-only response)
    if not has_file:
        return llm_explanation

    # Determine overall severity from diagnostics
    overall_severity = _overall_severity(diagnostics, events)

    parts: list[str] = []

    # ── 1. Severity header (only for non-nominal cases) ───────────────
    if overall_severity not in ("nominal", "low", "info"):
        header = _build_severity_header(overall_severity, diagnostics)
        parts.append(header)

    # ── 2. LLM explanation (main body) ───────────────────────────────
    parts.append(llm_explanation.strip())

    # ── 3. Diagnostic cards (deterministic) ──────────────────────────
    non_nominal = [d for d in diagnostics if d.get("diagnostic_id") != "NOMINAL_OPERATION"]
    if non_nominal:
        parts.append("\n---\n")
        parts.append(_build_diagnostic_cards(non_nominal))

    # ── 4. Key metrics table (if meaningful metrics exist) ────────────
    metric_table = _build_metrics_table(metrics, diagnostics)
    if metric_table:
        parts.append("\n")
        parts.append(metric_table)

    # ── 5. Evidence footer ────────────────────────────────────────────
    footer = _build_evidence_footer(tools_run, unavailable, elapsed_seconds)
    if footer:
        parts.append("\n")
        parts.append(footer)

    return "\n".join(parts)


def format_no_file_response(llm_explanation: str) -> str:
    """Pass-through for doc-only responses — no structure needed."""
    return llm_explanation.strip()


def format_fallback_response(correlation_json: dict) -> str:
    """
    LLM-free fallback: produce a fully deterministic response
    directly from the Correlation JSON when the LLM is unavailable.
    """
    diagnostics = correlation_json.get("diagnostics", [])
    events      = correlation_json.get("events", [])
    metrics     = correlation_json.get("metrics", {})
    tools_run   = correlation_json.get("execution_meta", {}).get("tools_run", [])
    query       = correlation_json.get("query", "")

    parts = [f"**Analysis: {query}**\n"]

    overall_severity = _overall_severity(diagnostics, events)
    icon = _SEVERITY_ICONS.get(overall_severity, "ℹ️")

    # Diagnostics
    if diagnostics:
        non_nominal = [d for d in diagnostics if d.get("diagnostic_id") != "NOMINAL_OPERATION"]
        if non_nominal:
            parts.append("**Diagnoses:**\n")
            for d in non_nominal:
                sev_icon = _SEVERITY_ICONS.get(d.get("severity", ""), "•")
                parts.append(f"{sev_icon} **{d['title']}** (confidence: {d['confidence']:.0%})")
                parts.append(f"   {d['conclusion']}")
                parts.append(f"   *Root cause:* {d['root_cause']}")
                parts.append("")

    # Events summary
    critical_events = [e for e in events if e.get("severity") == "critical"]
    if critical_events:
        parts.append("**Critical Events:**")
        for ev in critical_events:
            parts.append(f"- {ev.get('description', ev.get('event', ''))}")
        parts.append("")

    # Metrics
    metric_table = _build_metrics_table(metrics, diagnostics)
    if metric_table:
        parts.append(metric_table)

    parts.append(f"\n*Based on: {', '.join(tools_run) if tools_run else 'no tools run'}*")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# SECTION BUILDERS
# ═══════════════════════════════════════════════════════════════════

def _build_severity_header(severity: str, diagnostics: list[dict]) -> str:
    """Build the severity banner at the top of the response."""
    icon  = _SEVERITY_ICONS.get(severity, "ℹ️")
    label = _SEVERITY_LABELS.get(severity, severity.upper())

    # Get the primary (most severe) diagnosis title
    primary = diagnostics[0] if diagnostics else None
    title   = primary.get("title", "Issue Detected") if primary else "Issue Detected"

    return f"{icon} **[{label}] {title}**\n"


def _build_diagnostic_cards(diagnostics: list[dict]) -> str:
    """
    Build one compact card per diagnosis.
    Cards are deterministic — immune to LLM phrasing variation.
    """
    lines = ["**Diagnostic Summary**\n"]

    for d in diagnostics:
        sev     = d.get("severity", "")
        icon    = _SEVERITY_ICONS.get(sev, "•")
        conf    = d.get("confidence", 0)
        conf_pct = f"{conf:.0%}"
        rule_id = d.get("rule_id", "")

        lines.append(f"{icon} **{d['title']}** — {conf_pct} confidence")
        lines.append(f"> {d['conclusion']}")

        # Show top 2 contributing factors
        factors = d.get("contributing_factors", [])
        if factors:
            for f in factors[:2]:
                lines.append(f"> - {f}")
            if len(factors) > 2:
                lines.append(f"> - *...and {len(factors)-2} more factors*")

        # Show top 3 recommended actions
        actions = d.get("recommended_actions", [])
        if actions:
            lines.append(f">")
            lines.append(f"> **Recommended actions:**")
            for a in actions[:3]:
                lines.append(f"> 1. {a}")

        lines.append("")

    return "\n".join(lines)


def _build_metrics_table(metrics: dict, diagnostics: list[dict]) -> str:
    """
    Build a compact metrics table showing the most relevant values.
    Only shows metrics that are directly referenced by diagnostics.
    """
    if not metrics:
        return ""

    # Determine which metrics are most relevant from diagnostic snapshots
    relevant_keys: set[str] = set()
    for d in diagnostics:
        snapshot = d.get("metrics_snapshot", {})
        for k, v in snapshot.items():
            if v is not None:
                relevant_keys.add(k)

    # Always include these if present
    always_show = {
        "avg_cn0", "dominant_fix_type", "avg_correction_age",
        "jamming_detected", "spoofing_detected", "duration_minutes",
        "data_continuity_pct", "min_num_svs",
    }
    relevant_keys |= {k for k in always_show if k in metrics}

    if not relevant_keys:
        return ""

    # Format each metric
    rows: list[tuple[str, str]] = []
    _METRIC_LABELS = {
        "avg_cn0":             ("Avg C/No",             "dB-Hz"),
        "min_cn0":             ("Min C/No",             "dB-Hz"),
        "max_cn0":             ("Max C/No",             "dB-Hz"),
        "dominant_fix_type":   ("Dominant Fix Type",    ""),
        "avg_correction_age":  ("Avg Correction Age",   "s"),
        "max_correction_age":  ("Max Correction Age",   "s"),
        "correction_loss_pct": ("Correction Loss",      "%"),
        "avg_num_svs":         ("Avg Satellites",       ""),
        "min_num_svs":         ("Min Satellites",       ""),
        "jamming_detected":    ("Jamming",               ""),
        "spoofing_detected":   ("Spoofing",              ""),
        "duration_minutes":    ("Session Duration",     "min"),
        "data_continuity_pct": ("Data Continuity",      "%"),
        "gap_count":           ("Data Gaps",             ""),
        "low_cn0_epoch_pct":   ("Low C/No Epochs",      "%"),
    }

    for key in sorted(relevant_keys):
        val = metrics.get(key)
        if val is None:
            continue
        label, unit = _METRIC_LABELS.get(key, (key.replace("_", " ").title(), ""))

        # Format value
        if isinstance(val, bool):
            formatted = "Yes ⚠️" if val else "No ✓"
        elif isinstance(val, float):
            formatted = f"{val:.1f} {unit}".strip() if unit else f"{val:.3f}"
        elif isinstance(val, int):
            formatted = f"{val} {unit}".strip() if unit else str(val)
        else:
            formatted = f"{val} {unit}".strip() if unit else str(val)

        rows.append((label, formatted))

    if not rows:
        return ""

    lines = ["**Key Metrics**\n"]
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for label, val in rows:
        lines.append(f"| {label} | {val} |")

    return "\n".join(lines)


def _build_evidence_footer(
    tools_run: list[str],
    unavailable: list[dict],
    elapsed_seconds: float,
) -> str:
    """Build a compact evidence provenance footer."""
    lines = []

    if tools_run:
        tool_str = " · ".join(f"`{t}`" for t in tools_run)
        lines.append(f"*Evidence from: {tool_str}*")

    if unavailable:
        missing = [u["tool_id"].replace("_analyzer", "").replace("_", " ") for u in unavailable]
        lines.append(f"*Missing logs: {', '.join(missing)} — analysis may be incomplete*")

    if elapsed_seconds > 0:
        lines.append(f"*Analysis time: {elapsed_seconds:.1f}s*")

    return "  \n".join(lines) if lines else ""


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _overall_severity(diagnostics: list[dict], events: list[dict]) -> str:
    """Determine the overall session severity from all diagnostics and events."""
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "nominal": 5}

    worst = "nominal"
    for d in diagnostics:
        sev = d.get("severity", "low")
        if sev == "low" and d.get("diagnostic_id") == "NOMINAL_OPERATION":
            sev = "nominal"
        if order.get(sev, 99) < order.get(worst, 99):
            worst = sev

    # Also check events
    for ev in events:
        sev = ev.get("severity", "info")
        if order.get(sev, 99) < order.get(worst, 99):
            worst = sev

    return worst
