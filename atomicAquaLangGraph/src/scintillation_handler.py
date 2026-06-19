"""
scintillation_handler.py — In-memory scintillation analysis pipeline.

Wires the scintillation parsers and detector together so that the
agentic log assistant can run a full analysis purely from bytes —
no files are written to disk at any point.

Public API
----------
is_scintillation_question(text: str) -> bool
    Fast keyword check — true when the user is asking about scintillation.

analyse_bytes(file_bytes: bytes, environment_type: str = "OPEN_SKY") -> dict
    Run the full pipeline on raw file bytes.
    Returns a JSON-serialisable summary dict (same shape as
    scintillation_summary.json produced by the standalone script).

build_llm_prompt(summary: dict, user_question: str) -> str
    Build the reasoning prompt that is handed to the LLM.
"""

from __future__ import annotations

import json
import re
import pandas as pd

# ── lazy imports from the bundled scintillation modules ──────────────
# Both modules are placed alongside this file in src/.
# We import lazily so that numpy/pandas are only touched when actually needed.

def _get_parsers():
    from src.scintillation_log_decoders import (
        parse_range_from_bytes,
        parse_itdetect_from_bytes,
        parse_trackstat_from_bytes,
        parse_bestpos_from_bytes,
        parse_satvis2_from_bytes,
        pivot_range_df,
    )
    return (parse_range_from_bytes, parse_itdetect_from_bytes,
            parse_trackstat_from_bytes, parse_bestpos_from_bytes,
            parse_satvis2_from_bytes, pivot_range_df)


def _get_detector():
    from src.scintillation_detector import (
        enrich_range_df,
        enrich_range_with_elevation,
        epoch_health,
        enrich_bestpos_df,
        detect_scintillation,
        summarise_results,
    )
    return (enrich_range_df, enrich_range_with_elevation,
            epoch_health, enrich_bestpos_df,
            detect_scintillation, summarise_results)


# ── Keyword detection ────────────────────────────────────────────────

_SCINT_KEYWORDS = re.compile(
    r"\b(scintillat|ionospher|iono\s*scint|signal\s+fad|phase\s+noise"
    r"|adr[\s_-]?std|carrier[\s-]?noise|cn0[\s_-]?drop|cno[\s_-]?drop"
    r"|lock[\s_-]?loss|tracking[\s_-]?loss|high[\s_-]?elev"
    r"|auroral\b|equatorial\s+disturbance)",
    re.IGNORECASE,
)


def is_scintillation_question(text: str) -> bool:
    """Return True if the user message is asking about scintillation."""
    return bool(_SCINT_KEYWORDS.search(text))


# ── Core in-memory pipeline ──────────────────────────────────────────

