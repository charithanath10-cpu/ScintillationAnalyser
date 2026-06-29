"""
domain_ontology.py — Fixed domain vocabulary and tool registry.

This is the CONTRACT that everything else depends on.
Domains are fixed — never dynamic. Tools map to domains deterministically.

Architecture principle:
  Domain extraction is the ONLY place where query semantics are interpreted.
  Everything downstream is pure data flow.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# DOMAIN DEFINITIONS
# Fixed vocabulary — 9 domains covering all GNSS telemetry dimensions.
# ═══════════════════════════════════════════════════════════════════

DOMAINS = {
    "positioning": {
        "description": "Position solution quality, fix type, accuracy, RTK/INS state",
        "keywords": [
            "position", "fix", "rtk", "float", "single", "solution", "accuracy",
            "coordinate", "latitude", "longitude", "height", "altitude", "location",
            "pdop", "hdop", "bestpos", "ins", "navigation", "where", "horizontal",
            "vertical", "converge", "converged", "unstable", "drift", "lost fix",
        ],
    },
    "satellite_tracking": {
        "description": "Number of satellites tracked and used, satellite visibility, constellations",
        "keywords": [
            "satellite", "satellites", "sats", "tracked", "tracking", "visible",
            "in view", "elevation", "azimuth", "prn", "svn", "num sv", "satvis",
            "bestsats", "how many", "constellation", "constellations",
            "gps", "glonass", "galileo", "beidou", "qzss", "sbas", "navic",
            "satellite count", "satellite loss", "satellite drop",
            "which constellations", "what constellations",
        ],
    },
    "signal_quality": {
        "description": "C/No, signal strength, carrier-to-noise, signal fade/degradation, available signals",
        "keywords": [
            "signal", "c/no", "cno", "carrier to noise", "signal quality",
            "signal strength", "signal level", "signal power", "signal fade",
            "signal degradation", "trackstat", "weak signal", "strong signal",
            "average signal", "minimum signal", "maximum signal", "scintillation",
            "ionospheric", "multipath", "available signals", "signal types",
            "which signals", "what signals",
        ],
    },
    "interference": {
        "description": "Jamming, spoofing, RF interference, spectrum anomalies",
        "keywords": [
            "jamming", "jammer", "jam", "spoofing", "spoof", "interference",
            "interfere", "rf", "spectrum", "itdetect", "narrowband", "wideband",
            "attack", "threat", "anomaly", "detected", "detection", "power",
            "psd", "noise floor", "itspectral", "itbandpass",
        ],
    },
    "corrections": {
        "description": "Differential corrections, RTK base, SBAS, L-band, correction age",
        "keywords": [
            "correction", "corrections", "differential", "rtk base", "base station",
            "sbas", "lband", "l-band", "ntrip", "rtcm", "correction age", "age",
            "latency", "correction delay", "diff age", "reference station",
            "augmentation",
        ],
    },
    "receiver_status": {
        "description": "Receiver health, errors, warnings, resets, antenna status",
        "keywords": [
            "receiver status", "rxstatus", "error", "warning", "reset", "reboot",
            "antenna", "voltage", "temperature", "cpu", "overload", "buffer",
            "health", "fault", "failure", "hardware", "hwmonitor", "bit set",
            "status word", "status flag",
        ],
    },
    "time": {
        "description": "GPS time, UTC time, clock offset, time synchronization",
        "keywords": [
            "time", "clock", "utc", "gps time", "time status", "sync",
            "synchronization", "pps", "1 pps", "fine steering", "coarse",
            "time range", "duration", "time gap", "gap", "missing data",
            "continuous", "start time", "end time",
        ],
    },
    "inertial": {
        "description": "IMU, INS attitude, roll, pitch, azimuth, alignment",
        "keywords": [
            "imu", "ins", "inertial", "roll", "pitch", "azimuth", "heading",
            "attitude", "alignment", "converge", "inspva", "inspvax", "imu error",
            "angular rate", "acceleration", "bank angle", "yaw",
            "ins_solution_good", "ins_aligning", "ins_high_variance",
            "ins solution", "ins status", "ins converged",
        ],
    },
    "data_integrity": {
        "description": "Log completeness, file structure, data gaps, record counts",
        "keywords": [
            "data gap", "gap", "missing", "continuous", "file", "log types",
            "records", "count", "available", "what logs", "list logs", "summary",
            "overview", "file info", "data loss", "dropped", "interval",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# Each tool has a fixed ID, the log types it reads, and what it returns.
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ToolSpec:
    tool_id: str
    description: str
    required_logs: list[str]           # Log types this tool needs in the file
    output_fields: list[str]           # Keys the tool guarantees in its output JSON
    domains: list[str]                 # Domains this tool provides evidence for
    priority: int = 5                  # Lower = run first (1 = highest priority)
    optional_logs: list[str] = field(default_factory=list)  # Nice-to-have logs


TOOL_REGISTRY: dict[str, ToolSpec] = {

    # ── Positioning ───────────────────────────────────────────────────
    "bestpos_analyzer": ToolSpec(
        tool_id="bestpos_analyzer",
        description="Analyzes BESTPOS records: fix type distribution, accuracy stats, satellite count, correction age",
        required_logs=["BESTPOS"],
        output_fields=["fix_types", "position_accuracy", "num_svs_stats",
                       "correction_age_stats", "solution_status_distribution"],
        domains=["positioning", "corrections", "satellite_tracking"],
        priority=1,
    ),

    # ── Signal quality ────────────────────────────────────────────────
    "cn0_analyzer": ToolSpec(
        tool_id="cn0_analyzer",
        description="Analyzes C/No (carrier-to-noise) from TRACKSTAT: per-satellite stats, averages, degradation events",
        required_logs=["TRACKSTAT"],
        output_fields=["avg_cn0", "min_cn0", "max_cn0", "cn0_std_dev",
                       "satellites_tracked", "low_cn0_events", "cn0_timeline"],
        domains=["signal_quality", "satellite_tracking"],
        priority=2,
    ),

    # ── Interference ──────────────────────────────────────────────────
    "rxstatus_analyzer": ToolSpec(
        tool_id="rxstatus_analyzer",
        description="Decodes RXSTATUS status word: jamming, spoofing, antenna errors, receiver health flags",
        required_logs=["RXSTATUS"],
        output_fields=["jamming_events", "spoofing_events", "antenna_errors",
                       "receiver_errors", "status_flags_timeline"],
        domains=["interference", "receiver_status"],
        priority=1,
    ),

    "itdetect_analyzer": ToolSpec(
        tool_id="itdetect_analyzer",
        description="Analyzes ITDETECTSTATUS: spectrum analysis detections, RF power, bandwidth, center frequency",
        required_logs=["ITDETECTSTATUS"],
        output_fields=["interference_events", "spectrum_detections",
                       "rf_power_stats", "detection_count"],
        domains=["interference"],
        priority=2,
        optional_logs=["ITSPECTRALANALYSIS", "ITBANDPASSFILTBANK"],
    ),

    # ── Corrections ───────────────────────────────────────────────────
    "correction_age_analyzer": ToolSpec(
        tool_id="correction_age_analyzer",
        description="Analyzes differential correction age from BESTPOS field 14: age stats, high-age events",
        required_logs=["BESTPOS"],
        output_fields=["avg_correction_age", "max_correction_age",
                       "high_age_events", "correction_outage_periods"],
        domains=["corrections"],
        priority=3,
    ),

    # ── Satellite tracking ────────────────────────────────────────────
    "satellite_count_analyzer": ToolSpec(
        tool_id="satellite_count_analyzer",
        description="Tracks satellite count over time from BESTPOS: drops, minimums, constellations",
        required_logs=["BESTPOS"],
        output_fields=["avg_satellites", "min_satellites", "max_satellites",
                       "satellite_drop_events", "satellite_timeline"],
        domains=["satellite_tracking", "positioning"],
        priority=2,
    ),

    # ── Inertial ──────────────────────────────────────────────────────
    "ins_analyzer": ToolSpec(
        tool_id="ins_analyzer",
        description="Analyzes INS solution from INSPVA/INSPVAX: alignment status, attitude stats, solution quality, status transitions",
        required_logs=[],     # Works if either INSPVA or INSPVAX is present — checked internally
        output_fields=["ins_status_distribution", "roll_stats", "pitch_stats",
                       "azimuth_stats", "ins_solution_events", "status_first_seen"],
        domains=["inertial", "positioning"],
        priority=2,
        optional_logs=["INSPVA", "INSPVAX"],
    ),

    # ── Receiver status ───────────────────────────────────────────────
    "receiver_health_analyzer": ToolSpec(
        tool_id="receiver_health_analyzer",
        description="Full receiver health from RXSTATUS + HWMONITOR: all status bits, temperature, voltage",
        required_logs=["RXSTATUS"],
        output_fields=["all_status_events", "error_count", "warning_count",
                       "health_timeline"],
        domains=["receiver_status"],
        priority=2,
        optional_logs=["HWMONITOR"],
    ),

    # ── Time / data integrity ─────────────────────────────────────────
    "time_analyzer": ToolSpec(
        tool_id="time_analyzer",
        description="File time range, GPS/UTC coverage, time status distribution",
        required_logs=[],     # Works on any log with time fields
        output_fields=["time_range", "duration_seconds", "time_status_distribution",
                       "gps_weeks"],
        domains=["time", "data_integrity"],
        priority=1,
    ),

    "data_gap_analyzer": ToolSpec(
        tool_id="data_gap_analyzer",
        description="Detects time gaps and missing data intervals in the log file",
        required_logs=[],
        output_fields=["gap_count", "gaps", "total_missing_seconds",
                       "data_continuity_pct"],
        domains=["time", "data_integrity"],
        priority=3,
    ),

    "log_inventory": ToolSpec(
        tool_id="log_inventory",
        description="Lists all log types present in the file with record counts",
        required_logs=[],
        output_fields=["log_types", "total_records", "log_counts"],
        domains=["data_integrity"],
        priority=1,
    ),

    # ── Satellite visibility ──────────────────────────────────────────
    "satvis2_analyzer": ToolSpec(
        tool_id="satvis2_analyzer",
        description="Analyzes SATVIS2: per-constellation satellite counts, health, elevation/azimuth visibility",
        required_logs=["SATVIS2"],
        output_fields=["constellations", "total_visible_satellites",
                       "constellation_names", "avg_elevation"],
        domains=["satellite_tracking"],
        priority=2,
    ),

    # ── Channel configuration ─────────────────────────────────────────
    "chanconfiglist_analyzer": ToolSpec(
        tool_id="chanconfiglist_analyzer",
        description="Analyzes CHANCONFIGLIST: configured signal types and channel assignments per constellation",
        required_logs=["CHANCONFIGLIST"],
        output_fields=["configured_signals", "constellation_count",
                       "constellations", "total_signal_types"],
        domains=["satellite_tracking", "signal_quality"],
        priority=1,
    ),
}


# ═══════════════════════════════════════════════════════════════════
# DOMAIN → TOOL MAPPING
# Static registry: which tools provide evidence for each domain.
# ═══════════════════════════════════════════════════════════════════

DOMAIN_TOOL_MAP: dict[str, list[str]] = {
    "positioning":        ["bestpos_analyzer", "satellite_count_analyzer"],
    "satellite_tracking": ["cn0_analyzer", "satellite_count_analyzer", "satvis2_analyzer",
                           "chanconfiglist_analyzer", "bestpos_analyzer"],
    "signal_quality":     ["cn0_analyzer", "chanconfiglist_analyzer"],
    "interference":       ["rxstatus_analyzer", "itdetect_analyzer"],
    "corrections":        ["correction_age_analyzer", "bestpos_analyzer"],
    "receiver_status":    ["rxstatus_analyzer", "receiver_health_analyzer"],
    "time":               ["time_analyzer", "data_gap_analyzer"],
    "inertial":           ["ins_analyzer"],
    "data_integrity":     ["log_inventory", "time_analyzer", "data_gap_analyzer"],
}


# ═══════════════════════════════════════════════════════════════════
# DOMAIN EXTRACTION
# Pure keyword matching — zero LLM. Returns scored domain list.
# ═══════════════════════════════════════════════════════════════════

def extract_domains(question: str) -> list[dict]:
    """
    Extract relevant domains from a user query using keyword matching.

    Returns list of dicts ordered by relevance score:
      [{"domain": str, "score": int, "matched_keywords": list[str]}, ...]

    Score = number of matched keywords (simple, auditable, no magic).
    Only domains with score > 0 are returned.
    """
    q_lower = question.lower()
    scored: list[dict] = []

    for domain_name, domain_data in DOMAINS.items():
        matched = []
        for kw in domain_data["keywords"]:
            # Use word-boundary-aware matching for short keywords to avoid
            # "signal" matching "signals" but "gps" not matching "gps_time"
            if len(kw) <= 4:
                import re
                if re.search(rf'\b{re.escape(kw)}\b', q_lower):
                    matched.append(kw)
            else:
                if kw in q_lower:
                    matched.append(kw)

        if matched:
            scored.append({
                "domain": domain_name,
                "score": len(matched),
                "matched_keywords": matched,
            })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    print(f"[DOMAIN_EXTRACT] query={question!r}")
    for item in scored:
        print(f"  domain={item['domain']} score={item['score']} "
              f"keywords={item['matched_keywords'][:3]}")

    return scored


def get_tools_for_domains(domains: list[str]) -> list[str]:
    """
    Return deduplicated ordered list of tool IDs for a set of domains.
    Ordered by tool priority (lower number = higher priority).
    """
    tool_ids: dict[str, int] = {}  # tool_id → priority

    for domain in domains:
        for tool_id in DOMAIN_TOOL_MAP.get(domain, []):
            spec = TOOL_REGISTRY.get(tool_id)
            if spec and tool_id not in tool_ids:
                tool_ids[tool_id] = spec.priority

    # Sort by priority
    ordered = sorted(tool_ids.keys(), key=lambda t: tool_ids[t])
    return ordered
