"""
correlation_orchestrator.py — Multi-tool execution + correlation JSON assembly.

Pipeline position:
  ExecutionPlan → [THIS MODULE] → CorrelationJSON → LLM Reasoning Layer

This module:
  1. Executes all runnable tools from the plan (in parallel where safe)
  2. Each tool returns structured evidence (never natural language)
  3. Assembles all evidence into a fixed-schema CorrelationJSON
  4. Adds a structured "unavailable_evidence" block so the LLM knows what's missing

IMPORTANT:
  Tools NEVER produce natural language here.
  They only produce metrics, counts, events, confidence values.
  The LLM receives only the final CorrelationJSON.
"""

from __future__ import annotations

import time
import statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Any

from src.evidence_planner import ExecutionPlan
from src.semantic_event_engine import generate_semantic_events
from src.diagnostic_engine import run_diagnostics


# ═══════════════════════════════════════════════════════════════════
# CORRELATION JSON SCHEMA (fixed envelope)
# ═══════════════════════════════════════════════════════════════════

def _empty_correlation_json(query: str) -> dict:
    """
    Returns the fixed-schema correlation JSON envelope.
    All tools write into this structure — never outside it.
    """
    return {
        "query": query,
        "domains": [],
        "evidence": {},            # domain → tool_output
        "events": [],              # [{event, severity, timestamp, source_tool}]
        "metrics": {},             # flat key→value for quick LLM access
        "diagnostics": [],         # [{type, confidence, evidence_refs}]
        "unavailable_evidence": [], # [{tool_id, reason}]
        "execution_meta": {
            "tools_run": [],
            "tools_skipped": [],
            "elapsed_seconds": 0.0,
            "has_log_file": False,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# INDIVIDUAL TOOL IMPLEMENTATIONS
# Each returns a structured dict — NEVER natural language strings.
# Status field: "ok" | "no_data" | "error"
# ═══════════════════════════════════════════════════════════════════

def _run_bestpos_analyzer(log_entry: dict) -> dict:
    """
    Analyzes BESTPOS records.
    Returns: fix type distribution, position accuracy, satellite counts,
             correction age, solution status events.
    """
    import pandas as pd

    df = log_entry["df"]
    bestpos = df[df["log_name"].str.upper() == "BESTPOS"].copy()

    if bestpos.empty:
        return {"status": "no_data", "reason": "No BESTPOS records in file"}

    # Parse fields_raw into structured columns
    parsed_rows = []
    for _, row in bestpos.iterrows():
        parts = [p.strip() for p in row.get("fields_raw", "").split(",")]
        if len(parts) < 14:
            continue
        try:
            parsed_rows.append({
                "sol_status":      parts[0] if len(parts) > 0 else "",
                "pos_type":        parts[1] if len(parts) > 1 else "",
                "lat":             float(parts[2]) if len(parts) > 2 else None,
                "lon":             float(parts[3]) if len(parts) > 3 else None,
                "hgt":             float(parts[4]) if len(parts) > 4 else None,
                "lat_std":         _safe_float(parts[7]) if len(parts) > 7 else None,
                "lon_std":         _safe_float(parts[8]) if len(parts) > 8 else None,
                "hgt_std":         _safe_float(parts[9]) if len(parts) > 9 else None,
                "diff_age":        _safe_float(parts[12]) if len(parts) > 12 else None,
                "num_svs":         _safe_int(parts[13]) if len(parts) > 13 else None,
                "num_sol_svs":     _safe_int(parts[14]) if len(parts) > 14 else None,
                "utc_time":        row.get("utc_time", ""),
                "seconds":         float(row["seconds"]),
                "week":            int(row["week"]),
            })
        except (ValueError, IndexError):
            continue

    if not parsed_rows:
        return {"status": "no_data", "reason": "BESTPOS records present but fields could not be parsed"}

    bdf = pd.DataFrame(parsed_rows)

    # Fix type distribution
    fix_dist = bdf["pos_type"].value_counts().to_dict()

    # Solution status distribution
    sol_dist = bdf["sol_status"].value_counts().to_dict()

    # Accuracy stats
    lat_stds = bdf["lat_std"].dropna().tolist()
    lon_stds = bdf["lon_std"].dropna().tolist()
    hgt_stds = bdf["hgt_std"].dropna().tolist()

    # Satellite stats
    num_svs = bdf["num_svs"].dropna().tolist()
    sat_drops = _detect_drops(bdf["num_svs"].dropna().tolist(), threshold_pct=0.3)

    # Correction age stats
    diff_ages = bdf["diff_age"].dropna().tolist()
    high_age_events = [a for a in diff_ages if a > 10.0]

    # Height stats
    heights = bdf["hgt"].dropna().tolist()

    return {
        "status": "ok",
        "total_records": len(bdf),
        "fix_type_distribution": fix_dist,
        "solution_status_distribution": sol_dist,
        "dominant_fix_type": max(fix_dist, key=fix_dist.get) if fix_dist else "UNKNOWN",
        "position_accuracy": {
            "lat_std_avg": _avg(lat_stds),
            "lon_std_avg": _avg(lon_stds),
            "hgt_std_avg": _avg(hgt_stds),
            "lat_std_max": max(lat_stds) if lat_stds else None,
            "hgt_std_max": max(hgt_stds) if hgt_stds else None,
        },
        "satellite_count": {
            "avg": _avg(num_svs),
            "min": min(num_svs) if num_svs else None,
            "max": max(num_svs) if num_svs else None,
            "drop_events": sat_drops,
        },
        "correction_age": {
            "avg": _avg(diff_ages),
            "max": max(diff_ages) if diff_ages else None,
            "high_age_count": len(high_age_events),
            "high_age_threshold": 10.0,
        },
        "height": {
            "avg": _avg(heights),
            "min": min(heights) if heights else None,
            "max": max(heights) if heights else None,
            "range": (max(heights) - min(heights)) if heights else None,
        },
    }


def _run_cn0_analyzer(log_entry: dict) -> dict:
    """
    Analyzes TRACKSTAT C/No values and signal/constellation breakdown.
    Includes: reject code filtering, lock time quality, per-constellation counts.

    TRACKSTAT body layout (NovAtel OEM7):
      fields[0] = sol_status
      fields[1] = pos_type
      fields[2] = cutoff elevation
      fields[3] = num_channels
      fields[4..] = per-channel blocks, each 10 fields:
        +0: PRN/slot
        +1: glofreq (GLONASS offset)
        +2: ch_tr_status (hex — contains signal type + constellation)
        +3: PSR
        +4: doppler
        +5: C/No (dB-Hz)
        +6: locktime (seconds)
        +7: PSR residual
        +8: range reject code
        +9: PSR weight
    """
    df = log_entry["df"]
    trackstat = df[df["log_name"].str.upper() == "TRACKSTAT"].copy()

    if trackstat.empty:
        return {"status": "no_data", "reason": "No TRACKSTAT records in file"}

    cn0_values = []
    cn0_good_channels = []      # C/No from channels with good reject code
    sat_counts_per_epoch = []
    good_sat_counts_per_epoch = []   # Only channels with good reject code
    low_cn0_epochs = 0
    LOW_CN0_THRESHOLD = 35.0

    # Signal type tracking
    signal_types: dict[str, int] = {}
    constellation_sat_counts: dict[str, set] = {}  # constellation → set of PRNs seen

    # Lock time quality
    lock_times = []
    stable_channels = 0  # locktime >= 30s
    total_channels = 0

    # Reject codes: "good" codes from NAS reference
    # 0=good, 13=above elev mask, 18-23=various valid, 26=ObsL2
    _GOOD_REJECT_CODES = {0, 13, 18, 19, 20, 21, 22, 23, 26}

    # Constellation/signal maps
    _CONSTELLATION_MAP = {0: "GPS", 1: "GLONASS", 2: "SBAS", 3: "Galileo",
                          4: "BeiDou", 5: "QZSS", 6: "NavIC", 7: "Other"}
    _SIGNAL_MAP = {
        (0, 0): "GPS_L1CA", (0, 5): "GPS_L2P", (0, 9): "GPS_L2C",
        (0, 14): "GPS_L5Q", (0, 17): "GPS_L1C",
        (1, 0): "GLO_L1CA", (1, 5): "GLO_L2CA", (1, 1): "GLO_L2P",
        (2, 0): "SBAS_L1", (2, 6): "SBAS_L5",
        (3, 2): "GAL_E1", (3, 12): "GAL_E5a", (3, 17): "GAL_E5b", (3, 20): "GAL_E6",
        (4, 0): "BDS_B1I", (4, 1): "BDS_B1C", (4, 2): "BDS_B2I",
        (4, 4): "BDS_B2a", (4, 6): "BDS_B3I", (4, 7): "BDS_B2b",
        (5, 0): "QZSS_L1CA", (5, 14): "QZSS_L5",
        (6, 0): "NavIC_L5",
    }

    for _, row in trackstat.iterrows():
        parts = [p.strip() for p in row.get("fields_raw", "").split(",")]
        if len(parts) < 4:
            continue
        try:
            num_channels = int(float(parts[3]))
        except (ValueError, IndexError):
            continue

        epoch_cn0s = []
        epoch_good_cn0s = []
        epoch_constellations = set()
        satellite_start = 4

        for ch_idx in range(num_channels):
            base = satellite_start + (ch_idx * 10)
            if base + 9 >= len(parts):
                break

            cn0_idx = base + 5
            status_idx = base + 2
            locktime_idx = base + 6
            reject_idx = base + 8
            prn_idx = base + 0

            total_channels += 1

            # Parse C/No
            try:
                cn0 = float(parts[cn0_idx])
            except (ValueError, IndexError):
                continue

            if cn0 <= 0:
                continue

            epoch_cn0s.append(cn0)
            cn0_values.append(cn0)

            # Parse reject code
            reject_good = True
            try:
                reject_code = int(float(parts[reject_idx]))
                if reject_code not in _GOOD_REJECT_CODES:
                    reject_good = False
            except (ValueError, IndexError):
                pass

            if reject_good:
                epoch_good_cn0s.append(cn0)
                cn0_good_channels.append(cn0)

            # Parse lock time
            try:
                locktime = float(parts[locktime_idx])
                lock_times.append(locktime)
                if locktime >= 30.0:
                    stable_channels += 1
            except (ValueError, IndexError):
                pass

            # Decode constellation/signal from channel tracking status
            if status_idx < len(parts):
                try:
                    ch_status = int(parts[status_idx], 16)
                    sig_type = (ch_status >> 16) & 0x1F
                    constel  = (ch_status >> 21) & 0x07
                    constel_name = _CONSTELLATION_MAP.get(constel, f"Unknown({constel})")
                    sig_key = (constel, sig_type)
                    sig_name = _SIGNAL_MAP.get(sig_key, f"{constel_name}_Sig{sig_type}")

                    signal_types[sig_name] = signal_types.get(sig_name, 0) + 1
                    epoch_constellations.add(constel_name)

                    # Track unique PRNs per constellation
                    try:
                        prn = int(float(parts[prn_idx]))
                        if constel_name not in constellation_sat_counts:
                            constellation_sat_counts[constel_name] = set()
                        constellation_sat_counts[constel_name].add(prn)
                    except (ValueError, IndexError):
                        pass
                except (ValueError, TypeError):
                    pass

        if epoch_cn0s:
            sat_counts_per_epoch.append(len(epoch_cn0s))
            if _avg(epoch_cn0s) < LOW_CN0_THRESHOLD:
                low_cn0_epochs += 1
        if epoch_good_cn0s:
            good_sat_counts_per_epoch.append(len(epoch_good_cn0s))

    if not cn0_values:
        return {"status": "no_data", "reason": "TRACKSTAT present but no C/No values parseable"}

    # Sort signal types by count
    sorted_signals = dict(sorted(signal_types.items(), key=lambda x: -x[1]))

    # Per-constellation satellite counts (unique PRNs)
    per_constellation = {k: len(v) for k, v in sorted(
        constellation_sat_counts.items(), key=lambda x: -len(x[1])
    )}

    return {
        "status": "ok",
        "total_epochs": len(trackstat),
        "total_channels_seen": total_channels,
        # C/No stats (all channels)
        "avg_cn0": round(_avg(cn0_values), 2),
        "min_cn0": round(min(cn0_values), 2),
        "max_cn0": round(max(cn0_values), 2),
        "cn0_std_dev": round(statistics.stdev(cn0_values), 2) if len(cn0_values) > 1 else 0.0,
        # C/No stats (good channels only — reject code filtered)
        "avg_cn0_good_channels": round(_avg(cn0_good_channels), 2) if cn0_good_channels else None,
        "good_channel_count": len(cn0_good_channels),
        "rejected_channel_count": total_channels - len(cn0_good_channels),
        # Low C/No tracking
        "low_cn0_threshold": LOW_CN0_THRESHOLD,
        "low_cn0_epoch_count": low_cn0_epochs,
        "low_cn0_epoch_pct": round(low_cn0_epochs / len(trackstat) * 100, 1) if trackstat.shape[0] > 0 else 0,
        # Satellite counts
        "avg_satellites_tracked": round(_avg(sat_counts_per_epoch), 1) if sat_counts_per_epoch else 0,
        "min_satellites_tracked": min(sat_counts_per_epoch) if sat_counts_per_epoch else 0,
        "max_satellites_tracked": max(sat_counts_per_epoch) if sat_counts_per_epoch else 0,
        "avg_good_satellites": round(_avg(good_sat_counts_per_epoch), 1) if good_sat_counts_per_epoch else 0,
        # Lock time quality
        "stable_channel_pct": round(stable_channels / total_channels * 100, 1) if total_channels > 0 else 0,
        "avg_lock_time": round(_avg(lock_times), 1) if lock_times else 0,
        # Signal/constellation breakdown
        "signal_types": sorted_signals,
        "constellations_tracked": list(per_constellation.keys()),
        "satellites_per_constellation": per_constellation,
        "total_unique_satellites": sum(per_constellation.values()),
    }


def _run_rxstatus_analyzer(log_entry: dict) -> dict:
    """
    Analyzes RXSTATUS records.
    Returns: jamming events, spoofing events, antenna errors, all set bits summary.
    """
    df = log_entry["df"]
    rxstatus = df[df["log_name"].str.upper() == "RXSTATUS"].copy()

    if rxstatus.empty:
        return {"status": "no_data", "reason": "No RXSTATUS records in file"}

    # Use pre-built event index if available (faster)
    events = log_entry.get("events", {})
    jamming_events   = events.get("jamming", [])
    spoofing_events  = events.get("spoofing", [])
    antenna_open     = events.get("antenna_open", [])
    antenna_shorted  = events.get("antenna_shorted", [])
    pos_invalid      = events.get("position_invalid", [])
    track_degraded   = events.get("tracking_degraded", [])

    # Bit frequency across all records
    bit_counter: Counter = Counter()
    for _, row in rxstatus.iterrows():
        try:
            val = int(row.get("rx_status", "0").strip(), 16)
            for bit in range(32):
                if val & (1 << bit):
                    bit_counter[bit] += 1
        except (ValueError, AttributeError):
            continue

    return {
        "status": "ok",
        "total_records": len(rxstatus),
        "jamming_detected": len(jamming_events) > 0,
        "jamming_event_count": len(jamming_events),
        "jamming_events": jamming_events[:10],   # Cap for JSON size
        "spoofing_detected": len(spoofing_events) > 0,
        "spoofing_event_count": len(spoofing_events),
        "spoofing_events": spoofing_events[:10],
        "antenna_open_count": len(antenna_open),
        "antenna_shorted_count": len(antenna_shorted),
        "position_invalid_count": len(pos_invalid),
        "tracking_degraded_count": len(track_degraded),
        "most_frequent_bits": [
            {"bit": bit, "count": count, "pct": round(count / len(rxstatus) * 100, 1)}
            for bit, count in bit_counter.most_common(5)
        ],
        "any_errors": any([
            len(jamming_events) > 0,
            len(spoofing_events) > 0,
            len(antenna_open) > 0,
            len(antenna_shorted) > 0,
        ]),
    }


def _run_itdetect_analyzer(log_entry: dict) -> dict:
    """
    Analyzes ITDETECTSTATUS records.
    Returns: interference event count, spectrum analysis entries, RF power stats.
    """
    df = log_entry["df"]
    itdetect = df[df["log_name"].str.upper().isin(["ITDETECTSTATUS", "ITDETECTSTAT"])].copy()

    if itdetect.empty:
        return {"status": "no_data", "reason": "No ITDETECTSTATUS records in file"}

    events = log_entry.get("events", {})
    interference_events = events.get("itdetect_interference", [])

    spectrum_entries = [e for e in interference_events if e.get("detect_type") == "SPECTRUMANALYSIS"]
    stat_entries     = [e for e in interference_events if e.get("detect_type") == "STATISTICALANALYSIS"]

    power_values = [e["power_dbm"] for e in spectrum_entries if "power_dbm" in e]

    return {
        "status": "ok",
        "total_records": len(itdetect),
        "total_interference_events": len(interference_events),
        "spectrum_analysis_count": len(spectrum_entries),
        "statistical_analysis_count": len(stat_entries),
        "rf_power_stats": {
            "avg_dbm": round(_avg(power_values), 2) if power_values else None,
            "max_dbm": max(power_values) if power_values else None,
            "min_dbm": min(power_values) if power_values else None,
        },
        "interference_events": interference_events[:10],
        "has_interference": len(interference_events) > 0,
    }


def _run_correction_age_analyzer(log_entry: dict) -> dict:
    """
    Analyzes differential correction age from BESTPOS.
    Returns: age statistics and high-age event periods.
    """
    df = log_entry["df"]
    bestpos = df[df["log_name"].str.upper() == "BESTPOS"].copy()

    if bestpos.empty:
        return {"status": "no_data", "reason": "No BESTPOS records in file"}

    HIGH_AGE_THRESHOLD = 10.0  # seconds
    diff_ages = []
    high_age_events = []

    for _, row in bestpos.iterrows():
        parts = [p.strip() for p in row.get("fields_raw", "").split(",")]
        # NovAtel BESTPOS: doc field 14 = diff_age, body index = 12
        if len(parts) > 12:
            age = _safe_float(parts[12])
            if age is not None:
                diff_ages.append(age)
                if age > HIGH_AGE_THRESHOLD:
                    high_age_events.append({
                        "utc_time": row.get("utc_time", ""),
                        "correction_age": age,
                    })

    if not diff_ages:
        return {"status": "no_data", "reason": "No correction age data in BESTPOS"}

    return {
        "status": "ok",
        "avg_correction_age": round(_avg(diff_ages), 2),
        "max_correction_age": round(max(diff_ages), 2),
        "min_correction_age": round(min(diff_ages), 2),
        "high_age_threshold": HIGH_AGE_THRESHOLD,
        "high_age_event_count": len(high_age_events),
        "high_age_events": high_age_events[:10],
        "correction_loss_pct": round(len(high_age_events) / len(diff_ages) * 100, 1),
    }


def _run_satellite_count_analyzer(log_entry: dict) -> dict:
    """
    Tracks satellite count over time from BESTPOS.
    Returns: stats and drop events.
    """
    df = log_entry["df"]
    bestpos = df[df["log_name"].str.upper() == "BESTPOS"].copy()

    if bestpos.empty:
        return {"status": "no_data", "reason": "No BESTPOS records in file"}

    counts = []
    for _, row in bestpos.iterrows():
        parts = [p.strip() for p in row.get("fields_raw", "").split(",")]
        # NovAtel BESTPOS: doc field 15 = #SVs tracked, body index = 13
        n = _safe_int(parts[13]) if len(parts) > 13 else None
        if n is not None:
            counts.append(n)

    if not counts:
        return {"status": "no_data", "reason": "No satellite count data parseable from BESTPOS"}

    drop_events = _detect_drops(counts, threshold_pct=0.3)

    return {
        "status": "ok",
        "avg_satellites": round(_avg(counts), 1),
        "min_satellites": min(counts),
        "max_satellites": max(counts),
        "satellite_drop_events": drop_events,
        "drop_event_count": len(drop_events),
    }


def _run_ins_analyzer(log_entry: dict) -> dict:
    """
    Analyzes INSPVA/INSPVAX records.
    Returns: INS status distribution, roll/pitch/azimuth stats,
             and first/last occurrence of key INS states.

    INSPVA fields_raw layout:  lat, lon, hgt, N_vel, E_vel, Up_vel, roll, pitch, azimuth, status
    INSPVAX fields_raw layout: ins_status, pos_type, lat, lon, hgt, undulation, N_vel, E_vel, Up_vel,
                               roll, pitch, azimuth, ... (many more std dev fields)
    """
    df = log_entry["df"]
    inspva = df[df["log_name"].str.upper().isin(["INSPVA", "INSPVAX"])].copy()

    if inspva.empty:
        return {"status": "no_data", "reason": "No INSPVA/INSPVAX records in file"}

    rolls, pitches, azimuths, statuses = [], [], [], []
    status_timestamps: dict[str, list[str]] = {}  # status → [first_time, last_time]

    for _, row in inspva.iterrows():
        parts = [p.strip() for p in row.get("fields_raw", "").split(",")]
        log_name = row.get("log_name", "").upper()
        utc_time = row.get("utc_time", "")

        if log_name == "INSPVAX" and len(parts) >= 12:
            # INSPVAX: field 0 = ins_status, field 1 = pos_type,
            # field 2-4 = lat/lon/hgt, field 6-8 = N/E/Up vel,
            # field 9 = roll, field 10 = pitch, field 11 = azimuth
            status  = parts[0]
            roll    = _safe_float(parts[9])
            pitch   = _safe_float(parts[10])
            azimuth = _safe_float(parts[11])
        elif len(parts) >= 10:
            # INSPVA: field 0-2 = lat/lon/hgt, field 3-5 = vel,
            # field 6 = roll, field 7 = pitch, field 8 = azimuth, field 9 = status
            status  = parts[9] if len(parts) > 9 else ""
            roll    = _safe_float(parts[6])
            pitch   = _safe_float(parts[7])
            azimuth = _safe_float(parts[8])
        else:
            continue

        if status:
            statuses.append(status)
            # Track first/last timestamps per status
            if status not in status_timestamps:
                status_timestamps[status] = [utc_time, utc_time]
            else:
                status_timestamps[status][1] = utc_time

        if roll    is not None: rolls.append(roll)
        if pitch   is not None: pitches.append(pitch)
        if azimuth is not None: azimuths.append(azimuth)

    status_dist = dict(Counter(statuses))

    # Build status timeline with first occurrence
    status_first_seen = {
        status: timestamps[0]
        for status, timestamps in status_timestamps.items()
    }

    return {
        "status": "ok",
        "total_records": len(inspva),
        "ins_status_distribution": status_dist,
        "dominant_ins_status": max(status_dist, key=status_dist.get) if status_dist else "UNKNOWN",
        "status_first_seen": status_first_seen,
        "status_last_seen": {s: ts[1] for s, ts in status_timestamps.items()},
        "roll_stats":    _stats_dict(rolls),
        "pitch_stats":   _stats_dict(pitches),
        "azimuth_stats": _stats_dict(azimuths),
    }


def _run_receiver_health_analyzer(log_entry: dict) -> dict:
    """
    Comprehensive receiver health from RXSTATUS + optional HWMONITOR.
    Returns all error/warning counts and health timeline summary.
    """
    # Delegate to rxstatus_analyzer — same data, same events
    result = _run_rxstatus_analyzer(log_entry)

    # Try HWMONITOR if available
    df = log_entry["df"]
    hwmon = df[df["log_name"].str.upper() == "HWMONITOR"].copy()
    if not hwmon.empty:
        result["hwmonitor_records"] = len(hwmon)

    return result


def _run_time_analyzer(log_entry: dict) -> dict:
    """
    File time coverage from any log with GPS time fields.
    Returns: time range, duration, time status distribution.
    """
    import datetime

    VALID_TIME = {"FINESTEERING", "FINE", "FINEBACKUPSTEERING", "FINEADJUSTING",
                  "COARSE", "COARSESTEERING", "COARSEADJUSTING", "FREEWHEELING"}

    df = log_entry["df"]
    valid = df[df["time_status"].isin(VALID_TIME) & (df["week"] > 0)].copy()

    if valid.empty:
        return {"status": "no_data", "reason": "No records with valid GPS time found"}

    status_dist = valid["time_status"].value_counts().to_dict()

    w_s = int(valid.loc[valid["seconds"].idxmin(), "week"])
    w_e = int(valid.loc[valid["seconds"].idxmax(), "week"])
    s_s = float(valid["seconds"].min())
    s_e = float(valid["seconds"].max())
    weeks = sorted(valid["week"].unique().tolist())
    dur = (weeks[-1] - weeks[0]) * 604800 + (s_e - s_s) if len(weeks) > 1 else s_e - s_s

    from src.main import gps_to_utc_str
    return {
        "status": "ok",
        "start_utc": gps_to_utc_str(w_s, s_s),
        "end_utc":   gps_to_utc_str(w_e, s_e),
        "start_gps": {"week": w_s, "seconds": s_s},
        "end_gps":   {"week": w_e, "seconds": s_e},
        "duration_seconds": round(dur, 3),
        "duration_minutes": round(dur / 60, 2),
        "time_status_distribution": status_dist,
        "dominant_time_status": max(status_dist, key=status_dist.get) if status_dist else "UNKNOWN",
    }


def _run_data_gap_analyzer(log_entry: dict) -> dict:
    """
    Detects time gaps in the file.
    Returns: gap count, gap list, total missing time, continuity percentage.
    """
    VALID_TIME = {"FINESTEERING", "FINE", "FINEBACKUPSTEERING", "FINEADJUSTING",
                  "COARSE", "COARSESTEERING", "COARSEADJUSTING", "FREEWHEELING"}
    GAP_THRESHOLD = 2.0

    df = log_entry["df"]
    valid = df[df["time_status"].isin(VALID_TIME) & (df["week"] > 0)].copy()

    if valid.empty:
        return {"status": "no_data", "reason": "No valid-time records for gap analysis"}

    most_common_log = valid["log_name_raw"].value_counts().idxmax()
    ref = valid[valid["log_name_raw"] == most_common_log].copy()
    ref["abs_seconds"] = ref["week"] * 604800 + ref["seconds"]
    ref = ref.sort_values("abs_seconds").reset_index(drop=True)
    ref["delta"] = ref["abs_seconds"].diff()
    median_interval = ref["delta"].median()
    effective_threshold = max(GAP_THRESHOLD, median_interval * 3)
    gaps_df = ref[ref["delta"] > effective_threshold].copy()

    total_duration = ref["abs_seconds"].iloc[-1] - ref["abs_seconds"].iloc[0]
    total_gap_time = float(gaps_df["delta"].sum()) if not gaps_df.empty else 0.0
    continuity_pct = round((1 - total_gap_time / total_duration) * 100, 2) if total_duration > 0 else 100.0

    from src.main import gps_to_utc_str
    gaps = []
    for _, row in gaps_df.iterrows():
        gap_sec = float(row["delta"])
        gaps.append({
            "gap_start_utc": gps_to_utc_str(int(row["week"]), float(row["seconds"]) - gap_sec),
            "gap_end_utc":   gps_to_utc_str(int(row["week"]), float(row["seconds"])),
            "duration_seconds": round(gap_sec, 3),
        })

    return {
        "status": "ok",
        "gap_count": len(gaps),
        "gaps": gaps[:20],    # Cap
        "total_missing_seconds": round(total_gap_time, 3),
        "total_duration_seconds": round(total_duration, 3),
        "data_continuity_pct": continuity_pct,
        "reference_log": most_common_log,
        "median_interval_seconds": round(float(median_interval), 3),
    }


def _run_log_inventory(log_entry: dict) -> dict:
    """
    Lists all log types in the file.
    """
    df = log_entry["df"]
    counts = df["log_name_raw"].value_counts().to_dict()
    return {
        "status": "ok",
        "total_records": len(df),
        "log_type_count": len(counts),
        "log_counts": counts,
        "log_types": sorted(counts.keys()),
    }


# ── SATVIS2 analyzer ──────────────────────────────────────────────────
def _run_satvis2_analyzer(log_entry: dict) -> dict:
    """
    Analyzes SATVIS2 records for satellite visibility per constellation.
    Returns: per-constellation satellite counts with health/elevation info.
    """
    df = log_entry["df"]
    satvis = df[df["log_name"].str.upper() == "SATVIS2"].copy()

    if satvis.empty:
        return {"status": "no_data", "reason": "No SATVIS2 records in file"}

    # SATVIS2 ASCII body layout:
    # field 0: satellite_system enum (GPS=0, GLONASS=1, SBAS=2, Galileo=5, BeiDou=6, QZSS=7)
    # field 1: visibility type
    # field 2: almanac flag
    # field 3: num_satellites
    # Then per satellite (7 fields each):
    #   +0: satellite_id, +1: health, +2: elevation, +3: azimuth,
    #   +4: true_doppler, +5: apparent_doppler, +6: (padding/reserved)

    _SATVIS_SYSTEM_MAP = {
        "0": "GPS", "GPS": "GPS",
        "1": "GLONASS", "GLONASS": "GLONASS",
        "2": "SBAS", "SBAS": "SBAS",
        "5": "Galileo", "GALILEO": "Galileo",
        "6": "BeiDou", "BEIDOU": "BeiDou",
        "7": "QZSS", "QZSS": "QZSS",
        "8": "NavIC", "NAVIC": "NavIC",
    }

    constellation_sats: dict[str, dict] = {}  # constellation → {total, healthy, above_mask}
    all_elevations = []
    total_visible = 0

    for _, row in satvis.iterrows():
        parts = [p.strip() for p in row.get("fields_raw", "").split(",")]
        if len(parts) < 4:
            continue

        system_raw = parts[0]
        system_name = _SATVIS_SYSTEM_MAP.get(system_raw, system_raw)

        try:
            num_sats = int(parts[3])
        except (ValueError, IndexError):
            continue

        if system_name not in constellation_sats:
            constellation_sats[system_name] = {"total": 0, "healthy": 0, "above_10deg": 0}

        sat_start = 4
        fields_per_sat = 7  # NovAtel SATVIS2 has 7 fields per satellite entry

        for i in range(num_sats):
            base = sat_start + (i * fields_per_sat)
            if base + 2 >= len(parts):
                # Try 6 fields per sat (some firmware versions)
                fields_per_sat = 6
                base = sat_start + (i * fields_per_sat)
                if base + 2 >= len(parts):
                    break

            constellation_sats[system_name]["total"] += 1
            total_visible += 1

            # Health (field +1)
            try:
                health = parts[base + 1].strip()
                if health in ("0", "HEALTHY", "GOOD"):
                    constellation_sats[system_name]["healthy"] += 1
            except IndexError:
                pass

            # Elevation (field +2)
            try:
                elev = float(parts[base + 2])
                all_elevations.append(elev)
                if elev >= 10.0:
                    constellation_sats[system_name]["above_10deg"] += 1
            except (ValueError, IndexError):
                pass

    if not constellation_sats:
        return {"status": "no_data", "reason": "SATVIS2 present but no satellite data parseable"}

    return {
        "status": "ok",
        "total_epochs": len(satvis),
        "total_visible_satellites": total_visible,
        "constellations": constellation_sats,
        "constellation_names": list(constellation_sats.keys()),
        "avg_elevation": round(_avg(all_elevations), 1) if all_elevations else None,
    }


# ── CHANCONFIGLIST analyzer ───────────────────────────────────────────
def _run_chanconfiglist_analyzer(log_entry: dict) -> dict:
    """
    Analyzes CHANCONFIGLIST records.
    Returns: configured signal types and channel assignments.

    CHANCONFIGLIST body layout:
      field 0: num_channels
      Per channel (5 fields):
        +0: system (GPS, GLONASS, etc.)
        +1: signal_type (L1CA, L2C, etc.)
        +2: PRN (or 0 for all)
        +3: channel_assignment
        +4: additional flags
    """
    df = log_entry["df"]
    chancfg = df[df["log_name"].str.upper() == "CHANCONFIGLIST"].copy()

    if chancfg.empty:
        return {"status": "no_data", "reason": "No CHANCONFIGLIST records in file"}

    configured_signals: dict[str, list[str]] = {}  # constellation → [signal_types]
    total_channels = 0

    for _, row in chancfg.iterrows():
        parts = [p.strip() for p in row.get("fields_raw", "").split(",")]
        if len(parts) < 1:
            continue

        try:
            num_entries = int(parts[0])
        except (ValueError, IndexError):
            continue

        # Parse channel entries
        entry_start = 1
        fields_per_entry = 5  # Standard

        for i in range(num_entries):
            base = entry_start + (i * fields_per_entry)
            if base + 1 >= len(parts):
                # Try different field counts
                fields_per_entry = 4
                base = entry_start + (i * fields_per_entry)
                if base + 1 >= len(parts):
                    break

            system = parts[base].strip() if base < len(parts) else ""
            signal = parts[base + 1].strip() if base + 1 < len(parts) else ""

            if system and signal:
                total_channels += 1
                if system not in configured_signals:
                    configured_signals[system] = []
                if signal not in configured_signals[system]:
                    configured_signals[system].append(signal)

    if not configured_signals:
        return {"status": "no_data", "reason": "CHANCONFIGLIST present but no signal assignments parseable"}

    return {
        "status": "ok",
        "total_configured_channels": total_channels,
        "configured_signals": configured_signals,
        "constellation_count": len(configured_signals),
        "constellations": list(configured_signals.keys()),
        "total_signal_types": sum(len(v) for v in configured_signals.values()),
    }


# ═══════════════════════════════════════════════════════════════════
# TOOL DISPATCH TABLE
# Maps tool_id → implementation function
# ═══════════════════════════════════════════════════════════════════

_TOOL_FUNCTIONS = {
    "bestpos_analyzer":           _run_bestpos_analyzer,
    "cn0_analyzer":               _run_cn0_analyzer,
    "rxstatus_analyzer":          _run_rxstatus_analyzer,
    "itdetect_analyzer":          _run_itdetect_analyzer,
    "correction_age_analyzer":    _run_correction_age_analyzer,
    "satellite_count_analyzer":   _run_satellite_count_analyzer,
    "ins_analyzer":               _run_ins_analyzer,
    "receiver_health_analyzer":   _run_receiver_health_analyzer,
    "time_analyzer":              _run_time_analyzer,
    "data_gap_analyzer":          _run_data_gap_analyzer,
    "log_inventory":              _run_log_inventory,
    "satvis2_analyzer":           _run_satvis2_analyzer,
    "chanconfiglist_analyzer":    _run_chanconfiglist_analyzer,
}


# ═══════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════

def execute_plan(plan: ExecutionPlan, log_entry: Optional[dict]) -> dict:
    """
    Execute all runnable tools from the plan and assemble the Correlation JSON.

    Args:
        plan:       ExecutionPlan from evidence_planner
        log_entry:  The _log_store entry for this session (or None if no file)

    Returns:
        Correlation JSON dict (fixed schema from _empty_correlation_json)
    """
    t0 = time.time()
    corr = _empty_correlation_json(plan.query)
    corr["domains"] = plan.top_domains
    corr["execution_meta"]["has_log_file"] = plan.has_log_file

    # Record skipped tools
    for tc in plan.tool_calls:
        if not tc.available:
            corr["unavailable_evidence"].append({
                "tool_id": tc.tool_id,
                "reason": tc.unavailable_reason,
            })
            corr["execution_meta"]["tools_skipped"].append(tc.tool_id)

    if not plan.runnable_tools or not log_entry:
        corr["execution_meta"]["elapsed_seconds"] = round(time.time() - t0, 3)
        return corr

    # ── Parallel execution ────────────────────────────────────────────
    # Tools are independent — they all read from the same log_entry,
    # which is read-only after ingest. Safe to parallelize.
    results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=min(len(plan.runnable_tools), 4)) as executor:
        futures = {}
        for tool_id in plan.runnable_tools:
            fn = _TOOL_FUNCTIONS.get(tool_id)
            if fn:
                futures[executor.submit(fn, log_entry)] = tool_id
            else:
                print(f"[ORCHESTRATOR] No implementation for tool_id={tool_id!r}")

        for future in as_completed(futures):
            tool_id = futures[future]
            try:
                results[tool_id] = future.result()
                corr["execution_meta"]["tools_run"].append(tool_id)
                print(f"[ORCHESTRATOR] ✓ {tool_id} status={results[tool_id].get('status')}")
            except Exception as e:
                results[tool_id] = {"status": "error", "error": str(e)}
                corr["execution_meta"]["tools_run"].append(tool_id)
                print(f"[ORCHESTRATOR] ✗ {tool_id} error={e}")

    # ── Assemble evidence block ───────────────────────────────────────
    for tool_id, result in results.items():
        corr["evidence"][tool_id] = result

    # ── Extract flat metrics ──────────────────────────────────────────
    corr["metrics"] = _extract_metrics(results)

    # ── Generate semantic events (Phase 3 engine) ─────────────────────
    corr["events"] = generate_semantic_events(results)

    # ── Run diagnostic rules (Phase 4 engine) ────────────────────────
    corr["diagnostics"] = run_diagnostics(
        events   = corr["events"],
        metrics  = corr["metrics"],
        evidence = results,
    )

    corr["execution_meta"]["elapsed_seconds"] = round(time.time() - t0, 3)

    print(f"\n[ORCHESTRATOR] Completed in {corr['execution_meta']['elapsed_seconds']}s")
    print(f"  tools run    : {corr['execution_meta']['tools_run']}")
    print(f"  events found : {len(corr['events'])}")
    print(f"  diagnostics  : {len(corr['diagnostics'])}")
    print(f"  metrics      : {list(corr['metrics'].keys())}\n")

    return corr


def _extract_metrics(results: dict[str, dict]) -> dict:
    """
    Flatten key metrics from all tool results into a single dict.
    These are the numbers the LLM will reference most frequently.
    """
    m: dict[str, Any] = {}

    if "cn0_analyzer" in results and results["cn0_analyzer"].get("status") == "ok":
        r = results["cn0_analyzer"]
        m["avg_cn0"]                = r.get("avg_cn0")
        m["min_cn0"]                = r.get("min_cn0")
        m["max_cn0"]                = r.get("max_cn0")
        m["low_cn0_epoch_pct"]      = r.get("low_cn0_epoch_pct")
        m["avg_satellites_tracked"] = r.get("avg_satellites_tracked")
        m["max_satellites_tracked"] = r.get("max_satellites_tracked")
        if r.get("constellations_tracked"):
            m["constellations_tracked"] = r["constellations_tracked"]
        if r.get("signal_types"):
            m["signal_types_count"]     = len(r["signal_types"])

    if "bestpos_analyzer" in results and results["bestpos_analyzer"].get("status") == "ok":
        r = results["bestpos_analyzer"]
        m["dominant_fix_type"]      = r.get("dominant_fix_type")
        m["avg_correction_age"]     = r.get("correction_age", {}).get("avg")
        m["max_correction_age"]     = r.get("correction_age", {}).get("max")
        m["high_age_event_count"]   = r.get("correction_age", {}).get("high_age_count")
        m["avg_num_svs"]            = r.get("satellite_count", {}).get("avg")
        m["min_num_svs"]            = r.get("satellite_count", {}).get("min")
        m["avg_hgt_std"]            = r.get("position_accuracy", {}).get("hgt_std_avg")

    if "rxstatus_analyzer" in results and results["rxstatus_analyzer"].get("status") == "ok":
        r = results["rxstatus_analyzer"]
        m["jamming_detected"]       = r.get("jamming_detected")
        m["jamming_event_count"]    = r.get("jamming_event_count")
        m["spoofing_detected"]      = r.get("spoofing_detected")
        m["spoofing_event_count"]   = r.get("spoofing_event_count")

    if "correction_age_analyzer" in results and results["correction_age_analyzer"].get("status") == "ok":
        r = results["correction_age_analyzer"]
        m["avg_correction_age"]     = r.get("avg_correction_age")
        m["max_correction_age"]     = r.get("max_correction_age")
        m["correction_loss_pct"]    = r.get("correction_loss_pct")

    if "time_analyzer" in results and results["time_analyzer"].get("status") == "ok":
        r = results["time_analyzer"]
        m["duration_seconds"]       = r.get("duration_seconds")
        m["duration_minutes"]       = r.get("duration_minutes")

    if "data_gap_analyzer" in results and results["data_gap_analyzer"].get("status") == "ok":
        r = results["data_gap_analyzer"]
        m["gap_count"]              = r.get("gap_count")
        m["data_continuity_pct"]    = r.get("data_continuity_pct")

    return {k: v for k, v in m.items() if v is not None}


# ═══════════════════════════════════════════════════════════════════
# UTILITY HELPERS
# ═══════════════════════════════════════════════════════════════════

def _avg(values: list) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _safe_float(v: str) -> Optional[float]:
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_int(v: str) -> Optional[int]:
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _stats_dict(values: list) -> dict:
    if not values:
        return {"avg": None, "min": None, "max": None, "std_dev": None}
    return {
        "avg":     round(_avg(values), 3),
        "min":     round(min(values), 3),
        "max":     round(max(values), 3),
        "std_dev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
    }


def _detect_drops(values: list, threshold_pct: float = 0.3) -> list[dict]:
    """
    Detect sudden drops in a time-series list.
    A drop is defined as a decrease >= threshold_pct from one sample to the next.
    Returns list of {index, from_value, to_value, drop_pct}.
    """
    drops = []
    for i in range(1, len(values)):
        if values[i - 1] and values[i - 1] > 0:
            change = (values[i - 1] - values[i]) / values[i - 1]
            if change >= threshold_pct:
                drops.append({
                    "index": i,
                    "from_value": values[i - 1],
                    "to_value": values[i],
                    "drop_pct": round(change * 100, 1),
                })
    return drops