def analyse_bytes(
    file_bytes: bytes,
    environment_type: str = "OPEN_SKY",
) -> dict:
    """
    Run the full scintillation pipeline on raw log bytes.

    Parameters
    ----------
    file_bytes       : raw bytes of the NovAtel ASCII log file
    environment_type : "OPEN_SKY" (default) or "OBSTRUCTED"

    Returns
    -------
    JSON-serialisable summary dict — same schema as scintillation_summary.json.
    An extra key ``"pipeline_error"`` is added if something goes wrong.
    """
    try:
        (parse_range, parse_itdetect, parse_trackstat,
         parse_bestpos, parse_satvis2, pivot_range) = _get_parsers()

        (enrich_range, enrich_elev, epoch_hlth,
         enrich_bestpos, detect_scint, summarise) = _get_detector()

        # ── 1. Parse all log types from bytes ─────────────────────────
        text = file_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()

        range_obs    = []
        itdetect_obs = []
        trackstat_obs = []
        bestpos_obs  = []
        satvis2_obs  = []

        # re-use the line-level parsers from scintillation_log_decoders
        from src.scintillation_log_decoders import (
            _parse_range_line,
            _parse_itdetect_line,
            _parse_trackstat_line,
            _parse_abbrev_trackstat_blocks,
            _parse_bestpos_line,
            _parse_satvis2_line,
        )

        for line in lines:
            s = line.strip()
            if not s or s[0] not in ("#", "<"):
                continue
            if s.startswith("#RANGEA,"):
                obs = _parse_range_line(s)
                if obs:
                    range_obs.extend(obs)
            elif s.startswith("#ITDETECTSTATUSA,"):
                entries = _parse_itdetect_line(s)
                if entries:
                    itdetect_obs.extend(entries)
            elif s.startswith("#TRACKSTATA,"):
                entries = _parse_trackstat_line(s)
                if entries:
                    trackstat_obs.extend(entries)
            elif s.startswith("#BESTPOSA,"):
                row = _parse_bestpos_line(s)
                if row:
                    bestpos_obs.append(row)
            elif s.startswith("#SATVIS2A,"):
                sats = _parse_satvis2_line(s)
                if sats:
                    satvis2_obs.extend(sats)

        # Abbreviated TRACKSTAT blocks
        trackstat_obs.extend(_parse_abbrev_trackstat_blocks(lines))

        range_df     = pd.DataFrame(range_obs)     if range_obs     else pd.DataFrame()
        itdetect_df  = pd.DataFrame(itdetect_obs)  if itdetect_obs  else pd.DataFrame()
        trackstat_df = pd.DataFrame(trackstat_obs) if trackstat_obs else pd.DataFrame()
        bestpos_df   = pd.DataFrame(bestpos_obs)   if bestpos_obs   else pd.DataFrame()
        satvis2_df   = pd.DataFrame(satvis2_obs)   if satvis2_obs   else pd.DataFrame()

        # ── 2. Enrich RANGE ───────────────────────────────────────────
        range_df = enrich_range(range_df)
        range_df = enrich_elev(range_df, satvis2_df, environment_type=environment_type)

        # ── 3. Epoch health rollup ────────────────────────────────────
        epoch_health_df = epoch_hlth(range_df)

        # ── 4. Enrich BESTPOS ─────────────────────────────────────────
        bestpos_df = enrich_bestpos(bestpos_df)

        # ── 5. Final scintillation decision ───────────────────────────
        scintillation_df = detect_scint(
            epoch_health_df, bestpos_df,
            environment_type=environment_type,
        )

        # ── 6. Human-readable summary ─────────────────────────────────
        summary = summarise(scintillation_df, epoch_health_df, bestpos_df, range_df)

        # Attach counts from the other parsed logs for context
        summary["parsed_log_counts"] = {
            "RANGEA":           len(range_obs),
            "ITDETECTSTATUSA":  len(itdetect_obs),
            "TRACKSTATA":       len(trackstat_obs),
            "BESTPOSA":         len(bestpos_obs),
            "SATVIS2A":         len(satvis2_obs),
        }
        summary["environment_type"] = environment_type

        return summary

    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        print(f"[SCINTILLATION] pipeline error: {exc}\n{tb}")
        return {
            "pipeline_error": str(exc),
            "scintillation_detected": False,
            "answer": "Scintillation analysis failed — see pipeline_error for details.",
            "confidence_level": "LOW",
            "worst_flag": "FALSE",
        }


# ── LLM prompt builder ───────────────────────────────────────────────

_SCINT_REASONING_PROMPT = """\
You are a NovAtel OEM7 GNSS signal expert specialising in ionospheric scintillation analysis.

The user uploaded a receiver log file and asked about scintillation.
A deterministic scintillation detection pipeline was run on the file and produced the
structured JSON summary below.  Use this summary to give a clear, precise answer.

## Scintillation Analysis Summary (JSON)
```json
{summary_json}
```

## User Question
{user_question}

## Instructions
- Lead with a direct YES / NO / INCONCLUSIVE verdict and the confidence level.
- Explain the key evidence that drove the decision (cno_flag drops, adr_flag thresholds,
  lock-loss events, high-elevation lock loss, location zone, time-of-day flag).
- Mention any steps that were NOT evaluated (listed in steps_not_evaluated) so the user
  understands what was and was not checked.
- If scintillation_detected is false, explain why the thresholds were not met.
- Keep the tone technical but accessible — this is a GNSS engineer reading a diagnostic report.
- Do NOT fabricate numbers; every value you cite must come from the JSON summary.
"""


def build_llm_prompt(summary: dict, user_question: str) -> str:
    """Return a fully-formatted reasoning prompt for the LLM."""
    # Serialise with a fallback for any non-JSON-safe types (e.g. pandas NA)
    summary_json = json.dumps(summary, indent=2, default=str)
    return _SCINT_REASONING_PROMPT.format(
        summary_json=summary_json,
        user_question=user_question,
    )
